from __future__ import annotations

from django.conf import settings

from core.ai_usage_limits import consume_ai_usage_limits, user_usage_subject


def auto_metadata_limit_exceeded(user, *, material=None) -> bool:
    scopes = [
        (
            "edu_materials:auto_metadata:user",
            user_usage_subject(user),
            (
                (600, _int_setting("EDU_MATERIALS_AUTO_METADATA_BURST_LIMIT", 5)),
                (86400, _int_setting("EDU_MATERIALS_AUTO_METADATA_DAILY_LIMIT", 20)),
            ),
        )
    ]
    material_id = getattr(material, "id", None)
    if material_id:
        scopes.append(
            (
                "edu_materials:auto_metadata:material",
                f"{user_usage_subject(user)}:material:{material_id}",
                ((86400, _int_setting("EDU_MATERIALS_AUTO_METADATA_MATERIAL_DAILY_LIMIT", 3)),),
            )
        )
    return consume_ai_usage_limits(scopes)


def _int_setting(name: str, default: int) -> int:
    try:
        return max(int(getattr(settings, name, default)), 0)
    except (TypeError, ValueError):
        return max(int(default), 0)
