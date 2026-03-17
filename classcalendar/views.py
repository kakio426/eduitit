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
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
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
from .message_capture_llm import refine_message_capture_candidates
from .message_capture_classifier import (
    DEFAULT_ASSIST_THRESHOLD,
    predict_item_type as predict_message_capture_item_type,
)
from .calendar_scope import (
    get_calendar_access_for_user as resolve_calendar_access_for_user,
    get_visible_events_queryset,
    get_visible_tasks_queryset,
)
from .today_memos import build_today_execution_context, normalize_today_focus
from .models import (
    CalendarCollaborator,
    CalendarEvent,
    CalendarEventAttachment,
    CalendarIntegrationSetting,
    CalendarMessageCapture,
    CalendarMessageCaptureAttachment,
    CalendarMessageCaptureCandidate,
    CalendarTask,
    EventPageBlock,
)

SERVICE_ROUTE = "classcalendar:main"
INTEGRATION_SYNC_SESSION_KEY = "classcalendar_last_integration_sync_epoch"
INTEGRATION_SYNC_MIN_INTERVAL_SECONDS = 120
SHEETBOOK_RECENT_SHEETBOOK_ID_SESSION_KEY = "sheetbook_recent_sheetbook_id"
SHEETBOOK_SOURCE_SOURCES = {"sheetbook_action_calendar", "sheetbook_schedule_sync", "sheetbook_calendar_embed", "sheetbook_message_capture"}
HOME_CALENDAR_ANCHOR = "home-calendar"
HOME_CALENDAR_QUERY_KEYS = ("date", "action", "open_event", "open_task", "focus")

User = get_user_model()
logger = logging.getLogger(__name__)

MESSAGE_CAPTURE_MAX_FILES = 3
MESSAGE_CAPTURE_MAX_FILE_BYTES = 8 * 1024 * 1024
MESSAGE_CAPTURE_ALLOWED_EXTENSIONS = {
    "pdf",
    "xls",
    "xlsx",
    "doc",
    "docx",
    "hwp",
    "hwpx",
}
MESSAGE_CAPTURE_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/x-hwp",
    "application/haansofthwp",
    "application/octet-stream",
}
MESSAGE_CAPTURE_ALLOWED_MIME_PREFIXES = ()
MESSAGE_CAPTURE_RULE_VERSION = "mvp-v3"
MESSAGE_CAPTURE_CLASSIFIER_ASSIST_THRESHOLD = float(
    getattr(settings, "FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST_THRESHOLD", DEFAULT_ASSIST_THRESHOLD)
)
MESSAGE_CAPTURE_ARCHIVE_PAGE_SIZE = 20
MESSAGE_CAPTURE_WORKFLOW_FILTER_KEYS = {"kept", "dated", "linked", "done"}
DIRECT_HUB_INTEGRATION_SOURCES = {
    SOURCE_COLLECT_DEADLINE,
    SOURCE_CONSENT_EXPIRY,
    SOURCE_RESERVATION,
    SOURCE_SIGNATURES_TRAINING,
}
HUB_TONE_PRIORITY = {
    "warning": 3,
    "neutral": 2,
    "done": 1,
}
HUB_SERVICE_LABELS = {
    "event": "일정",
    "task": "할 일",
    "collect": "수합",
    "signature": "사인",
    "consent": "동의서",
    "reservation": "예약",
    "message": "메시지",
}


def _reverse_calendar_surface(alias_name, fallback_name):
    for route_name in (alias_name, fallback_name):
        try:
            return reverse(route_name)
        except NoReverseMatch:
            continue
    return ""


def _build_home_calendar_surface_url(request, *, include_request_state=True):
    home_url = reverse("home")
    preserved_pairs = []
    if include_request_state:
        for key in HOME_CALENDAR_QUERY_KEYS:
            for value in request.GET.getlist(key):
                if str(value or "").strip():
                    preserved_pairs.append((key, value))
        if str(request.GET.get("panel") or "").strip().lower() == "today-memos" and not any(
            key == "focus" for key, _ in preserved_pairs
        ):
            preserved_pairs.append(("focus", "memos"))
    query_string = urlencode(preserved_pairs, doseq=True)
    if query_string:
        return f"{home_url}?{query_string}#{HOME_CALENDAR_ANCHOR}"
    return f"{home_url}#{HOME_CALENDAR_ANCHOR}"


def _prime_calendar_surface_state(request):
    _sync_integrations_if_needed(request)
    _get_calendar_access_for_user(request.user)


def _redirect_to_home_calendar_surface(request):
    _prime_calendar_surface_state(request)
    response = redirect(_build_home_calendar_surface_url(request))
    return _apply_workspace_cache_headers(response)


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


def _apply_workspace_cache_headers(response):
    response["Cache-Control"] = "private, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


def _apply_sensitive_cache_headers(response):
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


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


def _get_message_capture_rollout_mode():
    raw_mode = str(
        _get_message_capture_rollout_value(
            "FEATURE_MESSAGE_CAPTURE_ROLLOUT_MODE",
            "FEATURE_MESSAGE_CAPTURE_ROLLOUT_MODE",
        )
        or ""
    ).strip().lower()
    if raw_mode in {"allowlist", "limited", "beta"}:
        return "allowlist"
    return "all"


def _is_message_capture_enabled_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return False

    feature_enabled = bool(getattr(settings, "FEATURE_MESSAGE_CAPTURE_ENABLED", False))
    if not feature_enabled:
        return False

    if _get_message_capture_rollout_mode() != "allowlist":
        return True

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


def _is_message_capture_item_types_enabled_for_user(user):
    return _is_message_capture_enabled_for_user(user) and bool(
        getattr(settings, "FEATURE_MESSAGE_CAPTURE_ITEM_TYPES", False)
    )



def _is_message_capture_classifier_shadow_enabled_for_user(user):
    return _is_message_capture_item_types_enabled_for_user(user) and bool(
        getattr(settings, "FEATURE_MESSAGE_CAPTURE_CLASSIFIER_SHADOW", False)
    )



def _is_message_capture_classifier_assist_enabled_for_user(user):
    return _is_message_capture_item_types_enabled_for_user(user) and bool(
        getattr(settings, "FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST", False)
    )



def _build_message_capture_limits_payload():
    return {
        "max_files": MESSAGE_CAPTURE_MAX_FILES,
        "max_file_bytes": MESSAGE_CAPTURE_MAX_FILE_BYTES,
        "allowed_extensions": sorted(MESSAGE_CAPTURE_ALLOWED_EXTENSIONS),
    }


def _build_message_capture_urls_payload():
    capture_placeholder = "00000000-0000-0000-0000-000000000000"
    return {
        "parse": reverse("classcalendar:api_message_capture_parse"),
        "save": reverse("classcalendar:api_message_capture_save"),
        "archive": reverse("classcalendar:api_message_capture_archive"),
        "parse_saved_template": reverse(
            "classcalendar:api_message_capture_parse_saved",
            kwargs={"capture_id": capture_placeholder},
        ).replace(capture_placeholder, "__capture_id__"),
        "archive_detail_template": reverse(
            "classcalendar:api_message_capture_archive_detail",
            kwargs={"capture_id": capture_placeholder},
        ).replace(capture_placeholder, "__capture_id__"),
        "link_template": reverse(
            "classcalendar:api_message_capture_link",
            kwargs={"capture_id": capture_placeholder},
        ).replace(capture_placeholder, "__capture_id__"),
        "commit_template": reverse(
            "classcalendar:api_message_capture_commit",
            kwargs={"capture_id": capture_placeholder},
        ).replace(capture_placeholder, "__capture_id__"),
        "complete_template": reverse(
            "classcalendar:api_message_capture_complete",
            kwargs={"capture_id": capture_placeholder},
        ).replace(capture_placeholder, "__capture_id__"),
        "delete_template": reverse(
            "classcalendar:api_message_capture_delete",
            kwargs={"capture_id": capture_placeholder},
        ).replace(capture_placeholder, "__capture_id__"),
        "messagebox_main": build_messagebox_main_url(),
    }


def build_message_capture_ui_context(user):
    enabled = bool(getattr(user, "is_authenticated", False)) and _is_message_capture_enabled_for_user(user)
    return {
        "enabled": enabled,
        "item_types_enabled": enabled and _is_message_capture_item_types_enabled_for_user(user),
        "limits": _build_message_capture_limits_payload(),
        "urls": _build_message_capture_urls_payload(),
    }


def build_messagebox_home_card_context(user):
    enabled = bool(getattr(user, "is_authenticated", False)) and _is_message_capture_enabled_for_user(user)
    card = {
        "enabled": enabled,
        "title": "업무 메시지 보관함",
        "primary_action_label": "새 메시지 보관",
        "url": build_messagebox_main_url(),
        "incomplete_count": 0,
        "linked_count": 0,
    }
    if not enabled:
        return card

    queryset = _build_message_capture_archive_queryset(user)
    incomplete_count = queryset.filter(completed_at__isnull=True).count()
    linked_count = sum(1 for capture in queryset if _message_capture_has_linked_item(capture))
    card.update(
        {
            "incomplete_count": incomplete_count,
            "linked_count": linked_count,
        }
    )
    return card


def build_messagebox_main_url(*, capture_id=""):
    try:
        base_url = reverse("messagebox:main")
    except NoReverseMatch:
        return ""
    capture_value = str(capture_id or "").strip()
    if not capture_value:
        return base_url
    return f"{base_url}?capture={capture_value}"


def _build_message_capture_deep_link(capture_id):
    capture_value = str(capture_id or "").strip()
    if not capture_value:
        return ""
    return build_messagebox_main_url(capture_id=capture_value)


def _build_message_capture_delete_link(capture_id):
    capture_value = str(capture_id or "").strip()
    if not capture_value:
        return ""
    try:
        return reverse("classcalendar:api_message_capture_delete", kwargs={"capture_id": capture_value})
    except NoReverseMatch:
        return ""


def _build_calendar_item_link(*, event=None, task=None):
    try:
        base_url = reverse("calendar_main")
    except NoReverseMatch:
        try:
            base_url = reverse("classcalendar:main")
        except NoReverseMatch:
            return ""

    params = []
    if event is not None:
        params.append(("open_event", str(event.id)))
        event_date = timezone.localtime(event.start_time).date().isoformat()
        params.append(("date", event_date))
    if task is not None:
        params.append(("open_task", str(task.id)))
        if task.due_at:
            params.append(("date", timezone.localtime(task.due_at).date().isoformat()))
    query_string = urlencode(params, doseq=True)
    return f"{base_url}?{query_string}" if query_string else base_url


def _build_calendar_delete_link(*, event=None, task=None):
    try:
        if event is not None:
            return reverse("classcalendar:api_delete_event", kwargs={"event_id": event.id})
        if task is not None:
            return reverse("classcalendar:api_delete_task", kwargs={"task_id": task.id})
    except NoReverseMatch:
        return ""
    return ""


def _serialize_message_capture_manual_date_value(value):
    if not value:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


def _merge_message_capture_manual_inputs(payload, *, manual_date=None, manual_note=""):
    base_payload = payload.copy() if isinstance(payload, dict) else {}
    manual_date_value = _serialize_message_capture_manual_date_value(manual_date)
    manual_note_value = str(manual_note or "").strip()
    if manual_date_value:
        base_payload["manual_date"] = manual_date_value
    else:
        base_payload.pop("manual_date", None)
    if manual_note_value:
        base_payload["manual_note"] = manual_note_value
    else:
        base_payload.pop("manual_note", None)
    return base_payload


def _update_message_capture_manual_inputs(capture, *, manual_date=None, manual_note=""):
    next_payload = _merge_message_capture_manual_inputs(
        capture.parse_payload,
        manual_date=manual_date,
        manual_note=manual_note,
    )
    if next_payload == (capture.parse_payload if isinstance(capture.parse_payload, dict) else {}):
        return capture
    capture.parse_payload = next_payload
    capture.save(update_fields=["parse_payload", "updated_at"])
    return capture


def _resolve_related_message_capture(capture_owner):
    related_manager = getattr(capture_owner, "message_captures", None)
    if related_manager is None:
        return None
    try:
        captures = list(related_manager.all())
    except Exception:
        return None
    return captures[0] if captures else None


def _build_related_message_capture_meta(capture_owner):
    capture = _resolve_related_message_capture(capture_owner)
    if capture is None:
        return {"message_capture_id": "", "message_capture_url": ""}
    return {
        "message_capture_id": str(capture.id),
        "message_capture_url": _build_message_capture_deep_link(capture.id),
    }


def _safe_related_event(source):
    if source is None or not getattr(source, "committed_event_id", None):
        return None
    try:
        return getattr(source, "committed_event", None)
    except CalendarEvent.DoesNotExist:
        return None


def _safe_related_task(source):
    if source is None or not getattr(source, "committed_task_id", None):
        return None
    try:
        return getattr(source, "committed_task", None)
    except CalendarTask.DoesNotExist:
        return None


def _locked_message_capture_candidates_queryset(capture):
    # Postgres rejects FOR UPDATE on nullable-side outer joins, so lock the
    # candidate rows first and let committed_event resolve lazily per row.
    return CalendarMessageCaptureCandidate.objects.select_for_update().filter(capture=capture)


