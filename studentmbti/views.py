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
    # 절대 URL 생성 (짧은 URL 별칭 사용)
    url = request.build_absolute_uri(f'/m/session/{session_id}/')
    
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
        test_type = request.POST.get('test_type', 'low')  # Default to 'low'
        
        if not session_name:
            session_name = f"검사 세션 ({timezone.now().strftime('%Y-%m-%d %H:%M')})"
        
        session = TestSession.objects.create(
            teacher=request.user,
            session_name=session_name,
            test_type=test_type
        )
        logger.info(f"[StudentMBTI] Action: SESSION_CREATE, Status: SUCCESS, SessionID: {session.id}, User: {request.user.username}, Type: {test_type}")
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
    
    # 전체화면 모드용 템플릿 요청인 경우
    template_name = 'studentmbti/partials/results_list.html'
    if request.GET.get('template') == 'fullscreen':
        template_name = 'studentmbti/partials/fullscreen_results.html'
    
    return render(request, template_name, {
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
@require_POST
def session_delete(request, session_id):
    """세션 삭제"""
    session = get_object_or_404(TestSession, id=session_id, teacher=request.user)
    session.delete()
    logger.info(f"[StudentMBTI] Action: SESSION_DELETE, Status: SUCCESS, SessionID: {session_id}, User: {request.user.username}")
    return redirect('studentmbti:dashboard')


def join_session(request):
    """입장 코드로 세션 참여"""
    code = request.GET.get('code', '').strip().upper()
    if not code:
        code = request.POST.get('code', '').strip().upper()
    
    if code:
        try:
            session = TestSession.objects.get(access_code=code, is_active=True)
            return redirect('studentmbti:session_test', session_id=session.id)
        except TestSession.DoesNotExist:
            return HttpResponse("유효하지 않은 입장 코드입니다. 선생님께 확인해주세요.", status=404)
    
    return HttpResponse("입장 코드를 입력해주세요.", status=400)


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
        
        # 즉시 '접속 중' 레코드 생성 (선생님 화면에 바로 뜨도록)
        # 이미 세션에 result_id가 있고 해당 레코드가 유효하면 재사용
        result_id = request.session.get('student_result_id')
        result = None
        if result_id:
            result = StudentMBTIResult.objects.filter(id=result_id, session=session).first()
        
        if not result:
            result = StudentMBTIResult.objects.create(
                session=session,
                student_name="접속 중...",
                mbti_type=None,
                animal_name=None,
                answers_json=None
            )
            request.session['student_result_id'] = str(result.id)
            logger.info(f"[StudentMBTI] Action: STUDENT_JOIN, Status: SUCCESS, ResultID: {result.id}, SessionID: {session_id}")
        
        # 세션 타입에 따른 질문 로드
        from .student_mbti_data import STUDENT_QUESTIONS_LOW, STUDENT_QUESTIONS_HIGH
        questions = STUDENT_QUESTIONS_HIGH if session.test_type == 'high' else STUDENT_QUESTIONS_LOW

        return render(request, 'studentmbti/test.html', {
            'session': session,
            'questions': questions,
            'result_id': result.id,
        })
    except Exception as e:
        logger.error(f"[StudentMBTI] Student Test View Error: {str(e)}")
        return HttpResponse("테스트 페이지를 불러오는 중 오류가 발생했습니다.", status=500)


@require_POST
def start_test(request, session_id):
    """학생이 이름을 입력하고 테스트를 시작할 때 호출 (기존 레코드 이름 업데이트)"""
    try:
        session = get_object_or_404(TestSession, id=session_id)
        
        if not session.is_active:
            return JsonResponse({'error': '이 검사 세션은 종료되었습니다.'}, status=400)
        
        student_name = request.POST.get('student_name', '').strip()
        if not student_name:
            return JsonResponse({'error': '이름을 입력해주세요.'}, status=400)
        
        # 세션에 저장된 result_id로 기존 레코드 찾아서 이름 업데이트
        result_id = request.session.get('student_result_id') or request.POST.get('result_id')
        
        if result_id:
            try:
                result = StudentMBTIResult.objects.get(id=result_id, session=session)
                result.student_name = student_name
                result.save()
                logger.info(f"[StudentMBTI] Student Named: {student_name} for Result {result.id}")
                return JsonResponse({'success': True, 'result_id': str(result.id)})
            except StudentMBTIResult.DoesNotExist:
                pass
        
        # 레코드가 없으면 새로 생성 (폴백)
        result = StudentMBTIResult.objects.create(
            session=session,
            student_name=student_name,
            mbti_type=None,
            animal_name=None,
            answers_json=None
        )
        request.session['student_result_id'] = str(result.id)
        
        logger.info(f"[StudentMBTI] Student Started (New): {student_name} in session {session_id}")
        return JsonResponse({'success': True, 'result_id': str(result.id)})
    except Exception as e:
        logger.error(f"[StudentMBTI] Start Test Error: {str(e)}")
        return JsonResponse({'error': '등록 중 오류가 발생했습니다.'}, status=500)



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
        
        # 테스트 타입에 따른 설정
        is_high = session.test_type == 'high'
        total_q = 28 if is_high else 12
        cutoff = 4 if is_high else 2
        
        # 답변 수집
        answers = {}
        for i in range(1, total_q + 1):
            answer = request.POST.get(f'q{i}')
            if answer is None or answer == '':
                # 답변이 없는 경우, 기존 세션이면 에러, 아니면 무시 (테스트 중일수도)
                # 여기서는 모든 답변이 필수라고 가정
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
        
        if is_high:
            # High Grade (28 Qs) - 7 per dimension
            # E/I: Q1-7, S/N: Q8-14, T/F: Q15-21, J/P: Q22-28
            e_count = get_dim_count(1, 7, 0)
            s_count = get_dim_count(8, 14, 0)
            t_count = get_dim_count(15, 21, 0)
            j_count = get_dim_count(22, 28, 0)
        else:
            # Low Grade (12 Qs) - 3 per dimension
            # E/I: Q1-3, S/N: Q4-6, T/F: Q7-9, J/P: Q10-12
            e_count = get_dim_count(1, 3, 0)
            s_count = get_dim_count(4, 6, 0)
            t_count = get_dim_count(7, 9, 0)
            j_count = get_dim_count(10, 12, 0)
        
        mbti_type = ''
        mbti_type += 'E' if e_count >= cutoff else 'I'
        mbti_type += 'S' if s_count >= cutoff else 'N'
        mbti_type += 'T' if t_count >= cutoff else 'F'
        mbti_type += 'J' if j_count >= cutoff else 'P'
        
        # 결과 데이터 가져오기
        mbti_data = STUDENT_MBTI_RESULTS.get(mbti_type, {})
        animal_name = mbti_data.get('animal_name', '알 수 없음')
        
        # 기존 레코드 업데이트 또는 새로 생성
        result_id = request.session.get('student_result_id')
        if result_id:
            try:
                result = StudentMBTIResult.objects.get(id=result_id, session=session)
                result.mbti_type = mbti_type
                result.animal_name = animal_name
                result.answers_json = answers
                result.save()
                logger.info(f"[StudentMBTI] Analyze Success (Updated): Result {result.id}, MBTI {mbti_type}")
            except StudentMBTIResult.DoesNotExist:
                # 세션에 저장된 ID가 유효하지 않으면 새로 생성
                result = StudentMBTIResult.objects.create(
                    session=session,
                    student_name=student_name,
                    mbti_type=mbti_type,
                    animal_name=animal_name,
                    answers_json=answers
                )
                logger.info(f"[StudentMBTI] Analyze Success (New): Result {result.id}, MBTI {mbti_type}")
        else:
            # start_test를 거치지 않은 경우 (이전 방식 호환)
            result = StudentMBTIResult.objects.create(
                session=session,
                student_name=student_name,
                mbti_type=mbti_type,
                animal_name=animal_name,
                answers_json=answers
            )
            logger.info(f"[StudentMBTI] Analyze Success (Legacy): Result {result.id}, MBTI {mbti_type}")
        
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
