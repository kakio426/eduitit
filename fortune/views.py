import os
import time
import asyncio
from openai import OpenAI, AsyncOpenAI
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from django_ratelimit.core import is_ratelimited
from asgiref.sync import sync_to_async
from core.utils import ratelimit_key_for_master_only
from core.seo import (
    build_fortune_detail_page_seo,
    build_fortune_history_page_seo,
    build_fortune_saju_page_seo,
)
from .forms import SajuForm
from .prompts import get_prompt
from .libs import calculator
from .privacy import (
    apply_private_fortune_headers,
    build_user_pseudonymous_fingerprint,
    get_cached_pseudonymous_result,
    normalize_birth_payload,
    normalize_daily_payload,
    scrub_personal_fortune_text,
    store_cached_pseudonymous_result,
)
from datetime import datetime
import pytz
import json
import logging
from django.views.decorators.http import require_POST

# 로거 설정
logger = logging.getLogger(__name__)

# 모델 설정
DEEPSEEK_MODEL_NAME = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _render_private_fortune_page(request, template_name, context):
    response = render(request, template_name, context)
    return apply_private_fortune_headers(response)


def _fortune_user_label(user):
    if user and user.is_authenticated:
        return getattr(user, "username", str(user))
    return "guest"


def _should_use_async_ai_stream():
    return getattr(settings, 'FORTUNE_ASYNC_STREAM_ENABLED', False)


def _should_use_async_ai_api():
    return getattr(settings, 'FORTUNE_ASYNC_API_ENABLED', False)

def fortune_rate_h(group, request):
    """1시간당 5회 제한 (관리자 무제한)"""
    if request.user and request.user.is_authenticated:
        if request.user.is_superuser:
            return None
    return '5/h'

def fortune_rate_d(group, request):
    """1일당 5회 제한 (관리자 무제한)"""
    if request.user and request.user.is_authenticated:
        if request.user.is_superuser:
            return None
    return '5/d'

def generate_ai_response(prompt, request):
    """
    DeepSeek 기반 AI 응답 생성 함수 (Streaming 지원)
    """
    from .utils.circuit_breaker import ai_circuit_breaker

    if not ai_circuit_breaker.can_execute():
        raise Exception("AI 서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해주세요.")

    master_deepseek_key = os.environ.get('MASTER_DEEPSEEK_API_KEY')
    if master_deepseek_key:
        try:
            client = OpenAI(
                api_key=master_deepseek_key,
                base_url=DEEPSEEK_BASE_URL,
                timeout=60.0,
            )
            
            # DeepSeek Retry Logic
            max_retries = 2
            for i in range(max_retries + 1):
                try:
                    response = client.chat.completions.create(
                        model=DEEPSEEK_MODEL_NAME,
                        messages=[
                            {"role": "system", "content": "You are a professional Saju (Four Pillars of Destiny) master."},
                            {"role": "user", "content": prompt}
                        ],
                        stream=True
                    )
                    
                    chunk_count = 0
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            chunk_count += 1
                            yield content
                    
                    if chunk_count == 0:
                        logger.warning("DeepSeek stream yielded 0 chunks.")
                        raise Exception("DeepSeek API returned empty response")
                        
                    return
                except Exception as e:
                    if '503' in str(e) and i < max_retries:
                        time.sleep(1.5)
                        continue
                    raise e
        except Exception as e:
            logger.exception(f"DeepSeek API Error (Master): {e}")
            raise e
            
    # 키가 없는 경우
    raise Exception("API_KEY_MISSING: API 키가 설정되지 않았습니다.")

def get_chart_context(data):
    """Refactor: Helper to get pillars from form data"""
    try:
        # Construct aware datetime from input
        year = data['birth_year']
        month = data['birth_month']
        day = data['birth_day']
        hour = data['birth_hour'] if data['birth_hour'] is not None else 12 # Default noon
        minute = data['birth_minute'] if data['birth_minute'] is not None else 0
        
        # User timezone assumption: KST (Asia/Seoul)
        tz = pytz.timezone('Asia/Seoul')
        dt = datetime(year, month, day, hour, minute, tzinfo=tz)
        
        return calculator.get_pillars(dt)
    except Exception as e:
        logger.error(f"Error calculating pillars: {e}")
        return None

