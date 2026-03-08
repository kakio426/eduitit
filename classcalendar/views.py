import logging
import hashlib
import json
import mimetypes
import os
import uuid
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import File
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin

from core.active_classroom import get_active_classroom_for_request
from products.models import Product

from .forms import CalendarEventCreateForm, MessageCaptureCommitForm, MessageCaptureParseForm
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
from .message_capture import parse_message_capture_draft
from .models import (
    CalendarCollaborator,
    CalendarEvent,
    CalendarEventAttachment,
    CalendarIntegrationSetting,
    CalendarMessageCapture,
    CalendarMessageCaptureAttachment,
    EventPageBlock,
)

SERVICE_ROUTE = "classcalendar:main"
INTEGRATION_SYNC_SESSION_KEY = "classcalendar_last_integration_sync_epoch"
INTEGRATION_SYNC_MIN_INTERVAL_SECONDS = 120
RETENTION_NOTICE_TITLE = "[안내] 자동 정리 정책 안내"
SHEETBOOK_RECENT_SHEETBOOK_ID_SESSION_KEY = "sheetbook_recent_sheetbook_id"
SHEETBOOK_SOURCE_SOURCES = {"sheetbook_action_calendar", "sheetbook_schedule_sync", "sheetbook_calendar_embed", "sheetbook_message_capture"}

User = get_user_model()
logger = logging.getLogger(__name__)

MESSAGE_CAPTURE_MAX_FILES = 5
MESSAGE_CAPTURE_MAX_FILE_BYTES = 8 * 1024 * 1024
MESSAGE_CAPTURE_ALLOWED_EXTENSIONS = {
    "txt",
    "md",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "heic",
    "csv",
    "xls",
    "xlsx",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "hwp",
    "hwpx",
}
MESSAGE_CAPTURE_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/x-hwp",
    "application/haansofthwp",
    "application/octet-stream",
}
MESSAGE_CAPTURE_ALLOWED_MIME_PREFIXES = (
    "image/",
)


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


def _feature_disabled_response(message):
    return JsonResponse(
        {
            "status": "error",
            "code": "feature_disabled",
            "message": message,
        },
        status=403,
    )


def _split_csv_setting(raw_value):
    if isinstance(raw_value, (list, tuple, set)):
        values = raw_value
    else:
        values = str(raw_value or "").split(",")
    return [str(item).strip() for item in values if str(item).strip()]


def _get_message_capture_rollout_value(setting_name, env_name):
    if hasattr(settings, setting_name):
        return getattr(settings, setting_name)
    return os.environ.get(env_name, "")


def _is_message_capture_enabled_for_user(user):
    feature_enabled = bool(getattr(settings, "FEATURE_MESSAGE_CAPTURE_ENABLED", False))
    if not feature_enabled:
        return False

    usernames = {
        value.lower()
        for value in _split_csv_setting(
            _get_message_capture_rollout_value(
                "FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES",
                "FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES",
            )
        )
    }
    emails = {
        value.lower()
        for value in _split_csv_setting(
            _get_message_capture_rollout_value(
                "FEATURE_MESSAGE_CAPTURE_ALLOWLIST_EMAILS",
                "FEATURE_MESSAGE_CAPTURE_ALLOWLIST_EMAILS",
            )
        )
    }
    user_ids = set(
        _split_csv_setting(
            _get_message_capture_rollout_value(
                "FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USER_IDS",
                "FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USER_IDS",
            )
        )
    )

    # Allowlist가 비어 있으면 기본 비활성 상태를 유지한다.
    if not usernames and not emails and not user_ids:
        return False

    if str(user.id) in user_ids:
        return True
    if user.username and user.username.lower() in usernames:
        return True
    if user.email and user.email.lower() in emails:
        return True
    return False


def _build_message_capture_limits_payload():
    return {
        "max_files": MESSAGE_CAPTURE_MAX_FILES,
        "max_file_bytes": MESSAGE_CAPTURE_MAX_FILE_BYTES,
        "allowed_extensions": sorted(MESSAGE_CAPTURE_ALLOWED_EXTENSIONS),
    }


def _serialize_message_capture_attachment(attachment):
    return {
        "id": str(attachment.id),
        "original_name": attachment.original_name,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "is_selected": bool(attachment.is_selected),
    }


