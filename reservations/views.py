from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.utils.text import slugify
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta, date
import uuid
from urllib.parse import quote, unquote

from .models import (
    BlackoutDate,
    GradeRecurringLock,
    RecurringSchedule,
    Reservation,
    ReservationCollaborator,
    School,
    SchoolConfig,
    SpecialRoom,
    build_reservation_owner_key,
    hash_reservation_edit_code,
    validate_reservation_edit_code,
)
from .utils import get_max_booking_date, list_user_accessible_schools, remember_recent_reservation_school, resolve_user_reservation_entry_url
import logging

logger = logging.getLogger(__name__)
OWNED_RESERVATIONS_SESSION_KEY = 'owned_reservation_ids'
WORKFLOW_ACTION_SEED_SESSION_KEY = 'workflow_action_seeds'
RESERVATION_FOLLOWUP_SESSION_KEY = 'reservation_followup_context'
RESERVATION_OWNER_COOKIE_NAME = 'reservation_owner_key'
RESERVATION_OWNER_COOKIE_MAX_AGE = 60 * 60 * 24 * 180


def _apply_workspace_cache_headers(response):
    response["Cache-Control"] = "private, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


def _apply_sensitive_cache_headers(response):
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def _build_school_access(request, school):
    public_access = {
        "has_access": True,
        "can_edit": True,
        "can_manage": False,
        "mode": "public",
        "mode_label": "주소로 예약",
    }

    if not request.user.is_authenticated:
        return public_access

    if school.owner_id == request.user.id:
        return {
            "has_access": True,
            "can_edit": True,
            "can_manage": True,
            "mode": "owner",
            "mode_label": "관리자",
        }

    relation = (
        ReservationCollaborator.objects.filter(school=school, collaborator=request.user)
        .only("can_edit")
        .first()
    )
    if relation:
        return {
            "has_access": True,
            "can_edit": bool(relation.can_edit),
            "can_manage": False,
            "mode": "edit" if relation.can_edit else "view",
            "mode_label": "편집 가능" if relation.can_edit else "읽기 전용",
        }

    return public_access


def _render_share_required(request, school, *, status=403):
    response = render(
        request,
        "reservations/access_required.html",
        {
            "school": school,
            "login_url": f"{reverse('account_login')}?next={request.get_full_path()}",
            "is_authenticated": bool(request.user.is_authenticated),
        },
        status=status,
    )
    return _apply_sensitive_cache_headers(response)


def _get_school_or_share_required(request, school_slug):
    school = get_object_or_404(School, slug=school_slug)
    access = _build_school_access(request, school)
    if not access["has_access"]:
        return school, access, _render_share_required(request, school)
    return school, access, None


def _build_school_collaborator_rows(school):
    relations = (
        ReservationCollaborator.objects.filter(school=school)
        .select_related("collaborator")
        .order_by("collaborator__username")
    )
    return [
        {
            "id": relation.collaborator_id,
            "name": relation.collaborator.get_full_name() or relation.collaborator.username,
            "username": relation.collaborator.username,
            "email": relation.collaborator.email,
            "can_edit": bool(relation.can_edit),
        }
        for relation in relations
    ]


def _get_reservation_owner_key_from_request(request):
    raw_value = request.COOKIES.get(RESERVATION_OWNER_COOKIE_NAME, '')
    if not raw_value:
        return ''
    return unquote(raw_value).strip()[:160]


def _set_reservation_owner_cookie(response, owner_key):
    if owner_key:
        response.set_cookie(
            RESERVATION_OWNER_COOKIE_NAME,
            quote(owner_key, safe=''),
            max_age=RESERVATION_OWNER_COOKIE_MAX_AGE,
            samesite='Lax',
            path='/',
        )
    else:
        response.delete_cookie(RESERVATION_OWNER_COOKIE_NAME, path='/', samesite='Lax')
    return response


def _reservation_owner_key_matches(reservation, owner_key):
    if not reservation or not owner_key:
        return False
    reservation_owner_key = reservation.owner_key or build_reservation_owner_key(
        grade=reservation.grade,
        class_no=reservation.class_no,
        target_label=reservation.target_label,
        name=reservation.name,
    )
    return bool(reservation_owner_key and reservation_owner_key == owner_key)