def _serialize_temporal_value(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _to_local_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def _parse_local_date_value(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
        return timezone.make_aware(
            datetime.combine(parsed_date, time.min),
            timezone.get_current_timezone(),
        )


def _normalize_hub_datetime(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value)


def _serialize_hub_datetime(value):
    safe_value = _normalize_hub_datetime(value)
    return safe_value.isoformat() if safe_value else ""


def _build_hub_date_key(*values):
    for value in values:
        local_value = _normalize_hub_datetime(value) if isinstance(value, datetime) else None
        if local_value:
            return local_value.date().isoformat()
    return ""


def _manual_date_to_linked_for_at(manual_date):
    if isinstance(manual_date, datetime):
        return _normalize_hub_datetime(manual_date)
    parsed = _parse_local_date_value(manual_date)
    if parsed is None:
        return None
    return _normalize_hub_datetime(parsed)


def _choose_default_selected_date_from_items(events, tasks, *, fallback_date):
    future_dates = []
    past_dates = []

    for event in events:
        start_date = _to_local_date(getattr(event, "start_time", None))
        end_date = _to_local_date(getattr(event, "end_time", None)) or start_date
        if start_date is None:
            continue
        if end_date is None or end_date < start_date:
            end_date = start_date
        if start_date <= fallback_date <= end_date:
            return fallback_date.isoformat()
        if start_date > fallback_date:
            future_dates.append(start_date)
        elif end_date < fallback_date:
            past_dates.append(end_date)

    for task in tasks:
        due_date = _to_local_date(getattr(task, "due_at", None))
        if due_date is None:
            continue
        if due_date == fallback_date:
            return fallback_date.isoformat()
        if due_date > fallback_date:
            future_dates.append(due_date)
        else:
            past_dates.append(due_date)

    if future_dates:
        return min(future_dates).isoformat()
    if past_dates:
        return max(past_dates).isoformat()
    return fallback_date.isoformat()


def _choose_default_selected_date(events, tasks, *, fallback_date):
    return _choose_default_selected_date_from_items(events, tasks, fallback_date=fallback_date)


def _serialize_json_safe(value):
    if isinstance(value, dict):
        return {str(key): _serialize_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_json_safe(item) for item in value]
    return _serialize_temporal_value(value)



def _candidate_kind_badge_text(kind):
    normalized_kind = str(kind or "event").strip().lower()
    labels = {
        "event": "행사",
        "meeting": "회의",
        "class": "수업",
        "consulting": "상담",
        "training": "연수",
        "exam": "평가",
        "deadline": "마감",
        "prep": "준비",
    }
    return labels.get(normalized_kind, labels["event"])


def _candidate_kind_color(kind):
    normalized_kind = str(kind or "event").strip().lower()
    colors = {
        "event": "indigo",
        "meeting": "sky",
        "class": "emerald",
        "consulting": "sky",
        "training": "amber",
        "exam": "rose",
        "deadline": "rose",
        "prep": "amber",
    }
    return colors.get(normalized_kind, colors["event"])


def _allowed_message_capture_candidate_kinds():
    return {
        CalendarMessageCaptureCandidate.CandidateKind.EVENT,
        CalendarMessageCaptureCandidate.CandidateKind.MEETING,
        CalendarMessageCaptureCandidate.CandidateKind.CLASS,
        CalendarMessageCaptureCandidate.CandidateKind.CONSULTING,
        CalendarMessageCaptureCandidate.CandidateKind.TRAINING,
        CalendarMessageCaptureCandidate.CandidateKind.EXAM,
        CalendarMessageCaptureCandidate.CandidateKind.DEADLINE,
        CalendarMessageCaptureCandidate.CandidateKind.PREP,
    }


def _build_message_capture_content_cache_key(normalized_text, attachment_checksums):
    digest = hashlib.sha256()
    digest.update((str(normalized_text or "").strip() + "\n").encode("utf-8"))
    digest.update((MESSAGE_CAPTURE_RULE_VERSION + "\n").encode("utf-8"))
    for checksum in sorted(str(item or "").strip() for item in attachment_checksums or [] if str(item or "").strip()):
        digest.update((checksum + "\n").encode("utf-8"))
    return digest.hexdigest()


def _serialize_parsed_candidate(candidate, *, candidate_id="", already_saved=False):
    evidence_payload = candidate.get("evidence_payload") if isinstance(candidate, dict) else {}
    return {
        "candidate_id": str(candidate_id or ""),
        "kind": str(candidate.get("kind") or "event").strip().lower(),
        "badge_text": candidate.get("badge_text") or _candidate_kind_badge_text(candidate.get("kind")),
        "title": str(candidate.get("title") or "").strip()[:200],
        "summary": str(candidate.get("summary") or "").strip()[:5000],
        "start_time": _serialize_temporal_value(candidate.get("start_time")),
        "end_time": _serialize_temporal_value(candidate.get("end_time")),
        "is_all_day": bool(candidate.get("is_all_day")),
        "confidence_score": float(candidate.get("confidence_score") or 0),
        "is_recommended": bool(candidate.get("is_recommended", True)),
        "already_saved": bool(already_saved),
        "evidence_text": str(candidate.get("evidence_text") or "").strip()[:1000],
        "needs_check": bool(candidate.get("needs_check")),
        "evidence_payload": _serialize_json_safe(evidence_payload or {}),
        "color": candidate.get("color") or _candidate_kind_color(candidate.get("kind")),
    }


def _serialize_message_capture_candidate(candidate):
    return {
        "candidate_id": str(candidate.id),
        "kind": candidate.candidate_kind,
        "badge_text": _candidate_kind_badge_text(candidate.candidate_kind),
        "title": candidate.title or "",
        "summary": candidate.summary or "",
        "start_time": _serialize_temporal_value(candidate.start_time),
        "end_time": _serialize_temporal_value(candidate.end_time),
        "is_all_day": bool(candidate.is_all_day),
        "confidence_score": float(candidate.confidence_score or 0),
        "is_recommended": bool(candidate.is_recommended),
        "already_saved": bool(candidate.committed_event_id or candidate.commit_status == CalendarMessageCaptureCandidate.CommitStatus.SAVED),
        "evidence_text": candidate.evidence_text or "",
        "needs_check": bool(candidate.needs_check),
        "evidence_payload": _serialize_json_safe(candidate.evidence_payload or {}),
        "color": _candidate_kind_color(candidate.candidate_kind),
    }


def _legacy_primary_candidate_from_parsed(parsed):
    candidates = list(parsed.get("candidates") or [])
    if not candidates:
        return None
    recommended = [candidate for candidate in candidates if candidate.get("is_recommended")]
    return (recommended or candidates)[0]


def _build_legacy_candidate_drafts(primary_candidate, parsed):
    candidate = primary_candidate or {}
    candidate_kind = str(candidate.get("kind") or "event").strip().lower()
    task_due_at = parsed.get("task_due_at")
    task_has_time = bool(parsed.get("task_has_time"))
    if not task_due_at and candidate_kind in {"deadline", "prep"}:
        task_due_at = candidate.get("end_time")
        task_has_time = not bool(candidate.get("is_all_day"))
    title = (candidate.get("title") or parsed.get("extracted_title") or "메시지에서 만든 일정")[:200]
    todo_summary = candidate.get("summary") or parsed.get("extracted_todo_summary") or ""
    evidence = candidate.get("evidence_payload") or parsed.get("evidence") or {}
    return {
        "draft_event": {
            "title": title,
            "start_time": _serialize_temporal_value(candidate.get("start_time") or parsed.get("extracted_start_time")),
            "end_time": _serialize_temporal_value(candidate.get("end_time") or parsed.get("extracted_end_time")),
            "is_all_day": bool(candidate.get("is_all_day", parsed.get("extracted_is_all_day"))),
            "todo_summary": todo_summary,
            "priority": parsed.get("extracted_priority") or CalendarMessageCapture.Priority.NORMAL,
            "parse_evidence": _serialize_json_safe(evidence),
        },
        "draft_task": {
            "title": title,
            "due_at": _serialize_temporal_value(task_due_at),
            "has_time": bool(task_has_time),
            "note": parsed.get("task_note") or todo_summary,
            "priority": parsed.get("extracted_priority") or CalendarTask.Priority.NORMAL,
            "parse_evidence": _serialize_json_safe(evidence),
        },
    }


def _build_message_capture_initial_extract_payload(parsed):
    primary_candidate = _legacy_primary_candidate_from_parsed(parsed)
    legacy_drafts = _build_legacy_candidate_drafts(primary_candidate, parsed)
    return {
        "parser_version": MESSAGE_CAPTURE_RULE_VERSION,
        "predicted_item_type": parsed.get("predicted_item_type") or CalendarMessageCapture.ItemType.UNKNOWN,
        "confidence_label": parsed.get("confidence_label") or "low",
        "warnings": list(parsed.get("warnings") or []),
        "evidence": parsed.get("evidence") or {},
        "deadline_only": bool(parsed.get("deadline_only")),
        "location": parsed.get("location") or "",
        "materials": parsed.get("materials") or "",
        "audience": parsed.get("audience") or "",
        "category": parsed.get("category") or "",
        "recurrence_hint": parsed.get("recurrence_hint") or "",
        "summary_text": parsed.get("summary_text") or "",
        "llm_used": bool(parsed.get("llm_used")),
        "candidates": [
            _serialize_parsed_candidate(candidate, candidate_id=str(index + 1))
            for index, candidate in enumerate(parsed.get("candidates") or [])
        ],
        "draft_event": legacy_drafts["draft_event"],
        "draft_task": legacy_drafts["draft_task"],
    }


def _build_message_capture_final_payload(cleaned_data, *, selected_attachment_ids=None, source_context=None):
    item_type = cleaned_data.get("confirmed_item_type") or CalendarMessageCapture.ItemType.EVENT
    payload = {
        "item_type": item_type,
        "title": cleaned_data.get("title") or "",
        "selected_attachment_ids": list(selected_attachment_ids or []),
    }
    if source_context:
        payload["source_sheetbook_id"] = source_context.get("sheetbook_id")
        payload["source_tab_id"] = source_context.get("tab_id")

    if item_type == CalendarMessageCapture.ItemType.TASK:
        payload.update(
            {
                "note": cleaned_data.get("note") or "",
                "due_at": _serialize_temporal_value(cleaned_data.get("due_at")),
                "has_time": bool(cleaned_data.get("has_time", False)),
                "priority": cleaned_data.get("priority") or CalendarTask.Priority.NORMAL,
            }
        )
        return payload

    payload.update(
        {
            "todo_summary": cleaned_data.get("todo_summary") or "",
            "start_time": _serialize_temporal_value(cleaned_data.get("start_time")),
            "end_time": _serialize_temporal_value(cleaned_data.get("end_time")),
            "is_all_day": bool(cleaned_data.get("is_all_day", False)),
            "color": cleaned_data.get("color") or "indigo",
        }
    )
    return payload


def _build_message_capture_edit_diff(capture, final_payload):
    initial_payload = capture.initial_extract_payload if isinstance(capture.initial_extract_payload, dict) else {}
    initial_item_type = initial_payload.get("predicted_item_type") or capture.predicted_item_type or CalendarMessageCapture.ItemType.UNKNOWN
    final_item_type = final_payload.get("item_type") or CalendarMessageCapture.ItemType.EVENT
    field_changes = {}

    def record(field_name, initial_value, final_value):
        changed = _serialize_json_safe(initial_value) != _serialize_json_safe(final_value)
        field_changes[field_name] = {
            "initial": _serialize_json_safe(initial_value),
            "final": _serialize_json_safe(final_value),
            "changed": changed,
        }

    record("item_type", initial_item_type, final_item_type)
    if final_item_type == CalendarMessageCapture.ItemType.TASK:
        initial_task = initial_payload.get("draft_task") or {}
        record("title", initial_task.get("title") or capture.extracted_title, final_payload.get("title") or "")
        record("due_at", initial_task.get("due_at") or "", final_payload.get("due_at") or "")
        record("has_time", bool(initial_task.get("has_time")), bool(final_payload.get("has_time")))
        record("note", initial_task.get("note") or "", final_payload.get("note") or "")
        record("priority", initial_task.get("priority") or CalendarTask.Priority.NORMAL, final_payload.get("priority") or CalendarTask.Priority.NORMAL)
    else:
        initial_event = initial_payload.get("draft_event") or {}
        record("title", initial_event.get("title") or capture.extracted_title, final_payload.get("title") or "")
        record("start_time", initial_event.get("start_time") or _serialize_temporal_value(capture.extracted_start_time), final_payload.get("start_time") or "")
        record("end_time", initial_event.get("end_time") or _serialize_temporal_value(capture.extracted_end_time), final_payload.get("end_time") or "")
        record("is_all_day", bool(initial_event.get("is_all_day", capture.extracted_is_all_day)), bool(final_payload.get("is_all_day")))
        record("todo_summary", initial_event.get("todo_summary") or capture.extracted_todo_summary or "", final_payload.get("todo_summary") or "")
        record("color", initial_event.get("color") or "indigo", final_payload.get("color") or "indigo")

    changed_fields = [name for name, value in field_changes.items() if value.get("changed")]
    return {
        "changed_fields": changed_fields,
        "field_changes": field_changes,
    }


def _count_message_capture_manual_edits_from_diff(diff_payload):
    if not isinstance(diff_payload, dict):
        return 0
    return len(diff_payload.get("changed_fields") or [])


def _extract_attachment_extensions(uploaded_files):
    extensions = []
    for uploaded_file in uploaded_files or []:
        extension = _extract_upload_extension(uploaded_file)
        if extension:
            extensions.append(extension)
    return sorted(set(extensions))


def _run_message_capture_classifier(*, user, raw_text, normalized_text, source_hint, uploaded_files, parsed):
    shadow_enabled = _is_message_capture_classifier_shadow_enabled_for_user(user)
    assist_enabled = _is_message_capture_classifier_assist_enabled_for_user(user)
    if not shadow_enabled and not assist_enabled:
        return None
    try:
        return predict_message_capture_item_type(
            raw_text=raw_text,
            normalized_text=normalized_text,
            source_hint=source_hint,
            attachment_extensions=_extract_attachment_extensions(uploaded_files),
            parser_result=parsed,
        )
    except Exception:
        logger.exception(
            "[ClassCalendar][MessageCapture] classifier_failed user_id=%s",
            getattr(user, "id", None),
        )
        return None


def _build_message_capture_duplicate_payload(capture):
    payload = {
        "status": "error",
        "code": "duplicate_request",
        "message": "이미 저장이 완료된 메시지입니다.",
    }
    if capture.committed_event_id:
        payload.update(
            {
                "item_type": CalendarMessageCapture.ItemType.EVENT,
                "event_id": str(capture.committed_event_id),
            }
        )
    elif capture.committed_task_id:
        payload.update(
            {
                "item_type": CalendarMessageCapture.ItemType.TASK,
                "task_id": str(capture.committed_task_id),
            }
        )
    return payload


def _build_fallback_message_capture_candidates(capture):
    initial_payload = capture.initial_extract_payload if isinstance(capture.initial_extract_payload, dict) else {}
    payload_candidates = initial_payload.get("candidates") or []
    if isinstance(payload_candidates, list) and payload_candidates:
        fallback = []
        for index, candidate in enumerate(payload_candidates):
            if not isinstance(candidate, dict):
                continue
            fallback.append(
                {
                    "candidate_id": str(candidate.get("candidate_id") or index + 1),
                    "kind": str(candidate.get("kind") or "event"),
                    "badge_text": candidate.get("badge_text") or _candidate_kind_badge_text(candidate.get("kind")),
                    "title": str(candidate.get("title") or "").strip(),
                    "summary": str(candidate.get("summary") or "").strip(),
                    "start_time": str(candidate.get("start_time") or ""),
                    "end_time": str(candidate.get("end_time") or ""),
                    "is_all_day": bool(candidate.get("is_all_day")),
                    "confidence_score": float(candidate.get("confidence_score") or capture.confidence_score or 0),
                    "is_recommended": bool(candidate.get("is_recommended", True)),
                    "already_saved": bool(capture.committed_event_id),
                    "evidence_text": str(candidate.get("evidence_text") or "").strip(),
                    "needs_check": bool(candidate.get("needs_check")),
                    "evidence_payload": candidate.get("evidence_payload") or {},
                    "color": candidate.get("color") or _candidate_kind_color(candidate.get("kind")),
                }
            )
        if fallback:
            return fallback

    draft_event = initial_payload.get("draft_event") or {}
    if not draft_event:
        return []
    inferred_kind = "deadline" if capture.predicted_item_type == CalendarMessageCapture.ItemType.TASK else "event"
    return [
        {
            "candidate_id": "legacy-primary",
            "kind": inferred_kind,
            "badge_text": _candidate_kind_badge_text(inferred_kind),
            "title": draft_event.get("title") or capture.extracted_title or "메시지에서 만든 일정",
            "summary": draft_event.get("todo_summary") or capture.extracted_todo_summary or "",
            "start_time": draft_event.get("start_time") or _serialize_temporal_value(capture.extracted_start_time),
            "end_time": draft_event.get("end_time") or _serialize_temporal_value(capture.extracted_end_time),
            "is_all_day": bool(draft_event.get("is_all_day", capture.extracted_is_all_day)),
            "confidence_score": float(capture.confidence_score or 0),
            "is_recommended": True,
            "already_saved": bool(capture.committed_event_id),
            "evidence_text": ((capture.parse_payload or {}).get("evidence") or {}).get("date") or "",
            "needs_check": capture.parse_status != CalendarMessageCapture.ParseStatus.PARSED,
            "evidence_payload": ((capture.parse_payload or {}).get("evidence") or {}),
            "color": _candidate_kind_color(inferred_kind),
        }
    ]


def _is_message_capture_archive_only(capture):
    parse_payload = capture.parse_payload if isinstance(capture.parse_payload, dict) else {}
    return bool(parse_payload.get("archive_only"))


def _serialize_message_capture_attachment(attachment):
    return {
        "id": str(attachment.id),
        "original_name": attachment.original_name,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "is_selected": bool(attachment.is_selected),
    }


def _get_message_capture_manual_date(capture):
    if capture.linked_for_at:
        return timezone.localtime(capture.linked_for_at).date().isoformat()
    parse_payload = capture.parse_payload if isinstance(capture.parse_payload, dict) else {}
    return str(parse_payload.get("manual_date") or "").strip()


def _get_message_capture_manual_note(capture):
    parse_payload = capture.parse_payload if isinstance(capture.parse_payload, dict) else {}
    return str(parse_payload.get("manual_note") or "").strip()


def _message_capture_has_linked_item(capture):
    if capture.linked_for_at:
        return True
    if capture.committed_event_id or capture.committed_task_id:
        return True
    saved_count = getattr(capture, "saved_count", None)
    if saved_count is not None:
        return int(saved_count or 0) > 0
    return capture.candidates.exclude(committed_event__isnull=True).exists()


def _default_follow_up_state_for_capture(capture):
    parse_status = str(getattr(capture, "parse_status", "") or "").strip()
    if parse_status in {
        CalendarMessageCapture.ParseStatus.NEEDS_REVIEW,
        CalendarMessageCapture.ParseStatus.FAILED,
    }:
        return CalendarMessageCapture.FollowUpState.NEEDS_CHECK
    return CalendarMessageCapture.FollowUpState.PENDING


def _normalize_follow_up_state_value(capture):
    follow_up_state = str(getattr(capture, "follow_up_state", "") or "").strip()
    if follow_up_state in {
        CalendarMessageCapture.FollowUpState.PENDING,
        CalendarMessageCapture.FollowUpState.NEEDS_CHECK,
        CalendarMessageCapture.FollowUpState.DONE,
    }:
        return follow_up_state
    if capture.completed_at:
        return CalendarMessageCapture.FollowUpState.DONE
    return _default_follow_up_state_for_capture(capture)


def _follow_up_state_label(follow_up_state):
    labels = {
        CalendarMessageCapture.FollowUpState.PENDING: "처리 예정",
        CalendarMessageCapture.FollowUpState.NEEDS_CHECK: "확인 필요",
        CalendarMessageCapture.FollowUpState.DONE: "처리 완료",
    }
    return labels.get(str(follow_up_state or "").strip(), "처리 예정")


def _message_capture_has_dated_candidate(capture):
    if _get_message_capture_manual_date(capture):
        return True
    if capture.extracted_start_time or capture.extracted_end_time:
        return True

    initial_payload = capture.initial_extract_payload if isinstance(capture.initial_extract_payload, dict) else {}
    draft_event = initial_payload.get("draft_event") or {}
    draft_task = initial_payload.get("draft_task") or {}
    if draft_event.get("start_time") or draft_event.get("end_time") or draft_task.get("due_at"):
        return True

    candidate_count = getattr(capture, "candidate_count", None)
    if candidate_count is not None and int(candidate_count or 0) > 0:
        return True

    for candidate in capture.candidates.all():
        if candidate.start_time or candidate.end_time:
            return True
    return False


def _message_capture_workflow_status_code(capture):
    follow_up_state = _normalize_follow_up_state_value(capture)
    if follow_up_state == CalendarMessageCapture.FollowUpState.DONE or capture.completed_at:
        return "done"
    if _message_capture_has_linked_item(capture):
        return "linked"
    if _message_capture_has_dated_candidate(capture):
        return "dated"
    return "kept"


def _message_capture_workflow_status_label(status_code):
    labels = {
        "kept": "보관만 함",
        "dated": "날짜 정함",
        "linked": "캘린더 연결됨",
        "done": "처리 완료",
    }
    return labels.get(str(status_code or "").strip().lower(), "보관만 함")


def _serialize_message_capture(capture, *, warnings=None, reused=False):
    parse_payload = capture.parse_payload if isinstance(capture.parse_payload, dict) else {}
    extract_payload = capture.initial_extract_payload if isinstance(capture.initial_extract_payload, dict) else {}
    warning_list = warnings if warnings is not None else extract_payload.get("warnings") or parse_payload.get("warnings") or []
    confidence_label = extract_payload.get("confidence_label") or parse_payload.get("confidence_label") or "low"

    all_candidate_objects = []
    try:
        all_candidate_objects = list(capture.candidates.all().order_by("sort_order", "id"))
    except Exception:
        all_candidate_objects = []
    candidate_objects = [
        candidate
        for candidate in all_candidate_objects
        if candidate.commit_status != CalendarMessageCaptureCandidate.CommitStatus.SKIPPED
    ]
    candidates = [
        _serialize_message_capture_candidate(candidate)
        for candidate in candidate_objects
    ]
    if not candidates and not all_candidate_objects:
        candidates = _build_fallback_message_capture_candidates(capture)

    primary_candidate = None
    if candidates:
        recommended = [candidate for candidate in candidates if candidate.get("is_recommended")]
        primary_candidate = (recommended or candidates)[0]
    legacy_drafts = _build_legacy_candidate_drafts(
        {
            "kind": (primary_candidate or {}).get("kind"),
            "title": (primary_candidate or {}).get("title"),
            "summary": (primary_candidate or {}).get("summary"),
            "start_time": (primary_candidate or {}).get("start_time"),
            "end_time": (primary_candidate or {}).get("end_time"),
            "is_all_day": (primary_candidate or {}).get("is_all_day"),
            "evidence_payload": (primary_candidate or {}).get("evidence_payload") or {},
        } if primary_candidate else None,
        {
            "extracted_title": capture.extracted_title,
            "extracted_start_time": capture.extracted_start_time,
            "extracted_end_time": capture.extracted_end_time,
            "extracted_is_all_day": capture.extracted_is_all_day,
            "extracted_todo_summary": capture.extracted_todo_summary,
            "extracted_priority": capture.extracted_priority,
            "task_due_at": capture.extracted_end_time,
            "task_has_time": False,
            "task_note": capture.extracted_todo_summary,
            "evidence": parse_payload.get("evidence") or {},
        },
    )
    draft_event = extract_payload.get("draft_event") or legacy_drafts["draft_event"]
    draft_task = extract_payload.get("draft_task") or legacy_drafts["draft_task"]
    draft_event["needs_confirmation"] = bool(capture.parse_status != CalendarMessageCapture.ParseStatus.PARSED or confidence_label == "low")
    draft_task["needs_confirmation"] = bool(capture.parse_status != CalendarMessageCapture.ParseStatus.PARSED or confidence_label == "low")

    summary_text = extract_payload.get("summary_text") or parse_payload.get("summary_text")
    if not summary_text:
        if _is_message_capture_archive_only(capture):
            summary_text = "아직 일정으로 읽지 않은 메시지"
        else:
            summary_text = f"찾은 일정 {len(candidates)}개"
    workflow_status = _message_capture_workflow_status_code(capture)
    follow_up_state = _normalize_follow_up_state_value(capture)
    return {
        "status": "success",
        "capture_id": str(capture.id),
        "parse_status": capture.parse_status,
        "summary_text": summary_text,
        "confidence_score": float(capture.confidence_score or 0),
        "confidence_label": confidence_label,
        "predicted_item_type": extract_payload.get("predicted_item_type") or capture.predicted_item_type or CalendarMessageCapture.ItemType.UNKNOWN,
        "draft_event": draft_event,
        "draft_task": draft_task,
        "attachments": [
            _serialize_message_capture_attachment(attachment)
            for attachment in capture.attachments.all().order_by("created_at", "id")
        ],
        "warnings": warning_list,
        "reused": bool(reused),
        "ml_scores": capture.ml_scores if isinstance(capture.ml_scores, dict) else {},
        "llm_used": bool(parse_payload.get("llm_used") or extract_payload.get("llm_used") or capture.llm_used),
        "candidates": candidates,
        "manual_date": _get_message_capture_manual_date(capture),
        "manual_note": _get_message_capture_manual_note(capture),
        "linked_for_at": _serialize_hub_datetime(capture.linked_for_at),
        "follow_up_state": follow_up_state,
        "follow_up_state_label": _follow_up_state_label(follow_up_state),
        "completed_at": capture.completed_at.isoformat() if capture.completed_at else "",
        "workflow_status": workflow_status,
        "workflow_status_label": _message_capture_workflow_status_label(workflow_status),
        "messagebox_url": _build_message_capture_deep_link(capture.id),
        "delete_url": _build_message_capture_delete_link(capture.id),
    }


def _build_message_capture_archive_preview(raw_text):
    lines = [
        line.strip()
        for line in str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    preview = "\n".join(lines[:2]).strip()
    return preview[:400]


def _message_capture_archive_status_code(capture):
    candidate_count = getattr(capture, "candidate_count", None)
    if candidate_count is None:
        candidate_count = capture.candidates.count()
    saved_count = getattr(capture, "saved_count", None)
    if saved_count is None:
        saved_count = capture.candidates.exclude(committed_event__isnull=True).count()
    if capture.linked_for_at or capture.committed_event_id or capture.committed_task_id:
        saved_count = max(int(saved_count or 0), 1)
    candidate_count = int(candidate_count or 0)
    saved_count = int(saved_count or 0)
    parse_status = str(getattr(capture, "parse_status", "") or "")
    if _is_message_capture_archive_only(capture) and saved_count == 0:
        return "unparsed"
    if saved_count > 0:
        return "saved"
    if parse_status == CalendarMessageCapture.ParseStatus.FAILED or candidate_count == 0:
        return "failed"
    if parse_status == CalendarMessageCapture.ParseStatus.NEEDS_REVIEW:
        return "needs_review"
    return "pending"


def _message_capture_archive_status_label(status_code):
    labels = {
        "unparsed": "미분석",
        "saved": "저장 완료",
        "pending": "미저장",
        "needs_review": "확인 필요",
        "failed": "일정 못 찾음",
    }
    return labels.get(status_code, "미분석")


def _build_message_capture_archive_queryset(user):
    return CalendarMessageCapture.objects.filter(author=user).annotate(
        candidate_count=Count("candidates", distinct=True),
        saved_count=Count("candidates", filter=Q(candidates__committed_event__isnull=False), distinct=True),
        attachment_count=Count("attachments", distinct=True),
    )


def _apply_message_capture_archive_query(queryset, query_text):
    query = str(query_text or "").strip()
    if not query:
        return queryset
    return queryset.filter(
        Q(raw_text__icontains=query)
        | Q(normalized_text__icontains=query)
        | Q(candidates__title__icontains=query)
        | Q(candidates__summary__icontains=query)
        | Q(attachments__original_name__icontains=query)
    ).distinct()


def _apply_message_capture_archive_filter(queryset, filter_value):
    normalized_filter = str(filter_value or "all").strip().lower()
    if normalized_filter not in {"unparsed", "saved", "pending", "needs_review", "failed"}:
        return queryset
    matched_ids = [
        capture.id
        for capture in queryset
        if _message_capture_archive_status_code(capture) == normalized_filter
    ]
    if not matched_ids:
        return queryset.none()
    if normalized_filter == "saved":
        return queryset.filter(id__in=matched_ids).distinct()
    if normalized_filter == "pending":
        return queryset.filter(id__in=matched_ids).distinct()
    if normalized_filter == "needs_review":
        return queryset.filter(id__in=matched_ids).distinct()
    if normalized_filter == "failed":
        return queryset.filter(id__in=matched_ids).distinct()
    if normalized_filter == "unparsed":
        return queryset.filter(id__in=matched_ids).distinct()
    return queryset


def _apply_message_capture_workflow_filter(queryset, workflow_status):
    normalized_filter = str(workflow_status or "all").strip().lower()
    if normalized_filter not in MESSAGE_CAPTURE_WORKFLOW_FILTER_KEYS:
        return queryset

    matched_ids = [
        capture.id
        for capture in queryset
        if _message_capture_workflow_status_code(capture) == normalized_filter
    ]
    if not matched_ids:
        return queryset.none()
    return queryset.filter(id__in=matched_ids)


def _build_message_capture_archive_counts(queryset):
    unparsed_ids = set()
    saved_ids = set()
    pending_ids = set()
    needs_review_ids = set()
    failed_ids = set()
    kept_ids = set()
    dated_ids = set()
    linked_ids = set()
    done_ids = set()
    for capture in queryset:
        archive_status = _message_capture_archive_status_code(capture)
        if archive_status == "unparsed":
            unparsed_ids.add(capture.id)
        elif archive_status == "saved":
            saved_ids.add(capture.id)
        elif archive_status == "pending":
            pending_ids.add(capture.id)
        elif archive_status == "needs_review":
            needs_review_ids.add(capture.id)
        elif archive_status == "failed":
            failed_ids.add(capture.id)
        workflow_status = _message_capture_workflow_status_code(capture)
        if workflow_status == "done":
            done_ids.add(capture.id)
        elif workflow_status == "linked":
            linked_ids.add(capture.id)
        elif workflow_status == "dated":
            dated_ids.add(capture.id)
        else:
            kept_ids.add(capture.id)
    all_ids = set(queryset.values_list("id", flat=True))
    return {
        "all": len(all_ids),
        "unparsed": len(unparsed_ids),
        "saved": len(saved_ids),
        "pending": len(pending_ids),
        "needs_review": len(needs_review_ids),
        "failed": len(failed_ids),
        "kept": len(kept_ids),
        "dated": len(dated_ids),
        "linked": len(linked_ids),
        "done": len(done_ids),
    }


def _serialize_message_capture_archive_item(capture):
    status_code = _message_capture_archive_status_code(capture)
    parse_payload = capture.parse_payload if isinstance(capture.parse_payload, dict) else {}
    initial_payload = capture.initial_extract_payload if isinstance(capture.initial_extract_payload, dict) else {}
    summary_text = initial_payload.get("summary_text") or parse_payload.get("summary_text") or f"찾은 일정 {int(getattr(capture, 'candidate_count', 0) or 0)}개"
    workflow_status = _message_capture_workflow_status_code(capture)
    follow_up_state = _normalize_follow_up_state_value(capture)
    return {
        "capture_id": str(capture.id),
        "created_at": capture.created_at.isoformat() if capture.created_at else "",
        "preview_text": _build_message_capture_archive_preview(capture.raw_text),
        "parse_status": capture.parse_status,
        "archive_status": status_code,
        "archive_status_label": _message_capture_archive_status_label(status_code),
        "workflow_status": workflow_status,
        "workflow_status_label": _message_capture_workflow_status_label(workflow_status),
        "completed_at": capture.completed_at.isoformat() if capture.completed_at else "",
        "manual_date": _get_message_capture_manual_date(capture),
        "manual_note": _get_message_capture_manual_note(capture),
        "linked_for_at": _serialize_hub_datetime(capture.linked_for_at),
        "follow_up_state": follow_up_state,
        "follow_up_state_label": _follow_up_state_label(follow_up_state),
        "candidate_count": int(getattr(capture, "candidate_count", 0) or 0),
        "saved_count": int(getattr(capture, "saved_count", 0) or 0),
        "attachment_count": int(getattr(capture, "attachment_count", 0) or 0),
        "summary_text": summary_text,
        "messagebox_url": _build_message_capture_deep_link(capture.id),
        "delete_url": _build_message_capture_delete_link(capture.id),
    }


def _serialize_message_capture_saved_events(capture):
    event_map = {}
    capture_event = _safe_related_event(capture)
    if capture.committed_event_id and capture_event is not None:
        event_map[str(capture.committed_event_id)] = capture_event
    for candidate in capture.candidates.all().order_by("sort_order", "id"):
        candidate_event = _safe_related_event(candidate)
        if not candidate.committed_event_id or candidate_event is None:
            continue
        event_map[str(candidate.committed_event_id)] = candidate_event
    return [_serialize_compact_event(event) for event in event_map.values()]


def _serialize_compact_task(task):
    return {
        "id": str(task.id),
        "title": task.title,
        "due_at": task.due_at.isoformat() if task.due_at else "",
        "has_time": bool(task.has_time),
        "priority": task.priority or CalendarTask.Priority.NORMAL,
        "status": task.status or CalendarTask.Status.OPEN,
        "calendar_url": _build_calendar_item_link(task=task),
        "delete_url": _build_calendar_delete_link(task=task),
        "message_capture_id": "",
        "message_capture_url": "",
    }


def _serialize_message_capture_saved_tasks(capture):
    task_map = {}
    capture_task = _safe_related_task(capture)
    if capture.committed_task_id and capture.committed_task_id not in task_map and capture_task is not None:
        task_map[str(capture.committed_task_id)] = capture_task
    return [_serialize_compact_task(task) for task in task_map.values() if task is not None]


def _serialize_message_capture_archive_detail(capture):
    payload = _serialize_message_capture(capture)
    status_code = _message_capture_archive_status_code(capture)
    payload.update(
        {
            "raw_text": capture.raw_text or "",
            "summary_text": payload.get("summary_text") or "",
            "created_at": capture.created_at.isoformat() if capture.created_at else "",
            "archive_status": status_code,
            "archive_status_label": _message_capture_archive_status_label(status_code),
            "saved_events": _serialize_message_capture_saved_events(capture),
            "saved_tasks": _serialize_message_capture_saved_tasks(capture),
        }
    )
    return payload


def _guess_upload_mime_type(uploaded_file):
    hinted_type = (getattr(uploaded_file, "content_type", "") or "").strip().lower()
    if hinted_type:
        return hinted_type
    guessed, _ = mimetypes.guess_type(uploaded_file.name or "")
    return (guessed or "application/octet-stream").lower()


def _extract_upload_extension(uploaded_file):
    file_name = (
        getattr(uploaded_file, "name", "")
        or getattr(uploaded_file, "original_name", "")
        or getattr(getattr(uploaded_file, "file", None), "name", "")
    )
    _, extension = os.path.splitext(file_name or "")
    return extension.lower().lstrip(".")


def _is_allowed_message_capture_file(uploaded_file):
    extension = _extract_upload_extension(uploaded_file)
    mime_type = _guess_upload_mime_type(uploaded_file)

    extension_allowed = extension in MESSAGE_CAPTURE_ALLOWED_EXTENSIONS
    mime_allowed = mime_type in MESSAGE_CAPTURE_ALLOWED_MIME_TYPES or any(
        mime_type.startswith(prefix) for prefix in MESSAGE_CAPTURE_ALLOWED_MIME_PREFIXES
    )
    return extension_allowed and mime_allowed


def _validate_message_capture_uploads(*, uploaded_files, user_id, operation_label):
    attachment_checksums = []
    for uploaded_file in uploaded_files:
        file_size = int(getattr(uploaded_file, "size", 0) or 0)
        if file_size > MESSAGE_CAPTURE_MAX_FILE_BYTES:
            logger.warning(
                "[ClassCalendar][MessageCapture] %s_failed user_id=%s reason=file_too_large file=%s size=%s",
                operation_label,
                user_id,
                uploaded_file.name,
                file_size,
            )
            return None, JsonResponse(
                {
                    "status": "error",
                    "code": "file_too_large",
                    "message": f"{uploaded_file.name} 파일이 용량 제한({MESSAGE_CAPTURE_MAX_FILE_BYTES // (1024 * 1024)}MB)을 초과했습니다.",
                },
                status=413,
            )
        if not _is_allowed_message_capture_file(uploaded_file):
            logger.warning(
                "[ClassCalendar][MessageCapture] %s_failed user_id=%s reason=invalid_file_type file=%s",
                operation_label,
                user_id,
                uploaded_file.name,
            )
            return None, JsonResponse(
                {
                    "status": "error",
                    "code": "validation_error",
                    "message": f"{uploaded_file.name} 파일 형식은 지원하지 않습니다.",
                },
                status=400,
            )
        attachment_checksums.append(_calculate_upload_sha256(uploaded_file))
    return attachment_checksums, None


def _calculate_upload_sha256(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return digest.hexdigest()


def _create_message_capture_attachments(capture, uploaded_files, attachment_checksums, *, uploaded_by):
    for uploaded_file, checksum in zip(uploaded_files, attachment_checksums):
        CalendarMessageCaptureAttachment.objects.create(
            capture=capture,
            uploaded_by=uploaded_by,
            file=uploaded_file,
            original_name=(os.path.basename(uploaded_file.name or "") or "attachment")[:255],
            mime_type=_guess_upload_mime_type(uploaded_file)[:120],
            size_bytes=int(getattr(uploaded_file, "size", 0) or 0),
            checksum_sha256=checksum,
            is_selected=True,
        )


def _create_message_capture_candidates(capture, parsed_candidates):
    for index, candidate in enumerate(parsed_candidates or []):
        candidate_kind = str(candidate.get("kind") or CalendarMessageCaptureCandidate.CandidateKind.EVENT).strip().lower()
        if candidate_kind not in _allowed_message_capture_candidate_kinds():
            candidate_kind = CalendarMessageCaptureCandidate.CandidateKind.EVENT
        CalendarMessageCaptureCandidate.objects.create(
            capture=capture,
            sort_order=index,
            candidate_kind=candidate_kind,
            title=(candidate.get("title") or "")[:200],
            summary=candidate.get("summary") or "",
            start_time=candidate.get("start_time"),
            end_time=candidate.get("end_time"),
            is_all_day=bool(candidate.get("is_all_day")),
            confidence_score=candidate.get("confidence_score") or 0,
            is_recommended=bool(candidate.get("is_recommended", True)),
            needs_check=bool(candidate.get("needs_check")),
            evidence_text=(candidate.get("evidence_text") or "")[:1000],
            evidence_payload=candidate.get("evidence_payload") or {},
            commit_status=CalendarMessageCaptureCandidate.CommitStatus.PENDING,
        )


def _build_message_capture_parse_result(*, user, raw_text, source_hint, uploaded_files, attachment_checksums):
    parsed = parse_message_capture_draft(
        raw_text,
        now=timezone.now(),
        has_files=bool(uploaded_files),
        llm_refiner=refine_message_capture_candidates,
    )
    item_types_enabled = _is_message_capture_item_types_enabled_for_user(user)
    predicted_item_type = parsed.get("predicted_item_type") or CalendarMessageCapture.ItemType.UNKNOWN
    if not item_types_enabled:
        predicted_item_type = CalendarMessageCapture.ItemType.EVENT

    classifier_result = _run_message_capture_classifier(
        user=user,
        raw_text=raw_text,
        normalized_text=parsed.get("normalized_text") or raw_text,
        source_hint=source_hint,
        uploaded_files=uploaded_files,
        parsed=parsed,
    )
    decision_source = CalendarMessageCapture.DecisionSource.RULE
    ml_scores = classifier_result.get("scores") if classifier_result else {}
    strong_deadline_candidate = any(
        str(candidate.get("kind") or "") == "deadline" and float(candidate.get("confidence_score") or 0) >= 70
        for candidate in (parsed.get("candidates") or [])
        if isinstance(candidate, dict)
    )
    if (
        item_types_enabled
        and classifier_result
        and _is_message_capture_classifier_assist_enabled_for_user(user)
        and float(classifier_result.get("confidence") or 0.0) >= MESSAGE_CAPTURE_CLASSIFIER_ASSIST_THRESHOLD
    ):
        classifier_label = classifier_result.get("label") or predicted_item_type
        if not (strong_deadline_candidate and classifier_label == CalendarMessageCapture.ItemType.EVENT):
            predicted_item_type = classifier_label
            decision_source = CalendarMessageCapture.DecisionSource.RULE_ML

    parsed["predicted_item_type"] = predicted_item_type
    content_cache_key = _build_message_capture_content_cache_key(
        parsed.get("normalized_text") or raw_text,
        attachment_checksums,
    )
    initial_extract_payload = _build_message_capture_initial_extract_payload(parsed)
    parse_payload = {
        "parser_version": MESSAGE_CAPTURE_RULE_VERSION,
        "confidence_label": parsed["confidence_label"],
        "warnings": parsed["warnings"],
        "evidence": parsed["evidence"],
        "predicted_item_type": predicted_item_type,
        "classifier": classifier_result or {},
        "summary_text": parsed.get("summary_text") or "",
        "candidate_count": len(parsed.get("candidates") or []),
        "content_cache_key": content_cache_key,
        "llm_used": bool(parsed.get("llm_used")),
    }
    return {
        "parsed": parsed,
        "predicted_item_type": predicted_item_type,
        "decision_source": decision_source,
        "ml_scores": ml_scores or {},
        "content_cache_key": content_cache_key,
        "initial_extract_payload": initial_extract_payload,
        "parse_payload": parse_payload,
    }


def _apply_message_capture_parse_result(capture, parse_result):
    parsed = parse_result["parsed"]
    capture.normalized_text = parsed["normalized_text"]
    capture.parse_status = parsed["parse_status"]
    capture.confidence_score = parsed["confidence_score"]
    capture.predicted_item_type = parse_result["predicted_item_type"]
    capture.decision_source = parse_result["decision_source"]
    capture.extracted_title = (parsed["extracted_title"] or "")[:200]
    capture.extracted_start_time = parsed["extracted_start_time"]
    capture.extracted_end_time = parsed["extracted_end_time"]
    capture.extracted_is_all_day = bool(parsed["extracted_is_all_day"])
    capture.extracted_priority = parsed["extracted_priority"] or CalendarMessageCapture.Priority.NORMAL
    capture.extracted_todo_summary = parsed["extracted_todo_summary"] or ""
    capture.parse_payload = parse_result["parse_payload"]
    capture.initial_extract_payload = parse_result["initial_extract_payload"]
    capture.rule_version = MESSAGE_CAPTURE_RULE_VERSION
    capture.ml_scores = parse_result["ml_scores"]
    capture.llm_used = bool(parsed.get("llm_used"))
    capture.content_cache_key = parse_result["content_cache_key"]
    return [
        "normalized_text",
        "parse_status",
        "confidence_score",
        "predicted_item_type",
        "decision_source",
        "extracted_title",
        "extracted_start_time",
        "extracted_end_time",
        "extracted_is_all_day",
        "extracted_priority",
        "extracted_todo_summary",
        "parse_payload",
        "initial_extract_payload",
        "rule_version",
        "ml_scores",
        "llm_used",
        "content_cache_key",
        "updated_at",
    ]


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


def _extract_selected_candidates(payload):
    selected_candidates = payload.get("selected_candidates") or []
    if not isinstance(selected_candidates, list):
        return []
    normalized = []
    for item in selected_candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or item.get("work_item_id") or "").strip()
        if not candidate_id:
            continue
        normalized.append(
            {
                "candidate_id": candidate_id,
                "selected": bool(item.get("selected", True)),
                "title": str(item.get("title") or "").strip()[:200],
                "kind": str(item.get("kind") or "").strip().lower(),
                "start_time": str(item.get("start_time") or "").strip(),
                "end_time": str(item.get("end_time") or "").strip(),
                "is_all_day": bool(item.get("is_all_day")),
                "summary": str(item.get("summary") or "").strip()[:5000],
            }
        )
    return normalized


def _normalize_selected_candidate_kind(raw_kind):
    normalized = str(raw_kind or "").strip().lower()
    allowed = _allowed_message_capture_candidate_kinds()
    return normalized if normalized in allowed else CalendarMessageCaptureCandidate.CandidateKind.EVENT


def _parse_candidate_datetime(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _serialize_compact_event(event):
    payload = {
        "id": str(event.id),
        "title": event.title,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "is_all_day": bool(event.is_all_day),
        "color": event.color or "indigo",
        "calendar_url": _build_calendar_item_link(event=event),
        "delete_url": _build_calendar_delete_link(event=event),
    }
    payload.update(_build_related_message_capture_meta(event))
    return payload


def _build_message_capture_commit_message(created_events, reused_events):
    labels = []
    for item in list(created_events or []) + list(reused_events or []):
        title = str((item or {}).get("title") or "").strip()
        if title:
            labels.append(title)
    if not labels:
        return "선택한 일정을 저장했어요."
    preview = ", ".join(labels[:3])
    if len(labels) > 3:
        preview = f"{preview} 외 {len(labels) - 3}건"
    return f"{preview}을 저장했어요."


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
            reservation_id = reservation_parts[1]
            school_slug = reservation_parts[2]
            date_text = reservation_parts[3]
            base_url = reverse("reservations:reservation_index", kwargs={"school_slug": school_slug})
            return f"{base_url}?{urlencode({'date': date_text, 'reservation': reservation_id})}", "예약 화면으로 이동"
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
                    return (
                        f"{base_url}?{urlencode({'date': reservation.date.strftime('%Y-%m-%d'), 'reservation': reservation.id})}",
                        "예약 화면으로 이동",
                    )
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

    if source == "hwpxchat_workitem":
        document_id = key.split(":", 1)[0].strip()
        if document_id:
            try:
                return (
                    reverse("hwpxchat:document_detail", kwargs={"document_id": document_id}),
                    "원본 문서로 이동",
                )
            except Exception:
                logger.exception("[ClassCalendar] hwpxchat source link resolve failed event_id=%s", event.id)
        return reverse("hwpxchat:main"), "원본 문서로 이동"

    return "", ""


def _compact_hub_text(value, *, default=""):
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return text or default


def _pick_latest_message_capture(item):
    captures = list(getattr(item, "message_captures", []).all())
    if not captures:
        return None
    return max(captures, key=lambda capture: capture.created_at)


def _build_collect_hub_meta(event, *, request_item, source_url):
    status_text = "진행 중"
    status_tone = "neutral"
    detail_text = "수합 요청 확인"
    title = _compact_hub_text(getattr(request_item, "title", "") or event.title, default="수합 요청")
    if request_item and request_item.deadline:
        deadline_date = timezone.localtime(request_item.deadline).date()
        today = timezone.localdate()
        if getattr(request_item, "status", "") == "closed":
            status_text = "완료"
            status_tone = "complete"
        elif request_item.is_deadline_passed:
            status_text = "마감 지남"
            status_tone = "warning"
        elif deadline_date == today:
            status_text = "오늘 마감"
            status_tone = "warning"
        submission_count = int(
            getattr(request_item, "submission_total", getattr(request_item, "submission_count", 0)) or 0
        )
        detail_text = f"제출 {submission_count}건" if submission_count else "제출 대기"
    return {
        "service_key": "collect",
        "service_label": "수합",
        "title": title,
        "status_text": status_text,
        "status_tone": status_tone,
        "detail_text": detail_text,
        "action_type": "source_link",
        "action_url": source_url,
        "message_capture_id": "",
    }


def _build_consent_hub_meta(event, *, request_item, source_url):
    status_text = "진행 중"
    status_tone = "neutral"
    detail_text = "서명 요청 확인"
    title = _compact_hub_text(getattr(request_item, "title", "") or event.title, default="서명 요청")
    if request_item:
        pending_count = int(getattr(request_item, "pending_recipient_count", 0) or 0)
        recipient_count = int(getattr(request_item, "recipient_count", 0) or 0)
        expires_at = request_item.link_expires_at
        expires_date = timezone.localtime(expires_at).date() if expires_at else None
        today = timezone.localdate()
        if getattr(request_item, "status", "") == request_item.STATUS_COMPLETED or pending_count == 0:
            status_text = "완료"
            status_tone = "complete"
        elif request_item.is_link_expired:
            status_text = "마감 지남"
            status_tone = "warning"
        elif expires_date == today:
            status_text = "오늘 마감"
            status_tone = "warning"
        detail_text = f"미완료 {pending_count}명" if pending_count else (f"대상 {recipient_count}명" if recipient_count else "서명 확인")
    return {
        "service_key": "consent",
        "service_label": "사인",
        "title": title,
        "status_text": status_text,
        "status_tone": status_tone,
        "detail_text": detail_text,
        "action_type": "source_link",
        "action_url": source_url,
        "message_capture_id": "",
    }


def _build_reservation_hub_meta(event, *, reservation, source_url):
    room_name = ""
    if reservation and getattr(reservation, "room", None):
        room_name = _compact_hub_text(reservation.room.name)
    title = room_name or _compact_hub_text(event.title, default="예약")
    detail_text = room_name if room_name and room_name != title else ""
    return {
        "service_key": "reservation",
        "service_label": "예약",
        "title": title,
        "status_text": "예약됨",
        "status_tone": "neutral",
        "detail_text": detail_text,
        "action_type": "source_link",
        "action_url": source_url,
        "message_capture_id": "",
    }


def _build_message_capture_hub_meta(item, *, capture):
    title = _compact_hub_text(capture.extracted_title or getattr(item, "title", ""), default="저장한 메시지")
    preview_text = _compact_hub_text(
        capture.initial_extract_payload.get("summary_text") if isinstance(capture.initial_extract_payload, dict) else ""
    )
    if not preview_text:
        preview_text = _compact_hub_text(
            capture.parse_payload.get("summary_text") if isinstance(capture.parse_payload, dict) else ""
        )
    if not preview_text:
        preview_text = _compact_hub_text(_build_message_capture_archive_preview(capture.raw_text))
    attachment_count = len(list(capture.attachments.all()))
    if capture.committed_event_id or capture.committed_task_id:
        status_text = "완료"
        status_tone = "complete"
    elif capture.parse_status == CalendarMessageCapture.ParseStatus.NEEDS_REVIEW:
        status_text = "확인 필요"
        status_tone = "warning"
    elif capture.parse_status == CalendarMessageCapture.ParseStatus.FAILED:
        status_text = "확인 필요"
        status_tone = "warning"
    else:
        status_text = "처리 예정"
        status_tone = "neutral"
    detail_bits = []
    if preview_text and preview_text != title:
        detail_bits.append(preview_text)
    if attachment_count:
        detail_bits.append("첨부 있음")
    return {
        "service_key": "message_capture",
        "service_label": "메시지 저장",
        "title": title,
        "status_text": status_text,
        "status_tone": status_tone,
        "detail_text": " · ".join(detail_bits),
        "action_type": "message_capture",
        "action_url": "",
        "message_capture_id": str(capture.id),
    }


def _build_default_event_hub_meta(event):
    return {
        "service_key": "event",
        "service_label": "일정",
        "title": _compact_hub_text(event.title, default="일정"),
        "status_text": "",
        "status_tone": "neutral",
        "detail_text": "",
        "action_type": "event_detail",
        "action_url": "",
        "message_capture_id": "",
    }


def _build_default_task_hub_meta(task):
    status_text = "완료" if (task.status or CalendarTask.Status.OPEN) == CalendarTask.Status.DONE else "진행 중"
    status_tone = "complete" if status_text == "완료" else "neutral"
    return {
        "service_key": "task",
        "service_label": "할 일",
        "title": _compact_hub_text(task.title, default="할 일"),
        "status_text": status_text,
        "status_tone": status_tone,
        "detail_text": "",
        "action_type": "task_detail",
        "action_url": "",
        "message_capture_id": "",
    }


def _build_event_source_record_lookup(events):
    lookup = {}
    if not events:
        return lookup

    collect_ids = set()
    consent_ids = set()
    reservation_ids = set()
    for event in events:
        source = str(event.integration_source or "").strip()
        key = str(event.integration_key or "").strip()
        _, payload = _split_integration_key(key)
        if source == SOURCE_COLLECT_DEADLINE and payload:
            collect_ids.add(payload)
        elif source == SOURCE_CONSENT_EXPIRY and payload:
            consent_ids.add(payload)
        elif source == SOURCE_RESERVATION and payload.isdigit():
            reservation_ids.add(int(payload))

    if collect_ids:
        try:
            from collect.models import CollectionRequest

            queryset = CollectionRequest.objects.filter(id__in=collect_ids).annotate(
                submission_total=Count("submissions", distinct=True)
            )
            for request_item in queryset:
                lookup[f"collect:{request_item.id}"] = request_item
        except Exception:
            logger.exception("[ClassCalendar] failed to build collect lookup")

    if consent_ids:
        try:
            from consent.models import SignatureRecipient, SignatureRequest

            pending_statuses = [
                SignatureRecipient.STATUS_PENDING,
                SignatureRecipient.STATUS_VERIFIED,
            ]
            queryset = SignatureRequest.objects.filter(request_id__in=consent_ids).annotate(
                recipient_count=Count("recipients", distinct=True),
                pending_recipient_count=Count(
                    "recipients",
                    filter=Q(recipients__status__in=pending_statuses),
                    distinct=True,
                ),
            )
            for request_item in queryset:
                lookup[f"consent:{request_item.request_id}"] = request_item
        except Exception:
            logger.exception("[ClassCalendar] failed to build consent lookup")

    if reservation_ids:
        try:
            from reservations.models import Reservation

            queryset = Reservation.objects.filter(id__in=reservation_ids).select_related("room", "room__school")
            for reservation in queryset:
                key = f"reservation:{reservation.id}:{reservation.room.school.slug}:{reservation.date.strftime('%Y-%m-%d')}"
                lookup[key] = reservation
                lookup[f"reservation:{reservation.id}"] = reservation
        except Exception:
            logger.exception("[ClassCalendar] failed to build reservation lookup")

    return lookup


def _build_event_hub_meta(event, *, source_url, source_record_lookup):
    capture = _pick_latest_message_capture(event)
    if capture:
        return _build_message_capture_hub_meta(event, capture=capture)

    source = str(event.integration_source or "").strip()
    key = str(event.integration_key or "").strip()
    source_record = source_record_lookup.get(key)
    if source == SOURCE_COLLECT_DEADLINE:
        return _build_collect_hub_meta(event, request_item=source_record, source_url=source_url)
    if source == SOURCE_CONSENT_EXPIRY:
        return _build_consent_hub_meta(event, request_item=source_record, source_url=source_url)
    if source == SOURCE_RESERVATION:
        return _build_reservation_hub_meta(event, reservation=source_record, source_url=source_url)
    return _build_default_event_hub_meta(event)


def _build_task_hub_meta(task):
    capture = _pick_latest_message_capture(task)
    if capture:
        return _build_message_capture_hub_meta(task, capture=capture)
    return _build_default_task_hub_meta(task)


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


def _serialize_event(event, *, current_user_id, editable_owner_ids, source_record_lookup=None):
    source_url, source_label = _resolve_integration_source_meta(event)
    sheetbook_source_meta = _resolve_sheetbook_source_meta(event, current_user_id=current_user_id) or {}
    if sheetbook_source_meta.get("source_url"):
        source_url = sheetbook_source_meta.get("source_url") or source_url
        source_label = sheetbook_source_meta.get("source_label") or source_label
    attachments = list(event.attachments.all())
    attachments.sort(key=lambda attachment: (attachment.sort_order, attachment.id))
    hub_meta = _build_event_hub_meta(
        event,
        source_url=source_url,
        source_record_lookup=source_record_lookup or {},
    )
    payload = {
        "item_type": CalendarMessageCapture.ItemType.EVENT,
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
        "hub_meta": hub_meta,
    }
    payload.update(_build_related_message_capture_meta(event))
    return payload



def _serialize_task(task, *, current_user_id):
    payload = {
        "item_type": CalendarMessageCapture.ItemType.TASK,
        "id": str(task.id),
        "title": task.title,
        "note": task.note or "",
        "due_at": task.due_at.isoformat() if task.due_at else "",
        "has_time": bool(task.has_time),
        "priority": task.priority or CalendarTask.Priority.NORMAL,
        "status": task.status or CalendarTask.Status.OPEN,
        "completed_at": task.completed_at.isoformat() if task.completed_at else "",
        "integration_source": task.integration_source or "",
        "source_url": "",
        "source_label": "",
        "is_locked": False,
        "calendar_owner_id": str(task.author_id),
        "calendar_owner_name": _display_user_name(task.author),
        "is_shared_calendar": False,
        "can_edit": task.author_id == current_user_id,
        "attachments": [],
        "hub_meta": _build_task_hub_meta(task),
    }
    payload.update(_build_related_message_capture_meta(task))
    return payload


def _serialize_event_list(events, *, current_user_id, editable_owner_ids):
    source_record_lookup = _build_event_source_record_lookup(events)
    return [
        _serialize_event(
            event,
            current_user_id=current_user_id,
            editable_owner_ids=editable_owner_ids,
            source_record_lookup=source_record_lookup,
        )
        for event in events
    ]


def _serialize_task_list(tasks, *, current_user_id):
    return [
        _serialize_task(task, current_user_id=current_user_id)
        for task in tasks
    ]


def _format_hub_clock(value):
    local_value = _normalize_hub_datetime(value)
    if local_value is None:
        return ""
    hour = local_value.hour
    minute = local_value.minute
    meridiem = "오후" if hour >= 12 else "오전"
    display_hour = hour % 12 or 12
    return f"{meridiem} {display_hour}:{minute:02d}"


def _format_hub_range_text(*, start_at=None, end_at=None, is_all_day=False):
    start_value = _normalize_hub_datetime(start_at)
    end_value = _normalize_hub_datetime(end_at) or start_value
    if start_value is None:
        return ""
    if is_all_day:
        if end_value and end_value.date() != start_value.date():
            return f"{start_value.strftime('%m/%d')} - {end_value.strftime('%m/%d')} 종일"
        return "하루 종일"
    if end_value and end_value.date() == start_value.date():
        if end_value.time() != start_value.time():
            return f"{_format_hub_clock(start_value)} - {_format_hub_clock(end_value)}"
        return _format_hub_clock(start_value)
    if end_value:
        return f"{start_value.strftime('%m/%d')} {_format_hub_clock(start_value)} - {end_value.strftime('%m/%d')} {_format_hub_clock(end_value)}"
    return _format_hub_clock(start_value)


def _build_hub_item(
    *,
    hub_id,
    item_kind,
    title,
    start_at=None,
    end_at=None,
    sort_at=None,
    is_all_day=False,
    meta_text="",
    status_label="",
    tone="neutral",
    source_url="",
    source_label="",
    has_attachment=False,
    is_readonly=True,
    source_item_kind="",
    source_item_id="",
):
    safe_start = _normalize_hub_datetime(start_at)
    safe_end = _normalize_hub_datetime(end_at) or safe_start
    safe_sort = _normalize_hub_datetime(sort_at) or safe_start or safe_end
    normalized_tone = str(tone or "neutral").strip().lower()
    if normalized_tone == "complete":
        normalized_tone = "done"
    if normalized_tone not in HUB_TONE_PRIORITY:
        normalized_tone = "neutral"
    return {
        "id": str(hub_id),
        "item_kind": str(item_kind or "").strip(),
        "date_key": _build_hub_date_key(safe_sort, safe_start, safe_end),
        "sort_at": _serialize_hub_datetime(safe_sort),
        "start_at": _serialize_hub_datetime(safe_start),
        "end_at": _serialize_hub_datetime(safe_end),
        "is_all_day": bool(is_all_day),
        "title": _compact_hub_text(title, default=HUB_SERVICE_LABELS.get(item_kind, "항목")),
        "meta_text": _compact_hub_text(meta_text),
        "status_label": _compact_hub_text(status_label),
        "tone": normalized_tone,
        "source_url": str(source_url or "").strip(),
        "source_label": _compact_hub_text(source_label),
        "has_attachment": bool(has_attachment),
        "is_readonly": bool(is_readonly),
        "source_item_kind": str(source_item_kind or "").strip(),
        "source_item_id": str(source_item_id or "").strip(),
    }


def _build_native_event_hub_item(event, *, current_user_id, editable_owner_ids):
    meta_text = _format_hub_range_text(
        start_at=event.start_time,
        end_at=event.end_time,
        is_all_day=event.is_all_day,
    )
    return _build_hub_item(
        hub_id=f"event:{event.id}",
        item_kind="event",
        title=event.title,
        start_at=event.start_time,
        end_at=event.end_time,
        sort_at=event.start_time,
        is_all_day=event.is_all_day,
        meta_text=meta_text,
        status_label="",
        tone="neutral",
        source_url="",
        source_label="",
        has_attachment=event.attachments.exists(),
        is_readonly=event.is_locked or event.author_id not in editable_owner_ids,
        source_item_kind="event",
        source_item_id=event.id,
    )


def _build_native_task_hub_item(task, *, current_user_id):
    due_at = task.due_at
    status_value = task.status or CalendarTask.Status.OPEN
    status_label = "완료" if status_value == CalendarTask.Status.DONE else "진행 중"
    tone = "done" if status_value == CalendarTask.Status.DONE else "neutral"
    meta_text = ""
    if due_at:
        meta_text = (
            f"{_format_hub_clock(due_at)}까지"
            if task.has_time
            else "시간 미정"
        )
    return _build_hub_item(
        hub_id=f"task:{task.id}",
        item_kind="task",
        title=task.title,
        start_at=due_at,
        end_at=due_at,
        sort_at=due_at,
        is_all_day=not bool(task.has_time),
        meta_text=meta_text,
        status_label=status_label,
        tone=tone,
        source_url="",
        source_label="",
        has_attachment=False,
        is_readonly=task.author_id != current_user_id,
        source_item_kind="task",
        source_item_id=task.id,
    )


def _build_owner_setting_lookup(owner_ids):
    return {
        setting.user_id: setting
        for setting in CalendarIntegrationSetting.objects.filter(user_id__in=owner_ids)
    }


def _is_owner_integration_enabled(setting_lookup, *, owner_id, field_name):
    setting = setting_lookup.get(owner_id)
    if setting is None:
        return True
    return bool(getattr(setting, field_name, True))


def _reservation_period_times(reservation):
    school_config = getattr(getattr(reservation.room, "school", None), "config", None)
    slot_time = ""
    slot_label = f"{reservation.period}교시"
    if school_config:
        for slot in school_config.get_period_slots():
            if int(slot.get("id") or 0) != int(reservation.period or 0):
                continue
            slot_label = slot.get("label") or slot_label
            slot_time = slot.get("time") or ""
            break
    if slot_time and "-" in slot_time:
        start_text, end_text = [segment.strip() for segment in slot_time.split("-", 1)]
        try:
            start_clock = datetime.strptime(start_text, "%H:%M").time()
            end_clock = datetime.strptime(end_text, "%H:%M").time()
        except ValueError:
            start_clock = None
            end_clock = None
    else:
        start_clock = None
        end_clock = None
    if not start_clock or not end_clock:
        start_hour = min(22, 8 + max(1, int(reservation.period or 1)))
        start_clock = time(hour=start_hour, minute=0)
        end_clock = (datetime.combine(timezone.localdate(), start_clock) + timedelta(minutes=40)).time()
    start_at = timezone.make_aware(
        datetime.combine(reservation.date, start_clock),
        timezone.get_current_timezone(),
    )
    end_at = timezone.make_aware(
        datetime.combine(reservation.date, end_clock),
        timezone.get_current_timezone(),
    )
    if end_at <= start_at:
        end_at = start_at + timedelta(minutes=40)
    return slot_label, start_at, end_at


def _build_collect_direct_hub_items(owner_ids, setting_lookup):
    enabled_owner_ids = [
        owner_id
        for owner_id in owner_ids
        if _is_owner_integration_enabled(
            setting_lookup,
            owner_id=owner_id,
            field_name="collect_deadline_enabled",
        )
    ]
    if not enabled_owner_ids:
        return []
    try:
        from collect.models import CollectionRequest
    except Exception:
        logger.exception("[ClassCalendar] collect direct hub import failed")
        return []

    today = timezone.localdate()
    queryset = (
        CollectionRequest.objects.filter(creator_id__in=enabled_owner_ids, deadline__isnull=False)
        .exclude(status="archived")
        .annotate(submission_total=Count("submissions", distinct=True))
        .order_by("deadline", "id")
    )
    items = []
    for request_item in queryset:
        deadline = _normalize_hub_datetime(request_item.deadline)
        if deadline is None:
            continue
        if request_item.status == "closed":
            status_label = "완료"
            tone = "done"
        elif request_item.is_deadline_passed:
            status_label = "마감 지남"
            tone = "warning"
        elif deadline.date() == today:
            status_label = "오늘 마감"
            tone = "warning"
        else:
            status_label = "진행 중"
            tone = "neutral"
        submission_total = int(getattr(request_item, "submission_total", 0) or 0)
        meta_bits = [_format_hub_clock(deadline)]
        meta_bits.append(f"제출 {submission_total}건" if submission_total else "제출 대기")
        items.append(
            _build_hub_item(
                hub_id=f"collect:{request_item.id}",
                item_kind="collect",
                title=request_item.title,
                start_at=deadline,
                end_at=deadline,
                sort_at=deadline,
                is_all_day=False,
                meta_text=" · ".join(bit for bit in meta_bits if bit),
                status_label=status_label,
                tone=tone,
                source_url=reverse("collect:request_detail", kwargs={"request_id": request_item.id}),
                source_label="수합 상세로 이동",
                has_attachment=False,
                is_readonly=True,
            )
        )
    return items


def _build_signature_direct_hub_items(owner_ids, setting_lookup):
    enabled_owner_ids = [
        owner_id
        for owner_id in owner_ids
        if _is_owner_integration_enabled(
            setting_lookup,
            owner_id=owner_id,
            field_name="signatures_training_enabled",
        )
    ]
    if not enabled_owner_ids:
        return []
    try:
        from signatures.models import TrainingSession
    except Exception:
        logger.exception("[ClassCalendar] signatures direct hub import failed")
        return []

    today = timezone.localdate()
    queryset = (
        TrainingSession.objects.filter(created_by_id__in=enabled_owner_ids)
        .annotate(signature_total=Count("signatures", distinct=True))
        .order_by("datetime", "id")
    )
    items = []
    for session in queryset:
        session_datetime = _normalize_hub_datetime(session.datetime)
        if session_datetime is None:
            continue
        if not session.is_active:
            status_label = "완료"
            tone = "done"
        elif session_datetime.date() < today:
            status_label = "지난 일정"
            tone = "warning"
        elif session_datetime.date() == today:
            status_label = "오늘"
            tone = "warning"
        else:
            status_label = "예정"
            tone = "neutral"
        meta_bits = [_format_hub_clock(session_datetime)]
        if session.location:
            meta_bits.append(_compact_hub_text(session.location))
        items.append(
            _build_hub_item(
                hub_id=f"signature:{session.uuid}",
                item_kind="signature",
                title=session.title,
                start_at=session_datetime,
                end_at=session_datetime + timedelta(minutes=60),
                sort_at=session_datetime,
                is_all_day=False,
                meta_text=" · ".join(bit for bit in meta_bits if bit),
                status_label=status_label,
                tone=tone,
                source_url=reverse("signatures:detail", kwargs={"uuid": session.uuid}),
                source_label="사인 상세로 이동",
                has_attachment=False,
                is_readonly=True,
            )
        )
    return items


def _build_consent_direct_hub_items(owner_ids, setting_lookup):
    enabled_owner_ids = [
        owner_id
        for owner_id in owner_ids
        if _is_owner_integration_enabled(
            setting_lookup,
            owner_id=owner_id,
            field_name="consent_expiry_enabled",
        )
    ]
    if not enabled_owner_ids:
        return []
    try:
        from consent.models import SignatureRecipient, SignatureRequest
    except Exception:
        logger.exception("[ClassCalendar] consent direct hub import failed")
        return []

    pending_statuses = [
        SignatureRecipient.STATUS_PENDING,
        SignatureRecipient.STATUS_VERIFIED,
    ]
    today = timezone.localdate()
    queryset = (
        SignatureRequest.objects.filter(created_by_id__in=enabled_owner_ids, sent_at__isnull=False)
        .annotate(
            recipient_count=Count("recipients", distinct=True),
            pending_recipient_count=Count(
                "recipients",
                filter=Q(recipients__status__in=pending_statuses),
                distinct=True,
            ),
        )
        .order_by("sent_at", "id")
    )
    items = []
    for request_item in queryset:
        expires_at = _normalize_hub_datetime(request_item.link_expires_at)
        if expires_at is None:
            continue
        pending_count = int(getattr(request_item, "pending_recipient_count", 0) or 0)
        recipient_count = int(getattr(request_item, "recipient_count", 0) or 0)
        if request_item.status == request_item.STATUS_COMPLETED or pending_count == 0:
            status_label = "완료"
            tone = "done"
        elif request_item.is_link_expired:
            status_label = "만료"
            tone = "warning"
        elif expires_at.date() == today:
            status_label = "오늘 만료"
            tone = "warning"
        else:
            status_label = "응답 대기"
            tone = "neutral"
        meta_bits = [_format_hub_clock(expires_at)]
        meta_bits.append(f"미완료 {pending_count}명" if pending_count else (f"대상 {recipient_count}명" if recipient_count else "응답 확인"))
        items.append(
            _build_hub_item(
                hub_id=f"consent:{request_item.request_id}",
                item_kind="consent",
                title=request_item.title,
                start_at=expires_at,
                end_at=expires_at,
                sort_at=expires_at,
                is_all_day=False,
                meta_text=" · ".join(bit for bit in meta_bits if bit),
                status_label=status_label,
                tone=tone,
                source_url=reverse("consent:detail", kwargs={"request_id": request_item.request_id}),
                source_label="동의서 상세로 이동",
                has_attachment=False,
                is_readonly=True,
            )
        )
    return items


def _build_reservation_direct_hub_items(owner_ids, setting_lookup):
    enabled_owner_ids = [
        owner_id
        for owner_id in owner_ids
        if _is_owner_integration_enabled(
            setting_lookup,
            owner_id=owner_id,
            field_name="reservation_enabled",
        )
    ]
    if not enabled_owner_ids:
        return []
    try:
        from reservations.models import Reservation
    except Exception:
        logger.exception("[ClassCalendar] reservation direct hub import failed")
        return []

    reservations = list(
        Reservation.objects.filter(created_by_id__in=enabled_owner_ids)
        .select_related("room", "room__school", "room__school__config")
        .order_by("date", "period", "id")
    )
    slot_counts = {}
    for reservation in reservations:
        slot_key = (reservation.created_by_id, reservation.date.isoformat(), int(reservation.period or 0))
        slot_counts[slot_key] = slot_counts.get(slot_key, 0) + 1

    items = []
    for reservation in reservations:
        slot_label, start_at, end_at = _reservation_period_times(reservation)
        slot_key = (reservation.created_by_id, reservation.date.isoformat(), int(reservation.period or 0))
        has_conflict = slot_counts.get(slot_key, 0) > 1
        meta_bits = [slot_label, _compact_hub_text(reservation.room.name)]
        items.append(
            _build_hub_item(
                hub_id=f"reservation:{reservation.id}",
                item_kind="reservation",
                title=reservation.room.name,
                start_at=start_at,
                end_at=end_at,
                sort_at=start_at,
                is_all_day=False,
                meta_text=" · ".join(bit for bit in meta_bits if bit),
                status_label="확인 필요" if has_conflict else "예약됨",
                tone="warning" if has_conflict else "neutral",
                source_url=f"{reverse('reservations:reservation_index', kwargs={'school_slug': reservation.room.school.slug})}?{urlencode({'date': reservation.date.strftime('%Y-%m-%d'), 'reservation': reservation.id})}",
                source_label="예약 상세로 이동",
                has_attachment=False,
                is_readonly=True,
            )
        )
    return items


def _build_message_direct_hub_items(user):
    if not getattr(user, "is_authenticated", False) or not _is_message_capture_enabled_for_user(user):
        return []

    captures = (
        CalendarMessageCapture.objects.filter(author=user, linked_for_at__isnull=False)
        .exclude(follow_up_state=CalendarMessageCapture.FollowUpState.DONE)
        .prefetch_related("attachments")
        .order_by("linked_for_at", "created_at", "id")
    )
    items = []
    for capture in captures:
        linked_for_at = _normalize_hub_datetime(capture.linked_for_at)
        if linked_for_at is None:
            continue
        follow_up_state = _normalize_follow_up_state_value(capture)
        if follow_up_state == CalendarMessageCapture.FollowUpState.DONE:
            continue
        status_label = _follow_up_state_label(follow_up_state)
        tone = "warning" if follow_up_state == CalendarMessageCapture.FollowUpState.NEEDS_CHECK else "neutral"
        preview_text = _compact_hub_text(_get_message_capture_manual_note(capture))
        if not preview_text:
            preview_text = _compact_hub_text(
                capture.initial_extract_payload.get("summary_text") if isinstance(capture.initial_extract_payload, dict) else ""
            )
        if not preview_text:
            preview_text = _compact_hub_text(
                capture.parse_payload.get("summary_text") if isinstance(capture.parse_payload, dict) else ""
            )
        if not preview_text:
            preview_text = _compact_hub_text(_build_message_capture_archive_preview(capture.raw_text))
        meta_bits = []
        if preview_text:
            meta_bits.append(preview_text)
        if capture.attachments.exists():
            meta_bits.append("첨부 있음")
        items.append(
            _build_hub_item(
                hub_id=f"message:{capture.id}",
                item_kind="message",
                title=capture.extracted_title or preview_text or "저장한 메시지",
                start_at=linked_for_at,
                end_at=linked_for_at,
                sort_at=linked_for_at,
                is_all_day=True,
                meta_text=" · ".join(bit for bit in meta_bits if bit),
                status_label=status_label,
                tone=tone,
                source_url=_build_message_capture_deep_link(capture.id),
                source_label="메시지 보관함으로 이동",
                has_attachment=capture.attachments.exists(),
                is_readonly=True,
            )
        )
    return items


def _iter_hub_item_date_keys(item):
    start_at = _parse_local_date_value(item.get("start_at") or item.get("sort_at"))
    end_at = _parse_local_date_value(item.get("end_at") or item.get("start_at") or item.get("sort_at"))
    start_date = _to_local_date(start_at)
    end_date = _to_local_date(end_at) or start_date
    if start_date is None:
        return []
    if end_date is None or end_date < start_date:
        end_date = start_date
    date_keys = []
    cursor = start_date
    while cursor <= end_date:
        date_keys.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return date_keys


def _build_day_markers(hub_items):
    markers = {}
    for item in hub_items:
        item_kind = str(item.get("item_kind") or "").strip()
        tone = str(item.get("tone") or "neutral").strip().lower()
        if tone not in HUB_TONE_PRIORITY:
            tone = "neutral"
        for date_key in _iter_hub_item_date_keys(item):
            marker = markers.setdefault(
                date_key,
                {
                    "count": 0,
                    "top_tone": "neutral",
                    "kinds": [],
                },
            )
            marker["count"] += 1
            if HUB_TONE_PRIORITY[tone] > HUB_TONE_PRIORITY.get(marker["top_tone"], 0):
                marker["top_tone"] = tone
            if item_kind and item_kind not in marker["kinds"]:
                marker["kinds"].append(item_kind)
    return markers


def _sort_hub_items(hub_items):
    tone_sort = {
        "warning": 0,
        "neutral": 1,
        "done": 2,
    }

    def item_key(item):
        sort_value = str(item.get("sort_at") or item.get("date_key") or "")
        timed_rank = 0 if item.get("start_at") and not item.get("is_all_day") else 1
        return (
            str(item.get("date_key") or ""),
            timed_rank,
            tone_sort.get(str(item.get("tone") or "neutral"), 1),
            sort_value,
            str(item.get("title") or ""),
        )

    return sorted(hub_items, key=item_key)


def _build_calendar_hub_payload(*, request_user, visible_owner_ids, editable_owner_ids, visible_events, visible_tasks):
    setting_lookup = _build_owner_setting_lookup(visible_owner_ids)
    hub_items = [
        _build_native_event_hub_item(
            event,
            current_user_id=request_user.id,
            editable_owner_ids=editable_owner_ids,
        )
        for event in visible_events
    ]
    hub_items.extend(
        _build_native_task_hub_item(task, current_user_id=request_user.id)
        for task in visible_tasks
    )
    hub_items.extend(_build_collect_direct_hub_items(visible_owner_ids, setting_lookup))
    hub_items.extend(_build_signature_direct_hub_items(visible_owner_ids, setting_lookup))
    hub_items.extend(_build_consent_direct_hub_items(visible_owner_ids, setting_lookup))
    hub_items.extend(_build_reservation_direct_hub_items(visible_owner_ids, setting_lookup))
    hub_items.extend(_build_message_direct_hub_items(request_user))
    sorted_items = _sort_hub_items(hub_items)
    return sorted_items, _build_day_markers(sorted_items)


def _choose_default_selected_date_from_day_markers(day_markers, *, fallback_date):
    fallback_key = fallback_date.isoformat()
    keys = sorted(str(key) for key in (day_markers or {}).keys())
    if fallback_key in day_markers:
        return fallback_key
    future_keys = [key for key in keys if key > fallback_key]
    past_keys = [key for key in keys if key < fallback_key]
    if future_keys:
        return future_keys[0]
    if past_keys:
        return past_keys[-1]
    return fallback_key


def _get_integration_setting_for_user(user):
    return get_or_create_integration_setting(user)


def _get_active_classroom_for_user(request):
    return get_active_classroom_for_request(request)


def _get_calendar_access_for_user(user):
    return resolve_calendar_access_for_user(user)


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
    return get_visible_events_queryset(
        request.user,
        active_classroom=active_classroom,
        visible_owner_ids=visible_owner_ids,
    ).exclude(
        is_locked=True,
        integration_source__in=DIRECT_HUB_INTEGRATION_SOURCES,
    )



def _get_teacher_visible_tasks(request):
    return get_visible_tasks_queryset(request.user)


def _get_editable_event(request, event_id, editable_owner_ids):
    return get_object_or_404(
        CalendarEvent.objects.select_related("author").prefetch_related("blocks"),
        id=event_id,
        author_id__in=editable_owner_ids,
    )


def _get_editable_task(request, task_id):
    return get_object_or_404(
        CalendarTask.objects.select_related("author"),
        id=task_id,
        author=request.user,
    )


def _sync_integrations_if_needed(request, force=False):
    return


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
        return redirect(_build_home_calendar_surface_url(request, include_request_state=False))

    bridge_context = _resolve_sheetbook_calendar_entry_for_user(request, request.user)
    if bridge_context.get("sheetbook_entry_url"):
        return redirect(bridge_context["sheetbook_entry_url"])
    return redirect(_build_home_calendar_surface_url(request, include_request_state=False))


@login_required
def legacy_main_redirect(request):
    return _redirect_to_home_calendar_surface(request)


def _redirect_legacy_today_panel(request):
    if str(request.GET.get("panel") or "").strip().lower() != "today-memos":
        return None
    return _redirect_to_home_calendar_surface(request)


def build_calendar_surface_context(
    request,
    *,
    embedded_sheetbook_context=None,
    page_variant="main",
    embedded_surface="page",
):
    visible_owner_ids, editable_owner_ids, incoming_calendars = _get_calendar_access_for_user(request.user)
    integration_setting = _get_integration_setting_for_user(request.user)
    service = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
    message_capture_ui = build_message_capture_ui_context(request.user)
    messagebox_home_card = build_messagebox_home_card_context(request.user)
    active_classroom = _get_active_classroom_for_user(request)
    visible_events = list(_get_teacher_visible_events(request, visible_owner_ids))
    visible_tasks = list(_get_teacher_visible_tasks(request))
    hub_items, day_markers = _build_calendar_hub_payload(
        request_user=request.user,
        visible_owner_ids=visible_owner_ids,
        editable_owner_ids=editable_owner_ids,
        visible_events=visible_events,
        visible_tasks=visible_tasks,
    )
    calendar_page_url = _build_home_calendar_surface_url(request, include_request_state=False)
    calendar_api_base_url = reverse("classcalendar:main")
    main_url = calendar_page_url
    today_url = calendar_page_url
    create_api_url = reverse("classcalendar:api_create_event")
    today_focus = normalize_today_focus(request.GET.get("focus"))
    today_date = timezone.localdate()
    requested_date = str(request.GET.get("date") or "").strip()
    initial_selected_date = requested_date or _choose_default_selected_date_from_day_markers(
        day_markers,
        fallback_date=today_date,
    )
    initial_open_create = str(request.GET.get("action") or "").strip().lower() == "create"
    initial_open_event_id = str(request.GET.get("open_event") or "").strip()
    initial_open_task_id = str(request.GET.get("open_task") or "").strip()
    today_workspace = build_today_execution_context(
        request.user,
        active_classroom=active_classroom,
        target_date=today_date,
        main_url=main_url,
        today_url=today_url,
        create_api_url=create_api_url,
        today_focus=today_focus,
    )
    normalized_surface = str(embedded_surface or "page").strip().lower()
    if normalized_surface not in {"page", "sheetbook", "home"}:
        normalized_surface = "page"
    return {
        "service": service,
        "title": service.title if service else "학급 캘린더",
        "events_json": _serialize_event_list(
            visible_events,
            current_user_id=request.user.id,
            editable_owner_ids=editable_owner_ids,
        ),
        "tasks_json": _serialize_task_list(
            visible_tasks,
            current_user_id=request.user.id,
        ),
        "hub_items_json": hub_items,
        "day_markers_json": day_markers,
        "integration_settings_json": serialize_integration_setting(integration_setting),
        "reservation_windows": _build_reservation_windows_for_user(request.user),
        "share_enabled": bool(integration_setting.share_enabled),
        "share_url": _build_share_url(request, integration_setting.share_uuid),
        "calendar_owner_options_json": _build_calendar_owner_options(request.user, editable_owner_ids),
        "owner_collaborators": _build_owner_collaborator_rows(request.user),
        "incoming_calendars": incoming_calendars,
        "message_capture_enabled": message_capture_ui["enabled"],
        "message_capture_item_types_enabled": message_capture_ui["item_types_enabled"],
        "message_capture_limits_json": message_capture_ui["limits"],
        "message_capture_urls_json": message_capture_ui["urls"],
        "messagebox_home_card": messagebox_home_card,
        "calendar_page_variant": page_variant,
        "today_workspace": today_workspace,
        "today_url": today_url,
        "today_focus": today_focus,
        "today_all_url": today_workspace["today_all_url"],
        "today_memo_url": today_workspace["today_memo_url"],
        "today_review_url": today_workspace["today_review_url"],
        "main_url": main_url,
        "calendar_page_url": calendar_page_url,
        "calendar_api_base_url": calendar_api_base_url,
        "initial_selected_date": initial_selected_date or today_workspace["date_key"],
        "initial_open_create": initial_open_create,
        "initial_open_event_id": initial_open_event_id,
        "initial_open_task_id": initial_open_task_id,
        "embedded_sheetbook_context": embedded_sheetbook_context,
        "embedded_sheetbook_context_json": embedded_sheetbook_context or {},
        "calendar_embed_mode": normalized_surface,
        "is_embedded_in_sheetbook": normalized_surface == "sheetbook",
        "is_embedded_on_home": normalized_surface == "home",
        "hide_navbar": normalized_surface == "sheetbook",
    }


def _build_calendar_page_context(request, *, embedded_sheetbook_context=None, page_variant="main"):
    embedded_surface = "sheetbook" if embedded_sheetbook_context else "page"
    return build_calendar_surface_context(
        request,
        embedded_sheetbook_context=embedded_sheetbook_context,
        page_variant=page_variant,
        embedded_surface=embedded_surface,
    )


@login_required
@xframe_options_sameorigin
def main_view(request):
    return _redirect_to_home_calendar_surface(request)


@login_required
@xframe_options_sameorigin
def today_view(request):
    return _redirect_to_home_calendar_surface(request)


@login_required
@require_POST
def collaborator_add(request):
    lookup = (request.POST.get("collaborator_query") or "").strip()
    if not lookup:
        messages.error(request, "협업자로 추가할 사용자의 가입시 적었던 이메일을 입력해 주세요.")
        return redirect(_build_home_calendar_surface_url(request, include_request_state=False))

    collaborator = (
        User.objects.filter(email__iexact=lookup)
        .only("id", "username", "email", "first_name", "last_name")
        .first()
    )
    if not collaborator:
        messages.error(request, "해당 이메일의 사용자를 찾지 못했습니다. 가입시 적었던 이메일인지 확인해 주세요.")
        return redirect(_build_home_calendar_surface_url(request, include_request_state=False))
    if collaborator.id == request.user.id:
        messages.error(request, "본인은 협업자로 추가할 수 없습니다.")
        return redirect(_build_home_calendar_surface_url(request, include_request_state=False))

    can_edit = _parse_bool_value(request.POST.get("can_edit", "true"))
    relation, created = CalendarCollaborator.objects.update_or_create(
        owner=request.user,
        collaborator=collaborator,
        defaults={"can_edit": can_edit},
    )
    logger.info(
        "[ClassCalendar] collaborator updated | owner_id=%s | collaborator_id=%s | can_edit=%s | created=%s",
        request.user.id,
        collaborator.id,
        can_edit,
        created,
    )
    if created:
        messages.success(request, f"{_display_user_name(collaborator)} 님을 협업자로 추가했습니다.")
    else:
        mode_text = "편집 가능" if relation.can_edit else "읽기 전용"
        messages.info(request, f"{_display_user_name(collaborator)} 님 협업 권한을 {mode_text}으로 업데이트했습니다.")
    return redirect(_build_home_calendar_surface_url(request, include_request_state=False))


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
        return redirect(_build_home_calendar_surface_url(request, include_request_state=False))

    collaborator_name = _display_user_name(relation.collaborator)
    logger.info(
        "[ClassCalendar] collaborator removed | owner_id=%s | collaborator_id=%s",
        request.user.id,
        collaborator_id,
    )
    relation.delete()
    messages.info(request, f"{collaborator_name} 님의 협업 권한을 해제했습니다.")
    return redirect(_build_home_calendar_surface_url(request, include_request_state=False))


@login_required
@require_POST
def share_enable(request):
    setting = _get_integration_setting_for_user(request.user)
    if not setting.share_enabled:
        setting.share_enabled = True
        setting.save(update_fields=["share_enabled", "updated_at"])
    logger.info("[ClassCalendar] public share enabled | owner_id=%s | share_uuid=%s", request.user.id, setting.share_uuid)
    messages.success(request, "공유 링크를 활성화했습니다.")
    return redirect(_build_home_calendar_surface_url(request, include_request_state=False))


@login_required
@require_POST
def share_disable(request):
    setting = _get_integration_setting_for_user(request.user)
    if setting.share_enabled:
        setting.share_enabled = False
        setting.save(update_fields=["share_enabled", "updated_at"])
    logger.info("[ClassCalendar] public share disabled | owner_id=%s | share_uuid=%s", request.user.id, setting.share_uuid)
    messages.info(request, "공유 링크를 비활성화했습니다.")
    return redirect(_build_home_calendar_surface_url(request, include_request_state=False))


@login_required
@require_POST
def share_rotate(request):
    setting = _get_integration_setting_for_user(request.user)
    setting.share_uuid = uuid.uuid4()
    setting.share_enabled = True
    setting.save(update_fields=["share_uuid", "share_enabled", "updated_at"])
    logger.info("[ClassCalendar] public share rotated | owner_id=%s | share_uuid=%s", request.user.id, setting.share_uuid)
    messages.success(request, "공유 링크를 재발급했습니다.")
    return redirect(_build_home_calendar_surface_url(request, include_request_state=False))


@require_GET
def shared_view(request, share_uuid):
    setting = (
        CalendarIntegrationSetting.objects.select_related("user")
        .filter(share_uuid=share_uuid, share_enabled=True)
        .first()
    )
    if not setting:
        response = render(request, "classcalendar/shared_unavailable.html", status=404)
        return _apply_sensitive_cache_headers(response)

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
    response = render(request, "classcalendar/shared.html", context)
    return _apply_sensitive_cache_headers(response)


@login_required
@require_GET
def api_events(request):
    visible_owner_ids, editable_owner_ids, _ = _get_calendar_access_for_user(request.user)
    visible_events = list(_get_teacher_visible_events(request, visible_owner_ids))
    visible_tasks = list(_get_teacher_visible_tasks(request))
    hub_items, day_markers = _build_calendar_hub_payload(
        request_user=request.user,
        visible_owner_ids=visible_owner_ids,
        editable_owner_ids=editable_owner_ids,
        visible_events=visible_events,
        visible_tasks=visible_tasks,
    )
    events_data = _serialize_event_list(
        visible_events,
        current_user_id=request.user.id,
        editable_owner_ids=editable_owner_ids,
    )
    tasks_data = _serialize_task_list(
        visible_tasks,
        current_user_id=request.user.id,
    )
    response = JsonResponse(
        {
            "status": "success",
            "events": events_data,
            "tasks": tasks_data,
            "hub_items": hub_items,
            "day_markers": day_markers,
        }
    )
    return _apply_workspace_cache_headers(response)


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
def api_delete_task(request, task_id):
    task = _get_editable_task(request, task_id)
    task_id_str = str(task.id)
    task.delete()
    return JsonResponse({"status": "success", "deleted_id": task_id_str})


@login_required
@require_POST
def api_message_capture_save(request):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 기능이 아직 활성화되지 않았습니다.")

    save_started_at = timezone.now()
    form = MessageCaptureParseForm(request.POST)
    if not form.is_valid():
        logger.warning(
            "[ClassCalendar][MessageCapture] save_failed user_id=%s reason=form_invalid",
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
    manual_date = form.cleaned_data.get("manual_date")
    manual_note = form.cleaned_data.get("manual_note") or ""
    uploaded_files = request.FILES.getlist("files")

    if not raw_text.strip() and not uploaded_files:
        logger.warning(
            "[ClassCalendar][MessageCapture] save_failed user_id=%s reason=empty_input",
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
            "[ClassCalendar][MessageCapture] save_failed user_id=%s reason=too_many_files files=%s",
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
        .prefetch_related("attachments", "candidates")
        .first()
    )
    if existing_capture:
        _update_message_capture_manual_inputs(
            existing_capture,
            manual_date=manual_date,
            manual_note=manual_note,
        )
        payload = _serialize_message_capture_archive_detail(existing_capture)
        payload.update({"reused": True, "message": "이미 보관한 메시지예요."})
        return JsonResponse(payload)

    attachment_checksums, upload_error_response = _validate_message_capture_uploads(
        uploaded_files=uploaded_files,
        user_id=request.user.id,
        operation_label="save",
    )
    if upload_error_response:
        return upload_error_response

    parse_payload = {
        "archive_only": True,
        "summary_text": "아직 일정으로 읽지 않은 메시지",
        "attachment_count": len(uploaded_files),
    }
    parse_payload = _merge_message_capture_manual_inputs(
        parse_payload,
        manual_date=manual_date,
        manual_note=manual_note,
    )

    with transaction.atomic():
        try:
            capture = CalendarMessageCapture.objects.create(
                author=request.user,
                raw_text=raw_text,
                normalized_text=raw_text.strip(),
                source_hint=source_hint,
                parse_status=CalendarMessageCapture.ParseStatus.NEEDS_REVIEW,
                confidence_score=0,
                predicted_item_type=CalendarMessageCapture.ItemType.UNKNOWN,
                decision_source=CalendarMessageCapture.DecisionSource.MANUAL,
                extracted_priority=CalendarMessageCapture.Priority.NORMAL,
                parse_payload=parse_payload,
                initial_extract_payload={},
                rule_version="archive-only",
                ml_scores={},
                llm_used=False,
                idempotency_key=idempotency_key,
                content_cache_key="",
            )
        except IntegrityError:
            capture = (
                CalendarMessageCapture.objects.filter(author=request.user, idempotency_key=idempotency_key)
                .prefetch_related("attachments", "candidates")
                .first()
            )
            if capture:
                _update_message_capture_manual_inputs(
                    capture,
                    manual_date=manual_date,
                    manual_note=manual_note,
                )
                payload = _serialize_message_capture_archive_detail(capture)
                payload.update({"reused": True, "message": "이미 보관한 메시지예요."})
                return JsonResponse(payload)
            raise

        _create_message_capture_attachments(
            capture,
            uploaded_files,
            attachment_checksums,
            uploaded_by=request.user,
        )

    capture = CalendarMessageCapture.objects.prefetch_related("attachments", "candidates").get(id=capture.id)
    save_elapsed_ms = int((timezone.now() - save_started_at).total_seconds() * 1000)
    logger.info(
        "[ClassCalendar][MessageCapture] save_result user_id=%s capture_id=%s files=%s elapsed_ms=%s",
        request.user.id,
        capture.id,
        capture.attachments.count(),
        save_elapsed_ms,
    )
    payload = _serialize_message_capture_archive_detail(capture)
    payload.update({"reused": False, "message": "메시지를 보관함에 저장했어요."})
    return JsonResponse(payload, status=201)


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
    manual_date = form.cleaned_data.get("manual_date")
    manual_note = form.cleaned_data.get("manual_note") or ""
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
        .prefetch_related("attachments", "candidates")
        .first()
    )
    if existing_capture:
        _update_message_capture_manual_inputs(
            existing_capture,
            manual_date=manual_date,
            manual_note=manual_note,
        )
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

    attachment_checksums, upload_error_response = _validate_message_capture_uploads(
        uploaded_files=uploaded_files,
        user_id=request.user.id,
        operation_label="parse",
    )
    if upload_error_response:
        return upload_error_response

    parse_result = _build_message_capture_parse_result(
        user=request.user,
        raw_text=raw_text,
        source_hint=source_hint,
        uploaded_files=uploaded_files,
        attachment_checksums=attachment_checksums,
    )
    parsed = parse_result["parsed"]
    content_cache_key = parse_result["content_cache_key"]
    cached_capture = (
        CalendarMessageCapture.objects.filter(
            author=request.user,
            content_cache_key=content_cache_key,
            rule_version=MESSAGE_CAPTURE_RULE_VERSION,
            )
          .prefetch_related("attachments", "candidates")
          .first()
    )
    if cached_capture:
        _update_message_capture_manual_inputs(
            cached_capture,
            manual_date=manual_date,
            manual_note=manual_note,
        )
        parse_elapsed_ms = int((timezone.now() - parse_started_at).total_seconds() * 1000)
        logger.info(
            "[ClassCalendar][MessageCapture] parse_cache_hit user_id=%s capture_id=%s parse_status=%s candidates=%s elapsed_ms=%s",
            request.user.id,
            cached_capture.id,
            cached_capture.parse_status,
            cached_capture.candidates.count(),
            parse_elapsed_ms,
        )
        return JsonResponse(_serialize_message_capture(cached_capture, reused=True))

    with transaction.atomic():
        try:
            capture = CalendarMessageCapture.objects.create(
                author=request.user,
                raw_text=raw_text,
                source_hint=source_hint,
                idempotency_key=idempotency_key,
            )
            _apply_message_capture_parse_result(capture, parse_result)
            capture.parse_payload = _merge_message_capture_manual_inputs(
                capture.parse_payload,
                manual_date=manual_date,
                manual_note=manual_note,
            )
            capture.save()
        except IntegrityError:
            capture = (
                CalendarMessageCapture.objects.filter(author=request.user, idempotency_key=idempotency_key)
                .prefetch_related("attachments", "candidates")
                .first()
            )
            if capture:
                _update_message_capture_manual_inputs(
                    capture,
                    manual_date=manual_date,
                    manual_note=manual_note,
                )
                return JsonResponse(_serialize_message_capture(capture, reused=True))
            raise

        _create_message_capture_attachments(
            capture,
            uploaded_files,
            attachment_checksums,
            uploaded_by=request.user,
        )

        _create_message_capture_candidates(capture, parsed.get("candidates") or [])

    capture = CalendarMessageCapture.objects.prefetch_related("attachments", "candidates").get(id=capture.id)
    parse_elapsed_ms = int((timezone.now() - parse_started_at).total_seconds() * 1000)
    logger.info(
        "[ClassCalendar][MessageCapture] parse_result user_id=%s capture_id=%s parse_status=%s confidence=%.2f predicted_item_type=%s files=%s candidates=%s warnings=%s elapsed_ms=%s",
        request.user.id,
        capture.id,
        capture.parse_status,
        float(capture.confidence_score or 0),
        capture.predicted_item_type,
        capture.attachments.count(),
        capture.candidates.count(),
        len((capture.parse_payload or {}).get("warnings") or []),
        parse_elapsed_ms,
    )
    return JsonResponse(_serialize_message_capture(capture), status=201)


@login_required
@require_POST
def api_message_capture_parse_saved(request, capture_id):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 바로 등록 기능이 아직 활성화되지 않았습니다.")
    parse_started_at = timezone.now()

    capture = get_object_or_404(
        CalendarMessageCapture.objects.filter(author=request.user).prefetch_related("attachments", "candidates"),
        id=capture_id,
    )
    if not _is_message_capture_archive_only(capture):
        payload = _serialize_message_capture_archive_detail(capture)
        payload.update({"reused": True, "message": "이미 읽어 둔 메시지예요."})
        return JsonResponse(payload)

    attachments = list(capture.attachments.all().order_by("created_at", "id"))
    if not (capture.raw_text or "").strip() and not attachments:
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "message": "메시지 텍스트 또는 첨부파일 중 하나는 반드시 입력해 주세요.",
            },
            status=400,
        )

    attachment_checksums = [attachment.checksum_sha256 for attachment in attachments]
    parse_result = _build_message_capture_parse_result(
        user=request.user,
        raw_text=capture.raw_text or "",
        source_hint=(capture.source_hint or "unknown").strip()[:30] or "unknown",
        uploaded_files=attachments,
        attachment_checksums=attachment_checksums,
    )

    with transaction.atomic():
        capture_for_update = CalendarMessageCapture.objects.select_for_update().get(id=capture.id, author=request.user)
        manual_date = _get_message_capture_manual_date(capture_for_update)
        manual_note = _get_message_capture_manual_note(capture_for_update)
        update_fields = _apply_message_capture_parse_result(capture_for_update, parse_result)
        capture_for_update.parse_payload = _merge_message_capture_manual_inputs(
            capture_for_update.parse_payload,
            manual_date=manual_date,
            manual_note=manual_note,
        )
        capture_for_update.save(update_fields=update_fields)
        capture_for_update.candidates.all().delete()
        _create_message_capture_candidates(capture_for_update, parse_result["parsed"].get("candidates") or [])

    capture = CalendarMessageCapture.objects.filter(author=request.user).prefetch_related("attachments", "candidates").get(id=capture.id)
    parse_elapsed_ms = int((timezone.now() - parse_started_at).total_seconds() * 1000)
    logger.info(
        "[ClassCalendar][MessageCapture] parse_saved_result user_id=%s capture_id=%s parse_status=%s confidence=%.2f files=%s candidates=%s warnings=%s elapsed_ms=%s",
        request.user.id,
        capture.id,
        capture.parse_status,
        float(capture.confidence_score or 0),
        capture.attachments.count(),
        capture.candidates.count(),
        len((capture.parse_payload or {}).get("warnings") or []),
        parse_elapsed_ms,
    )
    payload = _serialize_message_capture_archive_detail(capture)
    payload.update({"reused": False, "message": "보관한 메시지에서 일정을 찾았어요."})
    return JsonResponse(payload)


@login_required
@require_GET
def api_message_capture_archive(request):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 바로 등록 기능이 아직 활성화되지 않았습니다.")

    query = (request.GET.get("query") or "").strip()
    filter_value = (request.GET.get("filter") or "all").strip().lower() or "all"
    workflow_status = (request.GET.get("workflow_status") or "all").strip().lower() or "all"
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        page = 1

    base_queryset = _apply_message_capture_archive_query(
        _build_message_capture_archive_queryset(request.user),
        query,
    )
    counts = _build_message_capture_archive_counts(base_queryset)
    filtered_queryset = _apply_message_capture_archive_filter(base_queryset, filter_value)
    filtered_queryset = _apply_message_capture_workflow_filter(filtered_queryset, workflow_status).order_by("-created_at", "id")

    page_size = MESSAGE_CAPTURE_ARCHIVE_PAGE_SIZE
    start = (page - 1) * page_size
    end = start + page_size + 1
    page_items = list(filtered_queryset[start:end])
    has_next = len(page_items) > page_size
    items = page_items[:page_size]

    return JsonResponse(
        {
            "status": "success",
            "items": [_serialize_message_capture_archive_item(item) for item in items],
            "counts": counts,
            "page": page,
            "next_cursor_or_page": page + 1 if has_next else None,
            "next_page": page + 1 if has_next else None,
            "has_next": has_next,
            "query": query,
            "filter": filter_value,
            "workflow_status": workflow_status,
        }
    )


@login_required
@require_GET
def api_message_capture_archive_detail(request, capture_id):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 바로 등록 기능이 아직 활성화되지 않았습니다.")

    capture = get_object_or_404(
        CalendarMessageCapture.objects.filter(author=request.user)
        .prefetch_related("attachments", "candidates", "candidates__committed_event")
        .select_related("committed_event", "committed_task"),
        id=capture_id,
    )
    return JsonResponse(_serialize_message_capture_archive_detail(capture))


@login_required
@require_POST
def api_message_capture_delete(request, capture_id):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 바로 등록 기능이 아직 활성화되지 않았습니다.")

    capture = get_object_or_404(
        CalendarMessageCapture.objects.filter(author=request.user)
        .prefetch_related("attachments", "candidates")
        .select_related("committed_event", "committed_task"),
        id=capture_id,
    )
    had_linked_items = bool(capture.committed_event_id or capture.committed_task_id)
    capture.delete()
    return JsonResponse(
        {
            "status": "success",
            "capture_id": str(capture_id),
            "message": (
                "보관 메시지를 지웠어요. 연결된 일정과 할 일은 그대로 남겨두었습니다."
                if had_linked_items
                else "보관 메시지를 지웠어요."
            ),
        }
    )


@login_required
@require_POST
def api_message_capture_link(request, capture_id):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("업무 메시지 보관함이 아직 활성화되지 않았습니다.")

    payload = _extract_request_payload(request)
    capture = get_object_or_404(
        CalendarMessageCapture.objects.filter(author=request.user)
        .prefetch_related("attachments", "candidates", "candidates__committed_event")
        .select_related("committed_event", "committed_task"),
        id=capture_id,
    )

    manual_date = str(payload.get("manual_date") or _get_message_capture_manual_date(capture) or "").strip()
    manual_note = str(payload.get("manual_note") or _get_message_capture_manual_note(capture) or "").strip()
    linked_for_at = _manual_date_to_linked_for_at(manual_date)
    if linked_for_at is None:
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "message": "메시지를 다시 볼 날짜를 선택해 주세요.",
            },
            status=400,
        )

    requested_follow_up_state = str(payload.get("follow_up_state") or "").strip()
    allowed_states = {
        CalendarMessageCapture.FollowUpState.PENDING,
        CalendarMessageCapture.FollowUpState.NEEDS_CHECK,
        CalendarMessageCapture.FollowUpState.DONE,
    }
    follow_up_state = (
        requested_follow_up_state
        if requested_follow_up_state in allowed_states
        else _default_follow_up_state_for_capture(capture)
    )
    completed_at = timezone.now() if follow_up_state == CalendarMessageCapture.FollowUpState.DONE else None

    capture.parse_payload = _merge_message_capture_manual_inputs(
        capture.parse_payload,
        manual_date=manual_date,
        manual_note=manual_note,
    )
    capture.linked_for_at = linked_for_at
    capture.follow_up_state = follow_up_state
    capture.completed_at = completed_at
    capture.save(
        update_fields=[
            "parse_payload",
            "linked_for_at",
            "follow_up_state",
            "completed_at",
            "updated_at",
        ]
    )

    response_payload = _serialize_message_capture_archive_detail(capture)
    response_payload["message"] = (
        "캘린더에 메시지 항목으로 연결했어요."
        if follow_up_state != CalendarMessageCapture.FollowUpState.DONE
        else "메시지를 처리 완료로 저장했어요."
    )
    return JsonResponse(response_payload)


