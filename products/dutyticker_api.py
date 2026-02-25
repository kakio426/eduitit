from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
import random
from .models import DTStudent, DTRole, DTRoleAssignment, DTSchedule, DTTimeSlot
from .dutyticker_scope import (
    apply_classroom_scope,
    classroom_scope_create_kwargs,
    classroom_scope_filter,
    get_active_classroom_for_request,
    get_or_create_settings_for_scope,
)
from .dutyticker_slots import PERIOD_NUMBERS, SLOT_BY_CODE, SLOT_LAYOUT, WEEKDAY_LABELS


def _build_today_fallback_schedule_from_classcalendar(user, classroom=None):
    """
    Build today's timetable payload from classcalendar events when DTSchedule is empty.
    Returned day follows JavaScript getDay() convention (0=Sun ... 6=Sat).
    """
    try:
        from classcalendar.models import CalendarEvent
    except Exception:
        return None, []

    today = timezone.localdate()
    js_day = (today.weekday() + 1) % 7

    events = (
        CalendarEvent.objects.filter(
            **({"classroom": classroom} if classroom is not None else {"classroom__isnull": True}),
            author=user,
            start_time__date__lte=today,
            end_time__date__gte=today,
        )
        .order_by("start_time", "id")
    )

    fallback_rows = []
    for index, event in enumerate(events, start=1):
        start_time = timezone.localtime(event.start_time).strftime("%H:%M")
        end_time = timezone.localtime(event.end_time).strftime("%H:%M")
        fallback_rows.append(
            {
                "id": f"cc-{event.id}",
                "name": event.title,
                "startTime": start_time,
                "endTime": end_time,
                "period": index,
                "slot_code": f"cc-{index}",
                "slot_type": "period",
                "slot_label": f"{index}교시",
            }
        )

    return js_day, fallback_rows


def _ensure_time_slots_for_scope(user, classroom):
    existing_by_code = {
        slot.slot_code: slot
        for slot in apply_classroom_scope(DTTimeSlot.objects.filter(user=user), classroom)
    }

    for spec in SLOT_LAYOUT:
        if spec["code"] in existing_by_code:
            continue
        DTTimeSlot.objects.create(
            user=user,
            **classroom_scope_create_kwargs(classroom),
            slot_code=spec["code"],
            slot_kind=spec["kind"],
            slot_order=spec["order"],
            slot_label=spec["label"],
            period_number=spec["period"],
            start_time=spec["start"],
            end_time=spec["end"],
        )

    return list(apply_classroom_scope(DTTimeSlot.objects.filter(user=user), classroom).order_by("slot_order", "id"))


def _build_weekly_schedule_payload(user, classroom):
    time_slots = _ensure_time_slots_for_scope(user, classroom)
    slot_by_code = {slot.slot_code: slot for slot in time_slots}

    schedules = apply_classroom_scope(
        DTSchedule.objects.filter(user=user, day__in=[day for day, _ in WEEKDAY_LABELS], period__in=PERIOD_NUMBERS),
        classroom,
    ).order_by("day", "period")

    subject_by_day_period = {(row.day, row.period): row for row in schedules}
    weekly_schedule = {}

    for day, _ in WEEKDAY_LABELS:
        day_rows = []
        for spec in SLOT_LAYOUT:
            slot = slot_by_code.get(spec["code"])
            start_time = slot.start_time if slot else spec["start"]
            end_time = slot.end_time if slot else spec["end"]
            is_period = spec["kind"] == "period"
            period_number = spec["period"]
            schedule_row = subject_by_day_period.get((day, period_number)) if is_period else None

            if is_period:
                title = schedule_row.subject if schedule_row else f"{period_number}교시"
            else:
                title = spec["label"]

            day_rows.append(
                {
                    "id": f"{day}-{spec['code']}",
                    "name": title,
                    "startTime": start_time.strftime("%H:%M"),
                    "endTime": end_time.strftime("%H:%M"),
                    "period": period_number,
                    "slot_code": spec["code"],
                    "slot_type": spec["kind"],
                    "slot_label": spec["label"],
                }
            )
        weekly_schedule[str(day)] = day_rows

    return weekly_schedule