def _can_edit_reservation(request, reservation):
    """예약 생성자(로그인) 또는 동일 프로필/세션(익명)만 수정/삭제 허용."""
    owned_ids = set(request.session.get(OWNED_RESERVATIONS_SESSION_KEY, []))
    if reservation.id in owned_ids:
        return True
    if _reservation_owner_key_matches(reservation, _get_reservation_owner_key_from_request(request)):
        return True
    if request.user.is_authenticated and reservation.created_by_id == request.user.id:
        return True
    return False


def _normalize_reservation_party(grade_raw, class_no_raw, target_label_raw):
    """
    예약 주체 입력 정규화:
    - 학급 예약: grade/class_no 사용
    - 기타 예약: target_label 사용 (grade/class_no는 0으로 저장)
    """
    target_label = (target_label_raw or '').strip()
    if target_label:
        return 0, 0, target_label[:40]

    grade = int(grade_raw)
    class_no = int(class_no_raw)
    if grade < 1 or class_no < 1:
        raise ValueError("invalid-grade-class")
    return grade, class_no, ''


def _reservation_party_display(reservation):
    if not reservation:
        return ''
    if reservation.target_label:
        return f"{reservation.target_label} {reservation.name}".strip()
    if reservation.grade > 0 and reservation.class_no > 0:
        return f"{reservation.grade}-{reservation.class_no} {reservation.name}"
    if reservation.grade > 0:
        return f"{reservation.grade}학년 {reservation.name}"
    return reservation.name


def _period_display_label(school, period):
    config, _ = SchoolConfig.objects.get_or_create(school=school)
    for slot in config.get_period_slots():
        if slot['id'] == period:
            return slot['display_label']
    return f"{period}교시"


def _grade_lock_override_required_response(grade_lock):
    return HttpResponse(
        (
            f"이 슬롯은 현재 {grade_lock.grade}학년 고정입니다. "
            "다른 학년 예약은 이번 예약에서만 예외로 진행할 수 있으며, 다음 주 고정은 유지됩니다."
        ),
        status=409,
    )


def _build_reservation_modal_payload(reservation, *, period_label, lock_grade=None):
    return {
        'id': reservation.id,
        'roomId': reservation.room_id,
        'roomName': reservation.room.name,
        'period': reservation.period,
        'date': reservation.date.strftime('%Y-%m-%d'),
        'periodLabel': period_label,
        'grade': reservation.grade,
        'classNo': reservation.class_no,
        'targetLabel': reservation.target_label or '',
        'name': reservation.name or '',
        'memo': reservation.memo or '',
        'lockGrade': lock_grade,
        'hasEditCode': reservation.has_edit_code(),
    }


def _build_reservation_origin(request, school, reservation):
    origin_path = f"{reverse('reservations:reservation_index', args=[school.slug])}?date={reservation.date.strftime('%Y-%m-%d')}"
    return {
        'origin_service': 'reservations',
        'origin_url': request.build_absolute_uri(origin_path),
        'origin_label': '예약 화면으로 돌아가기',
    }


def _build_reservation_notice_seed(request, school, reservation):
    date_label = reservation.date.strftime('%m월 %d일')
    period_label = _period_display_label(school, reservation.period)
    party = _reservation_party_display(reservation)
    memo = (reservation.memo or '').strip()
    keywords = f"{date_label} {period_label} {reservation.room.name} 이용 안내, 대상 {party}"
    if memo:
        keywords = f"{keywords}, 메모 {memo}"
    data = {
        'target': 'parent',
        'topic': 'notice',
        'length_style': 'medium',
        'keywords': keywords[:1000],
        'source_label': '예약한 내용을 바탕으로 안내문 초안을 채워두었어요.',
    }
    data.update(_build_reservation_origin(request, school, reservation))
    return data


def _build_reservation_parentcomm_seed(request, school, reservation):
    date_label = reservation.date.strftime('%m월 %d일')
    period_label = _period_display_label(school, reservation.period)
    party = _reservation_party_display(reservation)
    memo = (reservation.memo or '').strip()
    classroom_label = ''
    if reservation.grade > 0 and reservation.class_no > 0:
        classroom_label = f"{reservation.grade}-{reservation.class_no}"
    title = f"{date_label} {reservation.room.name} 이용 안내"
    content = f"{date_label} {period_label}에 {reservation.room.name} 이용이 예정되어 있습니다. {party} 활동 준비를 부탁드립니다."
    if memo:
        content = f"{content} 참고: {memo}"
    data = {
        'classroom_label': classroom_label[:60],
        'title': title[:200],
        'content': content[:2000],
        'target_tab': 'notices',
        'source_label': '예약한 내용을 바탕으로 학부모 안내 초안을 채워두었어요.',
    }
    data.update(_build_reservation_origin(request, school, reservation))
    return data


