from __future__ import annotations

from .models import HandoffRosterGroup


def normalize_phone_last4(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 4:
        return ""
    return digits[-4:]


def _active_members(group: HandoffRosterGroup | None):
    if group is None:
        return []
    return list(group.members.filter(is_active=True).order_by("sort_order", "id"))


def signature_participants(group: HandoffRosterGroup | None) -> list[dict[str, str]]:
    participants = []
    for member in _active_members(group):
        name = (member.display_name or "").strip()
        if not name:
            continue
        participants.append(
            {
                "name": name,
                "affiliation": (member.affiliation or member.note or "").strip(),
            }
        )
    return participants


def consent_recipients(group: HandoffRosterGroup | None, *, audience_type: str) -> tuple[list[dict[str, str]], list[str]]:
    recipients = []
    warnings = []
    for member in _active_members(group):
        student_name = (member.display_name or "").strip()
        if not student_name:
            continue

        if audience_type == "general":
            recipients.append(
                {
                    "student_name": student_name,
                    "parent_name": "",
                    "phone_number": "",
                }
            )
            continue

        phone_last4 = normalize_phone_last4(member.phone_last4)
        if not phone_last4:
            warnings.append(f"{student_name}: 연락처 뒤 4자리가 없습니다.")
            continue

        parent_name = (member.guardian_name or "").strip() or f"{student_name} 보호자"
        recipients.append(
            {
                "student_name": student_name,
                "parent_name": parent_name,
                "phone_number": phone_last4,
            }
        )
    return recipients, warnings


def happy_seed_students(group: HandoffRosterGroup | None) -> tuple[list[dict[str, int | str | None]], list[str]]:
    students = []
    warnings = []
    fallback_number = 1
    for member in _active_members(group):
        name = (member.display_name or "").strip()
        if not name:
            continue
        student_number = member.student_number
        if student_number in (None, 0):
            warnings.append(f"{name}: 번호가 없어 명부 순서대로 번호를 붙입니다.")
            student_number = fallback_number
        fallback_number = max(fallback_number, int(student_number) + 1)
        students.append(
            {
                "name": name,
                "number": int(student_number),
                "member_id": member.id,
            }
        )
    return students, warnings


def infoboard_submitter_choices(group: HandoffRosterGroup | None) -> list[tuple[str, str]]:
    choices = []
    for member in _active_members(group):
        name = (member.display_name or "").strip()
        if not name:
            continue
        if member.student_number:
            label = f"{member.student_number}번 {name}"
        elif member.affiliation:
            label = f"{name} ({member.affiliation})"
        else:
            label = name
        choices.append((name, label))
    return choices


def roster_service_summary(group: HandoffRosterGroup | None) -> dict[str, int]:
    members = _active_members(group)
    return {
        "total": len(members),
        "with_affiliation": sum(1 for member in members if (member.affiliation or "").strip()),
        "with_guardian_phone": sum(
            1 for member in members if normalize_phone_last4(member.phone_last4)
        ),
        "with_student_number": sum(1 for member in members if member.student_number),
    }