def get_guest_default_data():
    """Returns the structure for guest session data."""
    student_names = ["김철수", "이영희", "박민수", "정지원", "최하늘", "강다니엘", "조유리", "한지민", "서태웅", "윤대협"]
    students = []
    for i, name in enumerate(student_names, 1):
        students.append({'id': i, 'name': name, 'number': i, 'is_mission_completed': False})
    
    roles_data = [
        {"id": 1, "name": "칠판 지우기", "time_slot": "쉬는시간", "description": "수업 후 칠판을 깨끗하게 정리합니다.", "icon": "📋", "color": "bg-white"},
        {"id": 2, "name": "우유 나르기", "time_slot": "아침시간", "description": "급식실에서 우유를 가져와 배부합니다.", "icon": "📋", "color": "bg-white"},
        {"id": 3, "name": "컴퓨터 끄기", "time_slot": "종례시간", "description": "교실 멀티미디어 기기 전원을 확인합니다.", "icon": "📋", "color": "bg-white"},
        {"id": 4, "name": "우리반 정리왕", "time_slot": "점심시간", "description": "식사 후 교실 바닥의 쓰레기를 줍습니다.", "icon": "📋", "color": "bg-white"},
        {"id": 5, "name": "식물 도우미", "time_slot": "아침시간", "description": "교실 창가 화분에 물을 줍니다.", "icon": "📋", "color": "bg-white"}
    ]
    
    assignments = []
    for i in range(min(5, len(students))):
        assignments.append({
            'id': i + 1,
            'role_id': roles_data[i]['id'],
            'student_id': students[i]['id'],
            'student_name': students[i]['name'],
            'is_completed': False
        })
        
    subjects = ["국어", "수학", "사회", "과학", "영어", "체육", "미술", "음악"]
    weekly_schedule = {}
    for day, _ in WEEKDAY_LABELS:
        rows = []
        for spec in SLOT_LAYOUT:
            is_period = spec["kind"] == "period"
            period = spec["period"]
            name = subjects[(day + period) % len(subjects)] if is_period else spec["label"]
            rows.append(
                {
                    "id": f"{day}-{spec['code']}",
                    "name": name,
                    "startTime": spec["start"].strftime("%H:%M"),
                    "endTime": spec["end"].strftime("%H:%M"),
                    "period": period,
                    "slot_code": spec["code"],
                    "slot_type": spec["kind"],
                    "slot_label": spec["label"],
                }
            )
        weekly_schedule[str(day)] = rows
            
    return {
        'students': students,
        'roles': roles_data,
        'assignments': assignments,
        'schedule': weekly_schedule,
        'settings': {
            'auto_rotation': False,
            'rotation_frequency': 'daily',
            'rotation_mode': 'manual_sequential',
            'last_broadcast': "환영합니다! 게스트 모드로 체험 중입니다.",
            'mission_title': "오늘도 행복한 우리 교실",
            'mission_desc': "선생님 말씀에 집중해 주세요.",
            'spotlight_student_id': None,
        }
    }