def _store_action_seed(request, *, action, data):
    token = uuid.uuid4().hex
    seed = {
        'action': action,
        'data': data,
        'created_at': timezone.now().isoformat(),
    }
    seeds = request.session.get(WORKFLOW_ACTION_SEED_SESSION_KEY, {})
    if not isinstance(seeds, dict):
        seeds = {}
    seeds[token] = seed
    if len(seeds) > 20:
        overflow = len(seeds) - 20
        for old_key in list(seeds.keys())[:overflow]:
            seeds.pop(old_key, None)
    request.session[WORKFLOW_ACTION_SEED_SESSION_KEY] = seeds
    request.session.modified = True
    return token


def _build_reservation_followup_context(school, reservation, *, edit_code=""):
    return {
        'school_slug': school.slug,
        'reservation_id': reservation.id,
        'summary': _reservation_party_display(reservation),
        'room_name': reservation.room.name,
        'period_label': _period_display_label(school, reservation.period),
        'date_label': reservation.date.strftime('%Y년 %m월 %d일'),
        'memo': (reservation.memo or '').strip(),
        'edit_code': edit_code,
    }


def _set_reservation_followup_context(request, school, reservation, *, edit_code=""):
    request.session[RESERVATION_FOLLOWUP_SESSION_KEY] = _build_reservation_followup_context(
        school,
        reservation,
        edit_code=edit_code,
    )
    request.session.modified = True


def _pop_reservation_followup_context(request, school_slug):
    context = request.session.get(RESERVATION_FOLLOWUP_SESSION_KEY)
    if not isinstance(context, dict):
        return None
    if context.get('school_slug') != school_slug:
        return None
    request.session.pop(RESERVATION_FOLLOWUP_SESSION_KEY, None)
    request.session.modified = True
    return context

@login_required
def dashboard_landing(request):
    """
    사용자의 학교 목록을 보여주거나 새 학교 생성으로 안내
    """
    school_entries = list_user_accessible_schools(request.user)
    user_schools = [
        entry["school"]
        for entry in school_entries
        if entry["role"] == "owner"
    ]
    shared_schools = [
        {
            "school": entry["school"],
            "can_edit": bool(entry["can_edit"]),
            "owner_name": entry["owner_name"],
        }
        for entry in school_entries
        if entry["role"] in {"edit", "view"}
    ]
    recent_schools = [
        {
            "school": entry["school"],
            "summary": entry["summary"],
        }
        for entry in school_entries
        if entry["role"] == "recent"
    ]
    
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

    response = render(
        request,
        'reservations/landing.html',
        {
            'user_schools': user_schools,
            'shared_schools': shared_schools,
            'recent_schools': recent_schools,
        },
    )
    return _apply_sensitive_cache_headers(response)


@login_required
def smart_entry(request):
    """Open the user's school reservation board directly when possible."""
    return redirect(resolve_user_reservation_entry_url(request.user))

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
        'reservation_entry_url': request.build_absolute_uri(
            reverse('reservations:reservation_index', kwargs={'school_slug': school.slug})
        ),
        'collaborators': _build_school_collaborator_rows(school),
    }
    response = render(request, 'reservations/dashboard.html', context)
    return _apply_sensitive_cache_headers(response)

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
            
    response = render(request, 'reservations/partials/room_list.html', {
        'rooms': school.specialroom_set.all(),
        'school': school
    })
    return _apply_sensitive_cache_headers(response)


@login_required
@require_POST
def collaborator_add(request, school_slug):
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    lookup = (request.POST.get("collaborator_query") or "").strip()
    if not lookup:
        messages.error(request, "공유할 선생님의 가입 이메일을 입력해 주세요.")
        return redirect('reservations:admin_dashboard', school_slug=school.slug)

    collaborator = (
        User.objects.filter(email__iexact=lookup)
        .only("id", "username", "email", "first_name", "last_name")
        .first()
    )
    if not collaborator:
        messages.error(request, "해당 이메일의 교사 계정을 찾지 못했습니다.")
        return redirect('reservations:admin_dashboard', school_slug=school.slug)
    if collaborator.id == request.user.id:
        messages.error(request, "본인은 다시 공유 대상으로 추가할 수 없습니다.")
        return redirect('reservations:admin_dashboard', school_slug=school.slug)

    can_edit = str(request.POST.get("can_edit") or "").strip().lower() in {"1", "true", "on", "yes"}
    relation, created = ReservationCollaborator.objects.update_or_create(
        school=school,
        collaborator=collaborator,
        defaults={"can_edit": can_edit},
    )
    logger.info(
        "[Reservations] collaborator share updated | school=%s | owner_id=%s | collaborator_id=%s | can_edit=%s | created=%s",
        school.slug,
        request.user.id,
        collaborator.id,
        can_edit,
        created,
    )
    if created:
        messages.success(request, f"{collaborator.get_full_name() or collaborator.username} 선생님을 공유 대상으로 추가했습니다.")
    else:
        mode_text = "편집 가능" if relation.can_edit else "읽기 전용"
        messages.info(request, f"{collaborator.get_full_name() or collaborator.username} 선생님의 권한을 {mode_text}으로 업데이트했습니다.")
    return redirect('reservations:admin_dashboard', school_slug=school.slug)


