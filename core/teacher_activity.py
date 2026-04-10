from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Min, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import TeacherActivityEvent, TeacherActivityProfile, UserProfile

logger = logging.getLogger(__name__)

ELIGIBLE_ACTIVITY_ROLES = {"school", "instructor"}

ACTIVITY_CATEGORY_DAILY_LOGIN = "daily_login"
ACTIVITY_CATEGORY_SERVICE_USE = "service_use"
ACTIVITY_CATEGORY_REQUEST_SENT = "request_sent"

ACTIVITY_CATEGORY_POINTS = {
    ACTIVITY_CATEGORY_DAILY_LOGIN: 1,
    ACTIVITY_CATEGORY_SERVICE_USE: 1,
    ACTIVITY_CATEGORY_REQUEST_SENT: 2,
}

ACTIVITY_CATEGORY_DAILY_CAPS = {
    ACTIVITY_CATEGORY_DAILY_LOGIN: 1,
    ACTIVITY_CATEGORY_SERVICE_USE: 2,
    ACTIVITY_CATEGORY_REQUEST_SENT: 1,
}


@dataclass(frozen=True)
class ActivityLevel:
    key: str
    label: str
    min_score: int
    min_active_days: int


ACTIVITY_LEVELS: tuple[ActivityLevel, ...] = (
    ActivityLevel("starter", "첫발", 0, 0),
    ActivityLevel("steady", "꾸준", 60, 30),
    ActivityLevel("solid", "탄탄", 240, 90),
    ActivityLevel("strong", "든든", 900, 365),
    ActivityLevel("veteran", "베테랑", 3200, 1095),
)


def _get_user_role(user) -> str:
    profile = getattr(user, "userprofile", None)
    if profile is not None and hasattr(profile, "role"):
        return str(profile.role or "")
    try:
        return str(UserProfile.objects.only("role").get(user=user).role or "")
    except UserProfile.DoesNotExist:
        return ""