def serialize_chart_context(chart_context):
    """DB 객체(Stem, Branch)가 포함된 context를 JSON 직렬화 가능한 형태로 변환"""
    if not chart_context:
        return None
    return {
        k: {
            'stem': str(v['stem']),
            'branch': str(v['branch'])
        } for k, v in chart_context.items()
    }


def normalize_natal_chart_payload(natal_chart):
    """
    natal_chart를 canonical 포맷({'year': {'stem': '甲', 'branch': '子'}})으로 정규화.
    레거시 포맷([stem, branch], '甲子')도 허용한다.
    """
    if not isinstance(natal_chart, dict):
        return natal_chart

    normalized = {}
    for pillar in ('year', 'month', 'day', 'hour'):
        raw_value = natal_chart.get(pillar)
        stem = None
        branch = None

        if isinstance(raw_value, dict):
            stem = raw_value.get('stem')
            branch = raw_value.get('branch')
        elif isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
            stem, branch = raw_value[0], raw_value[1]
        elif isinstance(raw_value, str) and len(raw_value) >= 2:
            stem, branch = raw_value[:1], raw_value[1:]

        if stem and branch:
            normalized[pillar] = {'stem': str(stem), 'branch': str(branch)}

    return normalized or natal_chart


def _get_full_analysis_cache_entry(user, data):
    if not user or not user.is_authenticated:
        return None, None
    fingerprint = build_user_pseudonymous_fingerprint(user.id, normalize_birth_payload(data))
    return fingerprint, get_cached_pseudonymous_result(user, 'full', fingerprint)


def _get_daily_cache_entry(user, mode, target_date, natal_chart):
    if not user or not user.is_authenticated:
        return None, None
    fingerprint = build_user_pseudonymous_fingerprint(
        user.id,
        normalize_daily_payload(mode, target_date, normalize_natal_chart_payload(natal_chart)),
    )
    return fingerprint, get_cached_pseudonymous_result(user, 'daily', fingerprint)


# ============================================
# Async 헬퍼 함수
# ============================================

@sync_to_async
def _check_saju_ratelimit(request):
    """동기 ratelimit 체크를 async에서 호출하기 위한 래퍼"""
    limited_h = is_ratelimited(
        request, group='saju_service', key=ratelimit_key_for_master_only,
        rate=fortune_rate_h, method='POST', increment=True
    )
    if limited_h:
        return True
    limited_d = is_ratelimited(
        request, group='saju_service', key=ratelimit_key_for_master_only,
        rate=fortune_rate_d, method='POST', increment=True
    )
    return limited_d


async def _async_stream_ai(prompt, request):
    """스트리밍 응답을 async로 제공. 플래그 OFF 시 기존 threadpool 경로 유지."""
    if _should_use_async_ai_stream():
        async for chunk in _async_stream_deepseek(prompt):
            yield chunk
        return

    # Fallback: 기존 sync generator를 threadpool에서 실행
    loop = asyncio.get_running_loop()
    gen = generate_ai_response(prompt, request)
    _next = next
    while True:
        try:
            chunk = await loop.run_in_executor(None, _next, gen)
            yield chunk
        except StopIteration:
            break


async def _async_stream_deepseek(prompt):
    """DeepSeek 스트리밍을 AsyncOpenAI로 직접 처리."""
    from .utils.circuit_breaker import ai_circuit_breaker

    if not ai_circuit_breaker.can_execute():
        raise Exception("AI 서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해주세요.")

    api_key = os.environ.get('MASTER_DEEPSEEK_API_KEY')
    if not api_key:
        raise Exception("API_KEY_MISSING: API 키가 설정되지 않았습니다.")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        timeout=60.0,
    )

    max_retries = 2
    for i in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=DEEPSEEK_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a professional Saju (Four Pillars of Destiny) master."},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
            )

            chunk_count = 0
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_count += 1
                    yield chunk.choices[0].delta.content

            if chunk_count == 0:
                logger.warning("DeepSeek stream yielded 0 chunks.")
                raise Exception("DeepSeek API returned empty response")

            ai_circuit_breaker.record_success()
            return
        except Exception as e:
            if '503' in str(e) and i < max_retries:
                await asyncio.sleep(1.5)
                continue
            ai_circuit_breaker.record_failure()
            logger.exception(f"DeepSeek API Error (Async Master): {e}")
            raise


