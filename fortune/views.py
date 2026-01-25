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


@login_required
@ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=True)
def saju_view(request):
    """사주 분석 메인 뷰 (마스터키: 10회/시간, 개인키: 무제한)"""
    result_html = None
    error_message = None

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
                    # Gemini API Call
                    response = client.models.generate_content(
                        model=FIXED_MODEL_NAME,
                        contents=prompt
                    )

                    result_html = response.text

                except Exception as e:
                    import logging
                    logging.exception("사주 분석 오류")
                    error_message = f"사주 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. ({str(e)})"
    else:
        form = SajuForm()

    return render(request, 'fortune/saju_form.html', {
        'form': form,
        'result': result_html,
        'error': error_message,
        'kakao_js_key': settings.KAKAO_JS_KEY,
    })


@login_required
@ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=True)
def saju_api_view(request):
    """사주 분석 API (마스터키: 10회/시간, 개인키: 무제한)"""
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
        response = client.models.generate_content(
            model=FIXED_MODEL_NAME,
            contents=prompt
        )

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
        return JsonResponse({'error': 'AI 응답 생성 중 오류가 발생했습니다.'}, status=500)
