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


def build_today_memo_items(user, *, active_classroom=None, limit=None, target_date=None):
    if not getattr(user, "is_authenticated", False):
        return []

    today = target_date or timezone.localdate()
    normalized_limit = int(limit or 0)
    items = []

    today_events = list(
        get_visible_events_queryset(user, active_classroom=active_classroom)
        .filter(start_time__date__lte=today, end_time__date__gte=today)
        .order_by("start_time", "id")[:8]
    )
    for event in today_events:
        memo_text = _extract_event_note_text(event)
        if not memo_text:
            continue
        items.append(
            {
                "source_kind": "event",
                "source_id": event.id,
                "title": event.title,
                "memo_text": memo_text,
                "memo_excerpt": _build_memo_excerpt(memo_text),
                "schedule_text": _format_event_schedule(event),
                "date_key": today.isoformat(),
            }
        )
        if normalized_limit and len(items) >= normalized_limit:
            return items

    today_tasks = list(
        get_visible_tasks_queryset(user)
        .filter(status=CalendarTask.Status.OPEN, due_at__date=today)
        .order_by("due_at", "created_at")[:8]
    )
    for task in today_tasks:
        memo_text = str(getattr(task, "note", "") or "").strip()
        if not memo_text:
            continue
        items.append(
            {
                "source_kind": "task",
                "source_id": task.id,
                "title": task.title,
                "memo_text": memo_text,
                "memo_excerpt": _build_memo_excerpt(memo_text),
                "schedule_text": _format_task_schedule(task),
                "date_key": today.isoformat(),
            }
        )
        if normalized_limit and len(items) >= normalized_limit:
            return items

    return items