@sync_to_async
def _collect_ai_response(prompt, request):
    """AI 응답을 동기적으로 수집 (async 뷰에서 사용)"""
    from .utils.circuit_breaker import ai_circuit_breaker
    try:
        result = "".join(generate_ai_response(prompt, request))
        ai_circuit_breaker.record_success()
        return result
    except Exception:
        ai_circuit_breaker.record_failure()
        raise


async def _collect_ai_response_async(prompt, request):
    """
    async API용 수집 함수.
    플래그 ON + DeepSeek 경로에서는 AsyncOpenAI를 사용하고,
    그 외는 기존 sync collector를 재사용한다.
    """
    if _should_use_async_ai_api():
        chunks = []
        async for chunk in _async_stream_deepseek(prompt):
            chunks.append(chunk)
        return "".join(chunks)

    return await _collect_ai_response(prompt, request)


@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_h, method='POST', block=True, group='saju_service')
@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_d, method='POST', block=True, group='saju_service')
def saju_view(request):
    """사주 분석 메인 뷰"""
    if getattr(request, 'limited', False):
        error_message = '선생님, 현재 공용 AI 한도가 모두 사용 중입니다. 잠시 후 다시 시도해주세요.'

        return _render_private_fortune_page(request, 'fortune/saju_form.html', {
            'form': SajuForm(request.POST),
            'error': error_message,
            'kakao_js_key': settings.KAKAO_JS_KEY,
            **build_fortune_saju_page_seo(request).as_context(),
        })
    result_html = None
    error_message = None
    chart_context = None

    if request.method == 'POST':
        form = SajuForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            mode = data['mode']

            # Logic Engine: Calculate Pillars
            chart_context = get_chart_context(data)
            prompt = get_prompt(mode, data, chart_context=chart_context)
            cache_fingerprint, cached_result = _get_full_analysis_cache_entry(request.user, data)

            try:
                if cached_result:
                    logger.info("[Fortune] Action: SAJU_ANALYZE, Cache: HIT, User: %s, Mode: %s", _fortune_user_label(request.user), mode)
                    generated_text = cached_result.result_text
                else:
                    generated_text = "".join(generate_ai_response(prompt, request))
                    generated_text = scrub_personal_fortune_text(generated_text)
                    if cache_fingerprint and generated_text:
                        store_cached_pseudonymous_result(request.user, 'full', cache_fingerprint, generated_text)
                    logger.info("[Fortune] Action: SAJU_ANALYZE, Cache: MISS, User: %s, Mode: %s", _fortune_user_label(request.user), mode)
                
                # Validation: If result is empty/whitespace, treat as None/Error
                if generated_text and generated_text.strip():
                    result_html = generated_text
                else:
                    logger.warning("AI returned empty response")
                    result_html = None
                    error_message = "AI가 답변을 생성하지 못했습니다. (내용 없음) 잠시 후 다시 시도해주세요."
            except Exception as e:
                logger.exception("사주 분석 오류")
                error_str = str(e)
                if "API_KEY_MISSING" in error_str:
                     error_message = "API 키가 설정되지 않았습니다. 관리자에게 문의해주세요."
                elif "matching query does not exist" in error_str:
                    error_message = "기본 데이터가 데이터베이스에 존재하지 않습니다. 관리자에게 문의하여 'python manage.py seed_saju_data'를 실행해주세요."
                elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    error_message = "선생님, 현재 많은 분들이 이용 중이라 공용 AI 한도가 초과되었습니다. 잠시 후 다시 시도해주세요."
                elif "503" in error_str:
                    error_message = "지금 AI 모델이 너무 바쁘네요! 30초 정도 뒤에 다시 시도해주시면 감사하겠습니다. 😊"
                elif "Insufficient Balance" in error_str: # DeepSeek specific
                     error_message = "선생님, 공용 AI 사용량이 초과되었습니다. 잠시 후 다시 시도해주세요."
                else:
                    error_message = f"사주 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. ({error_str})"
    else:
        form = SajuForm()

    # Ensure chart data is always available for template (even when using cached results)
    # chart_context is calculated at line 198 for all POST requests
    chart_data = None
    day_master_data = None
    
    if chart_context:
        try:
            chart_data = {
                'year': [str(chart_context['year']['stem']), str(chart_context['year']['branch'])],
                'month': [str(chart_context['month']['stem']), str(chart_context['month']['branch'])],
                'day': [str(chart_context['day']['stem']), str(chart_context['day']['branch'])],
                'hour': [str(chart_context['hour']['stem']), str(chart_context['hour']['branch'])],
            }
            day_master_data = {
                'char': str(chart_context['day']['stem']),
                'element': chart_context['day']['stem'].element
            }
        except Exception as e:
            logger.error(f"Error building chart data for template: {e}")
    
    return _render_private_fortune_page(request, 'fortune/saju_form.html', {
        'form': form,
        'result': result_html,
        'error': error_message,
        'gender': request.POST.get('gender') if request.method == 'POST' else None,
        'mode': request.POST.get('mode') if request.method == 'POST' else 'teacher',
        'day_master': day_master_data,
        'chart': chart_data,
        'kakao_js_key': settings.KAKAO_JS_KEY,
        **build_fortune_saju_page_seo(request).as_context(),
    })


