from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse, HttpResponse
from django.db.models import Count
from django.utils import timezone
import json
import qrcode
from io import BytesIO
import base64
import logging

from .models import TestSession, StudentMBTIResult
from .student_mbti_data import STUDENT_MBTI_RESULTS, STUDENT_QUESTIONS, STUDENT_MBTI_THEMES
from products.models import Product

logger = logging.getLogger(__name__)

def get_student_service():
    """SIS 규격에 따라 서비스 정보 로드"""
    return Product.objects.filter(title__icontains="우리반 캐릭터").first()

def generate_session_qr(session_id, request):
    """세션 QR 코드 생성 (Base64 반환)"""
    # 절대 URL 생성
    url = request.build_absolute_uri(f'/studentmbti/session/{session_id}/')
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode()


# ================================
# 공개 랜딩 페이지
# ================================

def landing_page(request):
    """공개 랜딩 페이지 - 로그인 불필요"""
    try:
        service = get_student_service()
        return render(request, 'studentmbti/landing.html', {
            'service': service,
        })
    except Exception as e:
        logger.error(f"[StudentMBTI] Landing Page Error: {str(e)}")
        return HttpResponse("페이지를 로드하는 중 오류가 발생했습니다.", status=500)


# ================================
# 교사용 대시보드 뷰
# ================================

@login_required
def dashboard(request):
    """교사 대시보드 메인 - 세션 목록"""
    try:
        service = get_student_service()
        sessions = TestSession.objects.filter(teacher=request.user).order_by('-created_at')
        
        return render(request, 'studentmbti/dashboard.html', {
            'service': service,
            'sessions': sessions,
        })
    except Exception as e:
        logger.error(f"[StudentMBTI] Dashboard Error: {str(e)}")
        return HttpResponse("대시보드를 로드하는 중 오류가 발생했습니다.", status=500)


@login_required
@require_POST
def session_create(request):
    """새 검사 세션 생성"""
    try:
        session_name = request.POST.get('session_name', '').strip()
        if not session_name:
            session_name = f"검사 세션 ({timezone.now().strftime('%Y-%m-%d %H:%M')})"
        
        session = TestSession.objects.create(
            teacher=request.user,
            session_name=session_name
        )
        logger.info(f"[StudentMBTI] Session Created: {session.id} by {request.user.username}")
        return redirect('studentmbti:session_detail', session_id=session.id)
    except Exception as e:
        logger.error(f"[StudentMBTI] Session Create Error: {str(e)}")
        return HttpResponse("세션 생성 중 오류가 발생했습니다.", status=500)


@login_required
def session_detail(request, session_id):
    """세션 상세 및 실시간 결과 모니터링"""
    try:
        service = get_student_service()
        session = get_object_or_404(TestSession, id=session_id, teacher=request.user)
        results = session.results.all().order_by('-created_at')
        
        # QR 코드 생성
        qr_code_base64 = generate_session_qr(session.id, request)
        
        # MBTI 통계 및 퍼센트 계산
        mbti_stats = results.values('mbti_type', 'animal_name').annotate(
            count=Count('mbti_type')
        ).order_by('-count')
        
        total_count = results.count()
        # 테마 정보 및 퍼센트 추가
        for stat in mbti_stats:
            stat['theme'] = STUDENT_MBTI_THEMES.get(stat['mbti_type'], {})
            stat['percentage'] = (stat['count'] / total_count * 100) if total_count > 0 else 0
        
        return render(request, 'studentmbti/session_detail.html', {
            'service': service,
            'session': session,
            'results': results,
            'qr_code_base64': qr_code_base64,
            'mbti_stats': mbti_stats,
            'total_count': total_count,
        })
    except Exception as e:
        logger.error(f"[StudentMBTI] Session Detail Error: {str(e)}")
        return HttpResponse("세션 상세 정보를 불러오는 중 오류가 발생했습니다.", status=500)


@login_required
def session_results_partial(request, session_id):
    """HTMX 폴링용 - 결과 목록 부분 업데이트"""
    session = get_object_or_404(TestSession, id=session_id, teacher=request.user)
    results = session.results.all().order_by('-created_at')
    
    return render(request, 'studentmbti/partials/results_list.html', {
        'results': results,
        'total_count': results.count(),
    })


@login_required
def session_toggle_active(request, session_id):
    """세션 활성화/비활성화 토글"""
    session = get_object_or_404(TestSession, id=session_id, teacher=request.user)
    session.is_active = not session.is_active
    session.save()
    
    return redirect('studentmbti:session_detail', session_id=session.id)


@login_required
def result_detail_teacher(request, result_id):
    """교사용 결과 상세보기"""
    try:
        service = get_student_service()
        result = get_object_or_404(StudentMBTIResult, id=result_id)
        
        # 해당 세션의 교사인지 확인
        if result.session.teacher != request.user:
            return HttpResponse("권한이 없습니다.", status=403)
        
        mbti_data = STUDENT_MBTI_RESULTS.get(result.mbti_type, {})
        theme = STUDENT_MBTI_THEMES.get(result.mbti_type, {})
        
        return render(request, 'studentmbti/result_detail.html', {
            'service': service,
            'result': result,
            'mbti_data': mbti_data,
            'theme': theme,
            'is_teacher_view': True,
        })
    except Exception as e:
        logger.error(f"[StudentMBTI] Teacher Result Detail Error: {str(e)}")
        return HttpResponse("결과 정보를 불러오는 중 오류가 발생했습니다.", status=500)


