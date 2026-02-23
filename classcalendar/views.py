import logging
import uuid
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from happy_seed.models import HSClassroom
from products.models import Product

from .forms import CalendarEventCreateForm
from .integrations import (
    SOURCE_COLLECT_DEADLINE,
    SOURCE_CONSENT_EXPIRY,
    SOURCE_RESERVATION,
    SOURCE_SETTING_FIELD_MAP,
    SOURCE_SIGNATURES_TRAINING,
    get_or_create_integration_setting,
    serialize_integration_setting,
    sync_user_calendar_integrations,
)
from .models import CalendarEvent, EventPageBlock

SERVICE_ROUTE = "classcalendar:main"
INTEGRATION_SYNC_SESSION_KEY = "classcalendar_last_integration_sync_epoch"
INTEGRATION_SYNC_MIN_INTERVAL_SECONDS = 120

logger = logging.getLogger(__name__)


def _serialize_event(event):
    source_url, source_label = _resolve_integration_source_meta(event)
    return {
        "id": str(event.id),
        "title": event.title,
        "note": _extract_primary_note(event),
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "is_all_day": event.is_all_day,
        "color": event.color or "indigo",
        "source": event.source,
        "visibility": event.visibility,
        "integration_source": event.integration_source,
        "source_url": source_url,
        "source_label": source_label,
        "is_locked": event.is_locked,
    }


def _split_integration_key(raw_key):
    if not raw_key or ":" not in raw_key:
        return "", ""
    return raw_key.split(":", 1)


def _resolve_integration_source_meta(event):
    source = (event.integration_source or "").strip()
    key = (event.integration_key or "").strip()
    _, payload = _split_integration_key(key)

    if not source:
        return "", ""

    if source == SOURCE_COLLECT_DEADLINE:
        if payload:
            try:
                request_uuid = uuid.UUID(payload)
                return (
                    reverse("collect:request_detail", kwargs={"request_id": request_uuid}),
                    "수합 요청으로 이동",
                )
            except (ValueError, TypeError):
                pass
        return reverse("collect:dashboard"), "수합 대시보드로 이동"

    if source == SOURCE_CONSENT_EXPIRY:
        if payload:
            try:
                request_uuid = uuid.UUID(payload)
                return (
                    reverse("consent:detail", kwargs={"request_id": request_uuid}),
                    "동의서 요청으로 이동",
                )
            except (ValueError, TypeError):
                pass
        return reverse("consent:dashboard"), "동의서 대시보드로 이동"

    if source == SOURCE_RESERVATION:
        reservation_parts = key.split(":")
        if len(reservation_parts) >= 4:
            school_slug = reservation_parts[2]
            date_text = reservation_parts[3]
            base_url = reverse("reservations:reservation_index", kwargs={"school_slug": school_slug})
            return f"{base_url}?{urlencode({'date': date_text})}", "예약 화면으로 이동"
        if payload and payload.isdigit():
            try:
                from reservations.models import Reservation

                reservation = (
                    Reservation.objects.select_related("room__school")
                    .filter(id=int(payload), room__school__owner=event.author)
                    .first()
                )
                if reservation:
                    base_url = reverse(
                        "reservations:reservation_index",
                        kwargs={"school_slug": reservation.room.school.slug},
                    )
                    return f"{base_url}?{urlencode({'date': reservation.date.strftime('%Y-%m-%d')})}", "예약 화면으로 이동"
            except Exception:
                logger.exception("[ClassCalendar] reservation source link resolve failed event_id=%s", event.id)
        return reverse("reservations:dashboard_landing"), "예약 대시보드로 이동"

    if source == SOURCE_SIGNATURES_TRAINING:
        if payload:
            try:
                session_uuid = uuid.UUID(payload)
                return (
                    reverse("signatures:detail", kwargs={"uuid": session_uuid}),
                    "서명 연수 상세로 이동",
                )
            except (ValueError, TypeError):
                pass
        return reverse("signatures:list"), "서명 연수 목록으로 이동"

    return "", ""


def _get_integration_setting_for_user(user):
    return get_or_create_integration_setting(user)


