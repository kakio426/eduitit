from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from .calendar_scope import get_visible_events_queryset, get_visible_tasks_queryset
from .models import CalendarTask


REVIEW_STATE_META = {
    "now": {
        "label": "지금 볼 메모",
        "description": "지금 바로 다시 확인할 메모입니다.",
        "order": 0,
    },
    "up_next": {
        "label": "곧 볼 메모",
        "description": "곧 시작할 일정 전에 다시 보면 좋습니다.",
        "order": 1,
    },
    "past": {
        "label": "이미 지난 메모",
        "description": "지나간 일정 메모를 다시 정리해 보세요.",
        "order": 2,
    },
}


def normalize_today_focus(raw_value):
    value = str(raw_value or "").strip().lower()
    if value in {"memos", "review"}:
        return value
    return "all"


def _append_query_params(url, **params):
    if not url:
        return ""
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    for key, value in params.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[str(key)] = str(value)
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def _build_focus_url(today_url, focus):
    if not today_url:
        return ""
    normalized = normalize_today_focus(focus)
    if normalized == "all":
        return today_url
    return _append_query_params(today_url, focus=normalized)


def _build_main_detail_url(main_url, *, date_key="", event_id="", task_id=""):
    return _append_query_params(
        main_url,
        date=date_key,
        open_event=event_id or None,
        open_task=task_id or None,
    )


def _build_messagebox_capture_url(capture_id):
    capture_value = str(capture_id or "").strip()
    if not capture_value:
        return ""
    try:
        return f"{reverse('messagebox:main')}?capture={capture_value}"
    except NoReverseMatch:
        return ""


def _serialize_related_message_capture(owner):
    related_manager = getattr(owner, "message_captures", None)
    if related_manager is None:
        return {"message_capture_id": "", "message_capture_url": ""}
    try:
        captures = list(related_manager.all())
    except Exception:
        captures = []
    if not captures:
        return {"message_capture_id": "", "message_capture_url": ""}
    capture = captures[0]
    return {
        "message_capture_id": str(capture.id),
        "message_capture_url": _build_messagebox_capture_url(capture.id),
    }


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


def _build_review_state(local_start, local_end, is_all_day, *, now_local):
    if is_all_day:
        key = "now"
    elif now_local < local_start:
        key = "up_next"
    elif now_local <= local_end:
        key = "now"
    else:
        key = "past"
    meta = REVIEW_STATE_META[key]
    return {
        "review_state_key": key,
        "review_state_label": meta["label"],
        "review_state_description": meta["description"],
        "review_order": meta["order"],
    }


def _serialize_today_event(event, *, current_user_id, main_url="", target_date=None, now_local=None):
    local_start = timezone.localtime(event.start_time)
    local_end = timezone.localtime(event.end_time)
    date_key = (target_date or local_start.date()).isoformat()
    memo_text = _extract_event_note_text(event)
    serialized = {
        "id": str(event.id),
        "title": event.title,
        "date_key": date_key,
        "schedule_text": _format_event_schedule(event),
        "note": memo_text,
        "note_excerpt": _build_memo_excerpt(memo_text, max_length=90),
        "calendar_owner_name": _display_user_name(event.author),
        "is_shared_calendar": event.author_id != current_user_id,
        "detail_url": _build_main_detail_url(main_url, date_key=date_key, event_id=str(event.id)),
        "start_iso": local_start.isoformat(),
        "end_iso": local_end.isoformat(),
        "is_all_day": bool(event.is_all_day),
    }
    serialized.update(
        _build_review_state(
            local_start,
            local_end,
            bool(event.is_all_day),
            now_local=now_local or timezone.localtime(),
        )
    )
    serialized.update(_serialize_related_message_capture(event))
    return serialized


def _serialize_today_task(task, *, main_url="", target_date=None):
    note_text = str(getattr(task, "note", "") or "").strip()
    due_at = timezone.localtime(task.due_at) if getattr(task, "due_at", None) else None
    date_key = (
        due_at.date().isoformat()
        if due_at is not None
        else ((target_date or timezone.localdate()).isoformat() if target_date else "")
    )
    payload = {
        "id": str(task.id),
        "title": task.title,
        "date_key": date_key,
        "schedule_text": _format_task_schedule(task),
        "note": note_text,
        "note_excerpt": _build_memo_excerpt(note_text, max_length=90),
        "priority": task.priority or CalendarTask.Priority.NORMAL,
        "priority_label": _get_task_priority_label(task.priority),
        "detail_url": _build_main_detail_url(main_url, date_key=date_key, task_id=str(task.id)),
    }
    payload.update(_serialize_related_message_capture(task))
    return payload