@login_required
@require_POST
def collaborator_remove(request, school_slug, collaborator_id):
    school = get_object_or_404(School, slug=school_slug, owner=request.user)
    relation = (
        ReservationCollaborator.objects.filter(school=school, collaborator_id=collaborator_id)
        .select_related("collaborator")
        .first()
    )
    if not relation:
        messages.error(request, "공유된 선생님 정보를 찾지 못했습니다.")
        return redirect('reservations:admin_dashboard', school_slug=school.slug)

    collaborator_name = relation.collaborator.get_full_name() or relation.collaborator.username
    relation.delete()
    logger.info(
        "[Reservations] collaborator share removed | school=%s | owner_id=%s | collaborator_id=%s",
        school.slug,
        request.user.id,
        collaborator_id,
    )
    messages.info(request, f"{collaborator_name} 선생님과의 공유를 해제했습니다.")
    return redirect('reservations:admin_dashboard', school_slug=school.slug)

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
    
    response = render(request, 'reservations/partials/recurring_matrix.html', {
        'school': school,
        'rooms_data': rooms_data,
        'days': days,
        'day_names': ['월', '화', '수', '목', '금']
    })
    return _apply_sensitive_cache_headers(response)


def _build_grade_lock_matrix_context(school):
    config, _ = SchoolConfig.objects.get_or_create(school=school)
    periods = config.get_period_slots()
    day_names = ['월', '화', '수', '목', '금']
    days = range(len(day_names))
    rooms = school.specialroom_set.all()
    grade_choices = range(1, 7)

    rooms_data = []
    total_locks = 0
    for room in rooms:
        recurring_map = {
            (schedule.day_of_week, schedule.period): schedule
            for schedule in RecurringSchedule.objects.filter(room=room, day_of_week__in=days)
        }
        lock_map = {
            (lock.day_of_week, lock.period): lock
            for lock in GradeRecurringLock.objects.filter(room=room, day_of_week__in=days)
        }
        total_locks += len(lock_map)

        rows = []
        for period_info in periods:
            slots = []
            for day in days:
                slots.append({
                    'day_index': day,
                    'recurring': recurring_map.get((day, period_info['id'])),
                    'lock': lock_map.get((day, period_info['id'])),
                })
            rows.append({
                'period': period_info,
                'slots': slots,
            })

        rooms_data.append({
            'room': room,
            'rows': rows,
        })

    return {
        'school': school,
        'rooms_data': rooms_data,
        'day_names': day_names,
        'grade_choices': grade_choices,
        'lock_total': total_locks,
    }


def _render_grade_lock_matrix(request, school, *, status=200):
    response = render(
        request,
        'reservations/partials/grade_lock_matrix.html',
        _build_grade_lock_matrix_context(school),
        status=status,
    )
    return _apply_sensitive_cache_headers(response)


