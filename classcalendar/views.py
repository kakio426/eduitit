import logging
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
from .models import CalendarCollaborator, CalendarEvent, CalendarIntegrationSetting, EventPageBlock

SERVICE_ROUTE = "classcalendar:main"
INTEGRATION_SYNC_SESSION_KEY = "classcalendar_last_integration_sync_epoch"
INTEGRATION_SYNC_MIN_INTERVAL_SECONDS = 120

User = get_user_model()
logger = logging.getLogger(__name__)


def _display_user_name(user):
    return user.get_full_name() or user.username


def _parse_bool_value(raw_value):
    return str(raw_value).strip().lower() in {"1", "true", "on", "yes"}


def _permission_denied_response(message):
    return JsonResponse(
        {
            "status": "error",
            "code": "permission_denied",
            "message": message,
        },
        status=403,
    )


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


def _serialize_event(event, *, current_user_id, editable_owner_ids):
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
        "calendar_owner_id": str(event.author_id),
        "calendar_owner_name": _display_user_name(event.author),
        "is_shared_calendar": event.author_id != current_user_id,
        "can_edit": event.author_id in editable_owner_ids,
    }


def _get_integration_setting_for_user(user):
    return get_or_create_integration_setting(user)


def _get_active_classroom_for_user(request):
    classroom_id = request.session.get("active_classroom_id")
    if not classroom_id:
        return None
    return HSClassroom.objects.filter(id=classroom_id, teacher=request.user, is_active=True).first()


def _get_calendar_access_for_user(user):
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


def _build_owner_collaborator_rows(user):
    relations = (
        CalendarCollaborator.objects.filter(owner=user)
        .select_related("collaborator")
        .order_by("collaborator__username")
    )
    return [
        {
            "id": relation.collaborator_id,
            "name": _display_user_name(relation.collaborator),
            "username": relation.collaborator.username,
            "email": relation.collaborator.email,
            "can_edit": bool(relation.can_edit),
        }
        for relation in relations
    ]


def _build_calendar_owner_options(user, editable_owner_ids):
    owners = {
        owner.id: owner
        for owner in User.objects.filter(id__in=editable_owner_ids).only("id", "username", "first_name", "last_name")
    }
    options = []

    if user.id in owners:
        options.append(
            {
                "id": str(user.id),
                "label": "내 캘린더",
                "is_default": True,
            }
        )

    for owner_id in sorted([owner_id for owner_id in owners.keys() if owner_id != user.id], key=lambda v: owners[v].username):
        owner = owners[owner_id]
        options.append(
            {
                "id": str(owner.id),
                "label": f"{_display_user_name(owner)} 캘린더",
                "is_default": False,
            }
        )

    if not options:
        options.append(
            {
                "id": str(user.id),
                "label": "내 캘린더",
                "is_default": True,
            }
        )

    return options


def _resolve_event_owner_for_create(request_user, requested_owner_id, editable_owner_ids):
    raw_owner_id = str(requested_owner_id or "").strip()
    if not raw_owner_id:
        return request_user

    owner_id = next((oid for oid in editable_owner_ids if str(oid) == raw_owner_id), None)
    if owner_id is None:
        return None
    if owner_id == request_user.id:
        return request_user
    return User.objects.filter(id=owner_id).first()


def _get_teacher_visible_events(request, visible_owner_ids):
    active_classroom = _get_active_classroom_for_user(request)
    query = Q(author_id__in=visible_owner_ids)
    if active_classroom:
        query |= Q(classroom=active_classroom)
    return (
        CalendarEvent.objects.filter(query)
        .select_related("author", "classroom")
        .prefetch_related("blocks")
        .distinct()
        .order_by("start_time", "id")
    )