def _get_active_classroom_for_user(request):
    classroom_id = request.session.get("active_classroom_id")
    if not classroom_id:
        return None
    return HSClassroom.objects.filter(id=classroom_id, teacher=request.user, is_active=True).first()


def _get_teacher_visible_events(request):
    active_classroom = _get_active_classroom_for_user(request)
    queryset = CalendarEvent.objects.filter(author=request.user)
    if active_classroom:
        queryset = CalendarEvent.objects.filter(Q(author=request.user) | Q(classroom=active_classroom))
    return queryset.select_related("classroom").prefetch_related("blocks").distinct().order_by("start_time", "id")


def _get_owned_event(request, event_id):
    return get_object_or_404(CalendarEvent, id=event_id, author=request.user)


def _extract_primary_note(event):
    text_blocks = sorted(
        (block for block in event.blocks.all() if block.block_type == "text"),
        key=lambda block: (block.order, block.id),
    )
    if not text_blocks:
        return ""
    content = text_blocks[0].content
    if isinstance(content, dict):
        note_text = content.get("text") or content.get("note") or ""
    elif isinstance(content, str):
        note_text = content
    else:
        note_text = ""
    return str(note_text).strip()


def _persist_primary_note(event, note_value):
    note_text = (note_value or "").strip()
    text_blocks = event.blocks.filter(block_type="text").order_by("order", "id")
    primary_block = text_blocks.first()

    if not note_text:
        text_blocks.delete()
        return

    if primary_block:
        primary_block.content = {"text": note_text}
        primary_block.order = 0
        primary_block.save(update_fields=["content", "order"])
        text_blocks.exclude(id=primary_block.id).delete()
        return

    EventPageBlock.objects.create(
        event=event,
        block_type="text",
        content={"text": note_text},
        order=0,
    )


def _sync_integrations_if_needed(request, force=False):
    if not request.user.is_authenticated:
        return
    now_epoch = timezone.now().timestamp()
    last_synced = float(request.session.get(INTEGRATION_SYNC_SESSION_KEY) or 0.0)
    if not force and (now_epoch - last_synced) < INTEGRATION_SYNC_MIN_INTERVAL_SECONDS:
        return
    try:
        sync_user_calendar_integrations(request.user)
        request.session[INTEGRATION_SYNC_SESSION_KEY] = now_epoch
        request.session.modified = True
    except Exception:
        logger.exception(
            "[ClassCalendar] integration sync failed user_id=%s",
            getattr(request.user, "id", None),
        )


def _build_reservation_windows_for_user(user):
    try:
        from reservations.models import School
        from reservations.utils import get_max_booking_date
    except Exception:
        logger.exception(
            "[ClassCalendar] reservation window import failed user_id=%s",
            getattr(user, "id", None),
        )
        return []

    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    windows = []
    schools = School.objects.filter(owner=user).select_related("config").order_by("name")

    for school in schools:
        school_config = getattr(school, "config", None)
        max_booking_date = get_max_booking_date(school)
        available_until = (
            f"{max_booking_date.strftime('%m월 %d일')}까지 예약 가능"
            if max_booking_date
            else "날짜 제한 없이 예약 가능"
        )
        if school_config and school_config.weekly_opening_mode:
            weekday_index = school_config.weekly_opening_weekday
            if weekday_index < 0 or weekday_index > 6:
                weekday_index = 4
            opening_rule = (
                f"매주 {weekdays[weekday_index]}요일 "
                f"{school_config.weekly_opening_hour:02d}:00 다음 주 오픈"
            )
        else:
            opening_rule = "상시 오픈"

        windows.append(
            {
                "school_name": school.name,
                "available_until": available_until,
                "opening_rule": opening_rule,
            }
        )
    return windows


def _integration_event_readonly_response():
    return JsonResponse(
        {
            "status": "error",
            "code": "integration_event_readonly",
            "message": "자동 연동 일정은 원본 서비스에서 수정하거나 삭제해 주세요.",
        },
        status=403,
    )


