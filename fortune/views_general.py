"""
일반 모드 전용 뷰
URL: /fortune/general/
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .forms import SajuForm


@login_required
def general_saju_view(request):
    """일반 모드 사주 분석 진입점"""
    # 세션에 모드 저장
    request.session['saju_mode'] = 'general'

    # 템플릿에 mode 전달
    context = {
        'form': SajuForm(),
        'mode': 'general',
    }

    return render(request, 'fortune/general_form.html', context)