def create_mockup_data(user, classroom=None):
    """Generates initial sample data for new users to demonstrate DutyTicker."""
    time_slots = _ensure_time_slots_for_scope(user, classroom)
    period_slots = {slot.period_number: slot for slot in time_slots if slot.slot_kind == "period" and slot.period_number}

    student_names = ["김철수", "이영희", "박민수", "정지원", "최하늘", "강다니엘", "조유리", "한지민", "서태웅", "윤대협"]
    scope_kwargs = classroom_scope_create_kwargs(classroom)
    students = []
    for i, name in enumerate(student_names, 1):
        students.append(DTStudent.objects.create(user=user, name=name, number=i, **scope_kwargs))
    
    roles_data = [
        {"name": "칠판 지우기", "time_slot": "쉬는시간", "description": "수업 후 칠판을 깨끗하게 정리합니다."},
        {"name": "우유 나르기", "time_slot": "아침시간", "description": "급식실에서 우유를 가져와 배부합니다."},
        {"name": "컴퓨터 끄기", "time_slot": "종례시간", "description": "교실 멀티미디어 기기 전원을 확인합니다."},
        {"name": "우리반 정리왕", "time_slot": "점심시간", "description": "식사 후 교실 바닥의 쓰레기를 줍습니다."},
        {"name": "식물 도우미", "time_slot": "아침시간", "description": "교실 창가 화분에 물을 줍니다."}
    ]
    roles = []
    for r in roles_data:
        role = DTRole.objects.create(user=user, **scope_kwargs, **r)
        roles.append(role)
    
    for i in range(min(5, len(students))):
        DTRoleAssignment.objects.create(user=user, role=roles[i], student=students[i], **scope_kwargs)
        
    subjects = ["국어", "수학", "사회", "과학", "영어", "체육", "미술", "음악"]
    for day, _ in WEEKDAY_LABELS:
        for period in PERIOD_NUMBERS:
            slot = period_slots.get(period)
            default_spec = SLOT_BY_CODE.get(f"p{period}")
            DTSchedule.objects.create(
                user=user,
                **scope_kwargs,
                day=day,
                period=period,
                subject=subjects[(day + period) % len(subjects)],
                start_time=slot.start_time if slot else default_spec["start"],
                end_time=slot.end_time if slot else default_spec["end"],
            )
    return True


def _safe_json_body(request):
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_rotation_behavior(raw_behavior):
    if str(raw_behavior).strip().lower() == "random":
        return "random"
    return "sequential"


def _behavior_from_rotation_mode(rotation_mode):
    mode = str(rotation_mode or "manual_sequential")
    return "random" if mode.endswith("_random") else "sequential"


def _sync_rotation_settings_flags(settings):
    desired_auto = str(settings.rotation_mode or "").startswith("auto_")
    updated_fields = []

    if settings.auto_rotation != desired_auto:
        settings.auto_rotation = desired_auto
        updated_fields.append("auto_rotation")

    if desired_auto and settings.rotation_frequency != "daily":
        settings.rotation_frequency = "daily"
        updated_fields.append("rotation_frequency")

    if updated_fields:
        settings.save(update_fields=updated_fields)


def _shuffle_without_same_position(values):
    shuffled = values[:]
    if len(shuffled) < 2:
        return shuffled
    for _ in range(8):
        random.shuffle(shuffled)
        if shuffled != values:
            break
    return shuffled


def _rotate_guest_assignments(guest_data, behavior="sequential"):
    students = guest_data.get("students") if isinstance(guest_data, dict) else []
    assignments = guest_data.get("assignments") if isinstance(guest_data, dict) else []
    if not students or not assignments:
        return False

    student_ids = []
    student_name_map = {}
    for student in students:
        student_id = student.get("id")
        if student_id is None:
            continue
        student_ids.append(student_id)
        student_name_map[student_id] = student.get("name", "Unassigned")

    if not student_ids:
        return False

    if behavior == "random":
        target_assignments = [a for a in assignments if a.get("student_id") in student_name_map]
        source_ids = [a.get("student_id") for a in target_assignments]
        if len(source_ids) < 2:
            return False

        shuffled_ids = _shuffle_without_same_position(source_ids)
        for idx, assignment in enumerate(target_assignments):
            next_student_id = shuffled_ids[idx]
            assignment["student_id"] = next_student_id
            assignment["student_name"] = student_name_map.get(next_student_id, "Unassigned")
            assignment["is_completed"] = False
        return True

    index_map = {student_id: idx for idx, student_id in enumerate(student_ids)}
    total_students = len(student_ids)
    rotated = False
    for assignment in assignments:
        student_id = assignment.get("student_id")
        if student_id not in index_map:
            continue
        next_idx = (index_map[student_id] + 1) % total_students
        next_student_id = student_ids[next_idx]
        assignment["student_id"] = next_student_id
        assignment["student_name"] = student_name_map.get(next_student_id, "Unassigned")
        assignment["is_completed"] = False
        rotated = True

    return rotated


