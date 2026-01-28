import os
import time
from google import genai
from openai import OpenAI
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from core.utils import ratelimit_key_for_master_only
from .forms import SajuForm
from .prompts import get_prompt
from .libs import calculator
from datetime import datetime
import pytz
import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# 로거 설정
logger = logging.getLogger(__name__)

# 모델 설정
GEMINI_MODEL_NAME = "gemini-2.5-flash-lite"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

def get_user_gemini_key(request):
    """사용자의 개인 Gemini API 키 반환"""
    if request.user.is_authenticated:
        try:
            return request.user.userprofile.gemini_api_key
        except Exception:
            pass
    return None

def fortune_rate_h(group, request):
    """1시간당 5회 제한"""
    return '5/h'

def fortune_rate_d(group, request):
    """1일당 10회 제한"""
    return '10/d'

def generate_ai_response(prompt, request):
    """
    하이브리드 AI 응답 생성 함수 (Streaming 지원)
    1순위: 사용자 개인 Gemini 키 (존재하는 경우)
    2순위: 마스터 DeepSeek 키 (환경변수)
    """
    user_gemini_key = get_user_gemini_key(request)
    
    # 1. 사용자 개인 Gemini API 키 사용
    if user_gemini_key:
        try:
            client = genai.Client(api_key=user_gemini_key)
            
            # Gemini Retry Logic
            max_retries = 2
            for i in range(max_retries + 1):
                try:
                    # Google GenAI SDK streaming
                    # Use generate_content_stream for proper streaming behavior
                    if hasattr(client.models, 'generate_content_stream'):
                        response = client.models.generate_content_stream(
                            model=GEMINI_MODEL_NAME,
                            contents=prompt,
                        )
                    else:
                        # Fallback for older versions or strict interface
                        response = client.models.generate_content(
                            model=GEMINI_MODEL_NAME,
                            contents=prompt,
                            config={'stream': True}
                        )

                    chunk_count = 0
                    for chunk in response:
                        if chunk.text:
                            chunk_count += 1
                            yield chunk.text
                    
                    if chunk_count == 0:
                        logger.warning("Gemini stream yielded 0 chunks.")
                    return
                except Exception as e:
                    if '503' in str(e) and i < max_retries:
                        time.sleep(1.5)
                        continue
                    raise e
        except Exception as e:
            logger.exception(f"Gemini API Error (User Key): {e}")
            raise e

    # 2. 마스터 DeepSeek API 사용 (Fallback)
    master_deepseek_key = os.environ.get('MASTER_DEEPSEEK_API_KEY')
    if master_deepseek_key:
        try:
            client = OpenAI(
                api_key=master_deepseek_key,
                base_url=DEEPSEEK_BASE_URL
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
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
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
        
        # Assume Solar input for now. 
        # TODO: Handle Lunar input if calendar_type is 'lunar' using manse.lunar_to_solar
        
        # User timezone assumption: KST (Asia/Seoul)
        tz = pytz.timezone('Asia/Seoul')
        dt = datetime(year, month, day, hour, minute, tzinfo=tz)
        
        return calculator.get_pillars(dt)
    except Exception as e:
        logger.error(f"Error calculating pillars: {e}")
        return None


@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_h, method='POST', block=False, group='saju_service')
@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_d, method='POST', block=False, group='saju_service')
def saju_view(request):
    """사주 분석 메인 뷰 (5회/h, 10회/d)"""
    if getattr(request, 'limited', False):
        error_message = '선생님, 이 서비스는 개인 개발자의 사비로 운영되다 보니 공용 AI 무료 한도를 넉넉히 드리기 어렵습니다. 😭 [내 설정]에서 개인 Gemini API 키를 등록하시면 중단 없이 본격적으로 이용하실 수 있습니다! 😊'
        
        return render(request, 'fortune/saju_form.html', {
            'form': SajuForm(request.POST),
            'error': error_message
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
            
            # [DEBUG] 로그: 입력 데이터와 계산된 사주 명식 확인
            logger.info(f"User Input: {data}")
            logger.info(f"Calculated Chart: {chart_context}")
            
            # Form Prompt with SSOT data
            prompt = get_prompt(mode, data, chart_context=chart_context)

            try:
                # Wrap generator to maintain current sync behavior until Phase 4
                result_html = "".join(generate_ai_response(prompt, request))
            except Exception as e:
                logger.exception("사주 분석 오류")
                error_str = str(e)
                if "API_KEY_MISSING" in error_str:
                     error_message = "API 키가 설정되지 않았습니다. 관리자에게 문의해주세요."
                elif "matching query does not exist" in error_str:
                    error_message = "기본 데이터가 데이터베이스에 존재하지 않습니다. 관리자에게 문의하여 'python manage.py seed_saju_data'를 실행해주세요."
                elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str: # Gemini specific
                    if request.user.is_authenticated:
                        error_message = "선생님, 공용 AI 한도가 모두 소진되었습니다! [설정] 페이지에서 개인 Gemini API 키를 등록하시면 중단 없이 계속 이용하실 수 있습니다. 😊"
                    else:
                        error_message = "선생님, 현재 많은 분들이 이용 중이라 공용 AI 한도가 초과되었습니다! 가입 후 [설정]에서 개인 API 키를 등록하시면 기다림 없이 이용 가능합니다. (무료)"
                elif "503" in error_str:
                    error_message = "지금 AI 모델이 너무 바쁘네요! 30초 정도 뒤에 다시 시도해주시면 감사하겠습니다. 😊"
                elif "Insufficient Balance" in error_str: # DeepSeek specific
                     if request.user.is_authenticated:
                        error_message = "선생님, 공용 AI 사용량이 초과되었습니다. [설정]에서 '개인 Gemini API 키'를 등록하시면 무료로 계속 이용하실 수 있습니다! 😊"
                     else:
                        error_message = "선생님, 공용 AI 사용량이 초과되었습니다. 로그인 후 [설정]에서 '개인 API 키'를 등록하시면 무료로 계속 이용하실 수 있습니다!"
                else:
                    error_message = f"사주 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. ({error_str})"
    else:
        form = SajuForm()

    return render(request, 'fortune/saju_form.html', {
        'form': form,
        'result': result_html,
        'error': error_message,
        'name': request.POST.get('name') if request.method == 'POST' else None,
        'gender': request.POST.get('gender') if request.method == 'POST' else None,
        'chart': {
            'year': str(chart_context['year']['stem']) + str(chart_context['year']['branch']),
            'month': str(chart_context['month']['stem']) + str(chart_context['month']['branch']),
            'day': str(chart_context['day']['stem']) + str(chart_context['day']['branch']),
            'hour': str(chart_context['hour']['stem']) + str(chart_context['hour']['branch']),
        } if chart_context else None,
        'kakao_js_key': settings.KAKAO_JS_KEY,
    })


@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_h, method='POST', block=False, group='saju_service')
@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_d, method='POST', block=False, group='saju_service')
def saju_streaming_api(request):
    """실시간 스트리밍 사주 분석 API"""
    if getattr(request, 'limited', False):
        return JsonResponse({'error': 'LIMIT_EXCEEDED'}, status=429)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    form = SajuForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': 'Invalid data'}, status=400)

    data = form.cleaned_data
    chart_context = get_chart_context(data)
    prompt = get_prompt(data['mode'], data, chart_context=chart_context)

    def stream_response():
        try:
            # Yield initial metadata if needed (or just start spawning text)
            for chunk in generate_ai_response(prompt, request):
                yield chunk
        except Exception as e:
            logger.exception("Streaming error")
            yield f"\n\n[오류 발생: {str(e)}]"

    response = StreamingHttpResponse(stream_response(), content_type='text/plain; charset=utf-8')
    response['X-Accel-Buffering'] = 'no'  # Disable buffering for Nginx/Gunicorn
    return response