@login_required
@require_POST
def api_message_capture_complete(request, capture_id):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("업무 메시지 보관함이 아직 활성화되지 않았습니다.")

    payload = _extract_request_payload(request)
    capture = get_object_or_404(
        CalendarMessageCapture.objects.filter(author=request.user)
        .prefetch_related("attachments", "candidates", "candidates__committed_event")
        .select_related("committed_event", "committed_task"),
        id=capture_id,
    )

    completed_value = payload.get("completed")
    if completed_value in (None, ""):
        should_complete = capture.completed_at is None
    else:
        should_complete = _parse_bool_value(completed_value)

    capture.completed_at = timezone.now() if should_complete else None
    capture.follow_up_state = (
        CalendarMessageCapture.FollowUpState.DONE
        if should_complete
        else _default_follow_up_state_for_capture(capture)
    )
    capture.save(update_fields=["completed_at", "follow_up_state", "updated_at"])

    response_payload = _serialize_message_capture_archive_detail(capture)
    response_payload["message"] = "처리 완료로 표시했어요." if should_complete else "다시 확인할 메시지로 되돌렸어요."
    return JsonResponse(response_payload)


@login_required
@require_POST
def api_message_capture_commit(request, capture_id):
    if not _is_message_capture_enabled_for_user(request.user):
        return _feature_disabled_response("메시지 바로 등록 기능이 아직 활성화되지 않았습니다.")
    commit_started_at = timezone.now()

    payload = _extract_request_payload(request)
    selected_candidates = _extract_selected_candidates(payload)

    capture = get_object_or_404(
        CalendarMessageCapture.objects.select_related("author", "committed_event", "committed_task").prefetch_related("attachments", "candidates", "candidates__committed_event"),
        id=capture_id,
        author=request.user,
    )

    if selected_candidates:
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

        if not any(item.get("selected", True) for item in selected_candidates):
            return JsonResponse(
                {
                    "status": "error",
                    "code": "validation_error",
                    "message": "저장할 일정을 하나 이상 선택해 주세요.",
                },
                status=400,
            )

        source_context = _resolve_sheetbook_context(
            request.user,
            payload.get("source_sheetbook_id"),
            payload.get("source_tab_id"),
        )
        classroom = _get_active_classroom_for_user(request)
        _, editable_owner_ids, _ = _get_calendar_access_for_user(request.user)

        created_events = []
        reused_events = []
        attachment_warnings = []
        skipped_count = 0
        updated_count = 0
        saved_count = 0
        selected_snapshot = []

        with transaction.atomic():
            capture_for_update = CalendarMessageCapture.objects.select_for_update().get(id=capture.id, author=request.user)
            candidate_map = {
                str(candidate.id): candidate
                for candidate in _locked_message_capture_candidates_queryset(capture_for_update)
            }
            next_sort_order = (
                max((candidate.sort_order for candidate in candidate_map.values()), default=-1) + 1
            )
            for item in selected_candidates:
                candidate_id = item.get("candidate_id")
                candidate = candidate_map.get(candidate_id)
                is_manual_candidate = str(candidate_id or "").startswith("manual:")
                if not candidate and not is_manual_candidate:
                    skipped_count += 1
                    continue

                if not item.get("selected", True):
                    if candidate and candidate.commit_status != CalendarMessageCaptureCandidate.CommitStatus.SAVED:
                        candidate.commit_status = CalendarMessageCaptureCandidate.CommitStatus.SKIPPED
                        candidate.save(update_fields=["commit_status", "updated_at"])
                    skipped_count += 1
                    continue

                candidate_kind = _normalize_selected_candidate_kind(
                    item.get("kind") or (candidate.candidate_kind if candidate else "")
                )
                title = (item.get("title") or (candidate.title if candidate else "") or "메시지에서 만든 일정").strip()
                summary = item.get("summary") or (candidate.summary if candidate else "") or ""
                start_time = _parse_candidate_datetime(item.get("start_time")) or (candidate.start_time if candidate else None)
                end_time = _parse_candidate_datetime(item.get("end_time")) or (candidate.end_time if candidate else None)
                is_all_day = bool(item.get("is_all_day"))

                if not title:
                    return JsonResponse(
                        {
                            "status": "error",
                            "code": "validation_error",
                            "message": "일정 제목을 입력해 주세요.",
                        },
                        status=400,
                    )
                if not start_time or not end_time:
                    return JsonResponse(
                        {
                            "status": "error",
                            "code": "validation_error",
                            "message": f"{title} 일정의 날짜를 확인해 주세요.",
                        },
                        status=400,
                    )
                if end_time < start_time:
                    return JsonResponse(
                        {
                            "status": "error",
                            "code": "validation_error",
                            "message": f"{title} 일정의 종료 시간이 시작 시간보다 빠를 수 없습니다.",
                        },
                        status=400,
                    )

                if not candidate and is_manual_candidate:
                    candidate = CalendarMessageCaptureCandidate.objects.create(
                        capture=capture_for_update,
                        sort_order=next_sort_order,
                        candidate_kind=candidate_kind,
                        title=title[:200],
                        summary=summary,
                        start_time=start_time,
                        end_time=end_time,
                        is_all_day=is_all_day,
                        confidence_score=0,
                        is_recommended=True,
                        needs_check=False,
                        evidence_text="직접 추가한 일정",
                        evidence_payload={"manual_created": True},
                        commit_status=CalendarMessageCaptureCandidate.CommitStatus.PENDING,
                    )
                    next_sort_order += 1
                    candidate_map[candidate_id] = candidate

                selected_snapshot.append(
                    {
                        "candidate_id": candidate_id,
                        "kind": candidate_kind,
                        "title": title,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "is_all_day": is_all_day,
                        "summary": summary,
                    }
                )

                candidate_committed_event = _safe_related_event(candidate)
                if candidate.committed_event_id and candidate_committed_event is None:
                    candidate.committed_event = None
                    candidate.commit_status = CalendarMessageCaptureCandidate.CommitStatus.PENDING
                    candidate.save(update_fields=["committed_event", "commit_status", "updated_at"])
                elif candidate.committed_event_id and candidate_committed_event is not None:
                    reused_events.append(_serialize_compact_event(candidate_committed_event))
                    if candidate.commit_status != CalendarMessageCaptureCandidate.CommitStatus.SAVED:
                        candidate.commit_status = CalendarMessageCaptureCandidate.CommitStatus.SAVED
                        candidate.save(update_fields=["commit_status", "updated_at"])
                    continue

                badge = _candidate_kind_badge_text(candidate_kind)
                prefixed_title = title if title.startswith(f"[{badge}]") else f"[{badge}] {title}"
                create_kwargs = {
                    "title": prefixed_title,
                    "start_time": start_time,
                    "end_time": end_time,
                    "is_all_day": is_all_day,
                    "color": _candidate_kind_color(candidate_kind),
                    "visibility": CalendarEvent.VISIBILITY_TEACHER,
                    "author": request.user,
                    "classroom": classroom,
                    "source": CalendarEvent.SOURCE_LOCAL,
                }
                if source_context:
                    create_kwargs["integration_source"] = "sheetbook_message_capture"
                    create_kwargs["integration_key"] = f"{source_context['sheetbook_id']}:{source_context['tab_id']}:{candidate.id}"
                event = CalendarEvent.objects.create(**create_kwargs)
                _persist_primary_note(event, summary)
                copied, warnings = _copy_capture_attachments_to_event(
                    event,
                    capture_attachments,
                    uploaded_by=request.user,
                )
                if copied:
                    updated_count += 1
                attachment_warnings.extend(warnings)
                created_events.append(_serialize_compact_event(event))
                saved_count += 1

                candidate.candidate_kind = candidate_kind
                candidate.title = title[:200]
                candidate.summary = summary
                candidate.start_time = start_time
                candidate.end_time = end_time
                candidate.is_all_day = is_all_day
                candidate.committed_event = event
                candidate.commit_status = CalendarMessageCaptureCandidate.CommitStatus.SAVED
                candidate.save(
                    update_fields=[
                        "candidate_kind",
                        "title",
                        "summary",
                        "start_time",
                        "end_time",
                        "is_all_day",
                        "committed_event",
                        "commit_status",
                        "updated_at",
                    ]
                )

            first_event_id = ""
            if created_events:
                first_event_id = created_events[0]["id"]
            elif reused_events:
                first_event_id = reused_events[0]["id"]

            capture_for_update.committed_event_id = first_event_id or None
            capture_for_update.committed_task = None
            capture_for_update.committed_at = timezone.now()
            capture_for_update.confirmed_item_type = CalendarMessageCapture.ConfirmedItemType.EVENT
            capture_for_update.decision_source = CalendarMessageCapture.DecisionSource.MANUAL
            capture_for_update.final_commit_payload = {
                "item_type": "event_multi",
                "selected_candidates": selected_snapshot,
                "selected_attachment_ids": [str(attachment.id) for attachment in capture_attachments],
                "source_sheetbook_id": source_context.get("sheetbook_id") if source_context else None,
                "source_tab_id": source_context.get("tab_id") if source_context else None,
            }
            capture_for_update.parse_status = CalendarMessageCapture.ParseStatus.PARSED
            capture_for_update.save(
                update_fields=[
                    "committed_event",
                    "committed_task",
                    "committed_at",
                    "confirmed_item_type",
                    "decision_source",
                    "final_commit_payload",
                    "parse_status",
                    "updated_at",
                ]
            )

        commit_elapsed_ms = int((timezone.now() - commit_started_at).total_seconds() * 1000)
        logger.info(
            "[ClassCalendar][MessageCapture] multi_commit_result user_id=%s capture_id=%s created=%s reused=%s skipped=%s elapsed_ms=%s",
            request.user.id,
            capture.id,
            len(created_events),
            len(reused_events),
            skipped_count,
            commit_elapsed_ms,
        )
        return JsonResponse(
            {
                "status": "success",
                "item_type": CalendarMessageCapture.ItemType.EVENT,
                "saved_count": len(created_events) + len(reused_events),
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "created_events": created_events,
                "reused_events": reused_events,
                "attachments": [],
                "warnings": list(dict.fromkeys(attachment_warnings)),
                "message": _build_message_capture_commit_message(created_events, reused_events),
                "sheetbook_sync": {
                    "status": "pending",
                    "enabled": bool(getattr(settings, "SHEETBOOK_ENABLED", False)),
                },
            },
            status=201,
        )

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

    if capture.committed_event_id or capture.committed_task_id:
        logger.warning(
            "[ClassCalendar][MessageCapture] commit_failed user_id=%s capture_id=%s reason=duplicate",
            request.user.id,
            capture.id,
        )
        return JsonResponse(_build_message_capture_duplicate_payload(capture), status=409)

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

    item_types_enabled = _is_message_capture_item_types_enabled_for_user(request.user)
    confirmed_item_type = form.cleaned_data.get("confirmed_item_type") or CalendarMessageCapture.ItemType.EVENT
    if not item_types_enabled:
        confirmed_item_type = CalendarMessageCapture.ItemType.EVENT
    if confirmed_item_type == CalendarMessageCapture.ItemType.IGNORE:
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "message": "무시 항목은 저장할 수 없습니다.",
            },
            status=400,
        )
    form.cleaned_data["confirmed_item_type"] = confirmed_item_type

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
    selected_attachment_count = len(capture_attachments)
    attachment_warnings = []
    processing_ms = 0
    manual_edit_count = 0

    with transaction.atomic():
        capture_for_update = CalendarMessageCapture.objects.select_for_update().get(id=capture.id, author=request.user)
        if capture_for_update.committed_event_id or capture_for_update.committed_task_id:
            logger.warning(
                "[ClassCalendar][MessageCapture] commit_failed user_id=%s capture_id=%s reason=duplicate_locked",
                request.user.id,
                capture_for_update.id,
            )
            return JsonResponse(_build_message_capture_duplicate_payload(capture_for_update), status=409)

        processing_ms = int((timezone.now() - capture_for_update.created_at).total_seconds() * 1000)
        classroom = _get_active_classroom_for_user(request)
        source_context = _resolve_sheetbook_context(
            request.user,
            payload.get("source_sheetbook_id"),
            payload.get("source_tab_id"),
        )
        final_payload = _build_message_capture_final_payload(
            form.cleaned_data,
            selected_attachment_ids=[str(attachment.id) for attachment in capture_attachments],
            source_context=source_context,
        )
        edit_diff_payload = _build_message_capture_edit_diff(capture_for_update, final_payload)
        manual_edit_count = _count_message_capture_manual_edits_from_diff(edit_diff_payload)
        decision_source = capture_for_update.decision_source
        if manual_edit_count > 0 or confirmed_item_type != capture_for_update.predicted_item_type:
            decision_source = CalendarMessageCapture.DecisionSource.MANUAL

        event = None
        task = None
        copied_attachments = []
        if confirmed_item_type == CalendarMessageCapture.ItemType.EVENT:
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
        else:
            task_kwargs = {
                "title": form.cleaned_data["title"],
                "note": form.cleaned_data.get("note") or "",
                "author": request.user,
                "classroom": classroom,
                "due_at": form.cleaned_data.get("due_at"),
                "has_time": bool(form.cleaned_data.get("has_time", False)),
                "priority": form.cleaned_data.get("priority") or CalendarTask.Priority.NORMAL,
                "status": CalendarTask.Status.OPEN,
            }
            if source_context:
                task_kwargs["integration_source"] = "sheetbook_message_capture"
                task_kwargs["integration_key"] = f"{source_context['sheetbook_id']}:{source_context['tab_id']}:{capture_for_update.id}"
            task = CalendarTask.objects.create(**task_kwargs)
            if capture_attachments:
                attachment_warnings.append("첨부파일은 할 일에 저장되지 않아 제외했습니다.")

        capture_for_update.committed_event = event
        capture_for_update.committed_task = task
        capture_for_update.committed_at = timezone.now()
        capture_for_update.confirmed_item_type = (
            CalendarMessageCapture.ConfirmedItemType.EVENT
            if confirmed_item_type == CalendarMessageCapture.ItemType.EVENT
            else CalendarMessageCapture.ConfirmedItemType.TASK
        )
        capture_for_update.decision_source = decision_source
        capture_for_update.final_commit_payload = final_payload
        capture_for_update.edit_diff_payload = edit_diff_payload
        capture_for_update.parse_status = CalendarMessageCapture.ParseStatus.PARSED
        capture_for_update.save(
            update_fields=[
                "committed_event",
                "committed_task",
                "committed_at",
                "confirmed_item_type",
                "decision_source",
                "final_commit_payload",
                "edit_diff_payload",
                "parse_status",
                "updated_at",
            ]
        )

    commit_elapsed_ms = int((timezone.now() - commit_started_at).total_seconds() * 1000)
    logger.info(
        "[ClassCalendar][MessageCapture] commit_result user_id=%s capture_id=%s item_type=%s manual_edits=%s selected_attachments=%s attachment_warnings=%s processing_ms=%s elapsed_ms=%s",
        request.user.id,
        capture.id,
        confirmed_item_type,
        manual_edit_count,
        selected_attachment_count,
        len(attachment_warnings),
        processing_ms,
        commit_elapsed_ms,
    )

    if confirmed_item_type == CalendarMessageCapture.ItemType.TASK:
        task = CalendarTask.objects.select_related("author", "classroom").get(id=task.id)
        return JsonResponse(
            {
                "status": "success",
                "item_type": CalendarMessageCapture.ItemType.TASK,
                "task": _serialize_task(task, current_user_id=request.user.id),
                "attachments": [],
                "warnings": attachment_warnings,
                "sheetbook_sync": {
                    "status": "not_applicable",
                    "enabled": bool(getattr(settings, "SHEETBOOK_ENABLED", False)),
                },
            },
            status=201,
        )

    event = CalendarEvent.objects.select_related("author").prefetch_related("blocks", "attachments").get(id=event.id)
    return JsonResponse(
        {
            "status": "success",
            "item_type": CalendarMessageCapture.ItemType.EVENT,
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