def is_teacher_activity_eligible(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return _get_user_role(user) in ELIGIBLE_ACTIVITY_ROLES


def _normalize_source_key(value: str) -> str:
    return str(value or "").strip()[:120]


def _resolve_related_fields(*, related_object=None, related_object_type: str = "", related_object_id: str = "") -> tuple[str, str]:
    if related_object is not None:
        object_type = f"{related_object._meta.app_label}.{related_object._meta.model_name}"
        object_id = str(related_object.pk)
        return object_type, object_id[:64]
    return str(related_object_type or "").strip()[:64], str(related_object_id or "").strip()[:64]


def resolve_teacher_activity_level(*, total_score: int, active_day_count: int) -> tuple[ActivityLevel, ActivityLevel | None]:
    current = ACTIVITY_LEVELS[0]
    next_level = None
    for index, level in enumerate(ACTIVITY_LEVELS):
        if total_score >= level.min_score and active_day_count >= level.min_active_days:
            current = level
            next_level = ACTIVITY_LEVELS[index + 1] if index + 1 < len(ACTIVITY_LEVELS) else None
            continue
        break
    return current, next_level


def build_teacher_activity_summary_for_user(user) -> dict[str, object]:
    if not getattr(user, "is_authenticated", False):
        level, next_level = resolve_teacher_activity_level(total_score=0, active_day_count=0)
        return _build_summary_payload(
            total_score=0,
            active_day_count=0,
            last_earned_at=None,
            current_level=level,
            next_level=next_level,
        )

    profile = TeacherActivityProfile.objects.filter(user=user).first()
    total_score = int(getattr(profile, "total_score", 0) or 0)
    active_day_count = int(getattr(profile, "active_day_count", 0) or 0)
    last_earned_at = getattr(profile, "last_earned_at", None)
    current_level, next_level = resolve_teacher_activity_level(
        total_score=total_score,
        active_day_count=active_day_count,
    )
    return _build_summary_payload(
        total_score=total_score,
        active_day_count=active_day_count,
        last_earned_at=last_earned_at,
        current_level=current_level,
        next_level=next_level,
    )


def _build_summary_payload(
    *,
    total_score: int,
    active_day_count: int,
    last_earned_at,
    current_level: ActivityLevel,
    next_level: ActivityLevel | None,
    awarded: bool = False,
    points_awarded: int = 0,
) -> dict[str, object]:
    return {
        "awarded": awarded,
        "points_awarded": int(points_awarded or 0),
        "total_score": int(total_score or 0),
        "active_day_count": int(active_day_count or 0),
        "level_key": current_level.key,
        "level_label": current_level.label,
        "last_earned_at": last_earned_at.isoformat() if last_earned_at else None,
        "next_level_key": next_level.key if next_level else "",
        "next_level_label": next_level.label if next_level else "",
        "next_level_min_score": int(next_level.min_score if next_level else 0),
        "next_level_min_active_days": int(next_level.min_active_days if next_level else 0),
    }


def award_teacher_activity(
    user,
    *,
    category: str,
    source_key: str,
    occurred_at: datetime | None = None,
    points: int | None = None,
    related_object=None,
    related_object_type: str = "",
    related_object_id: str = "",
    metadata: dict[str, object] | None = None,
    is_backfilled: bool = False,
) -> dict[str, object]:
    if not is_teacher_activity_eligible(user):
        return build_teacher_activity_summary_for_user(user)

    normalized_source_key = _normalize_source_key(source_key)
    if not normalized_source_key:
        raise ValueError("source_key is required")
    if category not in ACTIVITY_CATEGORY_POINTS:
        raise ValueError(f"Unsupported activity category: {category}")

    occurred_at = occurred_at or timezone.now()
    activity_date = timezone.localdate(occurred_at)
    resolved_points = int(points if points is not None else ACTIVITY_CATEGORY_POINTS[category])
    object_type, object_id = _resolve_related_fields(
        related_object=related_object,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )

    with transaction.atomic():
        profile, _ = TeacherActivityProfile.objects.get_or_create(user=user)
        profile = TeacherActivityProfile.objects.select_for_update().get(pk=profile.pk)

        if TeacherActivityEvent.objects.filter(
            user=user,
            activity_date=activity_date,
            category=category,
            source_key=normalized_source_key,
        ).exists():
            current_level, next_level = resolve_teacher_activity_level(
                total_score=profile.total_score,
                active_day_count=profile.active_day_count,
            )
            return _build_summary_payload(
                total_score=profile.total_score,
                active_day_count=profile.active_day_count,
                last_earned_at=profile.last_earned_at,
                current_level=current_level,
                next_level=next_level,
                awarded=False,
                points_awarded=0,
            )

        category_count = TeacherActivityEvent.objects.filter(
            user=user,
            activity_date=activity_date,
            category=category,
        ).count()
        if category_count >= ACTIVITY_CATEGORY_DAILY_CAPS[category]:
            current_level, next_level = resolve_teacher_activity_level(
                total_score=profile.total_score,
                active_day_count=profile.active_day_count,
            )
            return _build_summary_payload(
                total_score=profile.total_score,
                active_day_count=profile.active_day_count,
                last_earned_at=profile.last_earned_at,
                current_level=current_level,
                next_level=next_level,
                awarded=False,
                points_awarded=0,
            )

        day_has_existing_activity = TeacherActivityEvent.objects.filter(
            user=user,
            activity_date=activity_date,
        ).exists()
        try:
            TeacherActivityEvent.objects.create(
                user=user,
                activity_date=activity_date,
                category=category,
                source_key=normalized_source_key,
                points=resolved_points,
                occurred_at=occurred_at,
                related_object_type=object_type,
                related_object_id=object_id,
                metadata=metadata or {},
                is_backfilled=is_backfilled,
            )
        except IntegrityError:
            logger.info(
                "teacher activity duplicate ignored user_id=%s category=%s source_key=%s activity_date=%s",
                getattr(user, "id", None),
                category,
                normalized_source_key,
                activity_date,
            )
            current_level, next_level = resolve_teacher_activity_level(
                total_score=profile.total_score,
                active_day_count=profile.active_day_count,
            )
            return _build_summary_payload(
                total_score=profile.total_score,
                active_day_count=profile.active_day_count,
                last_earned_at=profile.last_earned_at,
                current_level=current_level,
                next_level=next_level,
                awarded=False,
                points_awarded=0,
            )

        profile.total_score = int(profile.total_score or 0) + resolved_points
        if not day_has_existing_activity:
            profile.active_day_count = int(profile.active_day_count or 0) + 1
        if profile.last_earned_at is None or occurred_at >= profile.last_earned_at:
            profile.last_earned_at = occurred_at
        profile.save(update_fields=["total_score", "active_day_count", "last_earned_at", "updated_at"])

    current_level, next_level = resolve_teacher_activity_level(
        total_score=profile.total_score,
        active_day_count=profile.active_day_count,
    )
    return _build_summary_payload(
        total_score=profile.total_score,
        active_day_count=profile.active_day_count,
        last_earned_at=profile.last_earned_at,
        current_level=current_level,
        next_level=next_level,
        awarded=True,
        points_awarded=resolved_points,
    )


def rebuild_teacher_activity_profile(user) -> TeacherActivityProfile | None:
    if not is_teacher_activity_eligible(user):
        TeacherActivityProfile.objects.filter(user=user).delete()
        return None

    aggregates = TeacherActivityEvent.objects.filter(user=user).aggregate(
        total_score=Sum("points"),
        active_day_count=Count("activity_date", distinct=True),
        last_earned_at=Max("occurred_at"),
    )
    profile, _ = TeacherActivityProfile.objects.get_or_create(user=user)
    profile.total_score = int(aggregates.get("total_score") or 0)
    profile.active_day_count = int(aggregates.get("active_day_count") or 0)
    profile.last_earned_at = aggregates.get("last_earned_at")
    profile.save(update_fields=["total_score", "active_day_count", "last_earned_at", "updated_at"])
    return profile


def backfill_teacher_activity() -> dict[str, int]:
    from consent.models import SignatureRequest
    from signatures.models import TrainingSession
    from .models import ProductUsageLog

    stats = {
        "service_use_awarded": 0,
        "service_use_skipped": 0,
        "request_sent_awarded": 0,
        "request_sent_skipped": 0,
        "profiles_rebuilt": 0,
    }
    touched_user_ids: set[int] = set()

    usage_rows = (
        ProductUsageLog.objects.annotate(activity_date=TruncDate("created_at"))
        .values("user_id", "product_id", "activity_date")
        .annotate(first_created=Min("created_at"))
        .order_by("user_id", "activity_date", "first_created", "product_id")
    )
    usage_user_ids = {row["user_id"] for row in usage_rows}
    usage_user_map = {
        profile.user_id: profile.user
        for profile in UserProfile.objects.select_related("user").filter(user_id__in=usage_user_ids)
    }
    for row in usage_rows:
        user = usage_user_map.get(row["user_id"])
        if user is None:
            continue
        result = award_teacher_activity(
            user,
            category=ACTIVITY_CATEGORY_SERVICE_USE,
            source_key=f"product:{row['product_id']}",
            occurred_at=row["first_created"],
            related_object_type="products.product",
            related_object_id=str(row["product_id"]),
            metadata={"source": "backfill"},
            is_backfilled=True,
        )
        touched_user_ids.add(user.id)
        key = "service_use_awarded" if result.get("awarded") else "service_use_skipped"
        stats[key] += 1

    request_rows = []
    consent_rows = SignatureRequest.objects.select_related("created_by").exclude(sent_at__isnull=True)
    for consent_request in consent_rows.iterator():
        request_rows.append(
            (
                consent_request.sent_at,
                consent_request.created_by,
                f"consent:{consent_request.request_id}",
                "consent.signaturerequest",
                str(consent_request.pk),
                {"channel": "consent", "source": "backfill"},
            )
        )

    signature_rows = TrainingSession.objects.select_related("created_by").filter(
        Q(last_shared_at__isnull=False) | Q(is_active=True)
    )
    for session in signature_rows.iterator():
        occurred_at = session.last_shared_at or session.created_at
        if occurred_at is None:
            continue
        request_rows.append(
            (
                occurred_at,
                session.created_by,
                f"signature:{session.uuid}",
                "signatures.trainingsession",
                str(session.uuid),
                {"channel": "signatures", "source": "backfill"},
            )
        )

    request_rows.sort(key=lambda item: (item[0], getattr(item[1], "id", 0), item[2]))
    for occurred_at, user, source_key, object_type, object_id, metadata in request_rows:
        result = award_teacher_activity(
            user,
            category=ACTIVITY_CATEGORY_REQUEST_SENT,
            source_key=source_key,
            occurred_at=occurred_at,
            related_object_type=object_type,
            related_object_id=object_id,
            metadata=metadata,
            is_backfilled=True,
        )
        if getattr(user, "id", None):
            touched_user_ids.add(user.id)
        key = "request_sent_awarded" if result.get("awarded") else "request_sent_skipped"
        stats[key] += 1

    for profile in UserProfile.objects.select_related("user").filter(user_id__in=touched_user_ids):
        rebuilt = rebuild_teacher_activity_profile(profile.user)
        if rebuilt is not None:
            stats["profiles_rebuilt"] += 1

    return stats
