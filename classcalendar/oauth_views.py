import base64
import hashlib
from datetime import datetime, timedelta, time

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET, require_POST

from .models import CalendarEvent, EventExternalMap, GoogleAccount, GoogleSyncState

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
DEFAULT_GOOGLE_CALENDAR_ID = "primary"
SESSION_STATE_KEY = "classcalendar_google_oauth_state"


def _json_error(status, code, message, **extra):
    payload = {"status": "error", "code": code, "message": message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _get_google_client_config():
    client_id = getattr(settings, "GOOGLE_CALENDAR_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_CALENDAR_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _build_fernet():
    secret = settings.SECRET_KEY.encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _encrypt_secret(value):
    if not value:
        return ""
    return _build_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt_secret(value):
    if not value:
        return ""
    try:
        return _build_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def _build_oauth_flow(request, state=None):
    try:
        from google_auth_oauthlib.flow import Flow
    except Exception as exc:
        raise RuntimeError("google_auth_oauthlib 라이브러리를 사용할 수 없습니다.") from exc

    client_config = _get_google_client_config()
    if not client_config:
        raise RuntimeError("Google OAuth 설정이 누락되어 있습니다.")

    flow = Flow.from_client_config(client_config, scopes=GOOGLE_SCOPES, state=state)
    flow.redirect_uri = request.build_absolute_uri(reverse("classcalendar:oauth_callback"))
    return flow


def _build_google_credentials(account):
    try:
        from google.oauth2.credentials import Credentials
    except Exception as exc:
        raise RuntimeError("google.oauth2.credentials를 사용할 수 없습니다.") from exc

    payload = account.credentials or {}
    encrypted_refresh_token = payload.get("refresh_token_encrypted", "")
    refresh_token = _decrypt_secret(encrypted_refresh_token)
    if not refresh_token:
        raise RuntimeError("저장된 refresh token이 없거나 복호화에 실패했습니다.")

    client_config = _get_google_client_config()
    if not client_config:
        raise RuntimeError("Google OAuth 설정이 누락되어 있습니다.")

    web = client_config["web"]
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=payload.get("token_uri", web["token_uri"]),
        client_id=web["client_id"],
        client_secret=web["client_secret"],
        scopes=payload.get("scopes") or GOOGLE_SCOPES,
    )


def _build_calendar_service(account):
    try:
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError("googleapiclient 라이브러리를 사용할 수 없습니다.") from exc
    credentials = _build_google_credentials(account)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _parse_google_datetime(value):
    date_time_text = (value or {}).get("dateTime")
    date_text = (value or {}).get("date")

    if date_time_text:
        parsed = parse_datetime(date_time_text)
        if parsed is None:
            return None, False
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed, False

    if date_text:
        parsed_date = parse_date(date_text)
        if parsed_date is None:
            return None, True
        parsed_datetime = datetime.combine(parsed_date, time.min)
        parsed_datetime = timezone.make_aware(parsed_datetime, timezone.get_current_timezone())
        return parsed_datetime, True

    return None, False


def _build_google_event_payload(event):
    if event.is_all_day:
        start_date = timezone.localtime(event.start_time).date()
        end_date = timezone.localtime(event.end_time).date()
        if end_date <= start_date:
            end_date = start_date + timedelta(days=1)
        start_payload = {"date": start_date.isoformat()}
        end_payload = {"date": end_date.isoformat()}
    else:
        start_payload = {"dateTime": timezone.localtime(event.start_time).isoformat()}
        end_payload = {"dateTime": timezone.localtime(event.end_time).isoformat()}

    return {
        "summary": event.title,
        "start": start_payload,
        "end": end_payload,
        "extendedProperties": {
            "private": {
                "eduit_event_id": str(event.id),
                "classroom_id": str(event.classroom_id or ""),
            }
        },
    }


def _handle_google_http_error(exc):
    status_code = getattr(getattr(exc, "resp", None), "status", None)
    if status_code == 401:
        return _json_error(401, "google_unauthorized", "구글 인증이 만료되었습니다. 다시 연결해 주세요.")
    if status_code == 403:
        return _json_error(403, "google_forbidden", "구글 캘린더 접근 권한이 없습니다.")
    if status_code == 410:
        return _json_error(410, "sync_token_expired", "동기화 토큰이 만료되었습니다. 전체 재동기화를 진행합니다.")
    if status_code == 429:
        return _json_error(429, "google_rate_limited", "요청이 많습니다. 잠시 후 다시 시도해 주세요.")
    return _json_error(502, "google_upstream_error", "구글 캘린더 통신 중 오류가 발생했습니다.")


def _list_google_events(service, calendar_id, sync_token=None):
    request_kwargs = {
        "calendarId": calendar_id,
        "showDeleted": True,
        "maxResults": 2500,
    }
    if sync_token:
        request_kwargs["syncToken"] = sync_token
    else:
        request_kwargs["singleEvents"] = True
        request_kwargs["orderBy"] = "startTime"
        request_kwargs["timeMin"] = (timezone.now() - timedelta(days=365)).isoformat()

    items = []
    next_page_token = None
    next_sync_token = None
    while True:
        if next_page_token:
            request_kwargs["pageToken"] = next_page_token
        else:
            request_kwargs.pop("pageToken", None)
        response = service.events().list(**request_kwargs).execute()
        items.extend(response.get("items", []))
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            next_sync_token = response.get("nextSyncToken")
            break
    return items, next_sync_token


def _upsert_google_event_to_local(account, calendar_id, item):
    google_event_id = (item or {}).get("id")
    if not google_event_id:
        return "skipped"

    mapping = (
        EventExternalMap.objects.select_related("event")
        .filter(account=account, google_calendar_id=calendar_id, google_event_id=google_event_id)
        .first()
    )

    if (item or {}).get("status") == "cancelled":
        if mapping and mapping.event:
            mapping.event.delete()
            return "deleted"
        return "skipped"

    start_time, is_all_day = _parse_google_datetime((item or {}).get("start"))
    end_time, _ = _parse_google_datetime((item or {}).get("end"))
    if not start_time or not end_time:
        return "skipped"

    defaults = {
        "title": (item or {}).get("summary") or "(제목 없음)",
        "start_time": start_time,
        "end_time": end_time,
        "is_all_day": is_all_day,
        "author": account.user,
        "source": CalendarEvent.SOURCE_GOOGLE,
        "visibility": CalendarEvent.VISIBILITY_TEACHER,
        "classroom": None,
    }

    if mapping and mapping.event:
        event = mapping.event
        for key, value in defaults.items():
            setattr(event, key, value)
        event.save(
            update_fields=[
                "title",
                "start_time",
                "end_time",
                "is_all_day",
                "author",
                "source",
                "visibility",
                "classroom",
                "updated_at",
            ]
        )
        mapping.etag = (item or {}).get("etag")
        mapping.save(update_fields=["etag"])
        return "updated"

    event = CalendarEvent.objects.create(**defaults)
    EventExternalMap.objects.create(
        account=account,
        event=event,
        google_calendar_id=calendar_id,
        google_event_id=google_event_id,
        etag=(item or {}).get("etag"),
    )
    return "created"


@login_required
def oauth_login(request):
    try:
        flow = _build_oauth_flow(request)
    except RuntimeError:
        return redirect(reverse("classcalendar:main") + "?error=oauth_config_missing")

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    request.session[SESSION_STATE_KEY] = state
    request.session.modified = True
    return redirect(authorization_url)


@login_required
def oauth_callback(request):
    if request.GET.get("error"):
        return redirect(reverse("classcalendar:main") + "?error=oauth_denied")

    state = (request.GET.get("state") or "").strip()
    expected_state = (request.session.pop(SESSION_STATE_KEY, "") or "").strip()
    if not state or not expected_state or state != expected_state:
        return redirect(reverse("classcalendar:main") + "?error=oauth_state_mismatch")

    code = (request.GET.get("code") or "").strip()
    if not code:
        return redirect(reverse("classcalendar:main") + "?error=oauth_code_missing")

    try:
        flow = _build_oauth_flow(request, state=state)
        flow.fetch_token(code=code)
    except Exception:
        return redirect(reverse("classcalendar:main") + "?error=oauth_exchange_failed")

    credentials = flow.credentials
    existing = GoogleAccount.objects.filter(user=request.user).first()
    existing_payload = existing.credentials if existing else {}
    encrypted_refresh_token = ""
    if credentials.refresh_token:
        encrypted_refresh_token = _encrypt_secret(credentials.refresh_token)
    else:
        encrypted_refresh_token = existing_payload.get("refresh_token_encrypted", "")

    if not encrypted_refresh_token:
        return redirect(reverse("classcalendar:main") + "?error=refresh_token_missing")

    account_payload = {
        "refresh_token_encrypted": encrypted_refresh_token,
        "token_uri": credentials.token_uri,
        "scopes": list(credentials.scopes or GOOGLE_SCOPES),
    }
    account, _ = GoogleAccount.objects.update_or_create(
        user=request.user,
        defaults={
            "email": request.user.email,
            "credentials": account_payload,
        },
    )

    GoogleSyncState.objects.get_or_create(
        account=account,
        google_calendar_id=DEFAULT_GOOGLE_CALENDAR_ID,
    )
    return redirect(reverse("classcalendar:main") + "?success=google_connected")


@login_required
@require_GET
def api_google_calendars(request):
    account = GoogleAccount.objects.filter(user=request.user).first()
    if not account:
        return _json_error(401, "google_not_connected", "구글 계정이 연결되어 있지 않습니다.")

    try:
        service = _build_calendar_service(account)
        response = service.calendarList().list(maxResults=250).execute()
    except Exception as exc:
        http_error_response = _handle_google_http_error(exc)
        if http_error_response.status_code != 502:
            return http_error_response
        return _json_error(502, "google_calendar_list_failed", "캘린더 목록을 불러오지 못했습니다.")

    calendars = []
    for item in response.get("items", []):
        calendars.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "access_role": item.get("accessRole"),
                "primary": bool(item.get("primary")),
            }
        )
    return JsonResponse({"status": "success", "calendars": calendars})


