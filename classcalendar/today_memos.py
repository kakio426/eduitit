from datetime import timedelta

from django.utils import timezone

from .calendar_scope import get_visible_events_queryset, get_visible_tasks_queryset
from .models import CalendarTask


def _extract_event_note_text(event):
    try:
        text_block = next(
            (
                block
                for block in sorted(
                    event.blocks.all(),
                    key=lambda item: (item.order, item.id),
                )
                if getattr(block, "block_type", "") == "text"
            ),
            None,
        )
    except Exception:
        return ""

    if text_block is None:
        return ""

    content = text_block.content
    if isinstance(content, dict):
        note_text = content.get("text") or content.get("note") or ""
    elif isinstance(content, str):
        note_text = content
    else:
        note_text = ""
    return str(note_text).strip()


def _build_memo_excerpt(note_text, *, max_length=120):
    lines = [line.strip() for line in str(note_text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    normalized = "\n".join(lines)
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def _format_event_schedule(event):
    local_start = timezone.localtime(event.start_time)
    local_end = timezone.localtime(event.end_time)
    date_label = f"{local_start.month}월 {local_start.day}일"
    if event.is_all_day:
        return f"{date_label} · 하루 종일"
    if local_start.date() == local_end.date():
        return f"{date_label} · {local_start:%H:%M} - {local_end:%H:%M}"
    return (
        f"{local_start.month}월 {local_start.day}일 {local_start:%H:%M} - "
        f"{local_end.month}월 {local_end.day}일 {local_end:%H:%M}"
    )


def _format_task_schedule(task):
    if not getattr(task, "due_at", None):
        return "오늘 다시 볼 할 일"
    due_dt = timezone.localtime(task.due_at)
    if getattr(task, "has_time", False):
        return f"{due_dt.month}월 {due_dt.day}일 · {due_dt:%H:%M}까지"
    return f"{due_dt.month}월 {due_dt.day}일 · 오늘 할 일"


def _get_task_priority_label(priority):
    if priority == CalendarTask.Priority.HIGH:
        return "중요"
    if priority == CalendarTask.Priority.LOW:
        return "낮음"
    return "보통"


def _display_user_name(user):
    full_name = user.get_full_name().strip()
    if full_name:
        return full_name
    profile = getattr(user, "userprofile", None)
    nickname = getattr(profile, "nickname", "")
    if nickname:
        return nickname
    return user.username or "교사"


def _serialize_today_event(event, *, current_user_id):
    memo_text = _extract_event_note_text(event)
    return {
        "id": str(event.id),
        "title": event.title,
        "schedule_text": _format_event_schedule(event),
        "note": memo_text,
        "note_excerpt": _build_memo_excerpt(memo_text, max_length=90),
        "calendar_owner_name": _display_user_name(event.author),
        "is_shared_calendar": event.author_id != current_user_id,
    }


def _serialize_today_task(task):
    note_text = str(getattr(task, "note", "") or "").strip()
    return {
        "id": str(task.id),
        "title": task.title,
        "schedule_text": _format_task_schedule(task),
        "note": note_text,
        "note_excerpt": _build_memo_excerpt(note_text, max_length=90),
        "priority": task.priority or CalendarTask.Priority.NORMAL,
        "priority_label": _get_task_priority_label(task.priority),
    }


def build_today_event_memo_items(user, *, active_classroom=None, limit=None, target_date=None):
    workspace = build_today_execution_context(
        user,
        active_classroom=active_classroom,
        target_date=target_date,
    )
    items = workspace["today_event_memos"]
    return items[:limit] if limit else items


def build_today_task_memo_items(user, *, limit=None, target_date=None):
    workspace = build_today_execution_context(
        user,
        target_date=target_date,
    )
    items = workspace["today_task_memos"]
    return items[:limit] if limit else items


def build_today_memo_items(user, *, active_classroom=None, limit=None, target_date=None):
    return build_today_event_memo_items(
        user,
        active_classroom=active_classroom,
        limit=limit,
        target_date=target_date,
    )


def build_today_execution_context(
    user,
    *,
    active_classroom=None,
    target_date=None,
    main_url="",
    today_url="",
    create_api_url="",
):
    today = target_date or timezone.localdate()
    empty_message = "오늘 확인할 일정, 메모, 할 일이 없습니다."
    context = {
        "date_key": today.isoformat(),
        "date_label": f"{today.month}월 {today.day}일",
        "today_count": 0,
        "week_count": 0,
        "today_event_count": 0,
        "today_event_memo_count": 0,
        "today_task_count": 0,
        "today_task_memo_count": 0,
        "today_events": [],
        "today_event_memos": [],
        "today_tasks": [],
        "today_task_memos": [],
        "has_items": False,
        "empty_message": empty_message,
        "main_url": main_url,
        "today_url": today_url,
        "today_create_url": f"{today_url}?action=create" if today_url else "",
        "create_api_url": create_api_url,
    }
    if not getattr(user, "is_authenticated", False):
        return context

    visible_events_qs = get_visible_events_queryset(user, active_classroom=active_classroom)
    today_events = [
        _serialize_today_event(event, current_user_id=user.id)
        for event in visible_events_qs.filter(
            start_time__date__lte=today,
            end_time__date__gte=today,
        ).order_by("start_time", "id")
    ]

    today_tasks = [
        _serialize_today_task(task)
        for task in get_visible_tasks_queryset(user)
        .filter(status=CalendarTask.Status.OPEN, due_at__date=today)
        .order_by("due_at", "created_at", "id")
    ]

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    week_count = visible_events_qs.filter(
        start_time__date__gte=week_start,
        start_time__date__lt=week_end,
    ).count()

    today_event_memos = [item for item in today_events if item["note"]]
    today_task_memos = [item for item in today_tasks if item["note"]]

    context.update(
        {
            "today_count": len(today_events),
            "week_count": week_count,
            "today_event_count": len(today_events),
            "today_event_memo_count": len(today_event_memos),
            "today_task_count": len(today_tasks),
            "today_task_memo_count": len(today_task_memos),
            "today_events": today_events,
            "today_event_memos": today_event_memos,
            "today_tasks": today_tasks,
            "today_task_memos": today_task_memos,
            "has_items": bool(today_events or today_event_memos or today_tasks or today_task_memos),
        }
    )
    return context