def _build_review_groups(items):
    grouped = []
    for key in ("now", "up_next", "past"):
        group_items = [item for item in items if item.get("review_state_key") == key]
        if not group_items:
            continue
        meta = REVIEW_STATE_META[key]
        grouped.append(
            {
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "items": group_items,
            }
        )
    return grouped


def _build_focus_copy(today_focus):
    if today_focus == "memos":
        return {
            "heading": "오늘의 메모",
            "description": "오늘 일정에 붙은 메모만 빠르게 확인합니다.",
            "empty_message": "오늘 확인할 메모가 없습니다.",
        }
    if today_focus == "review":
        return {
            "heading": "다시 볼 메모",
            "description": "언제 다시 봐야 하는지 시간 흐름에 맞춰 정리합니다.",
            "empty_message": "지금 다시 볼 메모가 없습니다.",
        }
    return {
        "heading": "오늘 보기",
        "description": "오늘 일정, 메모, 할 일을 같은 캘린더 기준으로 확인합니다.",
        "empty_message": "오늘 확인할 일정, 메모, 할 일이 없습니다.",
    }


def _pick_recent_memo_items(events, *, current_user_id, main_url, limit=1):
    items = []
    for event in events:
        serialized = _serialize_today_event(
            event,
            current_user_id=current_user_id,
            main_url=main_url,
            target_date=timezone.localtime(event.start_time).date(),
            now_local=timezone.localtime(),
        )
        if not serialized["note"]:
            continue
        items.append(serialized)
        if len(items) >= limit:
            break
    return items


def _build_month_grid(month_anchor, *, today, visible_events_qs, visible_tasks_qs, main_url):
    first_of_month = month_anchor.replace(day=1)
    next_month_start = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_of_month = next_month_start - timedelta(days=1)

    first_month_offset = (first_of_month.weekday() + 1) % 7
    grid_start = first_of_month - timedelta(days=first_month_offset)
    last_month_day = (last_of_month.weekday() + 1) % 7
    grid_end = last_of_month + timedelta(days=(6 - last_month_day))

    day_state = {}
    cursor = grid_start
    while cursor <= grid_end:
        date_key = cursor.isoformat()
        day_state[date_key] = {
            "date": date_key,
            "day_number": cursor.day,
            "is_current_month": cursor.month == month_anchor.month and cursor.year == month_anchor.year,
            "is_today": cursor == today,
            "has_events": False,
            "has_memos": False,
            "has_review_memos": False,
            "has_tasks": False,
            "event_count": 0,
            "memo_count": 0,
            "review_memo_count": 0,
            "task_count": 0,
            "detail_url": _build_main_detail_url(main_url, date_key=date_key),
        }
        cursor += timedelta(days=1)

    grid_events = (
        visible_events_qs.filter(
            start_time__date__lte=grid_end,
            end_time__date__gte=grid_start,
        )
        .prefetch_related("blocks")
        .order_by("start_time", "id")
    )
    for event in grid_events:
        local_start = timezone.localtime(event.start_time)
        local_end = timezone.localtime(event.end_time)
        note_text = _extract_event_note_text(event)
        overlap_start = max(local_start.date(), grid_start)
        overlap_end = min(local_end.date(), grid_end)
        cursor = overlap_start
        while cursor <= overlap_end:
            cell = day_state[cursor.isoformat()]
            cell["has_events"] = True
            cell["event_count"] += 1
            if note_text:
                cell["has_memos"] = True
                cell["memo_count"] += 1
                if cursor == today:
                    cell["has_review_memos"] = True
                    cell["review_memo_count"] += 1
            cursor += timedelta(days=1)

    grid_tasks = (
        visible_tasks_qs.filter(
            due_at__date__gte=grid_start,
            due_at__date__lte=grid_end,
        )
        .order_by("due_at", "created_at", "id")
    )
    for task in grid_tasks:
        if not getattr(task, "due_at", None):
            continue
        due_date = timezone.localtime(task.due_at).date()
        cell = day_state.get(due_date.isoformat())
        if cell is None:
            continue
        cell["has_tasks"] = True
        cell["task_count"] += 1

    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        week = []
        for _ in range(7):
            week.append(day_state[cursor.isoformat()])
            cursor += timedelta(days=1)
        weeks.append(week)

    return {
        "month_label": f"{first_of_month.year}년 {first_of_month.month}월",
        "month_grid": weeks,
    }