def _serialize_message_capture(capture, *, warnings=None, reused=False):
    parse_payload = capture.parse_payload if isinstance(capture.parse_payload, dict) else {}
    warning_list = warnings if warnings is not None else parse_payload.get("warnings") or []
    confidence_label = parse_payload.get("confidence_label") or "low"
    needs_confirmation = (
        confidence_label == "low"
        or capture.parse_status != CalendarMessageCapture.ParseStatus.PARSED
    )

    return {
        "status": "success",
        "capture_id": str(capture.id),
        "parse_status": capture.parse_status,
        "confidence_score": float(capture.confidence_score or 0),
        "confidence_label": confidence_label,
        "draft_event": {
            "title": capture.extracted_title or "메시지에서 만든 일정",
            "start_time": capture.extracted_start_time.isoformat() if capture.extracted_start_time else "",
            "end_time": capture.extracted_end_time.isoformat() if capture.extracted_end_time else "",
            "is_all_day": bool(capture.extracted_is_all_day),
            "todo_summary": capture.extracted_todo_summary or "",
            "priority": capture.extracted_priority or "normal",
            "needs_confirmation": needs_confirmation,
            "parse_evidence": parse_payload.get("evidence") or {},
        },
        "attachments": [
            _serialize_message_capture_attachment(attachment)
            for attachment in capture.attachments.all().order_by("created_at", "id")
        ],
        "warnings": warning_list,
        "reused": bool(reused),
    }


def _guess_upload_mime_type(uploaded_file):
    hinted_type = (getattr(uploaded_file, "content_type", "") or "").strip().lower()
    if hinted_type:
        return hinted_type
    guessed, _ = mimetypes.guess_type(uploaded_file.name or "")
    return (guessed or "application/octet-stream").lower()


def _extract_upload_extension(uploaded_file):
    _, extension = os.path.splitext(uploaded_file.name or "")
    return extension.lower().lstrip(".")


def _is_allowed_message_capture_file(uploaded_file):
    extension = _extract_upload_extension(uploaded_file)
    mime_type = _guess_upload_mime_type(uploaded_file)

    extension_allowed = extension in MESSAGE_CAPTURE_ALLOWED_EXTENSIONS
    mime_allowed = mime_type in MESSAGE_CAPTURE_ALLOWED_MIME_TYPES or any(
        mime_type.startswith(prefix) for prefix in MESSAGE_CAPTURE_ALLOWED_MIME_PREFIXES
    )
    return extension_allowed and mime_allowed


