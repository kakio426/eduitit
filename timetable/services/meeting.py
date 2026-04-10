from timetable.models import TimetableDateOverride, TimetableSlotAssignment
from timetable.services.date_overrides import build_date_override_block_reason, build_effective_date_assignments
from timetable.services.events import build_event_conflict_message, build_event_slot_map
from timetable.services.normalizer import build_display_text


def build_meeting_matrix(workspace, teacher, classrooms, assignments, effective_events=None, *, target_date=None, date_overrides=None):
    assignment_lookup = {(item.classroom_id, item.day_key, item.period_no): item for item in assignments}
    event_slot_map = build_event_slot_map(effective_events or [])
    teacher_busy = {}
    date_context = None
    if target_date:
        date_context = build_effective_date_assignments(workspace, target_date, assignments, date_overrides or [])
        assignment_lookup = {(item.classroom_id, item.day_key, item.period_no): item for item in date_context["assignments"]}
        for item in date_context["assignments"]:
            if item.teacher_id:
                teacher_busy.setdefault((item.teacher_id, item.day_key, item.period_no), []).append(item)
    else:
        for item in assignments:
            if item.teacher_id:
                teacher_busy.setdefault((item.teacher_id, item.day_key, item.period_no), []).append(item)

    slots = []
    day_keys = [date_context["day_key"]] if date_context else workspace.day_keys
    for day_key in day_keys:
        for period_no, period_label in enumerate(workspace.period_labels, start=1):
            slots.append(
                {
                    "slot_key": f"{day_key}:{period_no}",
                    "day_key": day_key,
                    "period_no": period_no,
                    "period_label": period_label,
                    "display_label": f"{day_key}{period_no}",
                }
            )

    rows = []
    for classroom in classrooms:
        cells = []
        for slot in slots:
            assignment = assignment_lookup.get((classroom.id, slot["day_key"], slot["period_no"]))
            state = "available"
            reason = ""
            slot_events = event_slot_map.get(f"{slot['day_key']}:{slot['period_no']}") or []
            if slot_events:
                state = "blocked"
                reason = build_event_conflict_message(slot_events) + " 시간입니다."
            elif date_context:
                override = date_context["override_lookup"].get((classroom.id, slot["period_no"]))
                base_assignment = date_context["weekly_lookup"].get((classroom.id, slot["period_no"]))
                base_blocked_reason = build_date_override_block_reason(base_assignment)
                if override and override.teacher_id == teacher.id:
                    state = "assigned"
                    reason = override.display_text or override.subject_name
                elif override:
                    state = "blocked"
                    reason = override.display_text or "이미 날짜별 일정이 있습니다."
                elif assignment and assignment.teacher_id == teacher.id:
                    state = "assigned"
                    reason = assignment.subject_name or assignment.display_text
                elif base_blocked_reason:
                    state = "blocked"
                    reason = base_blocked_reason
                elif teacher_busy.get((teacher.id, slot["day_key"], slot["period_no"])):
                    state = "blocked"
                    reason = f"{teacher.name} 교사가 다른 반 수업 중입니다."
            elif assignment and assignment.teacher_id == teacher.id:
                state = "assigned"
                reason = assignment.subject_name or assignment.display_text
            elif assignment:
                state = "blocked"
                reason = assignment.display_text or "이미 다른 수업이 있습니다."
            elif teacher_busy.get((teacher.id, slot["day_key"], slot["period_no"])):
                state = "blocked"
                reason = f"{teacher.name} 교사가 다른 반 수업 중입니다."
            cells.append(
                {
                    "slot_key": slot["slot_key"],
                    "day_key": slot["day_key"],
                    "period_no": slot["period_no"],
                    "state": state,
                    "reason": reason,
                }
            )
        rows.append({"classroom": classroom, "cells": cells})

    return {"slots": slots, "rows": rows}


def apply_meeting_selections(workspace, teacher, subject_name, room, selections, *, target_date=None):
    classroom_lookup = {
        classroom.id: classroom
        for classroom in workspace.school.timetable_classrooms.filter(
            school_year=workspace.school_year,
            grade=workspace.grade,
            is_active=True,
        )
    }
    applied_count = 0
    for selection in selections:
        classroom = classroom_lookup.get(int(selection["classroom_id"]))
        if not classroom:
            continue
        defaults = {
            "subject_name": subject_name,
            "teacher": teacher,
            "special_room": room,
            "display_text": build_display_text(subject_name, teacher.name, room.name if room else ""),
        }
        if target_date:
            TimetableDateOverride.objects.update_or_create(
                workspace=workspace,
                classroom=classroom,
                date=target_date,
                period_no=int(selection["period_no"]),
                defaults={
                    **defaults,
                    "source": TimetableDateOverride.Source.MEETING,
                },
            )
        else:
            TimetableSlotAssignment.objects.update_or_create(
                workspace=workspace,
                classroom=classroom,
                day_key=selection["day_key"],
                period_no=int(selection["period_no"]),
                defaults={
                    **defaults,
                    "source": TimetableSlotAssignment.Source.MEETING,
                },
            )
        applied_count += 1
    return applied_count