async def saju_streaming_api(request):
    """실시간 스트리밍 사주 분석 API (async)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    # Manual ratelimit check (async 뷰에서는 데코레이터 대신 수동 체크)
    if await _check_saju_ratelimit(request):
        return JsonResponse({'error': 'LIMIT_EXCEEDED'}, status=429)

    form = SajuForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': 'Invalid data'}, status=400)

    data = form.cleaned_data
    chart_context = await sync_to_async(get_chart_context)(data)
    prompt = get_prompt(data['mode'], data, chart_context=chart_context)

    async def stream_response():
        try:
            async for chunk in _async_stream_ai(prompt, request):
                yield chunk
        except Exception as e:
            logger.exception("Streaming error")
            yield f"\n\n[오류 발생: {str(e)}]"

    response = StreamingHttpResponse(stream_response(), content_type='text/plain; charset=utf-8')
    response['X-Accel-Buffering'] = 'no'
    return response

async def saju_api_view(request):
    """사주 분석 API (async)"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'POST 요청만 허용됩니다.'}, status=405)

        # Manual ratelimit check
        if await _check_saju_ratelimit(request):
            return JsonResponse({
                'error': 'LIMIT_EXCEEDED',
                'message': '선생님, 오늘 사주 분석 이용 한도를 모두 사용했습니다. 내일 다시 시도해주세요.'
            }, status=429)

        form = SajuForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'error': '입력값을 확인해주세요.', 'errors': form.errors}, status=400)

        data = form.cleaned_data
        mode = data['mode']
        user_label = _fortune_user_label(request.user)
        logger.info("[Fortune] Action: SAJU_API_REQUEST, User: %s, Mode: %s", user_label, mode)

        # Logic Engine (DB 조회 포함)
        chart_context = await sync_to_async(get_chart_context)(data)
        prompt = get_prompt(mode, data, chart_context=chart_context)
        cache_fingerprint, cached_result = await sync_to_async(_get_full_analysis_cache_entry)(request.user, data)

        if cached_result:
            logger.info("[Fortune] Action: SAJU_API_REQUEST, Cache: HIT, User: %s, Mode: %s", user_label, mode)
            response_text = cached_result.result_text
        else:
            response_text = await _collect_ai_response_async(prompt, request)
            response_text = scrub_personal_fortune_text(response_text)
            if cache_fingerprint and response_text:
                await sync_to_async(store_cached_pseudonymous_result)(request.user, 'full', cache_fingerprint, response_text)
            logger.info("[Fortune] Action: SAJU_API_REQUEST, Cache: MISS, User: %s, Mode: %s", user_label, mode)

        return JsonResponse({
            'success': True,
            'result': response_text,
            'mode': mode,
            'day_master': {
                'char': str(chart_context['day']['stem']),
                'element': chart_context['day']['stem'].element
            } if chart_context else None,
            'chart': {
                'year': [str(chart_context['year']['stem']), str(chart_context['year']['branch'])],
                'month': [str(chart_context['month']['stem']), str(chart_context['month']['branch'])],
                'day': [str(chart_context['day']['stem']), str(chart_context['day']['branch'])],
                'hour': [str(chart_context['hour']['stem']), str(chart_context['hour']['branch'])],
            } if chart_context else None
        })
    except Exception as e:
        logger.exception(f"사주 API 전역 오류 | User: {request.user} | UA: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        error_str = str(e)
        if "API_KEY_MISSING" in error_str:
            return JsonResponse({'error': 'CONFIG_ERROR', 'message': 'API 키가 설정되지 않았습니다. 관리자에게 문의해주세요.'}, status=500)
        if "matching query does not exist" in error_str:
            return JsonResponse({'error': 'DATABASE_ERROR', 'message': '기본 사주 데이터가 없습니다. 서버 점검 중입니다.'}, status=500)
        if "503" in error_str:
             return JsonResponse({'error': 'AI_OVERLOADED', 'message': '지금 AI 모델이 너무 바쁘네요! 30초 정도 뒤에 다시 시도해주시면 감사하겠습니다.'}, status=503)
        if "Insufficient Balance" in error_str:
             return JsonResponse({'error': 'AI_LIMIT', 'message': '선생님, 공용 AI 사용량이 초과되었습니다. 잠시 후 다시 시도해주세요.'}, status=429)
        return JsonResponse({'error': 'AI_ERROR', 'message': '분석 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'}, status=500)


async def daily_fortune_api(request):
    """특정 날짜의 일진(운세) 분석 API (async)"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'POST 요청만 허용됩니다.'}, status=405)

        # Manual ratelimit check
        if await _check_saju_ratelimit(request):
            return JsonResponse({
                'error': 'LIMIT_EXCEEDED',
                'message': '선생님, 오늘 사주 분석 이용 한도를 모두 사용했습니다. 내일 다시 시도해주세요.'
            }, status=429)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'INVALID_JSON', 'message': '유효한 JSON 본문이 필요합니다.'}, status=400)

        target_date_str = data.get('target_date')
        natal_data = normalize_natal_chart_payload(data.get('natal_chart'))
        gender = data.get('gender', 'female')
        mode = data.get('mode', 'teacher')

        if not target_date_str:
            return JsonResponse({'error': 'Target date required'}, status=400)

        # Parse target date and get its pillars (DB 조회 포함)
        target_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
        tz = pytz.timezone('Asia/Seoul')
        target_dt = tz.localize(target_dt).replace(hour=12)
        target_context = await sync_to_async(calculator.get_pillars)(target_dt)

        # Build Natal Context with objects to include element info
        from .models import Stem, Branch

        @sync_to_async
        def build_natal_context(natal_data):
            def get_pillar_obj(pillar_value):
                if not pillar_value:
                    return {'stem': None, 'branch': None}
                if isinstance(pillar_value, dict):
                    s_char = pillar_value.get('stem')
                    b_char = pillar_value.get('branch')
                elif isinstance(pillar_value, (list, tuple)) and len(pillar_value) >= 2:
                    s_char, b_char = pillar_value[0], pillar_value[1]
                elif isinstance(pillar_value, str) and len(pillar_value) >= 2:
                    s_char, b_char = pillar_value[:1], pillar_value[1:]
                else:
                    return {'stem': None, 'branch': None}

                return {
                    'stem': Stem.objects.filter(character=str(s_char)).first(),
                    'branch': Branch.objects.filter(character=str(b_char)).first()
                }
            return {
                'year': get_pillar_obj((natal_data or {}).get('year')),
                'month': get_pillar_obj((natal_data or {}).get('month')),
                'day': get_pillar_obj((natal_data or {}).get('day')),
                'hour': get_pillar_obj((natal_data or {}).get('hour'))
            }

        natal_context = await build_natal_context(natal_data)

        # Prompt
        from .prompts import get_daily_fortune_prompt
        prompt = get_daily_fortune_prompt(gender, natal_context, target_dt, target_context, mode=mode)
        cache_fingerprint, cached_response = await sync_to_async(
            _get_daily_cache_entry
        )(request.user, mode, target_date_str, natal_data)

        if cached_response:
            logger.info("[Fortune] Action: DAILY_ANALYZE, Cache: HIT, User: %s, Date: %s", _fortune_user_label(request.user), target_date_str)
            response_text = cached_response.result_text
        else:
            response_text = await _collect_ai_response_async(prompt, request)
            response_text = scrub_personal_fortune_text(response_text)
            if cache_fingerprint and response_text:
                await sync_to_async(store_cached_pseudonymous_result)(request.user, 'daily', cache_fingerprint, response_text)
            logger.info("[Fortune] Action: DAILY_ANALYZE, Cache: MISS, User: %s, Date: %s", _fortune_user_label(request.user), target_date_str)

        # 통계용 로그 저장
        if request.user.is_authenticated:
            from .models import DailyFortuneLog
            await DailyFortuneLog.objects.acreate(
                user=request.user,
                target_date=target_dt.date()
            )

        return JsonResponse({
            'success': True,
            'result': response_text,
            'target_date': target_date_str
        })
    except Exception as e:
        logger.exception(f"일진 API 전역 오류 | User: {request.user} | UA: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        return JsonResponse({'error': '일일 운세를 분석하는 중 오류가 발생했습니다.'}, status=500)


@login_required
@require_POST
def save_fortune_api(request):
    """결과 저장 API (회원 전용) - 저장된 pk 반환"""
    try:
        data = json.loads(request.body)
        from .models import FortuneResult

        result_text = scrub_personal_fortune_text(data.get('result_text'))
        if not result_text:
            return JsonResponse({'success': False, 'error': '저장 가능한 결과가 없습니다.'}, status=400)

        saved_result = FortuneResult.objects.create(
            user=request.user,
            mode=data.get('mode', 'teacher'),
            result_text=result_text,
            target_date=data.get('target_date') if data.get('target_date') else None
        )
        return JsonResponse({'success': True, 'result_id': saved_result.pk})
    except Exception as e:
        logger.error(f"Save Result Error: {e}")
        return JsonResponse({'success': False, 'error': '결과를 보관함에 저장하지 못했습니다.'}, status=400)


@login_required
def saju_history(request):
    """내 사주 보관함 목록"""
    from .models import FortuneResult
    history = FortuneResult.objects.filter(user=request.user)
    return _render_private_fortune_page(request, 'fortune/history.html', {
        'history': history,
        **build_fortune_history_page_seo(request).as_context(),
    })


@login_required
@require_POST
def delete_history_api(request, pk):
    """보관함 항목 삭제"""
    from .models import FortuneResult
    item = get_object_or_404(FortuneResult, pk=pk, user=request.user)
    item.delete()
    return JsonResponse({'success': True})


# ============================================
# 프로필 관리 API
# ============================================

def profile_list_api(request):
    """개인정보 비저장 전환 이후 프로필 목록은 더 이상 제공하지 않음"""
    return JsonResponse({'profiles': []})


@login_required
@require_POST
def profile_create_api(request):
    """프로필 저장 기능은 개인정보 비저장 전환 후 종료됨"""
    return JsonResponse({'success': False, 'error': '프로필 저장 기능이 종료되었습니다.'}, status=410)


@login_required
@require_POST
def profile_update_api(request, pk):
    """프로필 수정 기능은 개인정보 비저장 전환 후 종료됨"""
    return JsonResponse({'success': False, 'error': '프로필 저장 기능이 종료되었습니다.'}, status=410)


@login_required
@require_POST
def profile_delete_api(request, pk):
    """프로필 삭제 기능은 개인정보 비저장 전환 후 종료됨"""
    return JsonResponse({'success': False, 'error': '프로필 저장 기능이 종료되었습니다.'}, status=410)


@login_required
@require_POST
def profile_set_default_api(request, pk):
    """기본 프로필 기능은 개인정보 비저장 전환 후 종료됨"""
    return JsonResponse({'success': False, 'error': '프로필 저장 기능이 종료되었습니다.'}, status=410)


# ============================================
# 즐겨찾기 날짜 API
# ============================================

def favorite_dates_api(request):
    """즐겨찾기 날짜 목록 조회"""
    if not request.user.is_authenticated:
        return JsonResponse({'favorites': []})

    from .models import FavoriteDate
    from datetime import date

    favorites = FavoriteDate.objects.filter(user=request.user).order_by('date')
    today = date.today()

    data = [{
        'id': f.id,
        'date': f.date.strftime('%Y-%m-%d'),
        'label': f.label,
        'memo': f.memo,
        'color': f.color,
        'is_past': f.date < today,
        'days_until': (f.date - today).days
    } for f in favorites]

    return JsonResponse({'favorites': data})


@login_required
@require_POST
def favorite_date_add_api(request):
    """즐겨찾기 날짜 추가"""
    from .models import FavoriteDate
    from datetime import datetime

    try:
        data = json.loads(request.body)
        favorite = FavoriteDate.objects.create(
            user=request.user,
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            label=data['label'],
            memo=data.get('memo', ''),
            color=data.get('color', 'indigo')
        )
        return JsonResponse({'success': True, 'favorite_id': favorite.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def favorite_date_delete_api(request, pk):
    """즐겨찾기 날짜 삭제"""
    from .models import FavoriteDate
    favorite = get_object_or_404(FavoriteDate, pk=pk, user=request.user)
    favorite.delete()
    return JsonResponse({'success': True})


# ============================================
# 통계 API
# ============================================

def statistics_api(request):
    """사용자 통계 조회"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'total_analyses': 0,
            'total_daily_checks': 0,
            'recent_activity': 0,
            'top_dates': []
        })

    from .models import DailyFortuneLog, FortuneResult
    from django.db.models import Count
    from datetime import timedelta
    from django.utils import timezone

    # 최근 30일간 조회 기록
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_logs = DailyFortuneLog.objects.filter(
        user=request.user,
        viewed_at__gte=thirty_days_ago
    )

    # 가장 많이 본 날짜 (상위 5개)
    top_dates = recent_logs.values('target_date').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # 총 사주 분석 횟수
    total_analyses = FortuneResult.objects.filter(user=request.user).count()

    # 총 일진 조회 횟수
    total_daily_checks = DailyFortuneLog.objects.filter(user=request.user).count()

    # 최근 7일 활동
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_activity = recent_logs.filter(viewed_at__gte=seven_days_ago).count()

    return JsonResponse({
        'total_analyses': total_analyses,
        'total_daily_checks': total_daily_checks,
        'recent_activity': recent_activity,
        'top_dates': [{
            'date': item['target_date'].strftime('%Y-%m-%d'),
            'count': item['count']
        } for item in top_dates]
    })


def saju_history_detail(request, pk):
    """보관함 상세 보기 (공유 페이지로도 활용 가능 - 공개 접근 가능)"""
    from .models import FortuneResult
    item = get_object_or_404(FortuneResult, pk=pk)
    return _render_private_fortune_page(request, 'fortune/detail.html', {
        'item': item,
        'kakao_js_key': settings.KAKAO_JS_KEY,
        **build_fortune_detail_page_seo(request, item).as_context(),
    })