@login_required
@require_POST
def api_google_sync(request):
    account = GoogleAccount.objects.filter(user=request.user).first()
    if not account:
        return _json_error(401, "google_not_connected", "구글 계정이 연결되어 있지 않습니다.")

    google_calendar_id = (request.POST.get("google_calendar_id") or DEFAULT_GOOGLE_CALENDAR_ID).strip()
    sync_state, _ = GoogleSyncState.objects.get_or_create(
        account=account,
        google_calendar_id=google_calendar_id,
    )

    try:
        service = _build_calendar_service(account)
        items, next_sync_token = _list_google_events(service, google_calendar_id, sync_state.sync_token)
    except Exception as exc:
        error_response = _handle_google_http_error(exc)
        if error_response.status_code == 410 and sync_state.sync_token:
            sync_state.sync_token = None
            sync_state.save(update_fields=["sync_token"])
            try:
                items, next_sync_token = _list_google_events(service, google_calendar_id, None)
            except Exception as retry_exc:
                return _handle_google_http_error(retry_exc)
        else:
            return error_response

    counters = {"created": 0, "updated": 0, "deleted": 0, "skipped": 0}
    for item in items:
        result = _upsert_google_event_to_local(account, google_calendar_id, item)
        counters[result] = counters.get(result, 0) + 1

    sync_state.sync_token = next_sync_token
    sync_state.last_sync = timezone.now()
    sync_state.save(update_fields=["sync_token", "last_sync"])

    return JsonResponse(
        {
            "status": "success",
            "calendar_id": google_calendar_id,
            "counts": counters,
            "message": "동기화가 완료되었습니다.",
        }
    )


