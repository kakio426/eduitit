from .models import DTSettings
from core.active_classroom import get_active_classroom_for_request as resolve_active_classroom


def get_active_classroom_for_request(request):
    return resolve_active_classroom(request)


def classroom_scope_filter(classroom):
    if classroom is None:
        return {"classroom__isnull": True}
    return {"classroom": classroom}


def classroom_scope_create_kwargs(classroom):
    return {"classroom": classroom}


def apply_classroom_scope(queryset, classroom):
    return queryset.filter(**classroom_scope_filter(classroom))


def _build_settings_defaults_from_global(user):
    global_settings = DTSettings.objects.filter(user=user, classroom__isnull=True).first()
    if not global_settings:
        return {}
    return {
        "auto_rotation": global_settings.auto_rotation,
        "rotation_frequency": global_settings.rotation_frequency,
        "last_rotation_date": global_settings.last_rotation_date,
        "rotation_mode": global_settings.rotation_mode,
        "last_broadcast_message": global_settings.last_broadcast_message,
        "mission_title": global_settings.mission_title,
        "mission_desc": global_settings.mission_desc,
    }


def get_or_create_settings_for_scope(user, classroom):
    defaults = _build_settings_defaults_from_global(user) if classroom is not None else {}
    return DTSettings.objects.get_or_create(
        user=user,
        classroom=classroom,
        defaults=defaults,
    )