@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_h, method='POST', block=False, group='saju_service')
@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_d, method='POST', block=False, group='saju_service')
def saju_api_view(request):
    """사주 분석 API (5회/h, 10회/d)"""
    if getattr(request, 'limited', False):
        return JsonResponse({
            'error': 'LIMIT_EXCEEDED',
            'message': '선생님, 본 서비스는 개인 사비로 운영되어 공용 한도가 제한적입니다. 😭 [내 설정]에서 개인 Gemini API 키를 등록하시면 계속해서 이용 가능합니다! 😊'
        }, status=429)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST 요청만 허용됩니다.'}, status=405)

    form = SajuForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': '입력값을 확인해주세요.', 'errors': form.errors}, status=400)

    data = form.cleaned_data
    mode = data['mode']
    
    # Logic Engine
    chart_context = get_chart_context(data)
    
    prompt = get_prompt(mode, data, chart_context=chart_context)

    try:
        # Wrap generator to maintain current sync behavior
        response_text = "".join(generate_ai_response(prompt, request))
        
        return JsonResponse({
            'success': True,
            'result': response_text,
            'name': data['name'],
            'mode': mode,
            'chart': {
                'year': str(chart_context['year']['stem']) + str(chart_context['year']['branch']),
                'month': str(chart_context['month']['stem']) + str(chart_context['month']['branch']),
                'day': str(chart_context['day']['stem']) + str(chart_context['day']['branch']),
                'hour': str(chart_context['hour']['stem']) + str(chart_context['hour']['branch']),
            } if chart_context else None
        })
    except Exception as e:
        logger.exception("사주 API 오류")
        error_str = str(e)
        if "API_KEY_MISSING" in error_str:
            return JsonResponse({'error': 'CONFIG_ERROR', 'message': 'API 키가 설정되지 않았습니다.'}, status=500)
        if "matching query does not exist" in error_str:
            return JsonResponse({'error': 'DATABASE_ERROR', 'message': '기본 사주 데이터가 없습니다.'}, status=500)
        if "503" in error_str:
             return JsonResponse({'error': 'AI_OVERLOADED', 'message': 'AI가 현재 너무 바쁩니다.'}, status=503)
        if "Insufficient Balance" in error_str:
             return JsonResponse({'error': 'AI_LIMIT', 'message': '선생님, 공용 AI 사용량이 초과되었습니다. [설정]에서 개인 API 키를 등록해주세요!'}, status=429)
        return JsonResponse({'error': 'AI_ERROR', 'message': error_str}, status=500)


