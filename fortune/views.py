import os
import google.generativeai as genai
from django.shortcuts import render
from django.http import JsonResponse
from .forms import SajuForm
from .prompts import get_prompt


def get_api_key(request):
    """사용자 또는 환경변수에서 API 키 가져오기"""
    # 로그인한 사용자의 개인 API 키 우선
    if request.user.is_authenticated:
        try:
            user_key = request.user.userprofile.gemini_api_key
            if user_key:
                return user_key
        except Exception:
            pass
    # 환경변수 폴백
    return os.environ.get('GEMINI_API_KEY', '')


def saju_view(request):
    """사주 분석 메인 뷰"""
    result_html = None
    error_message = None

    if request.method == 'POST':
        form = SajuForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            mode = data['mode']

            # 프롬프트 생성
            prompt = get_prompt(mode, data)

            # API 키 가져오기
            api_key = get_api_key(request)

            if not api_key:
                error_message = "Gemini API 키가 설정되지 않았습니다. 설정 페이지에서 API 키를 등록해주세요."
            else:
                try:
                    # Gemini API 설정 및 호출
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.0-flash')

                    response = model.generate_content(prompt)

                    # 결과를 그대로 전달 (템플릿에서 마크다운 렌더링)
                    result_html = response.text

                except Exception as e:
                    error_message = f"사주 분석 중 오류가 발생했습니다: {str(e)}"
    else:
        form = SajuForm()

    return render(request, 'fortune/saju_form.html', {
        'form': form,
        'result': result_html,
        'error': error_message,
    })


def saju_api_view(request):
    """사주 분석 API (AJAX용)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST 요청만 허용됩니다.'}, status=405)

    form = SajuForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': '입력값을 확인해주세요.', 'errors': form.errors}, status=400)

    data = form.cleaned_data
    mode = data['mode']
    prompt = get_prompt(mode, data)

    api_key = get_api_key(request)
    if not api_key:
        return JsonResponse({'error': 'API 키가 설정되지 않았습니다.'}, status=400)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)

        return JsonResponse({
            'success': True,
            'result': response.text,
            'name': data['name'],
            'mode': mode,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