@login_required
def grade_lock_settings(request, school_slug):
    school = get_object_or_404(School, slug=school_slug, owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        room_id = request.POST.get('room_id')
        day_of_week = request.POST.get('day_of_week')
        period = request.POST.get('period')

        try:
            room = get_object_or_404(SpecialRoom, id=int(room_id), school=school)
            day_of_week = int(day_of_week)
            period = int(period)

            if day_of_week < 0 or day_of_week > 4 or period < 1:
                raise ValueError("invalid-range")

            if action in {'set', 'add'}:
                grade = int(request.POST.get('grade'))
                if grade < 1 or grade > 6:
                    raise ValueError("invalid-grade")

                if RecurringSchedule.objects.filter(room=room, day_of_week=day_of_week, period=period).exists():
                    return HttpResponse(
                        "해당 칸에는 이미 고정 수업이 있어 학년 고정을 설정할 수 없습니다.",
                        status=409,
                    )

                GradeRecurringLock.objects.update_or_create(
                    room=room,
                    day_of_week=day_of_week,
                    period=period,
                    defaults={'grade': grade},
                )
            elif action == 'delete':
                GradeRecurringLock.objects.filter(
                    room=room,
                    day_of_week=day_of_week,
                    period=period,
                ).delete()
            else:
                return HttpResponse("학년 고정 요청 방식이 올바르지 않습니다.", status=400)
        except (TypeError, ValueError):
            return HttpResponse("학년 고정 설정 값이 올바르지 않습니다.", status=400)

    return _render_grade_lock_matrix(request, school)

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
    return _apply_sensitive_cache_headers(response)

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

    response = render(request, 'reservations/partials/blackout_list.html', {
        'blackouts': school.blackoutdate_set.all().order_by('start_date'),
        'school': school,
    })
    return _apply_sensitive_cache_headers(response)

# Public Reservation Views

def reservation_index(request, school_slug):
    """
    사용자 예약 메인 페이지 (PC: 타임라인, Mobile: 리스트)
    - HTMX Polling 대상
    """
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    if request.user.is_authenticated and not request.headers.get("HX-Request"):
        remember_recent_reservation_school(request.user, school)
    config, _ = SchoolConfig.objects.get_or_create(school=school)
    
    initial_open_reservation_id = request.GET.get('reservation')

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
    if not access["can_manage"]:
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
    initial_open_reservation_payload = None
    for room in rooms:
        slots = []
        for p in periods_data:
            res = reservation_map.get((room.id, p['id']))
            rec = recurring_map.get((room.id, p['id']))
            grade_lock = grade_lock_map.get((room.id, p['id']))
            can_edit = bool(res and _can_edit_reservation(request, res))
            
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
                'reservation_party': _reservation_party_display(res),
                'recurring': rec,
                'grade_lock': grade_lock,
                'state': state,
                'can_edit': can_edit,
                'can_admin_override': bool(access["can_manage"]),
            })
            if (
                initial_open_reservation_payload is None
                and res
                and initial_open_reservation_id
                and str(res.id) == str(initial_open_reservation_id)
                and can_edit
            ):
                lock_grade = grade_lock.grade if grade_lock else None
                initial_open_reservation_payload = _build_reservation_modal_payload(
                    res,
                    period_label=p['display_label'],
                    lock_grade=lock_grade,
                )
            
        rooms_data.append({
            'room': room,
            'slots': slots
        })

    reservation_followup = None
    if not request.headers.get('HX-Request'):
        reservation_followup = _pop_reservation_followup_context(request, school.slug)

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
        'reservation_followup': reservation_followup,
        'reservation_access': access,
        'reservation_can_edit': bool(access["can_edit"]),
        'initial_open_reservation_payload': initial_open_reservation_payload,
    }
    
    # HTMX 요청이면 부분 렌더링 (Polling 등)
    if request.headers.get('HX-Request'):
        response = render(request, 'reservations/partials/reservation_grid.html', context)
        return _apply_workspace_cache_headers(response)

    response = render(request, 'reservations/index.html', context)
    return _apply_workspace_cache_headers(response)