@login_required
def main_view(request):
    _sync_integrations_if_needed(request)
    integration_setting = _get_integration_setting_for_user(request.user)
    service = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
    context = {
        "service": service,
        "title": service.title if service else "학급 캘린더 (Eduitit Calendar)",
        "events_json": [_serialize_event(event) for event in _get_teacher_visible_events(request)],
        "integration_settings_json": serialize_integration_setting(integration_setting),
        "reservation_windows": _build_reservation_windows_for_user(request.user),
    }
    return render(request, "classcalendar/main.html", context)


@login_required
@require_GET
def api_events(request):
    _sync_integrations_if_needed(request)
    events_data = [_serialize_event(event) for event in _get_teacher_visible_events(request)]
    return JsonResponse({"status": "success", "events": events_data})


def _parse_bool_value(raw_value):
    return str(raw_value).strip().lower() in {"1", "true", "on", "yes"}


@login_required
@require_POST
def api_integration_settings(request):
    integration_setting = _get_integration_setting_for_user(request.user)
    changed_fields = []

    editable_fields = (
        "collect_deadline_enabled",
        "consent_expiry_enabled",
        "reservation_enabled",
        "signatures_training_enabled",
    )
    for field_name in editable_fields:
        if field_name not in request.POST:
            continue
        new_value = _parse_bool_value(request.POST.get(field_name))
        if getattr(integration_setting, field_name) != new_value:
            setattr(integration_setting, field_name, new_value)
            changed_fields.append(field_name)

    if changed_fields:
        integration_setting.save(update_fields=[*changed_fields, "updated_at"])

    disabled_sources = [
        source
        for source, field_name in SOURCE_SETTING_FIELD_MAP.items()
        if not getattr(integration_setting, field_name, True)
    ]
    if disabled_sources:
        CalendarEvent.objects.filter(
            author=request.user,
            integration_source__in=disabled_sources,
            is_locked=True,
        ).delete()

    _sync_integrations_if_needed(request, force=True)
    refreshed = _get_integration_setting_for_user(request.user)
    return JsonResponse(
        {
            "status": "success",
            "settings": serialize_integration_setting(refreshed),
        }
    )


@login_required
@require_POST
def api_create_event(request):
    classroom = _get_active_classroom_for_user(request)

    form = CalendarEventCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    event = CalendarEvent.objects.create(
        title=form.cleaned_data["title"],
        start_time=form.cleaned_data["start_time"],
        end_time=form.cleaned_data["end_time"],
        is_all_day=form.cleaned_data.get("is_all_day", False),
        color=form.cleaned_data.get("color") or "indigo",
        visibility=CalendarEvent.VISIBILITY_TEACHER,
        author=request.user,
        classroom=classroom,
        source=CalendarEvent.SOURCE_LOCAL,
    )
    _persist_primary_note(event, form.cleaned_data.get("note", ""))
    return JsonResponse({"status": "success", "event": _serialize_event(event)}, status=201)


@login_required
@require_POST
def api_update_event(request, event_id):
    event = _get_owned_event(request, event_id)
    if event.is_locked:
        return _integration_event_readonly_response()
    form = CalendarEventCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    event.title = form.cleaned_data["title"]
    event.start_time = form.cleaned_data["start_time"]
    event.end_time = form.cleaned_data["end_time"]
    event.is_all_day = form.cleaned_data.get("is_all_day", False)
    event.color = form.cleaned_data.get("color") or "indigo"
    event.visibility = CalendarEvent.VISIBILITY_TEACHER
    event.source = CalendarEvent.SOURCE_LOCAL
    event.save(
        update_fields=[
            "title",
            "start_time",
            "end_time",
            "is_all_day",
            "color",
            "visibility",
            "source",
            "updated_at",
        ]
    )
    _persist_primary_note(event, form.cleaned_data.get("note", ""))
    return JsonResponse({"status": "success", "event": _serialize_event(event)})


@login_required
@require_POST
def api_delete_event(request, event_id):
    event = _get_owned_event(request, event_id)
    if event.is_locked:
        return _integration_event_readonly_response()
    event_id_str = str(event.id)
    event.delete()
    return JsonResponse({"status": "success", "deleted_id": event_id_str})
