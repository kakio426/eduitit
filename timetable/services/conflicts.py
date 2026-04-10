from timetable.services.events import build_event_conflict_message, build_event_slot_map


def _assignment_key(item):
    return f"{item.classroom_id}:{item.day_key}:{item.period_no}"


def validate_workspace_assignments(workspace, assignments, room_policies, issues=None, effective_events=None):
    issues = list(issues or [])
    event_slot_map = build_event_slot_map(effective_events or [])
    policy_map = {policy.special_room_id: max(1, int(policy.capacity_per_slot or 1)) for policy in room_policies}
    cell_map = {}
    cell_messages = {}
    teacher_slots = {}
    room_slots = {}

    for item in assignments:
        key = _assignment_key(item)
        cell_map[key] = item
        cell_messages.setdefault(key, [])

        if not item.subject_name:
            cell_messages[key].append("과목이 비어 있습니다.")
        if item.display_text and "(" in item.display_text and not item.teacher_id:
            cell_messages[key].append("교사 이름을 찾지 못했습니다.")

        if item.teacher_id:
            teacher_key = (item.teacher_id, item.day_key, item.period_no)
            teacher_slots.setdefault(teacher_key, []).append(item)
        if item.special_room_id:
            room_key = (item.special_room_id, item.day_key, item.period_no)
            room_slots.setdefault(room_key, []).append(item)
        slot_events = event_slot_map.get(f"{item.day_key}:{item.period_no}") or []
        if slot_events:
            message = f"{item.day_key} {item.period_no}교시는 {build_event_conflict_message(slot_events)} 시간입니다."
            cell_messages[key].append(message)

    conflicts = []
    warnings = []
    seen_event_conflicts = set()

    for issue in issues:
        target = warnings if issue.get("kind") in {"sheet", "format"} else conflicts
        target.append(issue["message"])
        cell_key = issue.get("cell_key")
        if cell_key:
            cell_messages.setdefault(cell_key, []).append(issue["message"])

    for (_teacher_id, day_key, period_no), items in teacher_slots.items():
        if len(items) < 2:
            continue
        message = f"{items[0].teacher.name} 교사가 {day_key} {period_no}교시에 여러 반에 배정되었습니다."
        conflicts.append(message)
        for item in items:
            cell_messages.setdefault(_assignment_key(item), []).append(message)

    for item in assignments:
        slot_events = event_slot_map.get(f"{item.day_key}:{item.period_no}") or []
        if not slot_events:
            continue
        message = f"{item.day_key} {item.period_no}교시는 {build_event_conflict_message(slot_events)} 시간입니다."
        slot_key = (item.day_key, item.period_no, message)
        if slot_key in seen_event_conflicts:
            continue
        seen_event_conflicts.add(slot_key)
        conflicts.append(message)

    for (room_id, day_key, period_no), items in room_slots.items():
        capacity = policy_map.get(room_id, 1)
        if len(items) <= capacity:
            continue
        room_name = items[0].special_room.name
        message = f"{room_name}은 {day_key} {period_no}교시에 {capacity}개 반까지만 배정할 수 있습니다."
        conflicts.append(message)
        for item in items:
            cell_messages.setdefault(_assignment_key(item), []).append(message)

    incomplete_count = 0
    for messages in cell_messages.values():
        if messages:
            incomplete_count += 1

    return {
        "conflicts": conflicts,
        "warnings": warnings,
        "cell_messages": cell_messages,
        "summary": {
            "conflict_count": len(conflicts),
            "warning_count": len(warnings),
            "incomplete_count": incomplete_count,
            "assignment_count": len(assignments),
        },
    }


def serialize_validation_result(validation):
    return {
        "conflicts": list(validation.get("conflicts") or []),
        "warnings": list(validation.get("warnings") or []),
        "cell_messages": dict(validation.get("cell_messages") or {}),
        "summary": dict(validation.get("summary") or {}),
    }
