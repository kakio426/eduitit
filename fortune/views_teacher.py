"""
교사 모드 전용 뷰
URL: /fortune/teacher/
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .forms import SajuForm


@login_required
def teacher_saju_view(request):
    """교사 모드 사주 분석 진입점"""
    # 세션에 모드 저장
    request.session['saju_mode'] = 'teacher'

    # 템플릿에 mode 전달
    context = {
        'form': SajuForm(),
        'mode': 'teacher',
    }

    return render(request, 'fortune/teacher_form.html', context)
