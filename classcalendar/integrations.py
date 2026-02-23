import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import CalendarEvent, CalendarIntegrationSetting

logger = logging.getLogger(__name__)

SOURCE_COLLECT_DEADLINE = "collect_deadline"
SOURCE_CONSENT_EXPIRY = "consent_expiry"
SOURCE_RESERVATION = "reservation"
SOURCE_SIGNATURES_TRAINING = "signatures_training"

INTEGRATION_SOURCES = (
    SOURCE_COLLECT_DEADLINE,
    SOURCE_CONSENT_EXPIRY,
    SOURCE_RESERVATION,
)

SOURCE_SETTING_FIELD_MAP = {
    SOURCE_COLLECT_DEADLINE: "collect_deadline_enabled",
    SOURCE_CONSENT_EXPIRY: "consent_expiry_enabled",
    SOURCE_RESERVATION: "reservation_enabled",
    SOURCE_SIGNATURES_TRAINING: "signatures_training_enabled",
}

RESERVATION_LOOKBACK_DAYS = 1
RESERVATION_LOOKAHEAD_DAYS = 60


def get_or_create_integration_setting(user):
    setting, _ = CalendarIntegrationSetting.objects.get_or_create(user=user)
    return setting


def serialize_integration_setting(setting):
    return {
        "collect_deadline_enabled": bool(setting.collect_deadline_enabled),
        "consent_expiry_enabled": bool(setting.consent_expiry_enabled),
        "reservation_enabled": bool(setting.reservation_enabled),
        "signatures_training_enabled": bool(setting.signatures_training_enabled),
    }


def is_integration_enabled(user, source):
    field_name = SOURCE_SETTING_FIELD_MAP.get(source)
    if not field_name:
        return True
    setting = get_or_create_integration_setting(user)
    return bool(getattr(setting, field_name, True))


def _ensure_local_datetime(value):
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value)


def _aware_datetime_from_date(date_value, time_value):
    return timezone.make_aware(
        datetime.combine(date_value, time_value),
        timezone.get_current_timezone(),
    )


def _parse_time_range(period_time_text):
    if not period_time_text or "-" not in period_time_text:
        return None, None
    start_text, end_text = [segment.strip() for segment in period_time_text.split("-", 1)]
    try:
        start_time = datetime.strptime(start_text, "%H:%M").time()
        end_time = datetime.strptime(end_text, "%H:%M").time()
    except ValueError:
        return None, None
    return start_time, end_time


def _default_period_times(period):
    safe_period = max(1, int(period))
    start_hour = min(22, 8 + safe_period)
    start_time = time(hour=start_hour, minute=0)
    end_dt = datetime.combine(timezone.localdate(), start_time) + timedelta(minutes=40)
    return start_time, end_dt.time()


def _upsert_integration_event(
    *,
    author,
    integration_source,
    integration_key,
    title,
    start_time,
    end_time,
    color,
    is_all_day=False,
):
    safe_start = _ensure_local_datetime(start_time)
    safe_end = _ensure_local_datetime(end_time)
    if safe_end <= safe_start:
        safe_end = safe_start + timedelta(minutes=30)

    CalendarEvent.objects.update_or_create(
        author=author,
        integration_source=integration_source,
        integration_key=integration_key,
        defaults={
            "title": (title or "")[:200],
            "start_time": safe_start,
            "end_time": safe_end,
            "is_all_day": is_all_day,
            "color": color,
            "visibility": CalendarEvent.VISIBILITY_TEACHER,
            "source": CalendarEvent.SOURCE_LOCAL,
            "classroom": None,
            "is_locked": True,
        },
    )


def _cleanup_missing_integration_events(author, source, keep_keys):
    queryset = CalendarEvent.objects.filter(
        author=author,
        integration_source=source,
        is_locked=True,
    )
    if keep_keys:
        queryset = queryset.exclude(integration_key__in=keep_keys)
    queryset.delete()


def _sync_collect_deadline_events(author, seen_keys):
    try:
        from collect.models import CollectionRequest
    except Exception:
        logger.exception("[ClassCalendar] collect import failed")
        return

    requests = (
        CollectionRequest.objects.filter(creator=author, deadline__isnull=False)
        .exclude(status="archived")
        .only("id", "title", "deadline", "status")
    )

    for request_item in requests:
        if not request_item.deadline:
            continue
        integration_key = f"collect:{request_item.id}"
        title_prefix = "[수합 마감]"
        if request_item.status == "closed":
            title_prefix = "[수합 마감완료]"
        _upsert_integration_event(
            author=author,
            integration_source=SOURCE_COLLECT_DEADLINE,
            integration_key=integration_key,
            title=f"{title_prefix} {request_item.title}",
            start_time=request_item.deadline,
            end_time=request_item.deadline + timedelta(minutes=30),
            color="amber",
        )
        seen_keys[SOURCE_COLLECT_DEADLINE].add(integration_key)


