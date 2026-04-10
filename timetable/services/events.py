from django.db.models import Q

from timetable.models import TimetableSharedEvent


def get_effective_shared_events(workspace):
    queryset = TimetableSharedEvent.objects.filter(
        school=workspace.school,
        school_year=workspace.school_year,
        term=workspace.term,
        is_active=True,
    ).filter(
        Q(scope_type=TimetableSharedEvent.ScopeType.SCHOOL)
        | Q(scope_type=TimetableSharedEvent.ScopeType.GRADE, grade=workspace.grade)
    )
    day_order = {day_key: index for index, day_key in enumerate(workspace.day_keys)}
    return sorted(
        list(queryset),
        key=lambda event: (
            day_order.get(event.day_key, 999),
            event.period_start,
            0 if event.scope_type == TimetableSharedEvent.ScopeType.SCHOOL else 1,
            event.title,
            event.id,
        ),
    )


def serialize_shared_event(workspace, event):
    period_count = len(workspace.period_labels)
    period_start = max(1, int(event.period_start or 1))
    period_end = max(period_start, int(event.period_end or period_start))
    period_end = min(period_end, period_count)
    slot_keys = [f"{event.day_key}:{period_no}" for period_no in range(period_start, period_end + 1)]
    if period_start == period_end:
        slot_label = f"{event.day_key} {period_start}교시"
    else:
        slot_label = f"{event.day_key} {period_start}~{period_end}교시"
    return {
        "id": event.id,
        "scope_type": event.scope_type,
        "scope_label": event.scope_label,
        "grade": event.grade,
        "title": event.title,
        "day_key": event.day_key,
        "period_start": period_start,
        "period_end": period_end,
        "slot_label": slot_label,
        "slot_keys": slot_keys,
        "note": event.note or "",
        "is_active": event.is_active,
    }


def build_effective_event_payloads(workspace, events):
    return [serialize_shared_event(workspace, event) for event in events]


def build_event_slot_map(effective_events):
    slot_map = {}
    for event in effective_events or []:
        for slot_key in event.get("slot_keys") or []:
            slot_map.setdefault(slot_key, []).append(event)
    return slot_map


def build_event_conflict_message(events):
    if not events:
        return ""
    labels = [f"{event.get('scope_label', '공통')} 행사 '{event.get('title', '')}'" for event in events]
    return ", ".join(labels)