def _rotate_user_assignments(user, behavior="sequential", classroom=None):
    students = list(
        apply_classroom_scope(
            DTStudent.objects.filter(user=user, is_active=True),
            classroom,
        ).order_by("number", "id")
    )
    assignments = list(
        apply_classroom_scope(DTRoleAssignment.objects.filter(user=user), classroom)
        .select_related("student", "role")
        .order_by("role_id", "id")
    )

    if not students or not assignments:
        return False

    student_ids = [student.id for student in students]
    student_map = {student.id: student for student in students}

    updated_assignments = []
    if behavior == "random":
        target_assignments = [assignment for assignment in assignments if assignment.student_id in student_map]
        source_ids = [assignment.student_id for assignment in target_assignments]
        if len(source_ids) < 2:
            return False

        shuffled_ids = _shuffle_without_same_position(source_ids)
        for idx, assignment in enumerate(target_assignments):
            assignment.student = student_map[shuffled_ids[idx]]
            assignment.is_completed = False
            updated_assignments.append(assignment)
    else:
        index_map = {student_id: idx for idx, student_id in enumerate(student_ids)}
        total_students = len(student_ids)
        for assignment in assignments:
            if assignment.student_id not in index_map:
                continue
            next_idx = (index_map[assignment.student_id] + 1) % total_students
            assignment.student = student_map[student_ids[next_idx]]
            assignment.is_completed = False
            updated_assignments.append(assignment)

    if updated_assignments:
        DTRoleAssignment.objects.bulk_update(updated_assignments, ["student", "is_completed"])
        return True
    return False


def _apply_auto_rotation_if_due(user, settings, classroom=None):
    mode = str(settings.rotation_mode or "")
    if not mode.startswith("auto_"):
        return

    today = timezone.localdate()
    if settings.last_rotation_date == today:
        return

    behavior = _behavior_from_rotation_mode(mode)
    _rotate_user_assignments(user, behavior=behavior, classroom=classroom)

    settings.last_rotation_date = today
    settings.auto_rotation = True
    settings.rotation_frequency = "daily"
    settings.save(update_fields=["last_rotation_date", "auto_rotation", "rotation_frequency"])

def get_dutyticker_data(request):
    if not request.user.is_authenticated:
        if 'guest_dt_data' not in request.session:
            request.session['guest_dt_data'] = get_guest_default_data()
        return JsonResponse(request.session['guest_dt_data'])

    user = request.user
    classroom = get_active_classroom_for_request(request)
    settings, _ = get_or_create_settings_for_scope(user, classroom)
    _sync_rotation_settings_flags(settings)
    
    students_qs = apply_classroom_scope(DTStudent.objects.filter(user=user, is_active=True), classroom)
    roles_qs = apply_classroom_scope(DTRole.objects.filter(user=user), classroom)
    
    if not students_qs.exists() and not roles_qs.exists():
        create_mockup_data(user, classroom=classroom)
        students_qs = apply_classroom_scope(DTStudent.objects.filter(user=user, is_active=True), classroom)
        roles_qs = apply_classroom_scope(DTRole.objects.filter(user=user), classroom)

    _apply_auto_rotation_if_due(user, settings, classroom=classroom)

    students = list(students_qs.values('id', 'name', 'number', 'is_mission_completed'))
    roles = list(roles_qs.values('id', 'name', 'description', 'time_slot', 'icon', 'color'))
    
    assignments_qs = (
        apply_classroom_scope(DTRoleAssignment.objects.filter(user=user), classroom)
        .select_related('role', 'student')
    )
    assignments = []
    for a in assignments_qs:
        assignments.append({
            'id': a.id,
            'role_id': a.role.id,
            'student_id': a.student.id if a.student else None,
            'student_name': a.student.name if a.student else "Unassigned",
            'is_completed': a.is_completed
        })
        
    weekly_schedule = _build_weekly_schedule_payload(user, classroom)

    # Fallback: if today's DTSchedule is empty, surface today's classcalendar events.
    fallback_day, fallback_rows = _build_today_fallback_schedule_from_classcalendar(user, classroom=classroom)
    if fallback_day is not None:
        day_key = str(fallback_day)
        has_today_period_schedule = apply_classroom_scope(
            DTSchedule.objects.filter(user=user, day=fallback_day, period__in=PERIOD_NUMBERS),
            classroom,
        ).exists()
        if not has_today_period_schedule:
            weekly_schedule[day_key] = fallback_rows

    spotlight_student_id = settings.spotlight_student_id
    visible_student_ids = {row["id"] for row in students}
    if spotlight_student_id and spotlight_student_id not in visible_student_ids:
        spotlight_student_id = None
        settings.spotlight_student = None
        settings.save(update_fields=["spotlight_student"])
        
    return JsonResponse({
        'students': students,
        'roles': roles,
        'assignments': assignments,
        'schedule': weekly_schedule,
        'settings': {
            'auto_rotation': settings.auto_rotation,
            'rotation_frequency': settings.rotation_frequency,
            'rotation_mode': settings.rotation_mode,
            'last_broadcast': settings.last_broadcast_message,
            'mission_title': settings.mission_title,
            'mission_desc': settings.mission_desc,
            'spotlight_student_id': spotlight_student_id,
        }
    })

