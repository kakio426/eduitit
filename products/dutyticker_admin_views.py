from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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


def _parse_time_value(raw_value):
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return None
    try:
        return datetime.datetime.strptime(raw_text, "%H:%M").time()
    except ValueError:
        return None

@login_required
def admin_dashboard(request):
    user = request.user
    classroom = get_active_classroom_for_request(request)
    students = apply_classroom_scope(DTStudent.objects.filter(user=user), classroom)
    roles = apply_classroom_scope(DTRole.objects.filter(user=user), classroom)
    settings, _ = get_or_create_settings_for_scope(user, classroom)
    time_slots = _ensure_time_slots_for_scope(user, classroom)
    period_rows = _build_period_subject_rows(user, classroom)
    
    return render(request, 'products/dutyticker/admin_dashboard.html', {
        'students': students,
        'roles': roles,
        'settings': settings,
        'active_classroom': classroom,
        'time_slots': time_slots,
        'period_rows': period_rows,
        'period_numbers': PERIOD_NUMBERS,
        'weekday_labels': WEEKDAY_LABELS,
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
            
    selected_theme = (request.POST.get("theme") or "").strip()
    valid_themes = {choice[0] for choice in DTSettings.THEME_CHOICES}
    if selected_theme in valid_themes:
        settings.theme = selected_theme

    settings.save(update_fields=["rotation_mode", "auto_rotation", "rotation_frequency", "last_rotation_date", "theme"])

    return redirect('dt_admin_dashboard')


@login_required
@require_http_methods(["POST"])
def update_schedule_settings(request):
    classroom = get_active_classroom_for_request(request)
    time_slots = _ensure_time_slots_for_scope(request.user, classroom)
    slot_map = {slot.slot_code: slot for slot in time_slots}

    updated_slots = []
    invalid_slots = []
    for spec in SLOT_LAYOUT:
        slot = slot_map.get(spec["code"])
        if not slot:
            continue

        start_time = _parse_time_value(request.POST.get(f"slot_{spec['code']}_start"))
        end_time = _parse_time_value(request.POST.get(f"slot_{spec['code']}_end"))
        if not start_time or not end_time or start_time >= end_time:
            invalid_slots.append(spec["label"])
            continue

        if slot.start_time != start_time or slot.end_time != end_time:
            slot.start_time = start_time
            slot.end_time = end_time
            updated_slots.append(slot)

    if updated_slots:
        DTTimeSlot.objects.bulk_update(updated_slots, ["start_time", "end_time"])

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

    messages.success(
        request,
        f"시간표 저장 완료: 과목 {saved_subject_count}개 저장, 비운 칸 {deleted_subject_count}개 반영, 시간 슬롯 {len(updated_slots)}개 수정",
    )

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