def build_today_event_memo_items(user, *, active_classroom=None, limit=None, target_date=None):
    workspace = build_today_execution_context(
        user,
        active_classroom=active_classroom,
        target_date=target_date,
    )
    items = workspace["today_memos"]
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
    today_focus="all",
):
    today = target_date or timezone.localdate()
    normalized_focus = normalize_today_focus(today_focus)
    focus_copy = _build_focus_copy(normalized_focus)
    empty_message = "오늘 확인할 일정, 메모, 할 일이 없습니다."
    today_all_url = _build_focus_url(today_url, "all")
    today_memo_url = _build_focus_url(today_url, "memos")
    today_review_url = _build_focus_url(today_url, "review")
    context = {
        "date_key": today.isoformat(),
        "date_label": f"{today.month}월 {today.day}일",
        "month_label": f"{today.year}년 {today.month}월",
        "month_grid": [],
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
        "today_memos": [],
        "review_memos": [],
        "review_groups": [],
        "next_upcoming_events": [],
        "recent_memo_items": [],
        "selected_date_events": [],
        "selected_date_tasks": [],
        "counts": {},
        "has_items": False,
        "has_supporting_items": False,
        "empty_message": empty_message,
        "focus_heading": focus_copy["heading"],
        "focus_description": focus_copy["description"],
        "focus_empty_message": focus_copy["empty_message"],
        "today_focus": normalized_focus,
        "main_url": main_url,
        "today_url": today_url,
        "today_all_url": today_all_url or today_url,
        "today_memo_url": today_memo_url,
        "today_review_url": today_review_url,
        "today_create_url": _append_query_params(today_all_url or today_url, action="create"),
        "main_create_url": _append_query_params(main_url, date=today.isoformat(), action="create"),
        "create_api_url": create_api_url,
    }
    if not getattr(user, "is_authenticated", False):
        return context

    now_local = timezone.localtime()
    visible_events_qs = get_visible_events_queryset(user, active_classroom=active_classroom)
    visible_tasks_qs = get_visible_tasks_queryset(user)
    month_grid = _build_month_grid(
        today,
        today=today,
        visible_events_qs=visible_events_qs,
        visible_tasks_qs=visible_tasks_qs,
        main_url=main_url,
    )
    today_events = [
        _serialize_today_event(
            event,
            current_user_id=user.id,
            main_url=main_url,
            target_date=today,
            now_local=now_local,
        )
        for event in visible_events_qs.filter(
            start_time__date__lte=today,
            end_time__date__gte=today,
        ).order_by("start_time", "id")
    ]

    today_tasks = [
        _serialize_today_task(task, main_url=main_url, target_date=today)
        for task in visible_tasks_qs
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
    review_memos = sorted(
        today_event_memos,
        key=lambda item: (
            item.get("review_order", 0),
            item.get("start_iso", ""),
            item.get("title", ""),
        ),
    )
    next_upcoming_events = [
        _serialize_today_event(
            event,
            current_user_id=user.id,
            main_url=main_url,
            target_date=timezone.localtime(event.start_time).date(),
            now_local=now_local,
        )
        for event in visible_events_qs.filter(start_time__date__gt=today).order_by("start_time", "id")[:2]
    ]
    recent_memo_items = _pick_recent_memo_items(
        visible_events_qs.filter(start_time__date__lte=today).order_by("-start_time")[:8],
        current_user_id=user.id,
        main_url=main_url,
        limit=1,
    )

    counts = {
        "today_events": len(today_events),
        "today_memos": len(today_event_memos),
        "review_memos": len(review_memos),
        "today_tasks": len(today_tasks),
    }

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
            "today_memos": today_event_memos,
            "review_memos": review_memos,
            "review_groups": _build_review_groups(review_memos),
            "month_label": month_grid["month_label"],
            "month_grid": month_grid["month_grid"],
            "next_upcoming_events": next_upcoming_events,
            "recent_memo_items": recent_memo_items,
            "selected_date_events": today_events,
            "selected_date_tasks": today_tasks,
            "counts": counts,
            "has_items": bool(today_events or today_event_memos or today_tasks or today_task_memos),
            "has_supporting_items": bool(next_upcoming_events or recent_memo_items),
        }
    )
    return context
