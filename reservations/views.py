from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.utils.text import slugify
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta, date

from .models import School, SchoolConfig, SpecialRoom, RecurringSchedule, BlackoutDate, Reservation
from .utils import get_max_booking_date
import logging

logger = logging.getLogger(__name__)

@login_required
def dashboard_landing(request):
    """
    사용자의 학교 유무를 확인하고 대시보드로 이동하거나 학교 생성으로 안내
    """
    # 사용자가 소유한 학교가 있는지 확인
    school = School.objects.filter(owner=request.user).first()
    
    if school:
        return redirect('reservations:admin_dashboard', school_slug=school.slug)
    
    # 학교가 없으면 생성 로직 (임시로 자동 생성 또는 폼으로 유도)
    if request.method == 'POST':
        name = request.POST.get('school_name')
        if name:
            # Slug 생성 (간단하게 처리, 실제로는 중복 체크 등 필요)
            slug = slugify(name, allow_unicode=True) or f"school-{request.user.id}"
            
            # 중복 slug 방지
            counter = 1
            original_slug = slug
            while School.objects.filter(slug=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
                
            school = School.objects.create(name=name, slug=slug, owner=request.user)
            SchoolConfig.objects.create(school=school) # Config 자동 생성
            
            # 기본 특별실 생성
            SpecialRoom.objects.create(school=school, name="과학실", icon="🧬")
            SpecialRoom.objects.create(school=school, name="컴퓨터실", icon="💻")
            
            messages.success(request, f"{school.name}이(가) 생성되었습니다.")
    if school:
        return redirect('reservations:admin_dashboard', school_slug=school.slug)
    
    # 사실 School 모델 정의 상 multi-school도 가능하지만 현재는 1인 1학교로 가정
    return render(request, 'reservations/dashboard_landing.html')

def short_url_redirect(request, school_id):
    """ID 기반의 짧은 URL으로 접속하면 학교 페이지로 리다이렉트"""
    school = get_object_or_404(School, id=school_id)
    return redirect('reservations:reservation_index', school_slug=school.slug)

@login_required
def admin_dashboard(request, school_slug):
    """
    관리자 대시보드 메인
    """
    school = get_object_or_404(School, slug=school_slug)
    
    # 권한 체크
    if school.owner != request.user:
        messages.error(request, "해당 학교의 관리자 권한이 없습니다.")
        return redirect('reservations:dashboard_landing')
        
    context = {
        'school': school,
        'config': school.config,
        'rooms': school.specialroom_set.all(),
        'blackouts': school.blackoutdate_set.all().order_by('start_date'),
    }
    return render(request, 'reservations/dashboard.html', context)

@login_required
def room_settings(request, school_slug):
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name')
            icon = request.POST.get('icon', '📍')
            if name:
                SpecialRoom.objects.create(school=school, name=name, icon=icon)
                messages.success(request, "특별실이 추가되었습니다.")
                
        elif action == 'delete':
            room_id = request.POST.get('room_id')
            SpecialRoom.objects.filter(id=room_id, school=school).delete()
            messages.success(request, "특별실이 삭제되었습니다.")
            
    return render(request, 'reservations/partials/room_list.html', {
        'rooms': school.specialroom_set.all(),
        'school': school
    })

@login_required
def recurring_settings(request, school_slug):
    """
    고정 시간표 설정 (Schedule Matrix)
    """
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        day = int(request.POST.get('day'))
        period = int(request.POST.get('period'))
        name = request.POST.get('name', '고정 수업') # 기본값
        
        room = get_object_or_404(SpecialRoom, id=room_id, school=school)
        
        # Toggle Logic: 이미 있으면 삭제, 없으면 생성
        schedule = RecurringSchedule.objects.filter(room=room, day_of_week=day, period=period).first()
        
        if schedule:
            schedule.delete()
            # messages.info(request, "고정 수업이 해제되었습니다.") # 너무 잦은 메시지는 방해될 수 있음
        else:
            RecurringSchedule.objects.create(room=room, day_of_week=day, period=period, name=name)
            # messages.success(request, "고정 수업이 설정되었습니다.")
            
        # HTMX 요청이면 전체 매트릭스를 다시 렌더링 (또는 해당 셀만 업데이트해도 되지만, 전체가 편함)
    
    rooms = school.specialroom_set.all()
    
    # 데이터 구조화: rooms_data = [ { 'room': room, 'matrix': [[sched or None, ...], ...] } ]
    # matrix[period-1][day] 형태로 접근 가능하게 (1교시가 0번 인덱스)
    
    config = school.config
    period_labels = config.get_period_list()
    periods = [{"id": i+1, "label": label} for i, label in enumerate(period_labels)]
    days = range(5) # 0~4 (월~금)
    
    rooms_data = []
    for room in rooms:
        # matrix[period-1][day]
        matrix = [[None for _ in days] for _ in periods]
        schedules = RecurringSchedule.objects.filter(room=room)
        for sched in schedules:
            if 1 <= sched.period <= len(periods) and 0 <= sched.day_of_week <= 4:
                matrix[sched.period-1][sched.day_of_week] = sched
        
        # 행 단위로 변환 (교시 정보 포함)
        rows = []
        for i, period_info in enumerate(periods):
            rows.append({
                'period': period_info,
                'slots': matrix[i]
            })
                
        rooms_data.append({
            'room': room,
            'rows': rows
        })
    
    return render(request, 'reservations/partials/recurring_matrix.html', {
        'school': school,
        'rooms_data': rooms_data,
        'days': days,
        'day_names': ['월', '화', '수', '목', '금']
    })

@login_required
@require_POST
def update_config(request, school_slug):
    """
    학교 설정 업데이트 (교시 이름 등)
    """
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    config = school.config
    
    # 학교 기본 정보 변경 (이름)
    new_name = request.POST.get('school_name')
    if new_name:
        school.name = new_name
    
    school.save()

    period_labels = request.POST.get('period_labels')
    if period_labels:
        config.period_labels = period_labels
        # max_periods 동기화 (기존 코드와의 호환성)
        config.max_periods = len(config.get_period_list())
    
    # 주간 예약 제한 설정 업데이트
    weekly_mode = request.POST.get('weekly_opening_mode') == 'on'
    config.weekly_opening_mode = weekly_mode
    
    if weekly_mode:
        config.weekly_opening_weekday = int(request.POST.get('weekly_opening_weekday', 4))
        config.weekly_opening_hour = int(request.POST.get('weekly_opening_hour', 9))
    else:
        # weekly_opening_mode가 꺼지면 관련 설정도 초기화하거나 무시
        config.weekly_opening_weekday = None
        config.weekly_opening_hour = None
    
    config.save()
    messages.success(request, "학교 설정이 저장되었습니다.")
    
    # 설정 후 대시보드로 리다이렉트 (HTMX일 경우 HX-Refresh)
    response = HttpResponse()
    # 슬러그가 바뀌었을 수 있으므로 전체 새로고침
    response['HX-Refresh'] = "true"
    return response

@login_required
def blackout_settings(request, school_slug):
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            start = request.POST.get('start_date')
            end = request.POST.get('end_date')
            reason = request.POST.get('reason')
            if start and end and reason:
                BlackoutDate.objects.create(school=school, start_date=start, end_date=end, reason=reason)
                messages.success(request, "블랙아웃 기간이 설정되었습니다.")
        elif action == 'delete':
            Item_id = request.POST.get('item_id')
            BlackoutDate.objects.filter(id=Item_id, school=school).delete()
            messages.success(request, "블랙아웃 기간이 삭제되었습니다.")

    return render(request, 'reservations/partials/blackout_list.html', {
        'blackouts': school.blackoutdate_set.all().order_by('start_date'),
    })

# Public Reservation Views

def reservation_index(request, school_slug):
    """
    사용자 예약 메인 페이지 (PC: 타임라인, Mobile: 리스트)
    - HTMX Polling 대상
    """
    school = get_object_or_404(School, slug=school_slug)
    config = school.config
    
    # 날짜 처리
    date_str = request.GET.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()
    
    # [Weekly Limit Check]
    max_date = get_max_booking_date(school)
    if not request.user.is_authenticated or school.owner != request.user:
        # 관리자는 제한 무시
        if max_date and target_date > max_date:
            # 예약 가능 날짜를 초과한 경우, max_date로 리다이렉트
            messages.warning(request, f"아직 예약이 열리지 않았습니다. (예약 가능: {max_date.strftime('%m월 %d일')}까지)")
            return redirect(f"{reverse('reservations:reservation_index', args=[school.slug])}?date={max_date.strftime('%Y-%m-%d')}")
    
        # 과거 날짜로 이동 시도 시 오늘 날짜로 리다이렉트 (관리자는 가능)
        if target_date < timezone.localdate():
            messages.warning(request, "과거 날짜는 조회할 수 없습니다.")
            return redirect(f"{reverse('reservations:reservation_index', args=[school.slug])}?date={timezone.localdate().strftime('%Y-%m-%d')}")
    
    # 날짜 네비게이션
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    
    # 블랙아웃 체크
    is_blackout = BlackoutDate.objects.filter(
        school=school, 
        start_date__lte=target_date, 
        end_date__gte=target_date
    ).first()
    
    # 데이터 조회
    rooms = school.specialroom_set.all()
    period_labels = config.get_period_list()
    periods_data = [{"id": i+1, "label": label} for i, label in enumerate(period_labels)]
    
    # 예약 및 고정 수업 조회
    reservations = Reservation.objects.filter(room__school=school, date=target_date).select_related('room')
    recurring = RecurringSchedule.objects.filter(room__school=school, day_of_week=target_date.weekday()).select_related('room')
    
    # 매트릭스 구성
    reservation_map = {(r.room_id, r.period): r for r in reservations}
    recurring_map = {(r.room_id, r.period): r for r in recurring}
    
    rooms_data = []
    for room in rooms:
        slots = []
        for p in periods_data:
            res = reservation_map.get((room.id, p['id']))
            rec = recurring_map.get((room.id, p['id']))
            
            # 상태 결정
            state = 'available'
            if is_blackout:
                state = 'blackout'
            elif rec:
                state = 'recurring'
            elif res:
                state = 'reserved'
            
            slots.append({
                'period': p['id'],
                'label': p['label'],
                'reservation': res,
                'recurring': rec,
                'state': state
            })
            
        rooms_data.append({
            'room': room,
            'slots': slots
        })

    context = {
        'school': school,
        'target_date': target_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'is_blackout': is_blackout,
        'rooms_data': rooms_data,
        'periods': periods_data,
        'weekday_name': ['월', '화', '수', '목', '금', '토', '일'][target_date.weekday()],
        'period_labels': period_labels,
        'max_date': max_date, # 템플릿에 전달하여 '다음' 버튼 비활성화에 사용
    }
    
    # HTMX 요청이면 부분 렌더링 (Polling 등)
    if request.headers.get('HX-Request'):
        return render(request, 'reservations/partials/reservation_grid.html', context)
        
    return render(request, 'reservations/index.html', context)

@require_POST
def create_reservation(request, school_slug):
    school = get_object_or_404(School, slug=school_slug)
    
    # 데이터 수신
    room_id = request.POST.get('room_id')
    date_str = request.POST.get('date')
    period = request.POST.get('period')
    grade = request.POST.get('grade')
    class_no = request.POST.get('class_no')
    name = request.POST.get('name')
    memo = request.POST.get('memo', '')
    
    # 유효성 검사
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        period = int(period)
        room = get_object_or_404(SpecialRoom, id=room_id, school=school)
        
        # [Weekly Limit Check] 백엔드 검증
        if not request.user.is_authenticated or school.owner != request.user: # 관리자는 제한 무시
            max_date = get_max_booking_date(school)
            if max_date and target_date > max_date:
                return HttpResponse(
                    f"<script>alert('예약이 아직 열리지 않았습니다. {max_date.strftime('%Y-%m-%d')}까지만 예약 가능합니다.');</script>", 
                    status=200 # HTMX swap을 위해 200 유지하되 스크립트 실행
                )
        
        # 1. 블랙아웃 체크
        if BlackoutDate.objects.filter(school=school, start_date__lte=target_date, end_date__gte=target_date).exists():
            return HttpResponse("예약이 불가능한 날짜입니다.", status=400)
            
        # 2. 고정 수업 체크
        if RecurringSchedule.objects.filter(room=room, day_of_week=target_date.weekday(), period=period).exists():
            return HttpResponse("고정 수업이 있는 시간입니다.", status=400)
            
        # 3. 중복 예약 체크 (Optimistic Locking 대용: Unique Constraint가 DB에서 막아주지만, 여기서도 체크)
        if Reservation.objects.filter(room=room, date=target_date, period=period).exists():
            return HttpResponse("이미 예약된 시간입니다.", status=409)
            
        # 생성
        reservation = Reservation.objects.create(
            room=room,
            date=target_date,
            period=period,
            grade=grade,
            class_no=class_no,
            name=name,
            memo=memo
        )
        
        messages.success(request, f"{period}교시 예약이 완료되었습니다.")
        
        # HTMX Redirect to refresh grid
        response = HttpResponse()
        response['HX-Refresh'] = "true" # 전체 리프레시가 가장 깔끔함 (모달 닫기 등)
        return response
        
    except Exception as e:
        logger.error(f"[Reservation Error] {e}")
        return HttpResponse("예약 처리 중 오류가 발생했습니다.", status=500)

@require_POST
def delete_reservation(request, school_slug, reservation_id):
    """
    일반 사용자용 예약 취소 (LocalStorage ID 매칭 전제, 보안 수준 낮음)
    """
    school = get_object_or_404(School, slug=school_slug)
    reservation = get_object_or_404(Reservation, id=reservation_id, room__school=school)
    
    # 추가 검증 로직이 없으므로, URL을 아는 누구나 삭제 가능할 수 있음.
    # 실서비스에서는 세션/쿠키 기반 소유권 검증이 필요하나, 현재 요구사항(로그인 없는 예약)상 유지.
    
    reservation.delete()
    messages.success(request, "예약이 취소되었습니다.")
    
    return redirect('reservations:reservation_index', school_slug=school.slug)

@login_required
@require_POST
def admin_delete_reservation(request, school_slug, reservation_id):
    """
    관리자용 예약 강제 삭제 (Admin Override)
    """
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    reservation = get_object_or_404(Reservation, id=reservation_id, room__school=school)
    
    reservation.delete()
    logger.info(f"[Reservation] Action: ADMIN_OVERRIDE | User: {request.user} | Deleted Reservation {reservation_id}")
    messages.success(request, "관리자 권한으로 예약이 삭제되었습니다.")
    
    # 대시보드로 리다이렉트할지, 인덱스로 갈지 결정. 보통 인덱스(현황판)에서 작업함.
    # HTMX 요청일 경우 200 OK + Grid Refresh
    if request.htmx:
        return HttpResponse(status=200)
        
    return redirect('reservations:reservation_index', school_slug=school.slug)