@csrf_exempt
@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_h, method='POST', block=False, group='saju_service')
@ratelimit(key=ratelimit_key_for_master_only, rate=fortune_rate_d, method='POST', block=False, group='saju_service')
def daily_fortune_api(request):
    """특정 날짜의 일진(운세) 분석 API (5회/h, 10회/d)"""
    if getattr(request, 'limited', False):
        return JsonResponse({
            'error': 'LIMIT_EXCEEDED',
            'message': '선생님, 본 서비스는 개인 사비로 운영되어 공용 한도가 제한적입니다. 😭 [내 설정]에서 개인 Gemini API 키를 등록하시면 계속해서 이용 가능합니다! 😊'
        }, status=429)

    try:
        data = json.loads(request.body)
        target_date_str = data.get('target_date') # YYYY-MM-DD
        natal_data = data.get('natal_chart') # {year: '...', month: '...', day: '...', hour: '...'}
        name = data.get('name', '선생님')
        gender = data.get('gender', 'female')

        if not target_date_str:
            return JsonResponse({'error': 'Target date required'}, status=400)

        # Parse target date and get its pillars
        target_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
        tz = pytz.timezone('Asia/Seoul')
        target_dt = tz.localize(target_dt).replace(hour=12) # Noon check
        target_context = calculator.get_pillars(target_dt)

        # Build Natal Context from strings
        natal_context = {
            'year': {'stem': natal_data['year'][:1], 'branch': natal_data['year'][1:]},
            'month': {'stem': natal_data['month'][:1], 'branch': natal_data['month'][1:]},
            'day': {'stem': natal_data['day'][:1], 'branch': natal_data['day'][1:]},
            'hour': {'stem': natal_data['hour'][:1], 'branch': natal_data['hour'][1:]}
        }

        # Prompt
        from .prompts import get_daily_fortune_prompt
        prompt = get_daily_fortune_prompt(name, gender, natal_context, target_dt, target_context)

        # Wrap generator to maintain current sync behavior
        response_text = "".join(generate_ai_response(prompt, request))

        return JsonResponse({
            'success': True,
            'result': response_text,
            'target_date': target_date_str
        })

    except Exception as e:
        logger.exception("일진 API 오류")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def save_fortune_api(request):
    """결과 저장 API (회원 전용)"""
    try:
        data = json.loads(request.body)
        from .models import FortuneResult
        
        FortuneResult.objects.create(
            user=request.user,
            mode=data.get('mode', 'teacher'),
            natal_chart=data.get('natal_chart'),
            result_text=data.get('result_text'),
            target_date=data.get('target_date') if data.get('target_date') else None
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def saju_history(request):
    """내 사주 보관함 목록"""
    from .models import FortuneResult
    history = FortuneResult.objects.filter(user=request.user)
    return render(request, 'fortune/history.html', {'history': history})


@login_required
@require_POST
def delete_history_api(request, pk):
    """보관함 항목 삭제"""
    from .models import FortuneResult
    item = get_object_or_404(FortuneResult, pk=pk, user=request.user)
    item.delete()
    return JsonResponse({'success': True})


@login_required
def saju_history_detail(request, pk):
    """보관함 상세 보기"""
    from .models import FortuneResult
    item = get_object_or_404(FortuneResult, pk=pk, user=request.user)
    return render(request, 'fortune/detail.html', {'item': item})