@require_http_methods(["POST"])
@csrf_exempt
def update_assignment_status(request, assignment_id):
    try:
        data = json.loads(request.body)
        status = data.get('is_completed')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                for a in guest_data['assignments']:
                    if a['id'] == assignment_id:
                        a['is_completed'] = status
                        request.session.modified = True
                        return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Guest data not found'}, status=400)

        classroom = get_active_classroom_for_request(request)
        assignment = DTRoleAssignment.objects.get(
            id=assignment_id,
            user=request.user,
            **classroom_scope_filter(classroom),
        )
        assignment.is_completed = status
        assignment.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def toggle_student_mission_status(request, student_id):
    try:
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                for s in guest_data['students']:
                    if s['id'] == student_id:
                        s['is_mission_completed'] = not s['is_mission_completed']
                        request.session.modified = True
                        return JsonResponse({'success': True, 'is_completed': s['is_mission_completed']})
            return JsonResponse({'success': False, 'error': 'Guest data not found'}, status=400)

        classroom = get_active_classroom_for_request(request)
        student = DTStudent.objects.get(
            id=student_id,
            user=request.user,
            **classroom_scope_filter(classroom),
        )
        student.is_mission_completed = not student.is_mission_completed
        student.save()
        return JsonResponse({'success': True, 'is_completed': student.is_mission_completed})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def update_broadcast_message(request):
    try:
        data = json.loads(request.body)
        msg = data.get('message', '')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                guest_data['settings']['last_broadcast'] = msg
                request.session.modified = True
                return JsonResponse({'success': True})
            return JsonResponse({'success': False}, status=400)

        classroom = get_active_classroom_for_request(request)
        settings, _ = get_or_create_settings_for_scope(request.user, classroom)
        settings.last_broadcast_message = msg
        settings.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def update_mission(request):
    try:
        data = json.loads(request.body)
        title = data.get('title')
        desc = data.get('description')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                if title is not None: guest_data['settings']['mission_title'] = title
                if desc is not None: guest_data['settings']['mission_desc'] = desc
                request.session.modified = True
                return JsonResponse({'success': True})
            return JsonResponse({'success': False}, status=400)

        classroom = get_active_classroom_for_request(request)
        settings, _ = get_or_create_settings_for_scope(request.user, classroom)
        if title is not None: settings.mission_title = title
        if desc is not None: settings.mission_desc = desc
        settings.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["POST"])
