import base64
import hashlib
import io
import random
import string
import uuid

from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone
import qrcode
from pypdf import PdfReader

from core.active_classroom import get_active_classroom_for_request
from products.models import Product

from .models import TextbookLiveParticipant, TextbookLiveSession, TextbookMaterial

SERVICE_ROUTE = "textbooks:main"
SERVICE_TITLE = "교과서 라이브 수업"
ACCESS_COOKIE_NAME = "textbooks_live_access"
ACCESS_COOKIE_MAX_AGE = 60 * 60 * 8
PDF_MAX_BYTES = 150 * 1024 * 1024
PDF_MAX_PAGES = 600
COOKIE_SALT = "textbooks-live-access"
ALLOWED_WS_EVENTS = {
    "session.snapshot",
    "session.navigate",
    "session.follow",
    "annotation.preview",
    "annotation.upsert",
    "annotation.delete",
    "pointer.move",
    "presence.join",
    "presence.leave",
    "session.end",
}
TEACHER_ONLY_EVENTS = {
    "session.snapshot",
    "session.navigate",
    "session.follow",
    "annotation.preview",
    "annotation.upsert",
    "annotation.delete",
    "pointer.move",
    "session.end",
}
NON_PERSISTED_EVENTS = {"annotation.preview", "pointer.move", "presence.join", "presence.leave"}


def get_service():
    return Product.objects.filter(launch_route_name=SERVICE_ROUTE).first() or Product.objects.filter(title=SERVICE_TITLE).first()


def generate_join_code():
    return "".join(random.choices(string.digits, k=6))


def build_join_qr_data_url(raw_text):
    if not raw_text:
        return ""

    qr_image = qrcode.make(raw_text)
    with io.BytesIO() as buffer:
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def validate_pdf_upload(uploaded_file):
    if uploaded_file is None:
        raise ValidationError("PDF 파일을 선택해 주세요.")
    if uploaded_file.size > PDF_MAX_BYTES:
        raise ValidationError("PDF는 최대 150MB까지 업로드할 수 있습니다.")
    name = (uploaded_file.name or "").lower()
    if not name.endswith(".pdf"):
        raise ValidationError("PDF 파일만 업로드할 수 있습니다.")

    sha256 = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        sha256.update(chunk)
    uploaded_file.seek(0)

    try:
        reader = PdfReader(uploaded_file)
    except Exception as exc:
        raise ValidationError("PDF를 읽을 수 없습니다. 손상되었거나 지원하지 않는 형식입니다.") from exc

    if reader.is_encrypted:
        raise ValidationError("암호가 걸린 PDF는 지원하지 않습니다.")

    page_count = len(reader.pages)
    if page_count < 1:
        raise ValidationError("페이지가 없는 PDF입니다.")
    if page_count > PDF_MAX_PAGES:
        raise ValidationError("PDF는 최대 600페이지까지 지원합니다.")

    uploaded_file.seek(0)
    return {
        "page_count": page_count,
        "sha256": sha256.hexdigest(),
        "original_filename": uploaded_file.name,
    }


def build_access_cookie_value(*, session, role, device_id, display_name):
    payload = {
        "session_id": str(session.id),
        "material_id": str(session.material_id),
        "role": role,
        "device_id": device_id,
        "display_name": display_name,
        "issued_at": int(timezone.now().timestamp()),
    }
    return signing.dumps(payload, salt=COOKIE_SALT, compress=True)


def load_access_cookie_value(raw_value):
    if not raw_value:
        return None
    try:
        return signing.loads(raw_value, salt=COOKIE_SALT, max_age=ACCESS_COOKIE_MAX_AGE)
    except signing.BadSignature:
        return None


def issue_student_access_cookie(response, *, session, display_name, device_id=None):
    actual_device_id = device_id or uuid.uuid4().hex
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        build_access_cookie_value(
            session=session,
            role=TextbookLiveParticipant.ROLE_STUDENT,
            device_id=actual_device_id,
            display_name=display_name,
        ),
        max_age=ACCESS_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
    return actual_device_id


