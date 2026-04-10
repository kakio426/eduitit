from timetable.models import TimetableDateOverride, TimetableSlotAssignment, TimetableTeacher
from timetable.services.events import build_event_conflict_message, build_event_slot_map


WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


def day_key_for_date(target_date):
    return WEEKDAY_LABELS[target_date.weekday()]


def calculate_week_number(workspace, target_date):
    if not target_date or not workspace.term_start_date:
        return None
    day_offset = (target_date - workspace.term_start_date).days
    if day_offset < 0:
        return None
    return (day_offset // 7) + 1


def build_week_label(workspace, target_date):
    week_number = calculate_week_number(workspace, target_date)
    return f"{week_number}주차" if week_number else ""


def get_workspace_date_overrides(workspace, *, classroom=None, target_date=None):
    queryset = TimetableDateOverride.objects.filter(workspace=workspace).select_related(
        "classroom",
        "teacher",
        "special_room",
    )
    if classroom is not None:
        queryset = queryset.filter(classroom=classroom)
    if target_date is not None:
        queryset = queryset.filter(date=target_date)
    return list(queryset.order_by("date", "classroom__class_no", "period_no", "id"))


def serialize_date_override(workspace, override):
    date_value = override.date
    return {
        "id": override.id,
        "classroom_id": override.classroom_id,
        "classroom_label": override.classroom.label,
        "date": date_value.isoformat(),
        "date_label": date_value.strftime("%Y-%m-%d"),
        "week_label": build_week_label(workspace, date_value),
        "day_key": day_key_for_date(date_value),
        "period_no": override.period_no,
        "subject_name": override.subject_name,
        "teacher_name": override.teacher.name if override.teacher_id else "",
        "room_name": override.special_room.name if override.special_room_id else "",
        "display_text": override.display_text,
        "note": override.note or "",
        "source": override.source,
    }


def build_serialized_date_overrides(workspace, overrides):
    return [serialize_date_override(workspace, item) for item in overrides]


def build_effective_date_assignments(workspace, target_date, weekly_assignments, date_overrides):
    day_key = day_key_for_date(target_date)
    weekly_lookup = {}
    for assignment in weekly_assignments:
        if assignment.day_key != day_key:
            continue
        weekly_lookup[(assignment.classroom_id, assignment.period_no)] = assignment

    override_lookup = {}
    for override in date_overrides:
        if override.date != target_date:
            continue
        override_lookup[(override.classroom_id, override.period_no)] = override

    assignment_map = dict(weekly_lookup)
    for (classroom_id, period_no), override in override_lookup.items():
        assignment_map[(classroom_id, period_no)] = TimetableSlotAssignment(
            workspace=workspace,
            classroom=override.classroom,
            day_key=day_key,
            period_no=period_no,
            subject_name=override.subject_name,
            teacher=override.teacher,
            special_room=override.special_room,
            source=TimetableSlotAssignment.Source.MANUAL,
            display_text=override.display_text,
            note=override.note,
        )

    assignments = [assignment_map[key] for key in sorted(assignment_map.keys(), key=lambda item: (item[0], item[1]))]
    return {
        "day_key": day_key,
        "weekly_lookup": weekly_lookup,
        "override_lookup": override_lookup,
        "assignments": assignments,
    }


def build_date_override_block_reason(base_assignment):
    if not base_assignment:
        return ""
    if base_assignment.teacher_id and base_assignment.teacher.teacher_type in {
        TimetableTeacher.TeacherType.SPECIALIST,
        TimetableTeacher.TeacherType.INSTRUCTOR,
    }:
        teacher_label = "전담" if base_assignment.teacher.teacher_type == TimetableTeacher.TeacherType.SPECIALIST else "강사"
        return f"기존 {teacher_label} 수업입니다."
    if base_assignment.special_room_id:
        return "기존 특별실 수업이 있습니다."
    return ""


def build_classroom_date_rows(workspace, classroom, target_date, weekly_assignments, date_overrides, effective_events):
    effective = build_effective_date_assignments(workspace, target_date, weekly_assignments, date_overrides)
    event_slot_map = build_event_slot_map(effective_events or [])
    rows = []
    for period_no, period_label in enumerate(workspace.period_labels, start=1):
        base_assignment = effective["weekly_lookup"].get((classroom.id, period_no))
        override = effective["override_lookup"].get((classroom.id, period_no))
        slot_events = event_slot_map.get(f"{effective['day_key']}:{period_no}") or []
        if override:
            status_tone = "override"
            status_label = "이 날짜만 변경"
            status_reason = override.display_text or override.subject_name or "예외 일정이 저장되어 있습니다."
        else:
            blocked_reason = build_date_override_block_reason(base_assignment)
            if slot_events:
                status_tone = "blocked"
                status_label = "배정 불가"
                status_reason = f"{build_event_conflict_message(slot_events)} 시간입니다."
            elif blocked_reason:
                status_tone = "blocked"
                status_label = "배정 불가"
                status_reason = blocked_reason
            else:
                status_tone = "available"
                status_label = "배정 가능"
                status_reason = "담임 시간이나 빈칸은 날짜별 일정으로 조정할 수 있습니다."

        rows.append(
            {
                "period_no": period_no,
                "period_label": period_label,
                "day_key": effective["day_key"],
                "base_text": (base_assignment.display_text or base_assignment.subject_name) if base_assignment else "",
                "override_text": override.display_text if override else "",
                "status_tone": status_tone,
                "status_label": status_label,
                "status_reason": status_reason,
                "is_blocked": status_tone == "blocked" and not override,
            }
        )
    return rows
