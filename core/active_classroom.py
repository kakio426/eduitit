from core.models import UserProfile

SESSION_CLASSROOM_SOURCE_KEY = "active_classroom_source"
SESSION_CLASSROOM_ID_KEY = "active_classroom_id"
HS_SOURCE = "hs"


def list_hs_classrooms_for_user(user):
    if not getattr(user, "is_authenticated", False):
        from happy_seed.models import HSClassroom

        return HSClassroom.objects.none()

    from happy_seed.models import HSClassroom

    return HSClassroom.objects.filter(
        teacher=user,
        is_active=True,
    ).order_by("-created_at")


def clear_active_classroom_session(request):
    request.session.pop(SESSION_CLASSROOM_SOURCE_KEY, None)
    request.session.pop(SESSION_CLASSROOM_ID_KEY, None)


def set_active_classroom_session(request, classroom):
    if classroom is None:
        clear_active_classroom_session(request)
        return

    request.session[SESSION_CLASSROOM_SOURCE_KEY] = HS_SOURCE
    request.session[SESSION_CLASSROOM_ID_KEY] = str(classroom.pk)


def _get_or_create_profile_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def get_default_classroom_for_user(user):
    profile = _get_or_create_profile_for_user(user)
    if profile is None or not profile.default_classroom_id:
        return None

    from happy_seed.models import HSClassroom

    classroom = HSClassroom.objects.filter(
        pk=profile.default_classroom_id,
        teacher=user,
        is_active=True,
    ).first()
    if classroom:
        return classroom

    profile.default_classroom = None
    profile.save(update_fields=["default_classroom"])
    return None


def set_default_classroom_for_user(user, classroom):
    profile = _get_or_create_profile_for_user(user)
    if profile is None:
        return None

    if classroom is not None:
        from happy_seed.models import HSClassroom

        is_valid = HSClassroom.objects.filter(
            pk=classroom.pk,
            teacher=user,
            is_active=True,
        ).exists()
        if not is_valid:
            return None

    next_id = classroom.pk if classroom is not None else None
    if profile.default_classroom_id != next_id:
        profile.default_classroom = classroom
        profile.save(update_fields=["default_classroom"])
    return classroom


def get_active_classroom_for_request(
    request,
    *,
    allow_default_fallback=True,
    persist_fallback_in_session=True,
):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return None

    source = request.session.get(SESSION_CLASSROOM_SOURCE_KEY)
    classroom_id = request.session.get(SESSION_CLASSROOM_ID_KEY)
    if source == HS_SOURCE and classroom_id:
        from happy_seed.models import HSClassroom

        classroom = HSClassroom.objects.filter(
            pk=classroom_id,
            teacher=request.user,
            is_active=True,
        ).first()
        if classroom:
            return classroom
        clear_active_classroom_session(request)

    if not allow_default_fallback:
        return None

    classroom = get_default_classroom_for_user(request.user)
    if classroom and persist_fallback_in_session:
        set_active_classroom_session(request, classroom)
    return classroom
