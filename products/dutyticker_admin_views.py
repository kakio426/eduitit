from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import datetime

from .models import DTStudent, DTRole, DTSettings, DTRoleAssignment, DTSchedule, DTTimeSlot
from .dutyticker_scope import (
    apply_classroom_scope,
    classroom_scope_create_kwargs,
    classroom_scope_filter,
    get_active_classroom_for_request,
    get_or_create_settings_for_scope,
)
from .dutyticker_slots import PERIOD_NUMBERS, SLOT_BY_CODE, SLOT_LAYOUT, WEEKDAY_LABELS
from .dutyticker_sync import sync_dt_students_from_hs
from .tts_announcement import annotate_tts_rows, build_demo_tts_rows, build_tts_announcement_rows

CONSENT_STATUS_LABELS = {
    "approved": "동의 완료",
    "pending": "대기",
    "rejected": "거부",
    "expired": "만료",
    "withdrawn": "철회",
}
CONSENT_PREVIEW_LIMIT = 6
EDITABLE_TRANSITION_SLOT_CODES = {"b3", "lunch", "b5"}
TRANSITION_SLOT_KIND_LABELS = {
    "break": "쉬는시간",
    "lunch": "점심시간",
}


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


def _build_slot_label(spec, slot_kind=None):
    resolved_kind = str(slot_kind or spec["kind"]).strip() or spec["kind"]
    if resolved_kind == "period":
        return spec["label"]

    base_label = TRANSITION_SLOT_KIND_LABELS.get(resolved_kind)
    if not base_label:
        return spec["label"]

    source_label = str(spec.get("label") or "").strip()
    transition_suffix = ""
    if "(" in source_label:
        start = source_label.find("(")
        end = source_label.find(")", start)
        if end != -1:
            transition_suffix = f" {source_label[start:end + 1]}"
    return f"{base_label}{transition_suffix}".strip()


def _get_transition_slot_kind(spec, slot, raw_value):
    current_kind = str(getattr(slot, "slot_kind", "") or spec["kind"]).strip() or spec["kind"]
    if spec["code"] not in EDITABLE_TRANSITION_SLOT_CODES:
        return current_kind

    selected_kind = str(raw_value or "").strip() or current_kind
    if selected_kind not in TRANSITION_SLOT_KIND_LABELS:
        return current_kind if current_kind in TRANSITION_SLOT_KIND_LABELS else spec["kind"]
    return selected_kind


def _sync_role_time_slot_labels(user, classroom, renamed_labels):
    normalized_map = {
        str(old_label or "").strip(): str(new_label or "").strip()
        for old_label, new_label in renamed_labels.items()
        if str(old_label or "").strip() and str(old_label or "").strip() != str(new_label or "").strip()
    }
    if not normalized_map:
        return 0

    roles = apply_classroom_scope(
        DTRole.objects.filter(user=user, time_slot__in=list(normalized_map.keys())),
        classroom,
    )
    updated_roles = []
    for role in roles:
        next_label = normalized_map.get(str(role.time_slot or "").strip())
        if not next_label or role.time_slot == next_label:
            continue
        role.time_slot = next_label
        updated_roles.append(role)

    if updated_roles:
        DTRole.objects.bulk_update(updated_roles, ["time_slot"])
    return len(updated_roles)


def _build_period_subject_rows(user, classroom):
    schedules = apply_classroom_scope(
        DTSchedule.objects.filter(user=user, day__in=[day for day, _ in WEEKDAY_LABELS], period__in=PERIOD_NUMBERS),
        classroom,
    )
    subject_map = {(row.day, row.period): row.subject for row in schedules}

    rows = []
    for period in PERIOD_NUMBERS:
        rows.append(
            {
                "period": period,
                "days": [
                    {
                        "day": day,
                        "label": label,
                        "subject": subject_map.get((day, period), ""),
                    }
                    for day, label in WEEKDAY_LABELS
                ],
            }
        )
    return rows


def _build_tts_preview_context(user, classroom, minutes_before):
    today = timezone.localdate()
    today_js_day = (today.weekday() + 1) % 7
    schedule_queryset = apply_classroom_scope(
        DTSchedule.objects.filter(user=user, day=today_js_day),
        classroom,
    ).order_by("period", "id")

    if schedule_queryset.exists():
        rows = build_tts_announcement_rows(schedule_queryset, date=today, minutes_before=minutes_before)
        source_label = "오늘 시간표 기준"
    else:
        rows = build_demo_tts_rows(date=today, minutes_before=minutes_before)
        source_label = "샘플 문구"

    rows = annotate_tts_rows(rows)
    next_row = next((row for row in rows if row.get("is_next")), rows[0] if rows else None)
    return {
        "tts_preview_source_label": source_label,
        "tts_preview_row": next_row,
    }


