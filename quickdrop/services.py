import base64
import io
import os
import uuid
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
import qrcode

from products.models import Product

from .models import QuickdropChannel, QuickdropDevice, QuickdropItem, QuickdropSession


SERVICE_ROUTE = "quickdrop:landing"
SERVICE_TITLE = "바로전송"
SERVICE_PRODUCT_DEFAULTS = {
    "lead_text": "처음 한 번만 로그인해 두면 내 기기끼리 텍스트나 이미지를 바로 옮깁니다.",
    "description": (
        "바로전송은 교사 기기에서 처음 한 번만 로그인해 개인 전용 통로를 만들고, 다른 기기는 한 번만 연결해 둔 뒤 텍스트 붙여넣기나 사진 선택만으로 "
        "다른 기기에 바로 띄우는 임시 전송 서비스입니다."
    ),
    "price": 0.00,
    "is_active": True,
    "is_featured": False,
    "is_guest_allowed": False,
    "icon": "⚡",
    "color_theme": "blue",
    "card_size": "small",
    "display_order": 17,
    "service_type": "classroom",
    "external_url": "",
    "launch_route_name": SERVICE_ROUTE,
    "solve_text": "내 폰과 PC 사이에 텍스트나 이미지를 바로 옮기고 싶어요",
    "result_text": "개인 전용 즉시 전송 통로",
    "time_text": "10초",
}
DEVICE_COOKIE_NAME = "quickdrop_device"
DEVICE_COOKIE_PATH = "/quickdrop/"
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
DEVICE_TOUCH_INTERVAL = timedelta(minutes=5)
PAIR_TOKEN_MAX_AGE = 60 * 10
TEXT_MAX_BYTES = 50 * 1024
UPLOAD_MAX_BYTES = 10 * 1024 * 1024
TODAY_ITEM_LIMIT = 30
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_FILE_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
}
ALLOWED_FILE_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".csv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".hwp",
    ".hwpx",
    ".zip",
}
DEVICE_COOKIE_SALT = "quickdrop-device"
PAIR_TOKEN_SALT = "quickdrop-pair"


def _find_service_product():
    return Product.objects.filter(launch_route_name=SERVICE_ROUTE).first() or Product.objects.filter(title=SERVICE_TITLE).first()


def ensure_service_product():
    product = _find_service_product()
    if product is None:
        return Product.objects.create(title=SERVICE_TITLE, **SERVICE_PRODUCT_DEFAULTS)

    changed_fields = []
    if product.title != SERVICE_TITLE:
        product.title = SERVICE_TITLE
        changed_fields.append("title")
    for field_name, value in SERVICE_PRODUCT_DEFAULTS.items():
        if getattr(product, field_name) != value:
            setattr(product, field_name, value)
            changed_fields.append(field_name)
    if changed_fields:
        product.save(update_fields=list(dict.fromkeys(changed_fields)))
    return product


def get_service():
    return ensure_service_product()


def history_day_start(now=None):
    current = timezone.localtime(now or timezone.now())
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def build_qr_data_url(raw_text):
    if not raw_text:
        return ""
    qr_image = qrcode.make(raw_text)
    with io.BytesIO() as buffer:
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_channel_slug():
    return uuid.uuid4().hex[:20]


def get_or_create_personal_channel(user):
    channel = QuickdropChannel.objects.filter(owner=user).first()
    if channel:
        return channel

    slug = generate_channel_slug()
    while QuickdropChannel.objects.filter(slug=slug).exists():
        slug = generate_channel_slug()
    return QuickdropChannel.objects.create(owner=user, slug=slug, title="바로전송")


def owner_display_label(user):
    try:
        profile = user.userprofile
    except Exception:
        profile = None
    nickname = str(getattr(profile, "nickname", "") or "").strip()
    if nickname:
        return nickname
    first_name = str(getattr(user, "first_name", "") or "").strip()
    if first_name:
        return first_name
    return user.get_username()


def build_pair_token(channel):
    pair_nonce = uuid.uuid4().hex
    issued_at = timezone.now()
    channel.active_pair_nonce = pair_nonce
    channel.active_pair_issued_at = issued_at
    channel.save(update_fields=["active_pair_nonce", "active_pair_issued_at", "updated_at"])
    return signing.dumps(
        {
            "channel_slug": channel.slug,
            "pair_nonce": pair_nonce,
        },
        salt=PAIR_TOKEN_SALT,
        compress=True,
    )