# ================================
# 학생용 뷰 (비회원 접근)
# ================================

def session_test(request, session_id):
    """학생이 세션 QR로 접속해서 테스트 진행"""
    try:
        session = get_object_or_404(TestSession, id=session_id)
        
        if not session.is_active:
            return render(request, 'studentmbti/session_closed.html', {
                'session': session,
            })
        
        return render(request, 'studentmbti/test.html', {
            'session': session,
            'questions': STUDENT_QUESTIONS,
        })
    except Exception as e:
        logger.error(f"[StudentMBTI] Student Test View Error: {str(e)}")
        return HttpResponse("테스트 페이지를 불러오는 중 오류가 발생했습니다.", status=500)


@require_POST
def analyze(request, session_id):
    """학생 MBTI 분석 및 결과 저장"""
    try:
        session = get_object_or_404(TestSession, id=session_id)
        
        if not session.is_active:
            return JsonResponse({'error': '이 검사 세션은 종료되었습니다.'}, status=400)
        
        student_name = request.POST.get('student_name', '').strip()
        if not student_name:
            return JsonResponse({'error': '이름을 입력해주세요.'}, status=400)
        
        # 답변 수집
        answers = {}
        for i in range(1, 13):
            answer = request.POST.get(f'q{i}')
            if answer is None or answer == '':
                return JsonResponse({'error': f'질문 {i}번에 답변해주세요.'}, status=400)
            answers[f'q{i}'] = int(answer)
        
        # MBTI 계산
        def get_dim_count(start, end, dim_index):
            """특정 범위의 질문에서 첫 번째 옵션(0) 선택 횟수"""
            count = 0
            for i in range(start, end + 1):
                if answers.get(f'q{i}') == dim_index:
                    count += 1
            return count
        
        # E/I: Q1-3, S/N: Q4-6, T/F: Q7-9, J/P: Q10-12
        e_count = get_dim_count(1, 3, 0)  # 첫번째 옵션이 E
        s_count = get_dim_count(4, 6, 0)  # 첫번째 옵션이 S
        t_count = get_dim_count(7, 9, 0)  # 첫번째 옵션이 T
        j_count = get_dim_count(10, 12, 0)  # 첫번째 옵션이 J
        
        mbti_type = ''
        mbti_type += 'E' if e_count >= 2 else 'I'
        mbti_type += 'S' if s_count >= 2 else 'N'
        mbti_type += 'T' if t_count >= 2 else 'F'
        mbti_type += 'J' if j_count >= 2 else 'P'
        
        # 결과 데이터 가져오기
        mbti_data = STUDENT_MBTI_RESULTS.get(mbti_type, {})
        animal_name = mbti_data.get('animal_name', '알 수 없음')
        
        # 결과 저장
        result = StudentMBTIResult.objects.create(
            session=session,
            student_name=student_name,
            mbti_type=mbti_type,
            animal_name=animal_name,
            answers_json=answers
        )
        logger.info(f"[StudentMBTI] Analyze Success: Result {result.id}, MBTI {mbti_type}")
        return redirect('studentmbti:result', result_id=result.id)
    except Exception as e:
        logger.error(f"[StudentMBTI] Analyze Error: {str(e)}")
        return HttpResponse("분석 중 오류가 발생했습니다.", status=500)


def result(request, result_id):
    """학생 결과 페이지"""
    try:
        result = get_object_or_404(StudentMBTIResult, id=result_id)
        mbti_data = STUDENT_MBTI_RESULTS.get(result.mbti_type, {})
        theme = STUDENT_MBTI_THEMES.get(result.mbti_type, {})
        
        return render(request, 'studentmbti/result.html', {
            'result': result,
            'mbti_data': mbti_data,
            'theme': theme,
            'is_teacher_view': False,
        })
    except Exception as e:
        logger.error(f"[StudentMBTI] Result View Error: {str(e)}")
        return HttpResponse("결과를 불러오는 중 오류가 발생했습니다.", status=500)


# ================================
# 엑셀 다운로드
# ================================

@login_required
def export_excel(request, session_id):
    """세션 결과 엑셀 다운로드"""
    try:
        import csv
        
        session = get_object_or_404(TestSession, id=session_id, teacher=request.user)
        results = session.results.all().order_by('created_at')
        
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{session.session_name}_results.csv"'
        
        # BOM for Excel
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow(['번호', '학생 이름', 'MBTI 유형', '동물 유형', '검사 시간'])
        
        for idx, r in enumerate(results, 1):
            writer.writerow([
                idx,
                r.student_name,
                r.mbti_type,
                r.animal_name,
                r.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        logger.info(f"[StudentMBTI] Excel Exported: Session {session.id} by {request.user.username}")
        return response
    except Exception as e:
        logger.error(f"[StudentMBTI] Excel Export Error: {str(e)}")
        return HttpResponse("엑셀 다운로드 중 오류가 발생했습니다.", status=500)