def _parse_int_in_range(raw_value, *, default, min_value, max_value):
    try:
        parsed = int(str(raw_value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    return max(min_value, min(max_value, parsed))


def _parse_float_in_range(raw_value, *, default, min_value, max_value):
    try:
        parsed = float(str(raw_value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    return max(min_value, min(max_value, parsed))


def _parse_time_value(raw_value):
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return None
    try:
        return datetime.datetime.strptime(raw_text, "%H:%M").time()
    except ValueError:
        return None


def _build_consent_summary(classroom):
    if classroom is None or not hasattr(classroom, "students"):
        return {
            "enabled": False,
            "manage_url": "",
            "classroom_name": "",
            "total_count": 0,
            "approved_count": 0,
            "pending_count": 0,
            "rejected_count": 0,
            "expired_count": 0,
            "withdrawn_count": 0,
            "needs_attention_count": 0,
            "preview_students": [],
            "remaining_preview_count": 0,
        }

    students = list(classroom.students.select_related("consent").order_by("number", "name"))
    status_counts = {status: 0 for status in CONSENT_STATUS_LABELS}
    preview_students = []

    for student in students:
        consent = getattr(student, "consent", None)
        status = getattr(consent, "status", "pending")
        if status not in status_counts:
            status = "pending"
        status_counts[status] += 1

        if status != "approved":
            preview_students.append(
                {
                    "number": student.number,
                    "name": student.name,
                    "status": status,
                    "status_label": CONSENT_STATUS_LABELS[status],
                }
            )

    needs_attention_count = len(preview_students)
    return {
        "enabled": True,
        "manage_url": reverse("happy_seed:consent_manage", kwargs={"classroom_id": classroom.id}),
        "classroom_name": classroom.name,
        "total_count": len(students),
        "approved_count": status_counts["approved"],
        "pending_count": status_counts["pending"],
        "rejected_count": status_counts["rejected"],
        "expired_count": status_counts["expired"],
        "withdrawn_count": status_counts["withdrawn"],
        "needs_attention_count": needs_attention_count,
        "preview_students": preview_students[:CONSENT_PREVIEW_LIMIT],
        "remaining_preview_count": max(needs_attention_count - CONSENT_PREVIEW_LIMIT, 0),
    }

@login_required
def admin_dashboard(request):
    user = request.user
    classroom = get_active_classroom_for_request(request)
    students = apply_classroom_scope(DTStudent.objects.filter(user=user), classroom)
    roles = apply_classroom_scope(DTRole.objects.filter(user=user), classroom)
    settings, _ = get_or_create_settings_for_scope(user, classroom)
    time_slots = _ensure_time_slots_for_scope(user, classroom)
    period_rows = _build_period_subject_rows(user, classroom)
    consent_summary = _build_consent_summary(classroom)
    
    return render(request, 'products/dutyticker/admin_dashboard.html', {
        'students': students,
        'roles': roles,
        'settings': settings,
        'active_classroom': classroom,
        'consent_summary': consent_summary,
        'time_slots': time_slots,
        'editable_transition_slot_codes': sorted(EDITABLE_TRANSITION_SLOT_CODES),
        'period_rows': period_rows,
        'period_numbers': PERIOD_NUMBERS,
        'weekday_labels': WEEKDAY_LABELS,
        'tts_minutes_choices': [0, 3, 5, 10],
        **_build_tts_preview_context(user, classroom, settings.tts_minutes_before),
    })


@login_required
@require_http_methods(["POST"])
def update_rotation_settings(request):
    classroom = get_active_classroom_for_request(request)
    settings, _ = get_or_create_settings_for_scope(request.user, classroom)
    selected_mode = (request.POST.get("rotation_mode") or "").strip()
    valid_modes = {choice[0] for choice in DTSettings.ROTATION_MODE_CHOICES}

    if selected_mode in valid_modes:
        settings.rotation_mode = selected_mode
        settings.auto_rotation = selected_mode.startswith("auto_")
        if settings.auto_rotation:
            settings.rotation_frequency = "daily"
        else:
            settings.last_rotation_date = None
            
    settings.save(
        update_fields=[
            "rotation_mode",
            "auto_rotation",
            "rotation_frequency",
            "last_rotation_date",
        ]
    )
    messages.success(request, "역할 운영 저장 완료")

    return redirect('dt_admin_dashboard')


@login_required
@require_http_methods(["POST"])
def update_display_settings(request):
    classroom = get_active_classroom_for_request(request)
    settings, _ = get_or_create_settings_for_scope(request.user, classroom)
    updated_fields = []

    selected_theme = (request.POST.get("theme") or "").strip()
    valid_themes = {choice[0] for choice in DTSettings.THEME_CHOICES}
    if selected_theme in valid_themes and settings.theme != selected_theme:
        settings.theme = selected_theme
        updated_fields.append("theme")

    selected_role_view_mode = (request.POST.get("role_view_mode") or "").strip()
    valid_role_view_modes = {choice[0] for choice in DTSettings.ROLE_VIEW_MODE_CHOICES}
    if selected_role_view_mode in valid_role_view_modes and settings.role_view_mode != selected_role_view_mode:
        settings.role_view_mode = selected_role_view_mode
        updated_fields.append("role_view_mode")

    if updated_fields:
        settings.save(update_fields=updated_fields)

    messages.success(request, "화면 표시 저장 완료")
    return redirect("dt_admin_dashboard")


@login_required
@require_http_methods(["POST"])
def update_schedule_settings(request):
    classroom = get_active_classroom_for_request(request)
    time_slots = _ensure_time_slots_for_scope(request.user, classroom)
    slot_map = {slot.slot_code: slot for slot in time_slots}

    updated_slots = []
    invalid_slots = []
    renamed_labels = {}
    for spec in SLOT_LAYOUT:
        slot = slot_map.get(spec["code"])
        if not slot:
            continue

        start_time = _parse_time_value(request.POST.get(f"slot_{spec['code']}_start"))
        end_time = _parse_time_value(request.POST.get(f"slot_{spec['code']}_end"))
        if not start_time or not end_time or start_time >= end_time:
            invalid_slots.append(slot.slot_label or spec["label"])
            continue

        next_slot_kind = _get_transition_slot_kind(spec, slot, request.POST.get(f"slot_{spec['code']}_kind"))
        next_slot_label = _build_slot_label(spec, next_slot_kind)
        did_change = False

        if slot.start_time != start_time:
            slot.start_time = start_time
            did_change = True
        if slot.end_time != end_time:
            slot.end_time = end_time
            did_change = True
        if slot.slot_kind != next_slot_kind:
            slot.slot_kind = next_slot_kind
            did_change = True
        if slot.slot_label != next_slot_label:
            renamed_labels[slot.slot_label] = next_slot_label
            slot.slot_label = next_slot_label
            did_change = True

        if did_change:
            updated_slots.append(slot)

    if updated_slots:
        DTTimeSlot.objects.bulk_update(updated_slots, ["start_time", "end_time", "slot_kind", "slot_label"])

    synced_role_count = _sync_role_time_slot_labels(request.user, classroom, renamed_labels)

    slot_map = {
        slot.slot_code: slot
        for slot in apply_classroom_scope(DTTimeSlot.objects.filter(user=request.user), classroom)
    }
    deleted_qs = apply_classroom_scope(DTSchedule.objects.filter(user=request.user), classroom)
    saved_subject_count = 0
    deleted_subject_count = 0

    for day, _ in WEEKDAY_LABELS:
        for period in PERIOD_NUMBERS:
            subject_key = f"subject_{day}_{period}"
            subject_value = (request.POST.get(subject_key) or "").strip()
            slot_code = f"p{period}"
            slot = slot_map.get(slot_code)
            default_spec = SLOT_BY_CODE.get(slot_code)

            if not subject_value:
                deleted_count, _ = deleted_qs.filter(day=day, period=period).delete()
                deleted_subject_count += deleted_count
                continue

            start_time = slot.start_time if slot else default_spec["start"]
            end_time = slot.end_time if slot else default_spec["end"]
            DTSchedule.objects.update_or_create(
                user=request.user,
                day=day,
                period=period,
                **classroom_scope_create_kwargs(classroom),
                defaults={
                    "subject": subject_value,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
            saved_subject_count += 1

    if invalid_slots:
        invalid_text = ", ".join(invalid_slots)
        messages.error(request, f"시간 설정 오류: {invalid_text}의 시작 시간은 종료 시간보다 빨라야 합니다.")

    summary_bits = [
        f"과목 {saved_subject_count}개 저장",
        f"비운 칸 {deleted_subject_count}개 반영",
        f"시간 슬롯 {len(updated_slots)}개 수정",
    ]
    if synced_role_count:
        summary_bits.append(f"역할 시간 {synced_role_count}개 동기화")

    messages.success(
        request,
        f"시간표 저장 완료: {', '.join(summary_bits)}",
    )

    return redirect("dt_admin_dashboard")


@login_required
@require_http_methods(["POST"])
def update_tts_settings(request):
    classroom = get_active_classroom_for_request(request)
    settings, _ = get_or_create_settings_for_scope(request.user, classroom)

    settings.tts_enabled = request.POST.get("tts_enabled") == "on"
    settings.tts_minutes_before = _parse_int_in_range(
        request.POST.get("tts_minutes_before"),
        default=settings.tts_minutes_before or 5,
        min_value=0,
        max_value=10,
    )
    settings.tts_voice_uri = (request.POST.get("tts_voice_uri") or "").strip()[:255]
    settings.tts_rate = _parse_float_in_range(
        request.POST.get("tts_rate"),
        default=settings.tts_rate or 0.95,
        min_value=0.7,
        max_value=1.3,
    )
    settings.tts_pitch = _parse_float_in_range(
        request.POST.get("tts_pitch"),
        default=settings.tts_pitch or 1.0,
        min_value=0.8,
        max_value=1.2,
    )
    settings.save(update_fields=["tts_enabled", "tts_minutes_before", "tts_voice_uri", "tts_rate", "tts_pitch"])

    tts_state_text = "교시 안내 방송 꺼짐"
    if settings.tts_enabled:
        tts_state_text = f"교시 안내 방송 켜짐 ({settings.tts_minutes_before}분 전)"

    messages.success(request, f"교시 안내 방송 저장 완료: {tts_state_text}")
    return redirect("dt_admin_dashboard")

@login_required
@require_http_methods(["POST"])
def add_student(request):
    classroom = get_active_classroom_for_request(request)
    names = request.POST.get('names', '').split(',')
    # Bulk add support (comma separated)
    current_count = apply_classroom_scope(
        DTStudent.objects.filter(user=request.user),
        classroom,
    ).count()
    
    new_students = []
    for name in names:
        name = name.strip()
        if name:
            current_count += 1
            new_students.append(
                DTStudent(
                    user=request.user,
                    name=name,
                    number=current_count,
                    **classroom_scope_create_kwargs(classroom),
                )
            )
    
    if new_students:
        DTStudent.objects.bulk_create(new_students)
             
    return redirect('dt_admin_dashboard')


@login_required
@require_http_methods(["POST"])
def sync_students_from_hs(request):
    classroom = get_active_classroom_for_request(request)
    if classroom is None:
        messages.error(request, "상단에서 활성 학급을 먼저 선택해 주세요.")
        return redirect("dt_admin_dashboard")

    try:
        summary = sync_dt_students_from_hs(request.user, classroom)
    except Exception as exc:
        messages.error(request, f"학급 명단 동기화에 실패했습니다: {exc}")
        return redirect("dt_admin_dashboard")

    messages.success(
        request,
        (
            "학급 명단 동기화 완료: "
            f"활성 {summary['active_count']}명, "
            f"신규 {summary['created_count']}명, "
            f"업데이트 {summary['updated_count']}명, "
            f"비활성 {summary['deactivated_count']}명"
        ),
    )
    return redirect("dt_admin_dashboard")

@login_required
def delete_student(request, pk):
    classroom = get_active_classroom_for_request(request)
    student = get_object_or_404(
        DTStudent,
        pk=pk,
        user=request.user,
        **classroom_scope_filter(classroom),
    )
    student.delete()
    return redirect('dt_admin_dashboard')

@login_required
@require_http_methods(["POST"])
def add_role(request):
    classroom = get_active_classroom_for_request(request)
    name = request.POST.get('name')
    time_slot = request.POST.get('time_slot')
    description = request.POST.get('description', '')
    
    if name and time_slot:
        role = DTRole.objects.create(
            user=request.user,
            **classroom_scope_create_kwargs(classroom),
            name=name,
            time_slot=time_slot,
            description=description
        )
        # Auto-create assignment entry if needed
        DTRoleAssignment.objects.create(
            user=request.user,
            role=role,
            **classroom_scope_create_kwargs(classroom),
        )
        
    return redirect('dt_admin_dashboard')

@login_required
def delete_role(request, pk):
    classroom = get_active_classroom_for_request(request)
    role = get_object_or_404(
        DTRole,
        pk=pk,
        user=request.user,
        **classroom_scope_filter(classroom),
    )
    role.delete()
    return redirect('dt_admin_dashboard')


@login_required
def print_sheet(request):
    user = request.user
    classroom = get_active_classroom_for_request(request)
    roles = list(apply_classroom_scope(DTRole.objects.filter(user=user), classroom).order_by('time_slot', 'id'))
    assignments_qs = (
        DTRoleAssignment.objects
        .filter(user=user, role__in=roles, **classroom_scope_filter(classroom))
        .select_related('role', 'student')
        .order_by('role_id', '-date', '-id')
    )

    assignment_by_role_id = {}
    for assignment in assignments_qs:
        if assignment.role_id not in assignment_by_role_id:
            assignment_by_role_id[assignment.role_id] = assignment

    rows = []
    for idx, role in enumerate(roles, start=1):
        assignment = assignment_by_role_id.get(role.id)
        rows.append({
            'index': idx,
            'role_name': role.name,
            'time_slot': role.time_slot or '-',
            'student_name': assignment.student.name if assignment and assignment.student else '미배정',
            'description': role.description or '-',
        })

    return render(request, 'products/dutyticker/print_sheet.html', {
        'rows': rows,
        'row_count': len(rows),
        'row_count_safe': max(len(rows), 1),
    })