def load_pair_token(token):
    if not token:
        return None
    try:
        return signing.loads(token, salt=PAIR_TOKEN_SALT, max_age=PAIR_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None


def pair_token_matches(channel, payload):
    if not payload or payload.get("channel_slug") != channel.slug:
        return False
    pair_nonce = str(payload.get("pair_nonce") or "").strip()
    if not pair_nonce:
        return False
    return bool(channel.active_pair_nonce and pair_nonce == channel.active_pair_nonce)


def consume_pair_token(channel, payload):
    if not pair_token_matches(channel, payload):
        return False
    channel.active_pair_nonce = ""
    channel.active_pair_issued_at = None
    channel.save(update_fields=["active_pair_nonce", "active_pair_issued_at", "updated_at"])
    return True


def build_device_cookie_value(channel, device):
    payload = {
        "channel_slug": channel.slug,
        "device_id": device.device_id,
        "issued_at": int(timezone.now().timestamp()),
    }
    return signing.dumps(payload, salt=DEVICE_COOKIE_SALT, compress=True)


def load_device_cookie_value(raw_value):
    if not raw_value:
        return None
    try:
        return signing.loads(raw_value, salt=DEVICE_COOKIE_SALT, max_age=DEVICE_COOKIE_MAX_AGE)
    except signing.BadSignature:
        return None


def issue_device_cookie(response, channel, device):
    response.set_cookie(
        DEVICE_COOKIE_NAME,
        build_device_cookie_value(channel, device),
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        path=DEVICE_COOKIE_PATH,
    )


def summarize_user_agent(user_agent):
    ua = str(user_agent or "").lower()
    if "iphone" in ua:
        return "iPhone"
    if "ipad" in ua:
        return "iPad"
    if "android" in ua:
        return "Android"
    if "windows" in ua:
        return "Windows PC"
    if "mac os x" in ua or "macintosh" in ua:
        return "Mac"
    if "linux" in ua:
        return "Linux"
    return "새 기기"


def default_owner_device_label(user_agent):
    summary = summarize_user_agent(user_agent)
    if summary in {"Windows PC", "Mac", "Linux"}:
        return "내 PC"
    if summary in {"iPhone", "iPad", "Android"}:
        return "내 휴대폰"
    return "내 기기"


def next_device_label(channel, base_label):
    label_root = (base_label or "새 기기").strip()[:60]
    if not QuickdropDevice.objects.filter(channel=channel, label=label_root, revoked_at__isnull=True).exists():
        return label_root

    index = 2
    while True:
        candidate = f"{label_root} {index}"
        if not QuickdropDevice.objects.filter(channel=channel, label=candidate, revoked_at__isnull=True).exists():
            return candidate
        index += 1


def get_active_device_from_cookie(channel, raw_cookie):
    payload = load_device_cookie_value(raw_cookie)
    if not payload or payload.get("channel_slug") != channel.slug:
        return None
    return channel.devices.filter(
        device_id=payload.get("device_id"),
        revoked_at__isnull=True,
    ).first()


def touch_device(device, *, now=None, force=False):
    current_time = now or timezone.now()
    if (
        not force
        and device.last_seen_at
        and current_time - device.last_seen_at < DEVICE_TOUCH_INTERVAL
    ):
        return device

    device.last_seen_at = current_time
    device.save(update_fields=["last_seen_at"])
    return device


def pair_device_for_request(request, channel):
    existing = get_active_device_from_cookie(channel, request.COOKIES.get(DEVICE_COOKIE_NAME))
    if existing:
        return touch_device(existing), False

    summary = summarize_user_agent(request.META.get("HTTP_USER_AGENT"))
    requested_label = str(request.POST.get("label") or "").strip()
    label = next_device_label(channel, requested_label or summary)
    device = QuickdropDevice.objects.create(
        channel=channel,
        device_id=uuid.uuid4().hex,
        label=label,
        user_agent_summary=summary,
    )
    return device, True


def remember_owner_device_for_request(request, channel):
    existing = get_active_device_from_cookie(channel, request.COOKIES.get(DEVICE_COOKIE_NAME))
    if existing:
        return touch_device(existing), False

    summary = summarize_user_agent(request.META.get("HTTP_USER_AGENT"))
    label = next_device_label(channel, default_owner_device_label(request.META.get("HTTP_USER_AGENT")))
    device = QuickdropDevice.objects.create(
        channel=channel,
        device_id=uuid.uuid4().hex,
        label=label,
        user_agent_summary=summary,
    )
    return device, True


def get_live_session(channel):
    return channel.sessions.filter(status=QuickdropSession.STATUS_LIVE).order_by("-created_at").first()


def today_items_qs(channel, now=None):
    return channel.items.filter(created_at__gte=history_day_start(now)).order_by("-created_at", "-id")


def latest_today_item(channel, now=None):
    return today_items_qs(channel, now).first()


def list_today_items(channel, now=None, limit=TODAY_ITEM_LIMIT):
    items = list(today_items_qs(channel, now)[:limit])
    items.reverse()
    return items


def today_item_count(channel, now=None):
    return channel.items.filter(created_at__gte=history_day_start(now)).count()


def delete_item_image(item):
    if item.image:
        item.image.delete(save=False)
    if item.file:
        item.file.delete(save=False)


def delete_item_record(item):
    delete_item_image(item)
    item.delete()


def clear_today_items(channel, now=None):
    items = list(today_items_qs(channel, now))
    cleared = 0
    for item in items:
        delete_item_record(item)
        cleared += 1
    return cleared


@transaction.atomic
def delete_today_item(channel, item_id, *, now=None):
    item = channel.items.filter(id=item_id, created_at__gte=history_day_start(now)).first()
    if item is None:
        raise ValidationError("이미 지워졌거나 오늘 기록이 아닙니다.")

    delete_item_record(item)
    session, _created = ensure_live_session(channel)
    return session


def delete_session_image(session):
    if not session.current_image:
        return
    session.current_image.delete(save=False)


def set_session_empty(session, *, status=QuickdropSession.STATUS_LIVE, ended_at=None, last_activity_at=None):
    delete_session_image(session)
    session.status = status
    session.current_kind = QuickdropSession.KIND_EMPTY
    session.current_text = ""
    session.current_image = None
    session.current_mime_type = ""
    session.current_filename = ""
    session.last_activity_at = last_activity_at or timezone.now()
    session.ended_at = ended_at
    session.save(
        update_fields=[
            "status",
            "current_kind",
            "current_text",
            "current_image",
            "current_mime_type",
            "current_filename",
            "last_activity_at",
            "ended_at",
            "updated_at",
        ]
    )
    return session


def sync_session_from_item(session, item):
    session.status = QuickdropSession.STATUS_LIVE
    if item.kind == QuickdropItem.KIND_TEXT:
        session.current_kind = QuickdropSession.KIND_TEXT
    elif item.kind == QuickdropItem.KIND_IMAGE:
        session.current_kind = QuickdropSession.KIND_IMAGE
    else:
        session.current_kind = QuickdropSession.KIND_FILE
    session.current_text = item.text if item.kind == QuickdropItem.KIND_TEXT else ""
    session.current_image = None
    session.current_mime_type = item.mime_type or ("text/plain" if item.kind == QuickdropItem.KIND_TEXT else "")
    session.current_filename = item.filename
    session.last_activity_at = item.created_at
    session.ended_at = None
    session.save(
        update_fields=[
            "status",
            "current_kind",
            "current_text",
            "current_image",
            "current_mime_type",
            "current_filename",
            "last_activity_at",
            "ended_at",
            "updated_at",
        ]
    )
    return session


def session_matches_item(session, item):
    if item is None:
        return (
            session.status == QuickdropSession.STATUS_LIVE
            and session.current_kind == QuickdropSession.KIND_EMPTY
            and not session.current_text
            and not session.current_filename
            and not session.current_mime_type
            and session.ended_at is None
        )

    if item.kind == QuickdropItem.KIND_TEXT:
        expected_kind = QuickdropSession.KIND_TEXT
    elif item.kind == QuickdropItem.KIND_IMAGE:
        expected_kind = QuickdropSession.KIND_IMAGE
    else:
        expected_kind = QuickdropSession.KIND_FILE
    expected_text = item.text if item.kind == QuickdropItem.KIND_TEXT else ""
    expected_mime_type = item.mime_type or ("text/plain" if item.kind == QuickdropItem.KIND_TEXT else "")
    return (
        session.status == QuickdropSession.STATUS_LIVE
        and session.current_kind == expected_kind
        and session.current_text == expected_text
        and session.current_filename == item.filename
        and session.current_mime_type == expected_mime_type
        and session.last_activity_at == item.created_at
        and session.ended_at is None
    )


@transaction.atomic
def end_session(session, *, ended_at=None, clear_today=True):
    ended_at = ended_at or timezone.now()
    if clear_today:
        clear_today_items(session.channel, now=ended_at)
    return set_session_empty(
        session,
        status=QuickdropSession.STATUS_ENDED,
        ended_at=ended_at,
        last_activity_at=ended_at,
    )


@transaction.atomic
def ensure_live_session(channel):
    live_session = get_live_session(channel)
    latest_item = latest_today_item(channel)

    if live_session:
        if latest_item:
            if not session_matches_item(live_session, latest_item):
                sync_session_from_item(live_session, latest_item)
        elif not session_matches_item(live_session, None):
            set_session_empty(live_session, status=QuickdropSession.STATUS_LIVE, ended_at=None, last_activity_at=timezone.now())
        return live_session, False

    live_session = QuickdropSession.objects.create(
        channel=channel,
        status=QuickdropSession.STATUS_LIVE,
        current_kind=QuickdropSession.KIND_EMPTY,
        last_activity_at=timezone.now(),
    )
    if latest_item:
        sync_session_from_item(live_session, latest_item)
    return live_session, True


def validate_text_payload(raw_text):
    text = str(raw_text or "").replace("\r\n", "\n").strip()
    if not text.strip():
        raise ValidationError("옮길 텍스트가 비어 있습니다.")
    if len(text.encode("utf-8")) > TEXT_MAX_BYTES:
        raise ValidationError("텍스트는 최대 50KB까지 전송할 수 있습니다.")
    return text


def _upload_extension(uploaded_file):
    return os.path.splitext(str(getattr(uploaded_file, "name", "") or "").lower())[1]


def classify_upload(uploaded_file):
    if uploaded_file is None:
        raise ValidationError("파일을 선택해 주세요.")
    if uploaded_file.size > UPLOAD_MAX_BYTES:
        raise ValidationError("파일은 최대 10MB까지 전송할 수 있습니다.")
    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
    extension = _upload_extension(uploaded_file)
    if content_type in ALLOWED_IMAGE_TYPES or extension in ALLOWED_IMAGE_EXTENSIONS:
        return QuickdropItem.KIND_IMAGE
    if extension in ALLOWED_FILE_EXTENSIONS:
        return QuickdropItem.KIND_FILE
    if content_type in ALLOWED_FILE_TYPES and content_type != "application/octet-stream":
        return QuickdropItem.KIND_FILE
    raise ValidationError("이미지, PDF, 한글, 오피스 문서 파일만 전송할 수 있습니다.")


def normalize_sender_label(sender_label):
    return str(sender_label or "").strip()[:80]


@transaction.atomic
def replace_with_text(session, raw_text, *, sender_label=""):
    text = validate_text_payload(raw_text)
    item = QuickdropItem.objects.create(
        channel=session.channel,
        sender_label=normalize_sender_label(sender_label),
        kind=QuickdropItem.KIND_TEXT,
        text=text,
        mime_type="text/plain",
    )
    sync_session_from_item(session, item)
    return session


@transaction.atomic
def replace_with_file(session, uploaded_file, *, sender_label=""):
    upload_kind = classify_upload(uploaded_file)
    item_kwargs = {
        "channel": session.channel,
        "sender_label": normalize_sender_label(sender_label),
        "kind": upload_kind,
        "mime_type": str(getattr(uploaded_file, "content_type", "") or ""),
        "filename": str(getattr(uploaded_file, "name", "") or ""),
    }
    if upload_kind == QuickdropItem.KIND_IMAGE:
        item_kwargs["image"] = uploaded_file
    else:
        item_kwargs["file"] = uploaded_file
    item = QuickdropItem.objects.create(**item_kwargs)
    sync_session_from_item(session, item)
    return session


def item_payload(item):
    return {
        "id": item.id,
        "kind": item.kind,
        "sender_label": item.sender_label,
        "text": item.text,
        "download_url": reverse("quickdrop:item_download", kwargs={"slug": item.channel.slug, "item_id": item.id}) if (item.image or item.file) else "",
        "preview_url": reverse("quickdrop:item_image", kwargs={"slug": item.channel.slug, "item_id": item.id}) if item.image else "",
        "delete_url": reverse("quickdrop:delete_item", kwargs={"slug": item.channel.slug, "item_id": item.id}),
        "filename": item.filename,
        "mime_type": item.mime_type,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def session_payload(session):
    latest_item = latest_today_item(session.channel)
    today_items = [item_payload(item) for item in list_today_items(session.channel)]
    if latest_item:
        if latest_item.kind == QuickdropItem.KIND_TEXT:
            current_kind = QuickdropSession.KIND_TEXT
        elif latest_item.kind == QuickdropItem.KIND_IMAGE:
            current_kind = QuickdropSession.KIND_IMAGE
        else:
            current_kind = QuickdropSession.KIND_FILE
        current_text = latest_item.text if latest_item.kind == QuickdropItem.KIND_TEXT else ""
        current_preview_url = (
            reverse("quickdrop:item_image", kwargs={"slug": session.channel.slug, "item_id": latest_item.id})
            if latest_item.image
            else ""
        )
        current_download_url = (
            reverse("quickdrop:item_download", kwargs={"slug": session.channel.slug, "item_id": latest_item.id})
            if latest_item.image or latest_item.file
            else ""
        )
        current_filename = latest_item.filename
        current_mime_type = latest_item.mime_type or ("text/plain" if latest_item.kind == QuickdropItem.KIND_TEXT else "")
        updated_at = latest_item.created_at.isoformat() if latest_item.created_at else None
        status = QuickdropSession.STATUS_LIVE
    else:
        current_kind = QuickdropSession.KIND_EMPTY
        current_text = ""
        current_preview_url = ""
        current_download_url = ""
        current_filename = ""
        current_mime_type = ""
        updated_at = session.updated_at.isoformat() if session.updated_at else None
        status = session.status

    return {
        "id": str(session.id),
        "status": status,
        "current_kind": current_kind,
        "current_text": current_text,
        "current_preview_url": current_preview_url,
        "current_download_url": current_download_url,
        "current_filename": current_filename,
        "current_mime_type": current_mime_type,
        "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "updated_at": updated_at,
        "today_items": today_items,
        "today_count": len(today_items),
    }


def snapshot_session_for_channel(channel):
    session = get_live_session(channel)
    if session is not None:
        return session

    latest_session = channel.sessions.order_by("-created_at").first()
    if latest_session is not None:
        return latest_session

    return QuickdropSession(
        channel=channel,
        status=QuickdropSession.STATUS_LIVE,
        current_kind=QuickdropSession.KIND_EMPTY,
        last_activity_at=timezone.now(),
    )


def channel_snapshot_payload(channel):
    return session_payload(snapshot_session_for_channel(channel))


def build_channel_bootstrap(channel, *, session, is_owner, device_label):
    return {
        "channel": {
            "slug": channel.slug,
            "title": channel.title,
        },
        "viewer": {
            "is_owner": bool(is_owner),
            "device_label": device_label or "",
        },
        "session": session_payload(session),
    }


def resolve_channel_access(request, slug, *, touch=True):
    channel = QuickdropChannel.objects.filter(slug=slug).first()
    if channel is None:
        return None

    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False) and channel.owner_id == user.id:
        return {
            "channel": channel,
            "is_owner": True,
            "device": None,
            "device_label": owner_display_label(user),
        }

    device = get_active_device_from_cookie(channel, request.COOKIES.get(DEVICE_COOKIE_NAME))
    if device is None:
        return None

    if touch:
        touch_device(device)
    return {
        "channel": channel,
        "is_owner": False,
        "device": device,
        "device_label": device.label,
    }


def resolve_default_access(request, *, touch=True):
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        channel = get_or_create_personal_channel(user)
        return {
            "channel": channel,
            "is_owner": True,
            "device": None,
            "device_label": owner_display_label(user),
        }

    payload = load_device_cookie_value(request.COOKIES.get(DEVICE_COOKIE_NAME))
    if not payload:
        return None

    return resolve_channel_access(request, payload.get("channel_slug"), touch=touch)


def group_name_for_channel(channel_or_slug):
    slug = channel_or_slug.slug if hasattr(channel_or_slug, "slug") else str(channel_or_slug)
    return f"quickdrop-{slug}"


def broadcast_message(channel_or_slug, message):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        group_name_for_channel(channel_or_slug),
        {
            "type": "quickdrop.broadcast",
            "message": message,
        },
    )


def broadcast_item_replace(session):
    broadcast_message(
        session.channel,
        {
            "type": "item.replace",
            "payload": session_payload(session),
        },
    )


def broadcast_session_ended(session):
    broadcast_message(
        session.channel,
        {
            "type": "session.ended",
            "payload": session_payload(session),
        },
    )


def cleanup_stale_activity(now=None):
    now = now or timezone.now()
    cutoff = history_day_start(now)
    stale_items = list(
        QuickdropItem.objects.select_related("channel")
        .filter(created_at__lt=cutoff)
        .order_by("created_at", "id")
    )
    cleared = 0
    for item in stale_items:
        delete_item_record(item)
        cleared += 1

    stale_sessions = list(
        QuickdropSession.objects.select_related("channel")
        .filter(status=QuickdropSession.STATUS_LIVE, last_activity_at__lt=cutoff)
        .order_by("last_activity_at")
    )
    for session in stale_sessions:
        set_session_empty(
            session,
            status=QuickdropSession.STATUS_ENDED,
            ended_at=now,
            last_activity_at=now,
        )
    return cleared


def cleanup_expired_sessions(now=None):
    return cleanup_stale_activity(now=now)
