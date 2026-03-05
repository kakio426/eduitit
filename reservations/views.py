from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.utils.text import slugify
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta, date

from .models import School, SchoolConfig, SpecialRoom, RecurringSchedule, GradeRecurringLock, BlackoutDate, Reservation
from .utils import get_max_booking_date
import logging

logger = logging.getLogger(__name__)
OWNED_RESERVATIONS_SESSION_KEY = 'owned_reservation_ids'

@login_required
def dashboard_landing(request):
    """
    사용자의 학교 목록을 보여주거나 새 학교 생성으로 안내
    """
    # 사용자가 소유한 학교 목록 확인
    user_schools = School.objects.filter(owner=request.user)
    
    # 학교가 없거나 생성 요청(POST)인 경우 처리
    if request.method == 'POST':
        name = request.POST.get('school_name')
        if name:
            # Slug 생성
            slug = slugify(name, allow_unicode=True) or f"school-{request.user.id}"
            
            # 중복 slug 방지
            counter = 1
            original_slug = slug
            while School.objects.filter(slug=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
                
            school = School.objects.create(name=name, slug=slug, owner=request.user)
            SchoolConfig.objects.create(school=school) # Config 자동 생성
            
            # 기본 특별실 생성 (이전보다 간소하게 변경 가능)
            SpecialRoom.objects.create(school=school, name="과학실", icon="🔬")
            SpecialRoom.objects.create(school=school, name="컴퓨터실", icon="💻")
            
            messages.success(request, f"{school.name}이(가) 생성되었습니다.")
            return redirect('reservations:admin_dashboard', school_slug=school.slug)
    
    return render(request, 'reservations/landing.html', {
        'user_schools': user_schools
    })

@login_required
@require_POST
def delete_school(request, school_slug):
    """학교 및 관련 데이터 전체 삭제"""
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    school_name = school.name
    school.delete()
    messages.success(request, f"'{school_name}' 학교와 관련된 모든 데이터가 삭제되었습니다.")
    return redirect('reservations:dashboard_landing')

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
        
    # Ensure config exists (OneToOne relationship safety)
    config, _ = SchoolConfig.objects.get_or_create(school=school)
    
    context = {
        'school': school,
        'config': config,
        'rooms': school.specialroom_set.all(),
        'grade_locks': GradeRecurringLock.objects.filter(room__school=school).select_related('room').order_by('day_of_week', 'period', 'room__name'),
        'period_slots': config.get_period_slots(),
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
    
    config, _ = SchoolConfig.objects.get_or_create(school=school)
    periods = config.get_period_slots()
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
def grade_lock_settings(request, school_slug):
    school = get_object_or_404(School, slug=school_slug, owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            room_id = request.POST.get('room_id')
            day_of_week = request.POST.get('day_of_week')
            period = request.POST.get('period')
            grade = request.POST.get('grade')

            try:
                room = get_object_or_404(SpecialRoom, id=int(room_id), school=school)
                day_of_week = int(day_of_week)
                period = int(period)
                grade = int(grade)

                if day_of_week < 0 or day_of_week > 6 or grade < 1 or grade > 6 or period < 1:
                    raise ValueError("invalid-range")

                if RecurringSchedule.objects.filter(room=room, day_of_week=day_of_week, period=period).exists():
                    messages.error(request, "해당 슬롯에는 이미 고정 수업이 있어 학년 고정을 설정할 수 없습니다.")
                else:
                    GradeRecurringLock.objects.update_or_create(
                        room=room,
                        day_of_week=day_of_week,
                        period=period,
                        defaults={'grade': grade},
                    )
                    messages.success(request, "학년 고정 슬롯이 저장되었습니다.")
            except Exception:
                messages.error(request, "학년 고정 설정 값이 올바르지 않습니다.")

        elif action == 'delete':
            item_id = request.POST.get('item_id')
            GradeRecurringLock.objects.filter(id=item_id, room__school=school).delete()
            messages.success(request, "학년 고정 슬롯이 해제되었습니다.")

    config, _ = SchoolConfig.objects.get_or_create(school=school)
    grade_locks = GradeRecurringLock.objects.filter(room__school=school).select_related('room').order_by('day_of_week', 'period', 'room__name')
    return render(request, 'reservations/partials/grade_lock_list.html', {
        'school': school,
        'grade_locks': grade_locks,
        'period_slots': config.get_period_slots(),
    })

@login_required
@require_POST
def update_config(request, school_slug):
    """
    학교 설정 업데이트 (교시 이름 등)
    """
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    config, _ = SchoolConfig.objects.get_or_create(school=school)
    
    # 학교 기본 정보 변경 (이름)
    new_name = request.POST.get('school_name')
    if new_name:
        school.name = new_name
    
    school.save()

    period_labels = request.POST.get('period_labels')
    if period_labels is not None:
        config.period_labels = period_labels

    period_times = request.POST.get('period_times')
    if period_times is not None:
        label_count = len(config.get_period_list())
        raw_times = [p.strip() for p in period_times.split(',')] if period_times else []
        normalized = raw_times[:label_count]
        if len(normalized) < label_count:
            normalized.extend([''] * (label_count - len(normalized)))
        while normalized and normalized[-1] == '':
            normalized.pop()
        config.period_times = ",".join(normalized)

    # max_periods 동기화 (기존 코드와의 호환성)
    config.max_periods = len(config.get_period_list())
    
    # 주간 예약 제한 설정 업데이트
    weekly_mode = request.POST.get('weekly_opening_mode') == 'on'
    config.weekly_opening_mode = weekly_mode

    # Fields are non-null. Keep sane defaults when mode is off or values are omitted.
    if weekly_mode:
        config.weekly_opening_weekday = int(request.POST.get('weekly_opening_weekday', config.weekly_opening_weekday or 4))
        config.weekly_opening_hour = int(request.POST.get('weekly_opening_hour', config.weekly_opening_hour or 9))
    else:
        config.weekly_opening_weekday = config.weekly_opening_weekday if config.weekly_opening_weekday is not None else 4
        config.weekly_opening_hour = config.weekly_opening_hour if config.weekly_opening_hour is not None else 9
    
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
            item_id = request.POST.get('item_id')
            BlackoutDate.objects.filter(id=item_id, school=school).delete()
            messages.success(request, "블랙아웃 기간이 삭제되었습니다.")

    return render(request, 'reservations/partials/blackout_list.html', {
        'blackouts': school.blackoutdate_set.all().order_by('start_date'),
        'school': school,
    })

# Public Reservation Views

def reservation_index(request, school_slug):
    """
    사용자 예약 메인 페이지 (PC: 타임라인, Mobile: 리스트)
    - HTMX Polling 대상
    """
    school = get_object_or_404(School, slug=school_slug)
    config, _ = SchoolConfig.objects.get_or_create(school=school)
    
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
    periods_data = config.get_period_slots()
    
    # 예약 및 고정 수업 조회
    reservations = Reservation.objects.filter(room__school=school, date=target_date).select_related('room')
    recurring = RecurringSchedule.objects.filter(room__school=school, day_of_week=target_date.weekday()).select_related('room')
    grade_locks = GradeRecurringLock.objects.filter(room__school=school, day_of_week=target_date.weekday()).select_related('room')
    
    # 매트릭스 구성
    reservation_map = {(r.room_id, r.period): r for r in reservations}
    recurring_map = {(r.room_id, r.period): r for r in recurring}
    grade_lock_map = {(g.room_id, g.period): g for g in grade_locks}
    
    rooms_data = []
    for room in rooms:
        slots = []
        for p in periods_data:
            res = reservation_map.get((room.id, p['id']))
            rec = recurring_map.get((room.id, p['id']))
            grade_lock = grade_lock_map.get((room.id, p['id']))
            
            # 상태 결정
            state = 'available'
            if is_blackout:
                state = 'blackout'
            elif rec:
                state = 'recurring'
            elif res:
                state = 'reserved'
            elif grade_lock:
                state = 'grade_locked'
            
            slots.append({
                'period': p['id'],
                'label': p['label'],
                'time': p['time'],
                'display_label': p['display_label'],
                'reservation': res,
                'recurring': rec,
                'grade_lock': grade_lock,
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
        'period_labels': [p['label'] for p in periods_data],
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
    override_grade_lock = request.POST.get('override_grade_lock') == '1'
    
    # 유효성 검사
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        period = int(period)
        room = get_object_or_404(SpecialRoom, id=room_id, school=school)
        grade = int(grade)
        class_no = int(class_no)
        
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

        # 2-1. 학년 고정 체크 (반 무관)
        grade_lock = GradeRecurringLock.objects.filter(room=room, day_of_week=target_date.weekday(), period=period).first()
        if grade_lock and grade != grade_lock.grade:
            if not override_grade_lock:
                return HttpResponse(
                    f"이 슬롯은 현재 {grade_lock.grade}학년 고정입니다. 다른 학년으로 예약하려면 고정을 해제하고 진행해 주세요.",
                    status=409,
                )
            grade_lock.delete()
            
        # 3. 중복 예약 체크 (Optimistic Locking 대용: Unique Constraint가 DB에서 막아주지만, 여기서도 체크)
        if Reservation.objects.filter(room=room, date=target_date, period=period).exists():
            return HttpResponse("이미 예약된 시간입니다.", status=409)
            
        # 생성
        reservation = Reservation.objects.create(
            room=room,
            created_by=request.user if request.user.is_authenticated else None,
            date=target_date,
            period=period,
            grade=grade,
            class_no=class_no,
            name=name,
            memo=memo
        )

        # 익명 사용자도 "내가 만든 예약"만 취소할 수 있도록 세션에 소유권 기록
        owned_ids = request.session.get(OWNED_RESERVATIONS_SESSION_KEY, [])
        if reservation.id not in owned_ids:
            owned_ids.append(reservation.id)
            request.session[OWNED_RESERVATIONS_SESSION_KEY] = owned_ids
            request.session.modified = True
        
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
    일반 사용자용 예약 취소
    - 생성 시 세션에 기록된 예약만 삭제 허용
    - URL 유추로 타인 예약 삭제하는 시도를 차단
    """
    school = get_object_or_404(School, slug=school_slug)
    reservation = get_object_or_404(Reservation, id=reservation_id, room__school=school)

    owned_ids = request.session.get(OWNED_RESERVATIONS_SESSION_KEY, [])
    if reservation.id not in owned_ids:
        logger.warning(
            "[Reservation] Unauthorized delete attempt blocked | reservation_id=%s | school=%s",
            reservation_id,
            school.slug,
        )
        return HttpResponseForbidden("삭제 권한이 없습니다.")

    reservation.delete()
    request.session[OWNED_RESERVATIONS_SESSION_KEY] = [rid for rid in owned_ids if rid != reservation.id]
    request.session.modified = True
    messages.success(request, "예약이 취소되었습니다.")

    if request.htmx:
        response = HttpResponse(status=200)
        response['HX-Refresh'] = "true"
        return response

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
