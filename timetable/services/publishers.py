from timetable.models import TimetablePublishedRecurring
from timetable.services.conflicts import validate_workspace_assignments


DAY_INDEX_BY_LABEL = {
    "월": 0,
    "화": 1,
    "수": 2,
    "목": 3,
    "금": 4,
    "토": 5,
    "일": 6,
}


def build_publication_payload(snapshot):
    workspace = snapshot.workspace
    assignments = list(
        workspace.assignments.select_related("classroom", "teacher", "special_room").order_by(
            "classroom__class_no",
            "day_key",
            "period_no",
            "id",
        )
    )
    payload = []
    for assignment in assignments:
        if not assignment.special_room_id:
            continue
        payload.append(
            {
                "room_id": assignment.special_room_id,
                "room_name": assignment.special_room.name,
                "day_key": assignment.day_key,
                "day_of_week": DAY_INDEX_BY_LABEL.get(assignment.day_key),
                "period_no": assignment.period_no,
                "classroom_label": assignment.classroom.label,
                "subject_name": assignment.subject_name,
                "teacher_name": assignment.teacher.name if assignment.teacher_id else "",
                "assignment": assignment,
            }
        )
    return payload


def publish_to_reservations(snapshot):
    from reservations.models import RecurringSchedule

    workspace = snapshot.workspace
    assignments = list(workspace.assignments.select_related("classroom", "teacher", "special_room"))
    room_policies = list(workspace.room_policies.select_related("special_room"))
    validation = validate_workspace_assignments(
        workspace,
        assignments,
        room_policies,
        effective_events=snapshot.events_json or [],
    )
    policy_map = {policy.special_room_id: max(1, int(policy.capacity_per_slot or 1)) for policy in room_policies}

    desired_payload = build_publication_payload(snapshot)
    desired_keys = set()
    response = {
        "applied_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "conflict_count": len(validation["conflicts"]),
        "warnings": list(validation["warnings"]),
        "conflicts": list(validation["conflicts"]),
    }

    existing_records = {
        (record.special_room_id, record.day_key, record.period_no): record
        for record in workspace.published_recurrings.select_related("recurring_schedule", "special_room")
    }
    payload_by_slot = {}
    for item in desired_payload:
        room_capacity = policy_map.get(item["room_id"], 1)
        slot_key = (item["room_id"], item["day_key"], item["period_no"])
        payload_by_slot.setdefault(slot_key, []).append(item)

        if room_capacity > 1:
            response["warnings"].append(
                f"{item['room_name']}은 수용량이 {room_capacity}라서 예약 시스템으로 자동 발행하지 않았습니다."
            )
            response["skipped_count"] += 1
            continue
        if item["day_of_week"] is None:
            response["warnings"].append(f"{item['day_key']} 요일은 예약 시스템 발행 대상이 아닙니다.")
            response["skipped_count"] += 1
            continue
        desired_keys.add(slot_key)

    for slot_key, items in payload_by_slot.items():
        room_id, day_key, period_no = slot_key
        room_capacity = policy_map.get(room_id, 1)
        if room_capacity > 1:
            continue
        if len(items) > 1:
            response["conflicts"].append(
                f"{items[0]['room_name']} {day_key} {period_no}교시에 여러 반이 배정되어 발행을 건너뛰었습니다."
            )
            response["conflict_count"] += 1
            response["skipped_count"] += len(items)
            continue

        item = items[0]
        recurring_name = f"[시간표] {item['classroom_label']} {item['subject_name']}".strip()
        if item["teacher_name"]:
            recurring_name = f"{recurring_name} ({item['teacher_name']})"

        record = existing_records.get(slot_key)
        if record:
            recurring = record.recurring_schedule
            if recurring.name != recurring_name:
                recurring.name = recurring_name
                recurring.save(update_fields=["name"])
                response["updated_count"] += 1
            record.snapshot = snapshot
            record.name_snapshot = recurring_name
            record.save(update_fields=["snapshot", "name_snapshot", "updated_at"])
            continue

        conflicting = RecurringSchedule.objects.filter(
            room_id=room_id,
            day_of_week=item["day_of_week"],
            period=period_no,
        ).first()
        if conflicting:
            response["conflicts"].append(
                f"{item['room_name']} {day_key} {period_no}교시에 기존 고정수업이 있어 발행을 건너뛰었습니다."
            )
            response["conflict_count"] += 1
            response["skipped_count"] += 1
            continue

        recurring = RecurringSchedule.objects.create(
            room_id=room_id,
            day_of_week=item["day_of_week"],
            period=period_no,
            name=recurring_name,
        )
        TimetablePublishedRecurring.objects.create(
            workspace=workspace,
            snapshot=snapshot,
            special_room_id=room_id,
            recurring_schedule=recurring,
            day_key=day_key,
            period_no=period_no,
            name_snapshot=recurring_name,
        )
        response["applied_count"] += 1

    stale_records = list(workspace.published_recurrings.select_related("recurring_schedule"))
    for record in stale_records:
        slot_key = (record.special_room_id, record.day_key, record.period_no)
        if slot_key in desired_keys:
            continue
        record.recurring_schedule.delete()
        record.delete()

    return response
