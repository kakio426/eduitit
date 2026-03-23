from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils.http import content_disposition_header
from django.urls import reverse
from django_ratelimit.decorators import ratelimit
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import QuickdropChannel
from .services import (
    build_channel_bootstrap,
    build_pair_token,
    build_qr_data_url,
    broadcast_item_replace,
    broadcast_session_ended,
    channel_snapshot_payload,
    consume_pair_token,
    delete_today_item,
    end_session,
    ensure_live_session,
    get_live_session,
    get_or_create_personal_channel,
    get_service,
    issue_device_cookie,
    latest_today_item,
    load_pair_token,
    pair_token_matches,
    pair_device_for_request,
    remember_owner_device_for_request,
    replace_with_file,
    replace_with_text,
    resolve_channel_access,
    resolve_default_access,
    session_payload,
    today_item_count,
)


def _request_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _quickdrop_public_ratelimit_key(group, request):
    resolver_match = getattr(request, "resolver_match", None)
    slug_or_token = ""
    if resolver_match is not None:
        slug_or_token = resolver_match.kwargs.get("slug") or resolver_match.kwargs.get("token") or ""
    return f"{_request_client_ip(request) or 'unknown'}:{slug_or_token or 'global'}"


def _apply_private_response_headers(response):
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def _forbidden_pairing():
    return _apply_private_response_headers(HttpResponseForbidden("이 기기는 먼저 연결 링크로 등록해야 합니다."))


def _error_response(request, message, status=400):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return _apply_private_response_headers(JsonResponse({"ok": False, "error": message}, status=status))
    return _apply_private_response_headers(HttpResponse(message, status=status))


def _json_or_redirect(request, channel, payload=None):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return _apply_private_response_headers(JsonResponse({"ok": True, "session": payload or {}}, status=200))
    return _apply_private_response_headers(redirect("quickdrop:channel", slug=channel.slug))


@login_required
def landing_view(request):
    channel = get_or_create_personal_channel(request.user)
    owner_device, _created = remember_owner_device_for_request(request, channel)
    token = build_pair_token(channel)
    pair_url = request.build_absolute_uri(reverse("quickdrop:pair", args=[token]))
    latest_item = latest_today_item(channel)
    context = {
        "service": get_service(),
        "channel": channel,
        "pair_url": pair_url,
        "pair_qr_data_url": build_qr_data_url(pair_url),
        "latest_item": latest_item,
        "today_count": today_item_count(channel),
        "active_devices": channel.devices.filter(revoked_at__isnull=True).order_by("paired_at"),
        "open_url": reverse("quickdrop:channel", kwargs={"slug": channel.slug}),
    }
    response = _apply_private_response_headers(render(request, "quickdrop/landing.html", context))
    issue_device_cookie(response, channel, owner_device)
    return response


@require_GET
def open_view(request):
    access = resolve_default_access(request)
    if access is None:
        return _apply_private_response_headers(redirect(f"{reverse('account_login')}?next={reverse('quickdrop:landing')}"))
    return _apply_private_response_headers(redirect("quickdrop:channel", slug=access["channel"].slug))


@require_GET
def channel_view(request, slug):
    access = resolve_channel_access(request, slug)
    if access is None:
        return _forbidden_pairing()

    session, _ = ensure_live_session(access["channel"])
    bootstrap = build_channel_bootstrap(
        access["channel"],
        session=session,
        is_owner=access["is_owner"],
        device_label=access["device_label"],
    )
    context = {
        "service": get_service(),
        "channel": access["channel"],
        "is_owner": access["is_owner"],
        "device_label": access["device_label"],
        "bootstrap": bootstrap,
        "ws_url": f"/quickdrop/ws/{access['channel'].slug}/",
        "snapshot_url": reverse("quickdrop:snapshot", kwargs={"slug": access["channel"].slug}),
        "send_text_url": reverse("quickdrop:send_text", kwargs={"slug": access["channel"].slug}),
        "send_file_url": reverse("quickdrop:send_file", kwargs={"slug": access["channel"].slug}),
        "end_session_url": reverse("quickdrop:end_session", kwargs={"slug": access["channel"].slug}),
        "landing_url": reverse("quickdrop:landing") if access["is_owner"] else "",
        "manifest_url": reverse("quickdrop:manifest"),
        "service_worker_url": reverse("quickdrop:service_worker"),
    }
    response = _apply_private_response_headers(render(request, "quickdrop/channel.html", context))
    if access["is_owner"]:
        owner_device, _created = remember_owner_device_for_request(request, access["channel"])
        issue_device_cookie(response, access["channel"], owner_device)
    return response