def room_overview(request, school_slug):
    """
    특별실별 예약 현황 요약/목록 (교사/일반 예약자 공용 조회)
    """
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    if request.user.is_authenticated and not request.headers.get("HX-Request"):
        remember_recent_reservation_school(request.user, school)
    config, _ = SchoolConfig.objects.get_or_create(school=school)

    from_str = request.GET.get('from')
    days_str = request.GET.get('days', '7')

    try:
        start_date = datetime.strptime(from_str, '%Y-%m-%d').date() if from_str else timezone.localdate()
    except ValueError:
        start_date = timezone.localdate()

    try:
        days = int(days_str)
    except (TypeError, ValueError):
        days = 7
    days = max(1, min(days, 31))
    end_date = start_date + timedelta(days=days - 1)

    period_slots = config.get_period_slots()
    period_map = {slot['id']: slot for slot in period_slots}
    weekday_names = ['월', '화', '수', '목', '금', '토', '일']

    rooms = list(school.specialroom_set.all().order_by('name'))
    reservations = Reservation.objects.filter(
        room__school=school,
        date__range=(start_date, end_date),
    ).select_related('room').order_by('room__name', 'date', 'period', 'created_at')

    grouped = {
        room.id: {
            'room': room,
            'total_count': 0,
            'active_dates': set(),
            'items': [],
        }
        for room in rooms
    }

    for reservation in reservations:
        slot = period_map.get(reservation.period)
        period_label = slot['label'] if slot else f"{reservation.period}교시"
        period_time = slot['time'] if slot else ''
        bucket = grouped[reservation.room_id]
        bucket['total_count'] += 1
        bucket['active_dates'].add(reservation.date)
        bucket['items'].append({
            'reservation': reservation,
            'party_display': _reservation_party_display(reservation),
            'weekday_name': weekday_names[reservation.date.weekday()],
            'period_label': period_label,
            'period_time': period_time,
        })

    rooms_data = []
    for room in rooms:
        bucket = grouped[room.id]
        rooms_data.append({
            'room': room,
            'total_count': bucket['total_count'],
            'active_day_count': len(bucket['active_dates']),
            'items': bucket['items'],
        })

    context = {
        'school': school,
        'rooms_data': rooms_data,
        'start_date': start_date,
        'end_date': end_date,
        'days': days,
        'total_count': sum(room_data['total_count'] for room_data in rooms_data),
        'reservation_access': access,
    }
    response = render(request, 'reservations/room_overview.html', context)
    return _apply_workspace_cache_headers(response)


@login_required
@require_POST
def start_notice_followup(request, school_slug, reservation_id):
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    reservation = get_object_or_404(Reservation.objects.select_related('room'), id=reservation_id, room__school=school)
    if not access["can_edit"] or not _can_edit_reservation(request, reservation):
        return HttpResponseForbidden('후속 작업을 열 권한이 없습니다.')
    seed_token = _store_action_seed(
        request,
        action='notice',
        data=_build_reservation_notice_seed(request, school, reservation),
    )
    return redirect(f"{reverse('noticegen:main')}?sb_seed={seed_token}")


@login_required
@require_POST
def start_parentcomm_followup(request, school_slug, reservation_id):
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    reservation = get_object_or_404(Reservation.objects.select_related('room'), id=reservation_id, room__school=school)
    if not access["can_edit"] or not _can_edit_reservation(request, reservation):
        return HttpResponseForbidden('후속 작업을 열 권한이 없습니다.')
    seed_token = _store_action_seed(
        request,
        action='parentcomm_notice',
        data=_build_reservation_parentcomm_seed(request, school, reservation),
    )
    return redirect(f"{reverse('parentcomm:main')}?sb_seed={seed_token}")