def _calculate_upload_sha256(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return digest.hexdigest()


def _extract_request_payload(request):
    content_type = (request.content_type or "").split(";")[0].strip().lower()
    if content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return {}
    return request.POST


def _extract_selected_attachment_ids(payload):
    if hasattr(payload, "getlist"):
        return [value for value in payload.getlist("selected_attachment_ids") if str(value).strip()]
    selected_ids = payload.get("selected_attachment_ids") or []
    if not isinstance(selected_ids, list):
        return []
    return [str(value).strip() for value in selected_ids if str(value).strip()]


def _copy_capture_attachments_to_event(event, capture_attachments, *, uploaded_by):
    saved_attachments = []
    warnings = []
    for index, capture_attachment in enumerate(capture_attachments):
        source_file = None
        try:
            source_file = capture_attachment.file
            source_file.open("rb")
            event_attachment = CalendarEventAttachment(
                event=event,
                uploaded_by=uploaded_by,
                source_capture_attachment=capture_attachment,
                original_name=(capture_attachment.original_name or "")[:255],
                mime_type=(capture_attachment.mime_type or "")[:120],
                size_bytes=capture_attachment.size_bytes or 0,
                checksum_sha256=(capture_attachment.checksum_sha256 or "")[:64],
                sort_order=index,
            )
            source_name = os.path.basename(source_file.name or "") or f"capture-{capture_attachment.id}"
            event_attachment.file.save(source_name, File(source_file), save=False)
            event_attachment.save()
            saved_attachments.append(
                {
                    "id": str(event_attachment.id),
                    "original_name": event_attachment.original_name,
                    "size_bytes": event_attachment.size_bytes,
                }
            )
        except Exception:
            warnings.append(
                f"{capture_attachment.original_name or '첨부파일'} 복사 중 오류가 발생해 건너뛰었습니다."
            )
            logger.exception(
                "[ClassCalendar] message capture attachment copy failed capture_attachment_id=%s event_id=%s",
                capture_attachment.id,
                event.id,
            )
        finally:
            try:
                if source_file:
                    source_file.close()
            except Exception:
                pass
    return saved_attachments, warnings


def _count_message_capture_manual_edits(capture, cleaned_data):
    edit_count = 0
    if (capture.extracted_title or "") != (cleaned_data.get("title") or ""):
        edit_count += 1
    if (capture.extracted_todo_summary or "") != (cleaned_data.get("todo_summary") or ""):
        edit_count += 1
    if capture.extracted_start_time != cleaned_data.get("start_time"):
        edit_count += 1
    if capture.extracted_end_time != cleaned_data.get("end_time"):
        edit_count += 1
    if bool(capture.extracted_is_all_day) != bool(cleaned_data.get("is_all_day", False)):
        edit_count += 1
    return edit_count


def _split_integration_key(raw_key):
    if not raw_key or ":" not in raw_key:
        return "", ""
    return raw_key.split(":", 1)


def _resolve_sheetbook_context(user, raw_sheetbook_id, raw_tab_id):
    try:
        sheetbook_id = int(raw_sheetbook_id or 0)
        tab_id = int(raw_tab_id or 0)
    except (TypeError, ValueError):
        return None
    if not sheetbook_id or not tab_id:
        return None
    try:
        from sheetbook.models import SheetTab, Sheetbook
    except Exception:
        logger.exception("[ClassCalendar] failed to import sheetbook models for context resolution")
        return None

    sheetbook = Sheetbook.objects.filter(owner=user, id=sheetbook_id).only("id", "title").first()
    if not sheetbook:
        return None
    tab = SheetTab.objects.filter(sheetbook_id=sheetbook.id, id=tab_id).only("id", "name", "tab_type").first()
    if not tab:
        return None
    detail_url = reverse("sheetbook:detail", kwargs={"pk": sheetbook.id})
    detail_url = f"{detail_url}?{urlencode({'tab': tab.id, 'source': 'calendar'})}"
    return {
        "sheetbook_id": sheetbook.id,
        "sheetbook_title": sheetbook.title,
        "tab_id": tab.id,
        "tab_name": tab.name,
        "tab_type": tab.tab_type,
        "detail_url": detail_url,
    }


def _resolve_sheetbook_source_meta(event, *, current_user_id):
    source = (event.integration_source or "").strip()
    if source not in SHEETBOOK_SOURCE_SOURCES or event.author_id != current_user_id:
        return None
    key_parts = str(event.integration_key or "").split(":")
    if len(key_parts) < 2:
        return None
    context = _resolve_sheetbook_context(event.author, key_parts[0], key_parts[1])
    if not context:
        return None
    return {
        "source_sheetbook_id": context["sheetbook_id"],
        "source_sheetbook_title": context["sheetbook_title"],
        "source_tab_id": context["tab_id"],
        "source_tab_name": context["tab_name"],
        "source_tab_type": context["tab_type"],
        "source_detail_url": context["detail_url"],
        "source_url": context["detail_url"],
        "source_label": "연결된 수첩으로 돌아가기",
    }


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
                    .filter(id=int(payload), created_by=event.author)
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

    if source == 'textbooks':
        if payload:
            return (
                reverse("textbooks:detail", kwargs={"pk": payload}),
                "수업 자료실로 이동",
            )

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


def _resolve_attachment_url(attachment):
    try:
        return attachment.file.url if attachment.file else ""
    except (ValueError, OSError):
        return ""


def _serialize_event_attachment(attachment):
    return {
        "id": str(attachment.id),
        "original_name": attachment.original_name or "첨부파일",
        "mime_type": attachment.mime_type or "",
        "size_bytes": attachment.size_bytes or 0,
        "url": _resolve_attachment_url(attachment),
    }


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
    sheetbook_source_meta = _resolve_sheetbook_source_meta(event, current_user_id=current_user_id) or {}
    if sheetbook_source_meta.get("source_url"):
        source_url = sheetbook_source_meta.get("source_url") or source_url
        source_label = sheetbook_source_meta.get("source_label") or source_label
    attachments = list(event.attachments.all())
    attachments.sort(key=lambda attachment: (attachment.sort_order, attachment.id))
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
        "source_sheetbook_id": sheetbook_source_meta.get("source_sheetbook_id") or 0,
        "source_sheetbook_title": sheetbook_source_meta.get("source_sheetbook_title") or "",
        "source_tab_id": sheetbook_source_meta.get("source_tab_id") or 0,
        "source_tab_name": sheetbook_source_meta.get("source_tab_name") or "",
        "source_tab_type": sheetbook_source_meta.get("source_tab_type") or "",
        "source_detail_url": sheetbook_source_meta.get("source_detail_url") or "",
        "is_locked": event.is_locked,
        "calendar_owner_id": str(event.author_id),
        "calendar_owner_name": _display_user_name(event.author),
        "is_shared_calendar": event.author_id != current_user_id,
        "can_edit": event.author_id in editable_owner_ids,
        "attachments": [
            _serialize_event_attachment(attachment)
            for attachment in attachments
        ],
    }


def _get_integration_setting_for_user(user):
    return get_or_create_integration_setting(user)