@require_GET
def snapshot_view(request, slug):
    access = resolve_channel_access(request, slug, touch=False)
    if access is None:
        return _error_response(request, "이 기기는 연결이 필요합니다.", status=403)

    return _apply_private_response_headers(
        JsonResponse({"ok": True, "session": channel_snapshot_payload(access["channel"])}, status=200)
    )


@ratelimit(key=_quickdrop_public_ratelimit_key, rate="60/10m", method=("GET", "POST"), block=True, group="quickdrop_pair")
def pair_view(request, token):
    payload = load_pair_token(token)
    if payload is None:
        raise Http404()

    slug = payload.get("channel_slug")
    access = resolve_channel_access(request, slug)
    if access is not None:
        return _apply_private_response_headers(redirect("quickdrop:channel", slug=slug))

    channel = QuickdropChannel.objects.filter(slug=slug).first()
    if channel is None or not pair_token_matches(channel, payload):
        raise Http404()

    if request.method == "POST":
        device, _created = pair_device_for_request(request, channel)
        consume_pair_token(channel, payload)
        response = _apply_private_response_headers(redirect("quickdrop:channel", slug=channel.slug))
        issue_device_cookie(response, channel, device)
        return response

    return _apply_private_response_headers(render(request, "quickdrop/pair.html", {"channel": channel, "token": token}))


@require_POST
def send_text_view(request, slug):
    access = resolve_channel_access(request, slug)
    if access is None:
        return _error_response(request, "이 기기는 연결이 필요합니다.", status=403)

    session, _ = ensure_live_session(access["channel"])
    try:
        session = replace_with_text(session, request.POST.get("text"), sender_label=access["device_label"])
    except ValidationError as exc:
        return _error_response(request, " ".join(exc.messages))

    broadcast_item_replace(session)
    return _json_or_redirect(request, access["channel"], session_payload(session))


@require_POST
def send_file_view(request, slug):
    access = resolve_channel_access(request, slug)
    if access is None:
        return _error_response(request, "이 기기는 연결이 필요합니다.", status=403)

    session, _ = ensure_live_session(access["channel"])
    try:
        session = replace_with_file(
            session,
            request.FILES.get("file") or request.FILES.get("image"),
            sender_label=access["device_label"],
        )
    except ValidationError as exc:
        return _error_response(request, " ".join(exc.messages))

    broadcast_item_replace(session)
    return _json_or_redirect(request, access["channel"], session_payload(session))


send_image_view = send_file_view


@require_POST
def end_session_view(request, slug):
    access = resolve_channel_access(request, slug)
    if access is None:
        return _error_response(request, "이 기기는 연결이 필요합니다.", status=403)

    session = get_live_session(access["channel"])
    if session:
        session = end_session(session)
        broadcast_session_ended(session)
        payload = session_payload(session)
    else:
        payload = {}
    return _json_or_redirect(request, access["channel"], payload)


@require_POST
def delete_item_view(request, slug, item_id):
    access = resolve_channel_access(request, slug)
    if access is None:
        return _error_response(request, "이 기기는 연결이 필요합니다.", status=403)

    try:
        session = delete_today_item(access["channel"], item_id)
    except ValidationError as exc:
        return _error_response(request, " ".join(exc.messages), status=404)

    broadcast_item_replace(session)
    return _json_or_redirect(request, access["channel"], session_payload(session))