@require_POST
def create_reservation(request, school_slug):
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    if not access["can_edit"]:
        return HttpResponseForbidden("이 예약판은 읽기 전용으로 공유되어 예약을 추가할 수 없습니다.")
    
    # 데이터 수신
    room_id = request.POST.get('room_id')
    date_str = request.POST.get('date')
    period = request.POST.get('period')
    grade = request.POST.get('grade')
    class_no = request.POST.get('class_no')
    target_label = request.POST.get('target_label')
    name = (request.POST.get('name') or '').strip()
    memo = (request.POST.get('memo') or '').strip()
    edit_code = request.POST.get('edit_code')
    override_grade_lock = request.POST.get('override_grade_lock') == '1'
    
    # 유효성 검사
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        period = int(period)
        room = get_object_or_404(SpecialRoom, id=room_id, school=school)
        grade, class_no, target_label = _normalize_reservation_party(grade, class_no, target_label)
        edit_code = validate_reservation_edit_code(edit_code)
        owner_key = build_reservation_owner_key(
            grade=grade,
            class_no=class_no,
            target_label=target_label,
            name=name,
        )

        if not name:
            return HttpResponse("이름을 입력해 주세요.", status=400)
        
        # [Weekly Limit Check] 백엔드 검증
        if not access["can_manage"]: # 관리자는 제한 무시
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
                return _grade_lock_override_required_response(grade_lock)
            
        # 3. 중복 예약 체크 (Optimistic Locking 대용: Unique Constraint가 DB에서 막아주지만, 여기서도 체크)
        if Reservation.objects.filter(room=room, date=target_date, period=period).exists():
            return HttpResponse("이미 예약된 시간입니다.", status=409)
            
        # 생성
        reservation = Reservation.objects.create(
            room=room,
            created_by=request.user if request.user.is_authenticated else None,
            owner_key=owner_key,
            edit_code_hash=hash_reservation_edit_code(edit_code),
            date=target_date,
            period=period,
            grade=grade,
            class_no=class_no,
            target_label=target_label,
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
        _set_reservation_followup_context(request, school, reservation, edit_code=edit_code)
        
        # HTMX Redirect to refresh grid
        response = HttpResponse()
        response['HX-Refresh'] = "true" # 전체 리프레시가 가장 깔끔함 (모달 닫기 등)
        _set_reservation_owner_cookie(response, owner_key)
        return _apply_workspace_cache_headers(response)
        
    except ValueError as exc:
        if str(exc) == "invalid-edit-code":
            return HttpResponse("수정 코드 4자리를 입력해 주세요.", status=400)
        return HttpResponse("학년/반 또는 기타 대상을 올바르게 입력해 주세요.", status=400)
    except Exception as e:
        logger.error(f"[Reservation Error] {e}")
        return HttpResponse("예약 처리 중 오류가 발생했습니다.", status=500)


@require_POST
def update_reservation(request, school_slug, reservation_id):
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    reservation = get_object_or_404(Reservation, id=reservation_id, room__school=school)

    if not access["can_edit"] or not _can_edit_reservation(request, reservation):
        logger.warning(
            "[Reservation] Unauthorized update attempt blocked | reservation_id=%s | school=%s",
            reservation_id,
            school.slug,
        )
        return HttpResponseForbidden("수정 권한이 없습니다.")

    room_id = request.POST.get('room_id')
    date_str = request.POST.get('date')
    period = request.POST.get('period')
    grade = request.POST.get('grade')
    class_no = request.POST.get('class_no')
    target_label = request.POST.get('target_label')
    name = (request.POST.get('name') or '').strip()
    memo = (request.POST.get('memo') or '').strip()
    edit_code = (request.POST.get('edit_code') or '').strip()
    override_grade_lock = request.POST.get('override_grade_lock') == '1'

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        period = int(period)
        room = get_object_or_404(SpecialRoom, id=room_id, school=school)
        grade, class_no, target_label = _normalize_reservation_party(grade, class_no, target_label)
        owner_key = build_reservation_owner_key(
            grade=grade,
            class_no=class_no,
            target_label=target_label,
            name=name,
        )

        if not name:
            return HttpResponse("이름을 입력해 주세요.", status=400)

        if not access["can_manage"]:
            max_date = get_max_booking_date(school)
            if max_date and target_date > max_date:
                return HttpResponse(
                    f"<script>alert('예약이 아직 열리지 않았습니다. {max_date.strftime('%Y-%m-%d')}까지만 예약 가능합니다.');</script>",
                    status=200
                )

        if BlackoutDate.objects.filter(school=school, start_date__lte=target_date, end_date__gte=target_date).exists():
            return HttpResponse("예약이 불가능한 날짜입니다.", status=400)

        if RecurringSchedule.objects.filter(room=room, day_of_week=target_date.weekday(), period=period).exists():
            return HttpResponse("고정 수업이 있는 시간입니다.", status=400)

        grade_lock = GradeRecurringLock.objects.filter(room=room, day_of_week=target_date.weekday(), period=period).first()
        if grade_lock and grade != grade_lock.grade:
            if not override_grade_lock:
                return _grade_lock_override_required_response(grade_lock)

        if Reservation.objects.filter(room=room, date=target_date, period=period).exclude(id=reservation.id).exists():
            return HttpResponse("이미 예약된 시간입니다.", status=409)

        edit_code_changed = ""
        if edit_code:
            edit_code = validate_reservation_edit_code(edit_code)
            reservation.edit_code_hash = hash_reservation_edit_code(edit_code)
            edit_code_changed = edit_code
        elif not reservation.has_edit_code():
            return HttpResponse("예전 예약이라 수정 코드가 없습니다. 이번에 4자리를 입력해 저장해 주세요.", status=400)

        reservation.room = room
        reservation.date = target_date
        reservation.period = period
        reservation.grade = grade
        reservation.class_no = class_no
        reservation.target_label = target_label
        reservation.name = name
        reservation.memo = memo
        reservation.owner_key = owner_key
        update_fields = ['room', 'date', 'period', 'grade', 'class_no', 'target_label', 'name', 'memo', 'owner_key']
        if edit_code or not reservation.has_edit_code():
            update_fields.append('edit_code_hash')
        reservation.save(update_fields=update_fields)

        messages.success(request, f"{period}교시 예약이 수정되었습니다.")
        _set_reservation_followup_context(request, school, reservation, edit_code=edit_code_changed)

        response = HttpResponse()
        response['HX-Refresh'] = "true"
        _set_reservation_owner_cookie(response, owner_key)
        return _apply_workspace_cache_headers(response)

    except ValueError as exc:
        if str(exc) == "invalid-edit-code":
            return HttpResponse("수정 코드는 숫자 4자리로 입력해 주세요.", status=400)
        return HttpResponse("학년/반 또는 기타 대상을 올바르게 입력해 주세요.", status=400)
    except Exception as e:
        logger.error(f"[Reservation Update Error] {e}")
        return HttpResponse("예약 수정 중 오류가 발생했습니다.", status=500)


@require_POST
def claim_reservation_access(request, school_slug, reservation_id):
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    if not access["can_edit"]:
        return HttpResponseForbidden("이 예약판은 읽기 전용입니다.")

    reservation = get_object_or_404(Reservation, id=reservation_id, room__school=school)

    if _can_edit_reservation(request, reservation):
        redirect_url = (
            f"{reverse('reservations:reservation_index', args=[school.slug])}"
            f"?date={reservation.date.strftime('%Y-%m-%d')}&reservation={reservation.id}"
        )
        if request.htmx:
            response = HttpResponse()
            response['HX-Redirect'] = redirect_url
            return _apply_workspace_cache_headers(response)
        return redirect(redirect_url)

    if not reservation.has_edit_code():
        return HttpResponse(
            "이 예약은 아직 수정 코드가 없습니다. 예약했던 기기에서 한 번 열어 코드 4자리를 저장해 주세요.",
            status=400,
        )

    try:
        edit_code = validate_reservation_edit_code(request.POST.get('edit_code'))
    except ValueError:
        return HttpResponse("수정 코드는 숫자 4자리로 입력해 주세요.", status=400)

    if not reservation.check_edit_code(edit_code):
        logger.warning(
            "[Reservation] Invalid edit code | reservation_id=%s | school=%s",
            reservation_id,
            school.slug,
        )
        return HttpResponse("수정 코드가 맞지 않습니다.", status=403)

    owned_ids = request.session.get(OWNED_RESERVATIONS_SESSION_KEY, [])
    if reservation.id not in owned_ids:
        owned_ids.append(reservation.id)
        request.session[OWNED_RESERVATIONS_SESSION_KEY] = owned_ids
        request.session.modified = True

    redirect_url = (
        f"{reverse('reservations:reservation_index', args=[school.slug])}"
        f"?date={reservation.date.strftime('%Y-%m-%d')}&reservation={reservation.id}"
    )
    messages.success(request, "내 예약을 열었습니다.")
    if request.htmx:
        response = HttpResponse()
        response['HX-Redirect'] = redirect_url
    else:
        response = redirect(redirect_url)
    _set_reservation_owner_cookie(response, reservation.owner_key)
    return _apply_workspace_cache_headers(response) if request.htmx else response

@require_POST
def delete_reservation(request, school_slug, reservation_id):
    """
    일반 사용자용 예약 취소
    - 생성 시 세션에 기록된 예약만 삭제 허용
    - URL 유추로 타인 예약 삭제하는 시도를 차단
    """
    school, access, access_response = _get_school_or_share_required(request, school_slug)
    if access_response is not None:
        return access_response
    reservation = get_object_or_404(Reservation, id=reservation_id, room__school=school)

    owned_ids = request.session.get(OWNED_RESERVATIONS_SESSION_KEY, [])
    if not access["can_edit"] or not _can_edit_reservation(request, reservation):
        logger.warning(
            "[Reservation] Unauthorized delete attempt blocked | reservation_id=%s | school=%s",
            reservation_id,
            school.slug,
        )
        return HttpResponseForbidden("삭제 권한이 없습니다.")

    if request.session.get(RESERVATION_FOLLOWUP_SESSION_KEY, {}).get('reservation_id') == reservation.id:
        request.session.pop(RESERVATION_FOLLOWUP_SESSION_KEY, None)
    reservation.delete()
    request.session[OWNED_RESERVATIONS_SESSION_KEY] = [rid for rid in owned_ids if rid != reservation.id]
    request.session.modified = True
    messages.success(request, "예약이 취소되었습니다.")

    if request.htmx:
        response = HttpResponse(status=204)
        response['HX-Trigger'] = "refresh-reservations"
        return _apply_workspace_cache_headers(response)

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
        response = HttpResponse(status=204)
        response['HX-Trigger'] = "refresh-reservations"
        return _apply_sensitive_cache_headers(response)
        
    return redirect('reservations:reservation_index', school_slug=school.slug)