def _get_active_classroom_for_user(request):
    return get_active_classroom_for_request(request)


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
                "label": "내 달력",
                "is_default": True,
            }
        )

    for owner_id in sorted([owner_id for owner_id in owners.keys() if owner_id != user.id], key=lambda v: owners[v].username):
        owner = owners[owner_id]
        options.append(
            {
                "id": str(owner.id),
                "label": f"{_display_user_name(owner)} 달력",
                "is_default": False,
            }
        )

    if not options:
        options.append(
            {
                "id": str(user.id),
                "label": "내 달력",
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
        .prefetch_related("blocks", "attachments")
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
                "entry_url": reverse(
                    "reservations:reservation_index",
                    kwargs={"school_slug": school.slug},
                ),
            }
        )
    return windows


def _build_retention_notice_text():
    return "\n".join(
        [
            "자동 정리 정책 안내",
            "",
            "1) 고용량 파일(90일): 수합 제출 파일/양식, 동의서 merged PDF",
            "2) 나머지 데이터(1년): 예약/수합마감/서명연수/동의서 관련 일반 데이터",
            "",
            "중요: 기간이 지나면 복구가 어려울 수 있으니 필요한 자료는 미리 보관해 주세요.",
            "필요하면 이 안내 일정은 직접 삭제해도 됩니다.",
        ]
    )


def _ensure_retention_notice_event_for_user(user, setting):
    if setting.retention_notice_event_seeded_at:
        return

    existing = CalendarEvent.objects.filter(
        author=user,
        title=RETENTION_NOTICE_TITLE,
        source=CalendarEvent.SOURCE_LOCAL,
        is_locked=False,
    ).first()
    if existing:
        setting.retention_notice_event_seeded_at = timezone.now()
        setting.save(update_fields=["retention_notice_event_seeded_at", "updated_at"])
        return

    today = timezone.localdate()
    start_time = timezone.make_aware(
        datetime.combine(today, time(hour=8, minute=0)),
        timezone.get_current_timezone(),
    )
    end_time = start_time + timedelta(minutes=20)
    event = CalendarEvent.objects.create(
        title=RETENTION_NOTICE_TITLE,
        author=user,
        start_time=start_time,
        end_time=end_time,
        is_all_day=False,
        visibility=CalendarEvent.VISIBILITY_TEACHER,
        source=CalendarEvent.SOURCE_LOCAL,
        color="amber",
        classroom=None,
        is_locked=False,
    )
    _persist_primary_note(event, _build_retention_notice_text())

    setting.retention_notice_event_seeded_at = timezone.now()
    setting.save(update_fields=["retention_notice_event_seeded_at", "updated_at"])


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


