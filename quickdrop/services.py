import base64
import io
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

from .models import QuickdropChannel, QuickdropDevice, QuickdropSession


SERVICE_ROUTE = "quickdrop:landing"
SERVICE_TITLE = "바로전송"
DEVICE_COOKIE_NAME = "quickdrop_device"
DEVICE_COOKIE_PATH = "/quickdrop/"
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
PAIR_TOKEN_MAX_AGE = 60 * 10
SESSION_IDLE_SECONDS = 60 * 10
TEXT_MAX_BYTES = 50 * 1024
IMAGE_MAX_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
DEVICE_COOKIE_SALT = "quickdrop-device"
PAIR_TOKEN_SALT = "quickdrop-pair"


def get_service():
    return Product.objects.filter(launch_route_name=SERVICE_ROUTE).first() or Product.objects.filter(title=SERVICE_TITLE).first()


def session_idle_cutoff(now=None):
    return (now or timezone.now()) - timedelta(seconds=SESSION_IDLE_SECONDS)


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


def touch_device(device):
    device.last_seen_at = timezone.now()
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


def session_is_expired(session, now=None):
    return bool(session and session.is_live and session.last_activity_at <= session_idle_cutoff(now))


def delete_session_image(session):
    if not session.current_image:
        return
    session.current_image.delete(save=False)


@transaction.atomic
def end_session(session, *, ended_at=None):
    ended_at = ended_at or timezone.now()
    if session.status == QuickdropSession.STATUS_ENDED and session.current_kind == QuickdropSession.KIND_EMPTY:
        return session

    delete_session_image(session)
    session.status = QuickdropSession.STATUS_ENDED
    session.current_kind = QuickdropSession.KIND_EMPTY
    session.current_text = ""
    session.current_mime_type = ""
    session.current_filename = ""
    session.last_activity_at = ended_at
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


@transaction.atomic
def ensure_live_session(channel):
    live_session = get_live_session(channel)
    if session_is_expired(live_session):
        ended_session = end_session(live_session)
        broadcast_session_ended(ended_session)
        live_session = None

    if live_session:
        return live_session, False

    return (
        QuickdropSession.objects.create(
            channel=channel,
            status=QuickdropSession.STATUS_LIVE,
            current_kind=QuickdropSession.KIND_EMPTY,
            last_activity_at=timezone.now(),
        ),
        True,
    )


def validate_text_payload(raw_text):
    text = str(raw_text or "")
    if not text.strip():
        raise ValidationError("옮길 텍스트가 비어 있습니다.")
    if len(text.encode("utf-8")) > TEXT_MAX_BYTES:
        raise ValidationError("텍스트는 최대 50KB까지 전송할 수 있습니다.")
    return text


def validate_image_upload(uploaded_file):
    if uploaded_file is None:
        raise ValidationError("이미지 파일을 선택해 주세요.")
    if uploaded_file.size > IMAGE_MAX_BYTES:
        raise ValidationError("이미지는 최대 10MB까지 전송할 수 있습니다.")
    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("PNG, JPG, WEBP, GIF 이미지 파일만 전송할 수 있습니다.")
    return uploaded_file


@transaction.atomic
def replace_with_text(session, raw_text):
    text = validate_text_payload(raw_text)
    delete_session_image(session)
    session.status = QuickdropSession.STATUS_LIVE
    session.current_kind = QuickdropSession.KIND_TEXT
    session.current_text = text
    session.current_image = None
    session.current_mime_type = "text/plain"
    session.current_filename = ""
    session.last_activity_at = timezone.now()
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


@transaction.atomic
def replace_with_image(session, uploaded_file):
    image = validate_image_upload(uploaded_file)
    delete_session_image(session)
    session.status = QuickdropSession.STATUS_LIVE
    session.current_kind = QuickdropSession.KIND_IMAGE
    session.current_text = ""
    session.current_image = image
    session.current_mime_type = str(getattr(image, "content_type", "") or "")
    session.current_filename = str(getattr(image, "name", "") or "")
    session.last_activity_at = timezone.now()
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


def session_payload(session):
    expires_at = session.last_activity_at + timedelta(seconds=SESSION_IDLE_SECONDS)
    return {
        "id": str(session.id),
        "status": session.status,
        "current_kind": session.current_kind,
        "current_text": session.current_text,
        "current_image_url": (
            reverse(
                "quickdrop:session_image",
                kwargs={"slug": session.channel.slug, "session_id": session.id},
            )
            if session.current_image
            else ""
        ),
        "current_filename": session.current_filename,
        "current_mime_type": session.current_mime_type,
        "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
        "expires_at": expires_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


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


def resolve_channel_access(request, slug):
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

    touch_device(device)
    return {
        "channel": channel,
        "is_owner": False,
        "device": device,
        "device_label": device.label,
    }


def resolve_default_access(request):
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

    return resolve_channel_access(request, payload.get("channel_slug"))


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


def cleanup_expired_sessions(now=None):
    now = now or timezone.now()
    expired_sessions = list(
        QuickdropSession.objects.select_related("channel")
        .filter(status=QuickdropSession.STATUS_LIVE, last_activity_at__lte=session_idle_cutoff(now))
        .order_by("last_activity_at")
    )
    cleaned = 0
    for session in expired_sessions:
        end_session(session, ended_at=now)
        broadcast_session_ended(session)
        cleaned += 1
    return cleaned
