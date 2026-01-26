import os
from google import genai
from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from core.utils import ratelimit_key_for_master_only
from .forms import SajuForm
from .prompts import get_prompt
from .libs import calculator
from datetime import datetime
import pytz
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# 선생님 요청 모델명
# 재미용 콘텐츠 → 가장 저렴한 Lite 모델
FIXED_MODEL_NAME = "gemini-2.5-flash-lite"


def get_gemini_client(request):
    """Gemini 클라이언트 생성 (사용자 API 키 또는 환경변수 사용)"""
    api_key = None

    # 로그인한 사용자의 개인 API 키 우선
    if request.user.is_authenticated:
        try:
            user_key = request.user.userprofile.gemini_api_key
            if user_key:
                api_key = user_key
        except Exception:
            pass

    # 환경변수 폴백
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY', '')

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


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
        import logging
        logging.error(f"Error calculating pillars: {e}")
        return None


@ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=False)
def saju_view(request):
    """사주 분석 메인 뷰 (Guest: 3/h, Member: 10/h)"""
    if getattr(request, 'limited', False):
        return render(request, 'fortune/saju_form.html', {
            'form': SajuForm(request.POST),
            'error': '선생님, 오늘의 무료 한도를 모두 사용하셨어요! 가입하시면 더 넉넉하게 보실 수 있습니다. 😊'
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
            
            # Form Prompt with SSOT data
            prompt = get_prompt(mode, data, chart_context=chart_context)

            # Gemini Client
            client = get_gemini_client(request)

            if not client:
                error_message = "Gemini API 키가 설정되지 않았습니다. 설정 페이지에서 API 키를 등록해주세요."
            else:
                try:
                    # Gemini API Call with simple retry for 503
                    max_retries = 2
                    import time
                    for i in range(max_retries + 1):
                        try:
                            response = client.models.generate_content(
                                model=FIXED_MODEL_NAME,
                                contents=prompt
                            )
                            result_html = response.text
                            break
                        except Exception as e:
                            if '503' in str(e) and i < max_retries:
                                time.sleep(1.5)
                                continue
                            raise e

                except Exception as e:
                    import logging
                    logging.exception("사주 분석 오류")
                    if "matching query does not exist" in str(e):
                        error_message = "기본 데이터가 데이터베이스에 존재하지 않습니다. 관리자에게 문의하여 'python manage.py seed_saju_data'를 실행해주세요."
                    elif "503" in str(e):
                        error_message = "지금 AI 모델이 너무 바쁘네요! 30초 정도 뒤에 다시 시도해주시면 감사하겠습니다. 😊"
                    else:
                        error_message = f"사주 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. ({str(e)})"
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


@ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=False)
def saju_api_view(request):
    """사주 분석 API (Guest: 3/h, Member: 10/h)"""
    if getattr(request, 'limited', False):
        return JsonResponse({
            'error': 'LIMIT_EXCEEDED',
            'message': '선생님, 오늘의 무료 한도를 모두 사용하셨어요! 가입하시면 더 넉넉하게 보실 수 있습니다. 😊'
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

    client = get_gemini_client(request)
    if not client:
        return JsonResponse({'error': 'API 키가 설정되지 않았습니다.'}, status=400)

    try:
        # GPT/Gemini API Call with retry
        max_retries = 2
        import time
        response = None
        for i in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=FIXED_MODEL_NAME,
                    contents=prompt
                )
                break
            except Exception as e:
                if '503' in str(e) and i < max_retries:
                    time.sleep(1.5)
                    continue
                raise e

        return JsonResponse({
            'success': True,
            'result': response.text,
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
        import logging
        logging.exception("사주 API 오류")
        if "matching query does not exist" in str(e):
            return JsonResponse({'error': 'DATABASE_ERROR', 'message': '기본 사주 데이터가 없습니다. 관리자에게 문의하세요.'}, status=500)
        if "503" in str(e):
             return JsonResponse({'error': 'AI_OVERLOADED', 'message': 'AI가 현재 너무 바쁩니다. 잠시 후 다시 시도해주세요.'}, status=503)
        return JsonResponse({'error': 'AI_ERROR', 'message': str(e)}, status=500)


@csrf_exempt
@ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=False)
def daily_fortune_api(request):
    """특정 날짜의 일진(운세) 분석 API (Guest: 3/h, Member: 10/h)"""
    if getattr(request, 'limited', False):
        return JsonResponse({
            'error': 'LIMIT_EXCEEDED',
            'message': '선생님, 오늘의 무료 한도를 모두 사용하셨어요! 가입하시면 더 넉넉하게 보실 수 있습니다. 😊'
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

        client = get_gemini_client(request)
        if not client:
            return JsonResponse({'error': 'API 키가 설정되지 않았습니다.'}, status=400)

        # Gemini API call with retry
        max_retries = 1
        import time
        response = None
        for i in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=FIXED_MODEL_NAME,
                    contents=prompt
                )
                break
            except Exception as e:
                if '503' in str(e) and i < max_retries:
                    time.sleep(1)
                    continue
                raise e

        return JsonResponse({
            'success': True,
            'result': response.text,
            'target_date': target_date_str
        })

    except Exception as e:
        import logging
        logging.exception("일진 API 오류")
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