def _resolve_sheetbook_calendar_entry_for_user(request, user):
    result = {
        "sheetbook_enabled": bool(getattr(settings, "SHEETBOOK_ENABLED", False)),
        "sheetbook_exists": False,
        "sheetbook_title": "",
        "sheetbook_entry_url": "",
        "sheetbook_index_url": "",
        "sheetbook_context_label": "",
    }
    if not result["sheetbook_enabled"]:
        return result

    try:
        from sheetbook.models import Sheetbook, SheetTab
    except Exception:
        logger.exception(
            "[ClassCalendar] sheetbook import failed for bridge user_id=%s",
            getattr(user, "id", None),
        )
        return result

    try:
        result["sheetbook_index_url"] = reverse("sheetbook:index")
    except Exception:
        return result

    recent_sheetbook_id = 0
    try:
        recent_sheetbook_id = int(request.session.get(SHEETBOOK_RECENT_SHEETBOOK_ID_SESSION_KEY) or 0)
    except (TypeError, ValueError):
        recent_sheetbook_id = 0

    sheetbooks = list(
        Sheetbook.objects.filter(owner=user)
        .prefetch_related("tabs")
        .order_by("-updated_at", "-id")
    )
    if not sheetbooks:
        return result

    resolved_sheetbooks = []
    for sheetbook in sheetbooks:
        ordered_tabs = sorted(sheetbook.tabs.all(), key=lambda item: (item.sort_order, item.id))
        preferred_calendar_tab_id = getattr(sheetbook, "preferred_calendar_tab_id", 0) or 0
        explicit_calendar_tab = None
        if preferred_calendar_tab_id:
            explicit_calendar_tab = next(
                (
                    tab for tab in ordered_tabs
                    if tab.id == preferred_calendar_tab_id and tab.tab_type == SheetTab.TYPE_CALENDAR
                ),
                None,
            )
        calendar_tab = explicit_calendar_tab or next(
            (tab for tab in ordered_tabs if tab.tab_type == SheetTab.TYPE_CALENDAR),
            None,
        )
        if calendar_tab is None:
            continue
        resolved_sheetbooks.append(
            {
                "sheetbook": sheetbook,
                "calendar_tab": calendar_tab,
                "is_explicit": explicit_calendar_tab is not None,
            }
        )

    if not resolved_sheetbooks:
        return result

    prioritized_sheetbooks = []
    prioritized_ids = set()

    explicit_entry = next((item for item in resolved_sheetbooks if item["is_explicit"]), None)
    if explicit_entry is not None:
        prioritized_sheetbooks.append(explicit_entry)
        prioritized_ids.add(explicit_entry["sheetbook"].id)

    if recent_sheetbook_id:
        recent_entry = next(
            (item for item in resolved_sheetbooks if item["sheetbook"].id == recent_sheetbook_id),
            None,
        )
        if recent_entry is not None and recent_entry["sheetbook"].id not in prioritized_ids:
            prioritized_sheetbooks.append(recent_entry)
            prioritized_ids.add(recent_entry["sheetbook"].id)

    for item in resolved_sheetbooks:
        sheetbook_id = item["sheetbook"].id
        if sheetbook_id in prioritized_ids:
            continue
        prioritized_sheetbooks.append(item)
        prioritized_ids.add(sheetbook_id)

    selected_entry = prioritized_sheetbooks[0]
    selected_sheetbook = selected_entry["sheetbook"]
    detail_url = reverse("sheetbook:detail", kwargs={"pk": selected_sheetbook.id})
    detail_url = f"{detail_url}?tab={selected_entry['calendar_tab'].id}"

    if selected_entry["is_explicit"]:
        context_label = "직접 연결한 수첩"
    elif selected_sheetbook.id == recent_sheetbook_id:
        context_label = "최근 열어본 수첩"
    else:
        context_label = "최근 수정한 수첩"

    result.update(
        {
            "sheetbook_exists": True,
            "sheetbook_title": selected_sheetbook.title,
            "sheetbook_entry_url": detail_url,
            "sheetbook_context_label": context_label,
        }
    )
    return result


@login_required
def main_entry(request):
    if not getattr(settings, "SHEETBOOK_ENABLED", False):
        return redirect("classcalendar:main")

    bridge_context = _resolve_sheetbook_calendar_entry_for_user(request, request.user)
    if bridge_context.get("sheetbook_entry_url"):
        return redirect(bridge_context["sheetbook_entry_url"])
    return redirect("classcalendar:main")


@login_required
def legacy_main_redirect(request):
    return redirect("classcalendar:main")


