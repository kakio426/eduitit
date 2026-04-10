def build_teacher_stat_rows(teachers, assignments):
    assignments_by_teacher = {}
    for assignment in assignments:
        if not assignment.teacher_id:
            continue
        assignments_by_teacher.setdefault(assignment.teacher_id, 0)
        assignments_by_teacher[assignment.teacher_id] += 1

    rows = []
    for teacher in teachers:
        assigned = assignments_by_teacher.get(teacher.id, 0)
        target = int(teacher.target_weekly_hours or 0)
        rows.append(
            {
                "teacher_id": teacher.id,
                "teacher_name": teacher.name,
                "teacher_type": teacher.teacher_type,
                "target_hours": target,
                "assigned_hours": assigned,
                "remaining_hours": max(0, target - assigned),
                "is_over": assigned > target if target else False,
            }
        )
    rows.sort(key=lambda item: (item["teacher_type"], item["teacher_name"]))
    return rows