def _get_editable_event(request, event_id, editable_owner_ids):
    return get_object_or_404(
        CalendarEvent.objects.select_related("author").prefetch_related("blocks"),
        id=event_id,
        author_id__in=editable_owner_ids,
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


def _build_share_url(request, share_uuid):
    return request.build_absolute_uri(reverse("classcalendar:shared", kwargs={"share_uuid": share_uuid}))


def _build_shared_event_groups(events):
    grouped = []
    current_date = None
    current_group = None

    for event in events:
        start_local = timezone.localtime(event.start_time)
        end_local = timezone.localtime(event.end_time)
        event_date = start_local.date()

        if current_date != event_date:
            current_date = event_date
            current_group = {"date": event_date, "events": []}
            grouped.append(current_group)

        current_group["events"].append(
            {
                "id": str(event.id),
                "title": event.title,
                "note": _extract_primary_note(event),
                "start_time": start_local,
                "end_time": end_local,
                "is_all_day": event.is_all_day,
                "color": event.color or "indigo",
            }
        )

    return grouped


@login_required
def main_view(request):
    _sync_integrations_if_needed(request)
    visible_owner_ids, editable_owner_ids, incoming_calendars = _get_calendar_access_for_user(request.user)
    integration_setting = _get_integration_setting_for_user(request.user)
    service = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
    context = {
        "service": service,
        "title": service.title if service else "학급 캘린더 (Eduitit Calendar)",
        "events_json": [
            _serialize_event(
                event,
                current_user_id=request.user.id,
                editable_owner_ids=editable_owner_ids,
            )
            for event in _get_teacher_visible_events(request, visible_owner_ids)
        ],
        "integration_settings_json": serialize_integration_setting(integration_setting),
        "reservation_windows": _build_reservation_windows_for_user(request.user),
        "share_enabled": bool(integration_setting.share_enabled),
        "share_url": _build_share_url(request, integration_setting.share_uuid),
        "calendar_owner_options_json": _build_calendar_owner_options(request.user, editable_owner_ids),
        "owner_collaborators": _build_owner_collaborator_rows(request.user),
        "incoming_calendars": incoming_calendars,
    }
    return render(request, "classcalendar/main.html", context)


@login_required
@require_POST
def collaborator_add(request):
    lookup = (request.POST.get("collaborator_query") or "").strip()
    if not lookup:
        messages.error(request, "협업자로 추가할 사용자의 가입시 적었던 이메일을 입력해 주세요.")
        return redirect("classcalendar:main")

    collaborator = (
        User.objects.filter(email__iexact=lookup)
        .only("id", "username", "email", "first_name", "last_name")
        .first()
    )
    if not collaborator:
        messages.error(request, "해당 이메일의 사용자를 찾지 못했습니다. 가입시 적었던 이메일인지 확인해 주세요.")
        return redirect("classcalendar:main")
    if collaborator.id == request.user.id:
        messages.error(request, "본인은 협업자로 추가할 수 없습니다.")
        return redirect("classcalendar:main")

    can_edit = _parse_bool_value(request.POST.get("can_edit", "true"))
    relation, created = CalendarCollaborator.objects.update_or_create(
        owner=request.user,
        collaborator=collaborator,
        defaults={"can_edit": can_edit},
    )
    if created:
        messages.success(request, f"{_display_user_name(collaborator)} 님을 협업자로 추가했습니다.")
    else:
        mode_text = "편집 가능" if relation.can_edit else "읽기 전용"
        messages.info(request, f"{_display_user_name(collaborator)} 님 협업 권한을 {mode_text}으로 업데이트했습니다.")
    return redirect("classcalendar:main")


@login_required
@require_POST
def collaborator_remove(request, collaborator_id):
    relation = (
        CalendarCollaborator.objects.filter(owner=request.user, collaborator_id=collaborator_id)
        .select_related("collaborator")
        .first()
    )
    if not relation:
        messages.error(request, "협업자 정보를 찾지 못했습니다.")
        return redirect("classcalendar:main")

    collaborator_name = _display_user_name(relation.collaborator)
    relation.delete()
    messages.info(request, f"{collaborator_name} 님의 협업 권한을 해제했습니다.")
    return redirect("classcalendar:main")


@login_required
@require_POST
def share_enable(request):
    setting = _get_integration_setting_for_user(request.user)
    if not setting.share_enabled:
        setting.share_enabled = True
        setting.save(update_fields=["share_enabled", "updated_at"])
    messages.success(request, "공유 링크를 활성화했습니다.")
    return redirect("classcalendar:main")


@login_required
@require_POST
def share_disable(request):
    setting = _get_integration_setting_for_user(request.user)
    if setting.share_enabled:
        setting.share_enabled = False
        setting.save(update_fields=["share_enabled", "updated_at"])
    messages.info(request, "공유 링크를 비활성화했습니다.")
    return redirect("classcalendar:main")


@login_required
@require_POST
def share_rotate(request):
    setting = _get_integration_setting_for_user(request.user)
    setting.share_uuid = uuid.uuid4()
    setting.share_enabled = True
    setting.save(update_fields=["share_uuid", "share_enabled", "updated_at"])
    messages.success(request, "공유 링크를 재발급했습니다.")
    return redirect("classcalendar:main")


@require_GET
def shared_view(request, share_uuid):
    setting = (
        CalendarIntegrationSetting.objects.select_related("user")
        .filter(share_uuid=share_uuid, share_enabled=True)
        .first()
    )
    if not setting:
        return render(request, "classcalendar/shared_unavailable.html", status=404)

    window_start = timezone.now() - timedelta(days=7)
    events = (
        CalendarEvent.objects.filter(author=setting.user, end_time__gte=window_start)
        .prefetch_related("blocks")
        .order_by("start_time", "id")
    )
    grouped_events = _build_shared_event_groups(events)

    context = {
        "owner_name": _display_user_name(setting.user),
        "grouped_events": grouped_events,
        "event_count": sum(len(group["events"]) for group in grouped_events),
        "generated_at": timezone.localtime(),
    }
    return render(request, "classcalendar/shared.html", context)


@login_required
@require_GET
def api_events(request):
    force_sync = _parse_bool_value(request.GET.get("force_sync", "false"))
    _sync_integrations_if_needed(request, force=force_sync)
    visible_owner_ids, editable_owner_ids, _ = _get_calendar_access_for_user(request.user)
    events_data = [
        _serialize_event(
            event,
            current_user_id=request.user.id,
            editable_owner_ids=editable_owner_ids,
        )
        for event in _get_teacher_visible_events(request, visible_owner_ids)
    ]
    return JsonResponse({"status": "success", "events": events_data})


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
    _, editable_owner_ids, _ = _get_calendar_access_for_user(request.user)
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

    event_owner = _resolve_event_owner_for_create(
        request_user=request.user,
        requested_owner_id=form.cleaned_data.get("calendar_owner_id"),
        editable_owner_ids=editable_owner_ids,
    )
    if not event_owner:
        return _permission_denied_response("선택한 캘린더에 일정을 추가할 권한이 없습니다.")

    classroom = _get_active_classroom_for_user(request) if event_owner.id == request.user.id else None
    event = CalendarEvent.objects.create(
        title=form.cleaned_data["title"],
        start_time=form.cleaned_data["start_time"],
        end_time=form.cleaned_data["end_time"],
        is_all_day=form.cleaned_data.get("is_all_day", False),
        color=form.cleaned_data.get("color") or "indigo",
        visibility=CalendarEvent.VISIBILITY_TEACHER,
        author=event_owner,
        classroom=classroom,
        source=CalendarEvent.SOURCE_LOCAL,
    )
    _persist_primary_note(event, form.cleaned_data.get("note", ""))
    event = CalendarEvent.objects.select_related("author").prefetch_related("blocks").get(id=event.id)
    return JsonResponse(
        {
            "status": "success",
            "event": _serialize_event(
                event,
                current_user_id=request.user.id,
                editable_owner_ids=editable_owner_ids,
            ),
        },
        status=201,
    )


@login_required
@require_POST
def api_update_event(request, event_id):
    _, editable_owner_ids, _ = _get_calendar_access_for_user(request.user)
    event = _get_editable_event(request, event_id, editable_owner_ids)
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
    event.refresh_from_db()
    return JsonResponse(
        {
            "status": "success",
            "event": _serialize_event(
                event,
                current_user_id=request.user.id,
                editable_owner_ids=editable_owner_ids,
            ),
        }
    )


@login_required
@require_POST
def api_delete_event(request, event_id):
    _, editable_owner_ids, _ = _get_calendar_access_for_user(request.user)
    event = _get_editable_event(request, event_id, editable_owner_ids)
    if event.is_locked:
        return _integration_event_readonly_response()
    event_id_str = str(event.id)
    event.delete()
    return JsonResponse({"status": "success", "deleted_id": event_id_str})
