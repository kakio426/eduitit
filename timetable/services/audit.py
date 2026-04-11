from django.utils import timezone

from ..models import TimetableAuditLog


EVENT_LABELS = {
    "class_link_issued": "입력 링크 발급",
    "class_link_revoked": "입력 링크 끊기",
    "class_weekly_saved": "주간 시간표 저장",
    "class_daily_saved": "날짜별 일정 저장",
    "class_submitted": "입력 완료",
    "class_reviewed": "관리자 검토 완료",
    "shared_event_created": "공통 행사 등록",
    "shared_event_updated": "공통 행사 수정",
    "shared_event_deleted": "공통 행사 삭제",
    "snapshot_saved": "스냅샷 저장",
    "snapshot_restored": "스냅샷 복원",
    "workspace_published": "확정 완료",
    "meeting_applied": "회의 반영",
}

EVENT_TONES = {
    "class_link_issued": "sky",
    "class_link_revoked": "slate",
    "class_weekly_saved": "amber",
    "class_daily_saved": "amber",
    "class_submitted": "sky",
    "class_reviewed": "emerald",
    "shared_event_created": "amber",
    "shared_event_updated": "amber",
    "shared_event_deleted": "rose",
    "snapshot_saved": "slate",
    "snapshot_restored": "slate",
    "workspace_published": "emerald",
    "meeting_applied": "sky",
}


def resolve_actor_name(*, user=None, fallback=""):
    if fallback:
        return fallback
    if not user:
        return ""
    profile = getattr(user, "userprofile", None)
    if profile and getattr(profile, "nickname", ""):
        return profile.nickname
    full_name = ""
    if hasattr(user, "get_full_name"):
        full_name = (user.get_full_name() or "").strip()
    return full_name or getattr(user, "username", "") or ""


def log_timetable_event(
    workspace,
    *,
    event_type,
    actor_name="",
    actor_type=TimetableAuditLog.ActorType.SYSTEM,
    classroom=None,
    payload=None,
):
    return TimetableAuditLog.objects.create(
        workspace=workspace,
        classroom=classroom,
        actor_name=(actor_name or "").strip(),
        actor_type=actor_type,
        event_type=event_type,
        payload_json=payload or {},
    )


def serialize_recent_activity(entries, *, limit=8):
    items = []
    for entry in list(entries)[:limit]:
        payload = entry.payload_json or {}
        classroom_label = payload.get("classroom_label") or (entry.classroom.label if entry.classroom_id and entry.classroom else "")
        title = payload.get("title") or ""
        date_label = payload.get("date") or ""
        message = EVENT_LABELS.get(entry.event_type, entry.event_type)
        if entry.event_type in {"class_link_issued", "class_link_revoked", "class_weekly_saved", "class_daily_saved", "class_submitted", "class_reviewed"} and classroom_label:
            message = f"{classroom_label} · {message}"
        elif entry.event_type in {"shared_event_created", "shared_event_updated", "shared_event_deleted"} and title:
            message = f"{title} · {message}"
        elif entry.event_type == "snapshot_saved" and payload.get("snapshot_name"):
            message = f"{payload['snapshot_name']} · {message}"
        elif entry.event_type == "snapshot_restored" and payload.get("snapshot_name"):
            message = f"{payload['snapshot_name']} · {message}"
        elif entry.event_type == "workspace_published" and payload.get("snapshot_name"):
            message = f"{payload['snapshot_name']} · {message}"
        elif entry.event_type == "meeting_applied" and classroom_label:
            message = f"{classroom_label} · {message}"
        if date_label:
            message = f"{message} ({date_label})"

        actor_label = entry.actor_name or entry.get_actor_type_display()
        items.append(
            {
                "id": entry.id,
                "message": message,
                "actor_label": actor_label,
                "actor_type": entry.actor_type,
                "event_type": entry.event_type,
                "tone": EVENT_TONES.get(entry.event_type, "slate"),
                "created_at": entry.created_at.isoformat(),
                "created_at_label": timezone.localtime(entry.created_at).strftime("%Y-%m-%d %H:%M"),
            }
        )
    return items