@csrf_exempt
def update_spotlight_student(request):
    try:
        data = _safe_json_body(request)
        requested_student_id = data.get("student_id")

        if not request.user.is_authenticated:
            guest_data = request.session.get("guest_dt_data")
            if guest_data:
                settings_data = guest_data.setdefault("settings", {})
                settings_data["spotlight_student_id"] = requested_student_id if requested_student_id else None
                request.session.modified = True
                return JsonResponse({"success": True, "spotlight_student_id": settings_data["spotlight_student_id"]})
            return JsonResponse({"success": False}, status=400)

        classroom = get_active_classroom_for_request(request)
        settings, _ = get_or_create_settings_for_scope(request.user, classroom)

        if not requested_student_id:
            settings.spotlight_student = None
            settings.save(update_fields=["spotlight_student"])
            return JsonResponse({"success": True, "spotlight_student_id": None})

        student = DTStudent.objects.filter(
            id=requested_student_id,
            user=request.user,
            **classroom_scope_filter(classroom),
        ).first()
        if not student:
            return JsonResponse({"success": False, "error": "student not found"}, status=404)

        settings.spotlight_student = student
        settings.save(update_fields=["spotlight_student"])
        return JsonResponse({"success": True, "spotlight_student_id": student.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def assign_role(request):
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')
        student_id = data.get('student_id')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                student_name = ""
                if student_id:
                    student_name = next((s['name'] for s in guest_data['students'] if s['id'] == student_id), "Unassigned")
                
                found = False
                for a in guest_data['assignments']:
                    if a['role_id'] == role_id:
                        a['student_id'] = student_id
                        a['student_name'] = student_name
                        a['is_completed'] = False
                        found = True
                        break
                if not found:
                    guest_data['assignments'].append({
                        'id': len(guest_data['assignments']) + 1,
                        'role_id': role_id,
                        'student_id': student_id,
                        'student_name': student_name,
                        'is_completed': False
                    })
                request.session.modified = True
                return JsonResponse({'success': True})
            return JsonResponse({'success': False}, status=400)

        classroom = get_active_classroom_for_request(request)
        role = DTRole.objects.get(
            id=role_id,
            user=request.user,
            **classroom_scope_filter(classroom),
        )
        student = (
            DTStudent.objects.get(
                id=student_id,
                user=request.user,
                **classroom_scope_filter(classroom),
            )
            if student_id
            else None
        )
        assignment, created = DTRoleAssignment.objects.get_or_create(
            user=request.user,
            role=role,
            **classroom_scope_create_kwargs(classroom),
            defaults={'student': student},
        )
        if not created:
            assignment.student = student
            assignment.is_completed = False
            assignment.save()
        return JsonResponse({'success': True, 'assignment_id': assignment.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def rotation_trigger(request):
    payload = _safe_json_body(request)
    requested_behavior = payload.get("behavior")
    requested_behavior = _normalize_rotation_behavior(requested_behavior) if requested_behavior is not None else None

    if not request.user.is_authenticated:
        guest_data = request.session.get('guest_dt_data')
        if not guest_data or not guest_data['students']:
             return JsonResponse({'success': False, 'error': 'No data'})

        behavior = requested_behavior or "sequential"
        rotated = _rotate_guest_assignments(guest_data, behavior=behavior)
        request.session.modified = True
        return JsonResponse({'success': True, 'behavior': behavior, 'rotated': rotated})

    user = request.user
    classroom = get_active_classroom_for_request(request)
    settings, _ = get_or_create_settings_for_scope(user, classroom)
    _sync_rotation_settings_flags(settings)

    behavior = requested_behavior or _behavior_from_rotation_mode(settings.rotation_mode)
    rotated = _rotate_user_assignments(user, behavior=behavior, classroom=classroom)

    if str(settings.rotation_mode or "").startswith("auto_"):
        today = timezone.localdate()
        if settings.last_rotation_date != today:
            settings.last_rotation_date = today
            settings.save(update_fields=["last_rotation_date"])

    return JsonResponse({
        'success': True,
        'message': 'Rotated successfully',
        'behavior': behavior,
        'rotated': rotated,
    })

@require_http_methods(["POST"])
@csrf_exempt
def reset_data(request):
    if not request.user.is_authenticated:
        request.session['guest_dt_data'] = get_guest_default_data()
        return JsonResponse({'success': True, 'message': 'Guest data reset'})

    user = request.user
    classroom = get_active_classroom_for_request(request)
    apply_classroom_scope(DTStudent.objects.filter(user=user), classroom).delete()
    apply_classroom_scope(DTRole.objects.filter(user=user), classroom).delete()
    apply_classroom_scope(DTSchedule.objects.filter(user=user), classroom).delete()
    apply_classroom_scope(DTRoleAssignment.objects.filter(user=user), classroom).delete()
    settings, _ = get_or_create_settings_for_scope(user, classroom)
    settings.last_broadcast_message = ""
    settings.save()
    create_mockup_data(user, classroom=classroom)
    return JsonResponse({'success': True, 'message': 'Data reset to mockup'})