@login_required
@xframe_options_sameorigin
def main_view(request):
    _sync_integrations_if_needed(request)
    embedded_sheetbook_context = None
    if request.GET.get("embedded") == "sheetbook":
        embedded_sheetbook_context = _resolve_sheetbook_context(
            request.user,
            request.GET.get("sheetbook_id"),
            request.GET.get("tab_id"),
        )
    visible_owner_ids, editable_owner_ids, incoming_calendars = _get_calendar_access_for_user(request.user)
    integration_setting = _get_integration_setting_for_user(request.user)
    _ensure_retention_notice_event_for_user(request.user, integration_setting)
    service = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
    context = {
        "service": service,
        "title": service.title if service else "달력 (Eduitit Calendar)",
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
        "show_retention_notice_banner": integration_setting.retention_notice_banner_dismissed_at is None,
        "message_capture_enabled": _is_message_capture_enabled_for_user(request.user),
        "message_capture_limits_json": _build_message_capture_limits_payload(),
        "embedded_sheetbook_context": embedded_sheetbook_context,
        "embedded_sheetbook_context_json": embedded_sheetbook_context or {},
        "is_embedded_in_sheetbook": bool(embedded_sheetbook_context),
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
def api_dismiss_retention_notice(request):
    integration_setting = _get_integration_setting_for_user(request.user)
    if not integration_setting.retention_notice_banner_dismissed_at:
        integration_setting.retention_notice_banner_dismissed_at = timezone.now()
        integration_setting.save(update_fields=["retention_notice_banner_dismissed_at", "updated_at"])
    return JsonResponse({"status": "success"})


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
        return _permission_denied_response("선택한 달력에 일정을 추가할 권한이 없습니다.")

    classroom = _get_active_classroom_for_user(request) if event_owner.id == request.user.id else None
    source_context = _resolve_sheetbook_context(
        request.user,
        request.POST.get("source_sheetbook_id"),
        request.POST.get("source_tab_id"),
    )
    create_kwargs = {
        "title": form.cleaned_data["title"],
        "start_time": form.cleaned_data["start_time"],
        "end_time": form.cleaned_data["end_time"],
        "is_all_day": form.cleaned_data.get("is_all_day", False),
        "color": form.cleaned_data.get("color") or "indigo",
        "visibility": CalendarEvent.VISIBILITY_TEACHER,
        "author": event_owner,
        "classroom": classroom,
        "source": CalendarEvent.SOURCE_LOCAL,
    }
    if source_context and event_owner.id == request.user.id:
        create_kwargs["integration_source"] = "sheetbook_calendar_embed"
        create_kwargs["integration_key"] = f"{source_context['sheetbook_id']}:{source_context['tab_id']}:{uuid.uuid4().hex[:8]}"
    event = CalendarEvent.objects.create(**create_kwargs)
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


@login_required
@require_POST
def api_message_capture_parse(request):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 바로 등록 기능이 아직 활성화되지 않았습니다.")
    parse_started_at = timezone.now()

    form = MessageCaptureParseForm(request.POST)
    if not form.is_valid():
        logger.warning(
            "[ClassCalendar][MessageCapture] parse_failed user_id=%s reason=form_invalid",
            request.user.id,
        )
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "errors": form.errors.get_json_data(),
                "message": "입력값을 확인해 주세요.",
            },
            status=400,
        )

    raw_text = form.cleaned_data.get("raw_text") or ""
    source_hint = (form.cleaned_data.get("source_hint") or "unknown").strip()[:30] or "unknown"
    idempotency_key = (form.cleaned_data.get("idempotency_key") or uuid.uuid4().hex).strip()[:64] or uuid.uuid4().hex
    uploaded_files = request.FILES.getlist("files")

    if not raw_text.strip() and not uploaded_files:
        logger.warning(
            "[ClassCalendar][MessageCapture] parse_failed user_id=%s reason=empty_input",
            request.user.id,
        )
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "message": "메시지 텍스트 또는 첨부파일 중 하나는 반드시 입력해 주세요.",
            },
            status=400,
        )

    if len(uploaded_files) > MESSAGE_CAPTURE_MAX_FILES:
        logger.warning(
            "[ClassCalendar][MessageCapture] parse_failed user_id=%s reason=too_many_files files=%s",
            request.user.id,
            len(uploaded_files),
        )
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "message": f"첨부파일은 최대 {MESSAGE_CAPTURE_MAX_FILES}개까지 업로드할 수 있습니다.",
            },
            status=400,
        )

    existing_capture = (
        CalendarMessageCapture.objects.filter(author=request.user, idempotency_key=idempotency_key)
        .prefetch_related("attachments")
        .first()
    )
    if existing_capture:
        parse_elapsed_ms = int((timezone.now() - parse_started_at).total_seconds() * 1000)
        logger.info(
            "[ClassCalendar][MessageCapture] parse_reused user_id=%s capture_id=%s parse_status=%s confidence=%.2f files=%s elapsed_ms=%s",
            request.user.id,
            existing_capture.id,
            existing_capture.parse_status,
            float(existing_capture.confidence_score or 0),
            existing_capture.attachments.count(),
            parse_elapsed_ms,
        )
        return JsonResponse(_serialize_message_capture(existing_capture, reused=True))

    for uploaded_file in uploaded_files:
        file_size = int(getattr(uploaded_file, "size", 0) or 0)
        if file_size > MESSAGE_CAPTURE_MAX_FILE_BYTES:
            logger.warning(
                "[ClassCalendar][MessageCapture] parse_failed user_id=%s reason=file_too_large file=%s size=%s",
                request.user.id,
                uploaded_file.name,
                file_size,
            )
            return JsonResponse(
                {
                    "status": "error",
                    "code": "file_too_large",
                    "message": f"{uploaded_file.name} 파일이 용량 제한({MESSAGE_CAPTURE_MAX_FILE_BYTES // (1024 * 1024)}MB)을 초과했습니다.",
                },
                status=413,
            )
        if not _is_allowed_message_capture_file(uploaded_file):
            logger.warning(
                "[ClassCalendar][MessageCapture] parse_failed user_id=%s reason=invalid_file_type file=%s",
                request.user.id,
                uploaded_file.name,
            )
            return JsonResponse(
                {
                    "status": "error",
                    "code": "validation_error",
                    "message": f"{uploaded_file.name} 파일 형식은 지원하지 않습니다.",
                },
                status=400,
            )

    parsed = parse_message_capture_draft(
        raw_text,
        now=timezone.now(),
        has_files=bool(uploaded_files),
    )
    parse_payload = {
        "parser_version": "mvp-v1",
        "confidence_label": parsed["confidence_label"],
        "warnings": parsed["warnings"],
        "evidence": parsed["evidence"],
    }

    with transaction.atomic():
        try:
            capture = CalendarMessageCapture.objects.create(
                author=request.user,
                raw_text=raw_text,
                normalized_text=parsed["normalized_text"],
                source_hint=source_hint,
                parse_status=parsed["parse_status"],
                confidence_score=parsed["confidence_score"],
                extracted_title=(parsed["extracted_title"] or "")[:200],
                extracted_start_time=parsed["extracted_start_time"],
                extracted_end_time=parsed["extracted_end_time"],
                extracted_is_all_day=bool(parsed["extracted_is_all_day"]),
                extracted_priority=parsed["extracted_priority"] or CalendarMessageCapture.Priority.NORMAL,
                extracted_todo_summary=parsed["extracted_todo_summary"] or "",
                parse_payload=parse_payload,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            capture = (
                CalendarMessageCapture.objects.filter(author=request.user, idempotency_key=idempotency_key)
                .prefetch_related("attachments")
                .first()
            )
            if capture:
                return JsonResponse(_serialize_message_capture(capture, reused=True))
            raise

        for uploaded_file in uploaded_files:
            checksum = _calculate_upload_sha256(uploaded_file)
            CalendarMessageCaptureAttachment.objects.create(
                capture=capture,
                uploaded_by=request.user,
                file=uploaded_file,
                original_name=(os.path.basename(uploaded_file.name or "") or "attachment")[:255],
                mime_type=_guess_upload_mime_type(uploaded_file)[:120],
                size_bytes=int(getattr(uploaded_file, "size", 0) or 0),
                checksum_sha256=checksum,
                is_selected=True,
            )

    capture = CalendarMessageCapture.objects.prefetch_related("attachments").get(id=capture.id)
    parse_elapsed_ms = int((timezone.now() - parse_started_at).total_seconds() * 1000)
    logger.info(
        "[ClassCalendar][MessageCapture] parse_result user_id=%s capture_id=%s parse_status=%s confidence=%.2f files=%s warnings=%s elapsed_ms=%s",
        request.user.id,
        capture.id,
        capture.parse_status,
        float(capture.confidence_score or 0),
        capture.attachments.count(),
        len((capture.parse_payload or {}).get("warnings") or []),
        parse_elapsed_ms,
    )
    return JsonResponse(_serialize_message_capture(capture), status=201)


@login_required
@require_POST
def api_message_capture_commit(request, capture_id):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 바로 등록 기능이 아직 활성화되지 않았습니다.")
    commit_started_at = timezone.now()

    payload = _extract_request_payload(request)
    form = MessageCaptureCommitForm(payload)
    if not form.is_valid():
        logger.warning(
            "[ClassCalendar][MessageCapture] commit_failed user_id=%s capture_id=%s reason=form_invalid",
            request.user.id,
            capture_id,
        )
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "errors": form.errors.get_json_data(),
                "message": "필수 입력값을 확인해 주세요.",
            },
            status=400,
        )

    capture = get_object_or_404(
        CalendarMessageCapture.objects.select_related("author", "committed_event").prefetch_related("attachments"),
        id=capture_id,
        author=request.user,
    )

    if capture.committed_event_id:
        logger.warning(
            "[ClassCalendar][MessageCapture] commit_failed user_id=%s capture_id=%s reason=duplicate",
            request.user.id,
            capture.id,
        )
        return JsonResponse(
            {
                "status": "error",
                "code": "duplicate_request",
                "message": "이미 저장이 완료된 메시지입니다.",
                "event_id": str(capture.committed_event_id),
            },
            status=409,
        )

    confidence_label = ""
    if isinstance(capture.parse_payload, dict):
        confidence_label = (capture.parse_payload.get("confidence_label") or "").strip().lower()
    confirm_low_confidence = form.cleaned_data.get("confirm_low_confidence", False)
    if confidence_label == "low" and not confirm_low_confidence:
        logger.warning(
            "[ClassCalendar][MessageCapture] commit_failed user_id=%s capture_id=%s reason=needs_confirmation",
            request.user.id,
            capture.id,
        )
        return JsonResponse(
            {
                "status": "error",
                "code": "needs_confirmation",
                "message": "신뢰도가 낮아 저장 전에 확인 완료 체크가 필요합니다.",
            },
            status=422,
        )

    selected_attachment_ids = set(_extract_selected_attachment_ids(payload))
    capture_attachments = list(capture.attachments.all().order_by("created_at", "id"))
    if selected_attachment_ids:
        capture_attachments = [
            attachment
            for attachment in capture_attachments
            if str(attachment.id) in selected_attachment_ids
        ]

    changed_attachments = []
    for attachment in capture.attachments.all():
        is_selected = (not selected_attachment_ids) or (str(attachment.id) in selected_attachment_ids)
        if attachment.is_selected != is_selected:
            attachment.is_selected = is_selected
            changed_attachments.append(attachment)
    for attachment in changed_attachments:
        attachment.save(update_fields=["is_selected"])

    _, editable_owner_ids, _ = _get_calendar_access_for_user(request.user)
    manual_edit_count = 0
    selected_attachment_count = len(capture_attachments)
    attachment_warnings = []
    processing_ms = 0
    with transaction.atomic():
        capture_for_update = CalendarMessageCapture.objects.select_for_update().get(id=capture.id, author=request.user)
        if capture_for_update.committed_event_id:
            logger.warning(
                "[ClassCalendar][MessageCapture] commit_failed user_id=%s capture_id=%s reason=duplicate_locked",
                request.user.id,
                capture_for_update.id,
            )
            return JsonResponse(
                {
                    "status": "error",
                    "code": "duplicate_request",
                    "message": "이미 저장이 완료된 메시지입니다.",
                    "event_id": str(capture_for_update.committed_event_id),
                },
                status=409,
            )
        manual_edit_count = _count_message_capture_manual_edits(capture_for_update, form.cleaned_data)
        processing_ms = int((timezone.now() - capture_for_update.created_at).total_seconds() * 1000)

        classroom = _get_active_classroom_for_user(request)
        source_context = _resolve_sheetbook_context(
            request.user,
            payload.get("source_sheetbook_id"),
            payload.get("source_tab_id"),
        )
        create_kwargs = {
            "title": form.cleaned_data["title"],
            "start_time": form.cleaned_data["start_time"],
            "end_time": form.cleaned_data["end_time"],
            "is_all_day": form.cleaned_data.get("is_all_day", False),
            "color": form.cleaned_data.get("color") or "indigo",
            "visibility": CalendarEvent.VISIBILITY_TEACHER,
            "author": request.user,
            "classroom": classroom,
            "source": CalendarEvent.SOURCE_LOCAL,
        }
        if source_context:
            create_kwargs["integration_source"] = "sheetbook_message_capture"
            create_kwargs["integration_key"] = f"{source_context['sheetbook_id']}:{source_context['tab_id']}:{capture_for_update.id}"
        event = CalendarEvent.objects.create(**create_kwargs)
        _persist_primary_note(event, form.cleaned_data.get("todo_summary", ""))
        copied_attachments, attachment_warnings = _copy_capture_attachments_to_event(
            event,
            capture_attachments,
            uploaded_by=request.user,
        )

        capture_for_update.committed_event = event
        capture_for_update.committed_at = timezone.now()
        capture_for_update.extracted_title = form.cleaned_data["title"]
        capture_for_update.extracted_start_time = form.cleaned_data["start_time"]
        capture_for_update.extracted_end_time = form.cleaned_data["end_time"]
        capture_for_update.extracted_is_all_day = form.cleaned_data.get("is_all_day", False)
        capture_for_update.extracted_todo_summary = form.cleaned_data.get("todo_summary", "")
        capture_for_update.parse_status = CalendarMessageCapture.ParseStatus.PARSED
        capture_for_update.save(
            update_fields=[
                "committed_event",
                "committed_at",
                "extracted_title",
                "extracted_start_time",
                "extracted_end_time",
                "extracted_is_all_day",
                "extracted_todo_summary",
                "parse_status",
                "updated_at",
            ]
        )

    event = CalendarEvent.objects.select_related("author").prefetch_related("blocks").get(id=event.id)
    commit_elapsed_ms = int((timezone.now() - commit_started_at).total_seconds() * 1000)
    logger.info(
        "[ClassCalendar][MessageCapture] commit_result user_id=%s capture_id=%s event_id=%s manual_edits=%s manual_edit_rate=%.2f selected_attachments=%s attachment_warnings=%s processing_ms=%s elapsed_ms=%s",
        request.user.id,
        capture.id,
        event.id,
        manual_edit_count,
        (manual_edit_count / 5.0),
        selected_attachment_count,
        len(attachment_warnings),
        processing_ms,
        commit_elapsed_ms,
    )
    return JsonResponse(
        {
            "status": "success",
            "event": _serialize_event(
                event,
                current_user_id=request.user.id,
                editable_owner_ids=editable_owner_ids,
            ),
            "attachments": copied_attachments,
            "warnings": attachment_warnings,
            "sheetbook_sync": {
                "status": "pending",
                "enabled": bool(getattr(settings, "SHEETBOOK_ENABLED", False)),
            },
        },
        status=201,
    )