@login_required
@require_POST
def api_google_export(request, event_id):
    account = GoogleAccount.objects.filter(user=request.user).first()
    if not account:
        return _json_error(401, "google_not_connected", "구글 계정이 연결되어 있지 않습니다.")

    google_calendar_id = (request.POST.get("google_calendar_id") or DEFAULT_GOOGLE_CALENDAR_ID).strip()
    event = get_object_or_404(CalendarEvent, id=event_id, author=request.user)

    try:
        service = _build_calendar_service(account)
    except Exception as exc:
        error_response = _handle_google_http_error(exc)
        if error_response.status_code != 502:
            return error_response
        return _json_error(502, "google_service_build_failed", "구글 캘린더 서비스를 초기화하지 못했습니다.")

    mapping = (
        EventExternalMap.objects.filter(
            account=account,
            event=event,
            google_calendar_id=google_calendar_id,
        )
        .order_by("id")
        .first()
    )
    payload = _build_google_event_payload(event)

    try:
        if mapping:
            remote_event = service.events().get(
                calendarId=google_calendar_id,
                eventId=mapping.google_event_id,
            ).execute()
            remote_etag = remote_event.get("etag")
            if mapping.etag and remote_etag and mapping.etag != remote_etag:
                return _json_error(412, "etag_mismatch", "구글 이벤트가 외부에서 변경되었습니다. 다시 동기화해 주세요.")
            exported = service.events().update(
                calendarId=google_calendar_id,
                eventId=mapping.google_event_id,
                body=payload,
                sendUpdates="none",
            ).execute()
        else:
            exported = service.events().insert(
                calendarId=google_calendar_id,
                body=payload,
                sendUpdates="none",
            ).execute()
            mapping = EventExternalMap.objects.create(
                account=account,
                event=event,
                google_calendar_id=google_calendar_id,
                google_event_id=exported.get("id", ""),
                etag=exported.get("etag"),
            )

        mapping.etag = exported.get("etag")
        mapping.google_event_id = exported.get("id", mapping.google_event_id)
        mapping.save(update_fields=["etag", "google_event_id"])
    except Exception as exc:
        return _handle_google_http_error(exc)

    return JsonResponse(
        {
            "status": "success",
            "google_calendar_id": google_calendar_id,
            "google_event_id": mapping.google_event_id,
            "etag": mapping.etag,
        }
    )


@login_required
@require_POST
def api_google_disconnect(request):
    account = GoogleAccount.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({"status": "success", "message": "이미 연결 해제된 상태입니다."})

    encrypted_refresh_token = (account.credentials or {}).get("refresh_token_encrypted", "")
    refresh_token = _decrypt_secret(encrypted_refresh_token)
    if refresh_token:
        try:
            import requests

            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": refresh_token},
                timeout=10,
            )
        except Exception:
            pass

    account.delete()
    return JsonResponse({"status": "success", "message": "구글 계정 연결을 해제했습니다."})
