from collections import defaultdict

from django.db import transaction

from happy_seed.models import HSStudent

from .dutyticker_scope import apply_classroom_scope, classroom_scope_create_kwargs
from .models import DTRoleAssignment, DTStudent


def sync_dt_students_from_hs(user, classroom):
    """Mirror active HSClassroom students into DTStudent for the same classroom scope."""
    if classroom is None:
        raise ValueError("active classroom is required")

    hs_students = list(
        HSStudent.objects.filter(classroom=classroom, is_active=True).order_by("number", "name", "id")
    )
    existing_students = list(
        apply_classroom_scope(DTStudent.objects.filter(user=user), classroom).order_by("id")
    )

    by_number = defaultdict(list)
    by_name = defaultdict(list)
    for student in existing_students:
        by_number[int(student.number)].append(student)
        by_name[str(student.name or "").strip()].append(student)

    remaining_ids = {student.id for student in existing_students}
    to_update = []
    to_create = []
    deactivated_ids = []
    created_count = 0
    updated_count = 0

    def _take_candidate(candidates):
        for candidate in candidates:
            if candidate.id in remaining_ids:
                remaining_ids.remove(candidate.id)
                return candidate
        return None

    with transaction.atomic():
        for hs_student in hs_students:
            hs_name = str(hs_student.name or "").strip()
            hs_number = int(hs_student.number or 0)

            candidate = _take_candidate(by_number[hs_number])
            if candidate is None and hs_name:
                candidate = _take_candidate(by_name[hs_name])

            if candidate is None:
                to_create.append(
                    DTStudent(
                        user=user,
                        name=hs_name,
                        number=hs_number,
                        is_active=True,
                        is_mission_completed=False,
                        **classroom_scope_create_kwargs(classroom),
                    )
                )
                created_count += 1
                continue

            changed = False
            if candidate.name != hs_name:
                candidate.name = hs_name
                changed = True
            if candidate.number != hs_number:
                candidate.number = hs_number
                changed = True
            if not candidate.is_active:
                candidate.is_active = True
                changed = True

            if changed:
                to_update.append(candidate)
                updated_count += 1

        for student in existing_students:
            if student.id not in remaining_ids:
                continue
            if student.is_active:
                student.is_active = False
                student.is_mission_completed = False
                to_update.append(student)
                deactivated_ids.append(student.id)

        if to_create:
            DTStudent.objects.bulk_create(to_create)
        if to_update:
            DTStudent.objects.bulk_update(
                to_update,
                ["name", "number", "is_active", "is_mission_completed"],
            )
        if deactivated_ids:
            apply_classroom_scope(
                DTRoleAssignment.objects.filter(user=user, student_id__in=deactivated_ids),
                classroom,
            ).update(student=None, is_completed=False)

    return {
        "hs_count": len(hs_students),
        "created_count": created_count,
        "updated_count": updated_count,
        "deactivated_count": len(deactivated_ids),
        "active_count": len(hs_students),
    }