def get_session_access(request, session):
    if getattr(request, "user", None) and request.user.is_authenticated and session.teacher_id == request.user.id:
        return {
            "role": TextbookLiveParticipant.ROLE_TEACHER,
            "device_id": f"teacher-{request.user.id}",
            "display_name": request.user.get_username(),
        }

    payload = load_access_cookie_value(request.COOKIES.get(ACCESS_COOKIE_NAME))
    if not payload:
        return None
    if payload.get("session_id") != str(session.id):
        return None
    return payload


def get_pdf_access(request, material):
    if getattr(request, "user", None) and request.user.is_authenticated and material.teacher_id == request.user.id:
        return True
    session_id = request.GET.get("session")
    if not session_id:
        return False
    session = material.live_sessions.filter(id=session_id).first()
    if session is None:
        return False
    payload = get_session_access(request, session)
    return bool(payload)


def default_session_viewport():
    return {
        "bookmarks": [],
        "blackout": False,
        "spotlight": {"enabled": False, "x": 0.5, "y": 0.5},
        "teacher_note": "",
        "follow_hint": "teacher",
    }


def get_or_create_teacher_session(material, request):
    existing = material.live_sessions.filter(
        teacher=request.user,
        status__in=[TextbookLiveSession.STATUS_DRAFT, TextbookLiveSession.STATUS_LIVE],
    ).order_by("-created_at").first()
    if existing:
        return existing, False

    classroom = get_active_classroom_for_request(request)
    session = TextbookLiveSession.objects.create(
        material=material,
        teacher=request.user,
        classroom=classroom,
        status=TextbookLiveSession.STATUS_LIVE,
        join_code=generate_join_code(),
        current_page=1,
        zoom_scale=1.0,
        viewport_json=default_session_viewport(),
        started_at=timezone.now(),
        last_heartbeat=timezone.now(),
    )
    return session, True


def session_snapshot_payload(session, *, include_private=False):
    viewport = dict(session.viewport_json or default_session_viewport())
    if not include_private:
        viewport.pop("teacher_note", None)
    page_states = {
        str(item.page_index): item.fabric_json
        for item in session.page_states.order_by("page_index")
    }
    participants = [
        {
            "id": participant.device_id,
            "role": participant.role,
            "display_name": participant.display_name,
            "is_connected": participant.is_connected,
            "last_seen_at": participant.last_seen_at.isoformat(),
        }
        for participant in session.participants.order_by("role", "display_name")
    ]
    return {
        "session": {
            "id": str(session.id),
            "status": session.status,
            "join_code": session.join_code if include_private else None,
            "allow_student_annotation": session.allow_student_annotation,
            "follow_mode": session.follow_mode,
            "current_page": session.current_page,
            "zoom_scale": session.zoom_scale,
            "viewport": viewport,
            "last_seq": session.last_seq,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        },
        "material": {
            "id": str(session.material_id),
            "title": session.material.title,
            "subject": session.material.get_subject_display(),
            "grade": session.material.grade,
            "unit_title": session.material.unit_title,
            "source_type": session.material.source_type,
            "page_count": session.material.page_count,
            "content": session.material.content,
        },
        "page_states": page_states,
        "participants": participants,
    }


def touch_participant(session, *, role, device_id, display_name, user=None, connected=True):
    participant, _ = TextbookLiveParticipant.objects.get_or_create(
        session=session,
        device_id=device_id,
        defaults={
            "role": role,
            "display_name": display_name,
            "user": user,
            "is_connected": connected,
        },
    )
    changed = []
    if participant.role != role:
        participant.role = role
        changed.append("role")
    if display_name and participant.display_name != display_name:
        participant.display_name = display_name
        changed.append("display_name")
    if participant.user_id != getattr(user, "id", None):
        participant.user = user
        changed.append("user")
    if participant.is_connected != connected:
        participant.is_connected = connected
        changed.append("is_connected")
    participant.last_seen_at = timezone.now()
    changed.append("last_seen_at")
    participant.save(update_fields=list(dict.fromkeys(changed)))
    return participant