def _sync_consent_expiry_events(author, seen_keys):
    try:
        from consent.models import SignatureRequest
    except Exception:
        logger.exception("[ClassCalendar] consent import failed")
        return

    requests = SignatureRequest.objects.filter(
        created_by=author,
        status=SignatureRequest.STATUS_SENT,
        sent_at__isnull=False,
    ).only("request_id", "title", "sent_at", "link_expire_days")

    for request_item in requests:
        expires_at = request_item.link_expires_at
        if not expires_at:
            continue
        integration_key = f"consent:{request_item.request_id}"
        _upsert_integration_event(
            author=author,
            integration_source=SOURCE_CONSENT_EXPIRY,
            integration_key=integration_key,
            title=f"[동의서 만료] {request_item.title}",
            start_time=expires_at,
            end_time=expires_at + timedelta(minutes=30),
            color="indigo",
        )
        seen_keys[SOURCE_CONSENT_EXPIRY].add(integration_key)


def _sync_reservation_events(author, seen_keys):
    try:
        from reservations.models import Reservation
    except Exception:
        logger.exception("[ClassCalendar] reservations import failed")
        return

    today = timezone.localdate()
    start_date = today - timedelta(days=RESERVATION_LOOKBACK_DAYS)
    end_date = today + timedelta(days=RESERVATION_LOOKAHEAD_DAYS)

    reservations = (
        Reservation.objects.filter(
            room__school__owner=author,
            date__gte=start_date,
            date__lte=end_date,
        )
        .select_related("room", "room__school", "room__school__config")
        .order_by("date", "period", "id")
    )

    period_slot_cache = {}
    for reservation in reservations:
        school_id = reservation.room.school_id
        if school_id not in period_slot_cache:
            school_config = getattr(reservation.room.school, "config", None)
            if school_config:
                slots = school_config.get_period_slots()
                period_slot_cache[school_id] = {
                    slot["id"]: {
                        "label": slot.get("label") or f'{slot["id"]}교시',
                        "time": slot.get("time") or "",
                    }
                    for slot in slots
                }
            else:
                period_slot_cache[school_id] = {}

        slot_info = period_slot_cache[school_id].get(reservation.period, {})
        period_label = slot_info.get("label") or f"{reservation.period}교시"
        start_time, end_time = _parse_time_range(slot_info.get("time"))
        if not start_time or not end_time:
            start_time, end_time = _default_period_times(reservation.period)

        start_dt = _aware_datetime_from_date(reservation.date, start_time)
        end_dt = _aware_datetime_from_date(reservation.date, end_time)
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(minutes=40)

        name_suffix = f"{reservation.grade}-{reservation.class_no} {reservation.name}"
        integration_key = f"reservation:{reservation.id}:{reservation.room.school.slug}:{reservation.date:%Y-%m-%d}"
        _upsert_integration_event(
            author=author,
            integration_source=SOURCE_RESERVATION,
            integration_key=integration_key,
            title=f"[예약] {reservation.room.school.name} · {reservation.room.name} · {period_label} · {name_suffix}",
            start_time=start_dt,
            end_time=end_dt,
            color="rose",
        )
        seen_keys[SOURCE_RESERVATION].add(integration_key)


def sync_user_calendar_integrations(author):
    setting = get_or_create_integration_setting(author)
    seen_keys = defaultdict(set)

    if setting.collect_deadline_enabled:
        _sync_collect_deadline_events(author, seen_keys)
    else:
        _cleanup_missing_integration_events(
            author=author,
            source=SOURCE_COLLECT_DEADLINE,
            keep_keys=set(),
        )

    if setting.consent_expiry_enabled:
        _sync_consent_expiry_events(author, seen_keys)
    else:
        _cleanup_missing_integration_events(
            author=author,
            source=SOURCE_CONSENT_EXPIRY,
            keep_keys=set(),
        )

    if setting.reservation_enabled:
        _sync_reservation_events(author, seen_keys)
    else:
        _cleanup_missing_integration_events(
            author=author,
            source=SOURCE_RESERVATION,
            keep_keys=set(),
        )

    for source in INTEGRATION_SOURCES:
        _cleanup_missing_integration_events(
            author=author,
            source=source,
            keep_keys=seen_keys[source],
        )

    if not setting.signatures_training_enabled:
        _cleanup_missing_integration_events(
            author=author,
            source=SOURCE_SIGNATURES_TRAINING,
            keep_keys=set(),
        )