@require_GET
def item_download_view(request, slug, item_id):
    access = resolve_channel_access(request, slug)
    if access is None:
        return _forbidden_pairing()

    item = access["channel"].items.filter(id=item_id).first()
    asset = None if item is None else (item.image or item.file)
    if item is None or not asset:
        raise Http404()

    image_file = asset.open("rb")
    response = FileResponse(
        image_file,
        content_type=item.mime_type or "application/octet-stream",
    )
    response["Content-Disposition"] = content_disposition_header(
        False,
        item.filename or "quickdrop-image",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return _apply_private_response_headers(response)


item_image_view = item_download_view


@login_required
@require_POST
def rename_device_view(request, slug, device_id):
    access = resolve_channel_access(request, slug)
    if access is None or not access["is_owner"]:
        return HttpResponseForbidden("이 작업은 채널 소유자만 할 수 있습니다.")

    device = access["channel"].devices.filter(device_id=device_id, revoked_at__isnull=True).first()
    if device is None:
        raise Http404()

    label = str(request.POST.get("label") or "").strip()
    if label:
        device.label = label[:80]
        device.save(update_fields=["label"])
    return _apply_private_response_headers(redirect("quickdrop:landing"))


@login_required
@require_POST
def revoke_device_view(request, slug, device_id):
    access = resolve_channel_access(request, slug)
    if access is None or not access["is_owner"]:
        return HttpResponseForbidden("이 작업은 채널 소유자만 할 수 있습니다.")

    device = access["channel"].devices.filter(device_id=device_id, revoked_at__isnull=True).first()
    if device is None:
        raise Http404()

    from django.utils import timezone

    device.revoked_at = timezone.now()
    device.save(update_fields=["revoked_at"])
    return _apply_private_response_headers(redirect("quickdrop:landing"))


@csrf_exempt
@require_POST
@ratelimit(key=_quickdrop_public_ratelimit_key, rate="60/10m", method="POST", block=True, group="quickdrop_share_target")
def share_target_view(request):
    access = resolve_default_access(request)
    if access is None:
        return _forbidden_pairing()

    session, _ = ensure_live_session(access["channel"])
    shared_file = request.FILES.get("shared_file")
    shared_text = " ".join(
        piece.strip()
        for piece in [
            str(request.POST.get("shared_title") or "").strip(),
            str(request.POST.get("shared_text") or "").strip(),
            str(request.POST.get("shared_url") or "").strip(),
        ]
        if piece and piece.strip()
    ).strip()

    try:
        if shared_file is not None:
            session = replace_with_file(session, shared_file, sender_label=access["device_label"])
        else:
            session = replace_with_text(session, shared_text, sender_label=access["device_label"])
    except ValidationError as exc:
        return _apply_private_response_headers(HttpResponse(" ".join(exc.messages), status=400))

    broadcast_item_replace(session)
    return _apply_private_response_headers(redirect("quickdrop:channel", slug=access["channel"].slug))


@require_GET
def manifest_view(request):
    icon_url = request.build_absolute_uri(static("images/favicon.png"))
    payload = {
        "name": "바로전송",
        "short_name": "바로전송",
        "description": "내 기기끼리 텍스트와 이미지를 바로 옮기는 개인 전용 통로",
        "start_url": reverse("quickdrop:open"),
        "scope": "/quickdrop/",
        "display": "standalone",
        "background_color": "#f4f6fb",
        "theme_color": "#1f4fd1",
        "icons": [
            {"src": icon_url, "sizes": "192x192", "type": "image/png"},
            {"src": icon_url, "sizes": "512x512", "type": "image/png"},
        ],
        "share_target": {
            "action": reverse("quickdrop:share_target"),
            "method": "POST",
            "enctype": "multipart/form-data",
            "params": {
                "title": "shared_title",
                "text": "shared_text",
                "url": "shared_url",
                "files": [
                    {
                        "name": "shared_file",
                        "accept": [
                            "image/png",
                            "image/jpeg",
                            "image/webp",
                            "image/gif",
                        ],
                    }
                ],
            },
        },
    }
    return JsonResponse(payload, content_type="application/manifest+json")


@require_GET
def service_worker_view(request):
    return HttpResponse(
        "\n".join(
            [
                "self.addEventListener('install', () => self.skipWaiting());",
                "self.addEventListener('activate', (event) => {",
                "  event.waitUntil(self.clients.claim());",
                "});",
            ]
        ),
        content_type="text/javascript",
    )
