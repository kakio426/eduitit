from django.db.models import Q

from .models import CalendarCollaborator, CalendarEvent, CalendarTask


def get_calendar_access_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return set(), set(), []

    incoming_relations = list(
        CalendarCollaborator.objects.filter(collaborator=user)
        .select_related("owner")
        .order_by("owner__username")
    )
    visible_owner_ids = {user.id}
    editable_owner_ids = {user.id}
    incoming_calendars = []

    for relation in incoming_relations:
        visible_owner_ids.add(relation.owner_id)
        if relation.can_edit:
            editable_owner_ids.add(relation.owner_id)
        incoming_calendars.append(
            {
                "owner_id": relation.owner_id,
                "owner_name": _display_user_name(relation.owner),
                "can_edit": bool(relation.can_edit),
            }
        )

    return visible_owner_ids, editable_owner_ids, incoming_calendars


def get_visible_events_queryset(user, *, active_classroom=None, visible_owner_ids=None):
    if not getattr(user, "is_authenticated", False):
        return CalendarEvent.objects.none()

    owner_ids = visible_owner_ids
    if owner_ids is None:
        owner_ids, _, _ = get_calendar_access_for_user(user)

    query = Q(author_id__in=owner_ids)
    if active_classroom is not None:
        query |= Q(classroom=active_classroom)

    return (
        CalendarEvent.objects.filter(query)
        .select_related("author", "classroom")
        .prefetch_related("blocks", "attachments")
        .distinct()
        .order_by("start_time", "id")
    )


def get_visible_tasks_queryset(user):
    if not getattr(user, "is_authenticated", False):
        return CalendarTask.objects.none()

    return (
        CalendarTask.objects.filter(author=user)
        .select_related("author", "classroom")
        .order_by("due_at", "created_at", "id")
    )


def _display_user_name(user):
    full_name = user.get_full_name().strip()
    if full_name:
        return full_name
    profile = getattr(user, "userprofile", None)
    nickname = getattr(profile, "nickname", "")
    if nickname:
        return nickname
    return user.username or "교사"
