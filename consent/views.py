import csv
import hashlib
import io
import logging
import mimetypes
import secrets
import os
import re
import qrcode
import base64
import requests
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count
from django.db.utils import DataError, OperationalError, ProgrammingError
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    ConsentDocumentForm,
    ConsentRequestForm,
    ConsentSignForm,
    RecipientBulkForm,
)
from .models import ConsentAuditLog, SignatureRecipient, SignatureRequest
from .policy_content import (
    CONSENT_POLICY_REFERENCES,
    CONSENT_POLICY_TERMS,
    CONSENT_POLICY_UPDATED_AT,
)
from .schema import get_consent_schema_status
from .services import (
    generate_summary_pdf,
    guess_file_type,
)

logger = logging.getLogger(__name__)


DEFAULT_LEGAL_NOTICE = (
    "본 동의서는 학교 교육활동 운영을 위한 목적 범위 내에서만 사용됩니다.\n"
    "수집 정보(학생명, 보호자명, 동의 결과, 서명 이미지, 처리 시각)는 관련 법령 및 학교 내부 규정에 따라 "
    "보관 및 파기됩니다."
)

SCHEMA_UNAVAILABLE_MESSAGE = (
    "동의서 서비스 데이터베이스가 아직 준비되지 않았습니다. "
    "관리자에게 `python manage.py migrate` 실행을 요청해 주세요."
)

SHEETBOOK_ACTION_SEED_SESSION_KEY = "sheetbook_action_seeds"


def _snapshot_file_metadata(file_obj):
    """Return immutable evidence info for a file-like object."""
    if not file_obj:
        return "", None, ""
    name = (getattr(file_obj, "name", "") or "").split("/")[-1]
    # Keep snapshot within DB field size even for very long client filenames.
    if len(name) > 255:
        root, ext = os.path.splitext(name)
        name = f"{root[:240]}{ext}"[:255]
    size = getattr(file_obj, "size", None)
    digest = hashlib.sha256()
    try:
        file_obj.seek(0)
    except Exception:
        pass
    for chunk in file_obj.chunks() if hasattr(file_obj, "chunks") else [file_obj.read()]:
        if chunk:
            digest.update(chunk)
    try:
        file_obj.seek(0)
    except Exception:
        pass
    return name, size, digest.hexdigest()


def _peek_sheetbook_seed(request, token, *, expected_action=""):
    token = (token or "").strip()
    if not token:
        return None
    seeds = request.session.get(SHEETBOOK_ACTION_SEED_SESSION_KEY, {})
    if not isinstance(seeds, dict):
        return None
    seed = seeds.get(token)
    if not isinstance(seed, dict):
        return None
    if expected_action and seed.get("action") != expected_action:
        return None
    return seed


def _pop_sheetbook_seed(request, token, *, expected_action=""):
    token = (token or "").strip()
    if not token:
        return None
    seeds = request.session.get(SHEETBOOK_ACTION_SEED_SESSION_KEY, {})
    if not isinstance(seeds, dict):
        return None
    seed = seeds.get(token)
    if not isinstance(seed, dict):
        return None
    if expected_action and seed.get("action") != expected_action:
        return None
    seeds.pop(token, None)
    request.session[SHEETBOOK_ACTION_SEED_SESSION_KEY] = seeds
    request.session.modified = True
    return seed


def _request_document_evidence(consent_request: SignatureRequest):
    name = (consent_request.document_name_snapshot or "").strip()
    sha256 = (consent_request.document_sha256_snapshot or "").strip()
    size = consent_request.document_size_snapshot
    if name and sha256:
        return {
            "document_name": name,
            "document_size": size,
            "document_sha256": sha256,
        }

    file_field = consent_request.document.original_file
    if not file_field or not file_field.name:
        return {
            "document_name": name,
            "document_size": size,
            "document_sha256": sha256,
        }

    try:
        with file_field.open("rb") as f:
            digest = hashlib.sha256()
            total = 0
            for chunk in iter(lambda: f.read(8192), b""):
                digest.update(chunk)
                total += len(chunk)
        file_name = file_field.name.split("/")[-1]
        hash_value = digest.hexdigest()
        consent_request.document_name_snapshot = file_name
        consent_request.document_size_snapshot = total
        consent_request.document_sha256_snapshot = hash_value
        consent_request.save(
            update_fields=[
                "document_name_snapshot",
                "document_size_snapshot",
                "document_sha256_snapshot",
            ]
        )
        return {
            "document_name": file_name,
            "document_size": total,
            "document_sha256": hash_value,
        }
    except Exception:
        return {
            "document_name": name,
            "document_size": size,
            "document_sha256": sha256,
        }


def _parse_recipients(text):
    recipients = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        recipients.append(
            {
                "student_name": parts[0],
                "parent_name": parts[1],
                "phone_number": parts[2] if len(parts) >= 3 else "",
            }
        )
    return recipients


def _parse_recipients_csv(file_obj):
    if not file_obj:
        return [], []

    raw = file_obj.read()
    try:
        file_obj.seek(0)
    except Exception:
        pass

    decoded = None
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded is None:
        return [], [0]

    recipients = []
    invalid_rows = []
    reader = csv.reader(io.StringIO(decoded))
    for idx, row in enumerate(reader, start=1):
        cols = [(cell or "").strip() for cell in row]
        if not any(cols):
            continue

        first = cols[0].lower() if cols else ""
        second = cols[1].lower() if len(cols) > 1 else ""
        if idx == 1 and (
            "학생" in first
            or "student" in first
            or "학부모" in second
            or "parent" in second
        ):
            continue

        if len(cols) < 2 or not cols[0] or not cols[1]:
            invalid_rows.append(idx)
            continue

        recipients.append(
            {
                "student_name": cols[0],
                "parent_name": cols[1],
                "phone_number": cols[2] if len(cols) >= 3 else "",
            }
        )

    return recipients, invalid_rows


def _build_recipients_from_shared_roster(group):
    if not group:
        return []

    recipients = []
    members = group.members.filter(is_active=True).order_by("sort_order", "id")
    for member in members:
        student_name = (member.display_name or "").strip()
        if not student_name:
            continue
        recipients.append(
            {
                "student_name": student_name,
                "parent_name": f"{student_name} 보호자",
                "phone_number": "",
            }
        )
    return recipients


def _generate_qr_base64(url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _compose_parent_message(consent_request: SignatureRequest, recipient: SignatureRecipient, sign_url: str) -> str:
    custom = (consent_request.message or "").strip()
    body = custom or f"{consent_request.title} 동의서 확인 부탁드립니다."
    return (
        f"안녕하세요. {recipient.student_name} 학생 보호자님.\n"
        f"{body}\n"
        f"동의서 링크: {sign_url}"
    )


def _sanitize_filename_base(raw: str, fallback: str = "document") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", (raw or "").strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    lowered = cleaned.lower()
    if not cleaned or lowered in {"untitled", "untitled_document", "document", "무제", "제목없음"}:
        return fallback
    return cleaned[:80]


def _build_summary_download_filename(consent_request: SignatureRequest) -> str:
    title_seed = (consent_request.title or "").strip()
    if title_seed.lower() in {"untitled", "untitled_document"} or title_seed in {"무제", "제목없음"}:
        title_seed = (consent_request.document.title or "").strip()
    safe_base = _sanitize_filename_base(title_seed, fallback="동의서_수합_요약")
    request_short = str(consent_request.request_id).split("-")[0]
    return f"{safe_base}_수합요약_{request_short}.pdf"


def _build_file_response(file_field, *, inline=True, filename_hint=""):
    if not file_field or not file_field.name:
        raise Http404("문서 파일을 찾을 수 없습니다.")

    original_filename = (file_field.name or "").split("/")[-1] or "document.pdf"
    ext = os.path.splitext(original_filename)[1] or ".pdf"
    if filename_hint:
        base = _sanitize_filename_base(filename_hint, fallback="document")
        filename = f"{base}{ext}" if not base.lower().endswith(ext.lower()) else base
    else:
        filename = original_filename
    guessed_content_type = mimetypes.guess_type(file_field.name)[0]
    content_type = guessed_content_type or "application/octet-stream"

    try:
        file_obj = file_field.open("rb")
    except Exception:
        try:
            file_url = file_field.url
        except Exception:
            file_url = ""

        remote_urls = _iter_remote_file_urls(file_field, fallback_url=file_url)
        for remote_url in remote_urls:
            response = _build_remote_proxy_response(
                remote_url,
                filename=filename,
                content_type=content_type,
                inline=inline,
            )
            if response is not None:
                return response
        if remote_urls:
            response = redirect(remote_urls[0])
            response["Cache-Control"] = "no-store"
            return response
        raise

    response = FileResponse(
        file_obj,
        content_type=content_type,
        as_attachment=not inline,
        filename=filename,
    )
    response["Cache-Control"] = "no-store"
    return response


def _strip_cloudinary_signature(url: str) -> str:
    """Cloudinary signed path(/s--...--/)를 제거한 URL을 생성한다."""
    if not url or "res.cloudinary.com" not in url:
        return ""
    return re.sub(r"/s--[^/]+--/", "/", url, count=1)


def _iter_remote_file_urls(file_field, *, fallback_url=""):
    urls = []
    seen = set()

    def push(url):
        if not url or not isinstance(url, str):
            return
        if not url.startswith("http"):
            return
        if url in seen:
            return
        seen.add(url)
        urls.append(url)

    is_cloudinary_url = "res.cloudinary.com" in (fallback_url or "")
    storage_module = getattr(getattr(file_field, "storage", None), "__class__", type("X", (), {})).__module__
    is_cloudinary_storage = "cloudinary" in (storage_module or "")

    if is_cloudinary_url or is_cloudinary_storage:
        try:
            from cloudinary.utils import private_download_url as _pdl
            file_name = (getattr(file_field, "name", "") or "").lstrip("/")

            # fallback_url에서 resource_type/delivery_type 파싱
            detected_rt = "image"
            detected_dt = "upload"
            if is_cloudinary_url:
                try:
                    parts = fallback_url.split("res.cloudinary.com/")[1].split("/")
                    if len(parts) >= 3:
                        detected_rt = parts[1]
                        detected_dt = parts[2]
                except Exception:
                    pass

            # API 인증 방식 다운로드 URL (CDN 보안 설정 우회)
            for rt in dict.fromkeys([detected_rt, "raw", "image"]):
                try:
                    api_dl = _pdl(file_name, "", resource_type=rt, type=detected_dt)
                    if api_dl:
                        push(api_dl)
                except Exception:
                    pass
        except Exception:
            pass

    # 원본 URL을 마지막 fallback으로
    push(fallback_url)

    return urls


def _build_remote_proxy_response(url: str, *, filename: str, content_type: str, inline: bool):
    if not url or not url.startswith("http"):
        return None

    try:
        remote = requests.get(url, stream=True, timeout=(5, 30))
    except Exception:
        return None

    if remote.status_code >= 400:
        remote.close()
        return None

    def iterator():
        try:
            for chunk in remote.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        finally:
            remote.close()

    response = StreamingHttpResponse(
        iterator(),
        content_type=remote.headers.get("Content-Type") or content_type,
    )
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f"{disposition}; filename*=UTF-8''{quote(filename)}"
    content_length = remote.headers.get("Content-Length")
    if content_length:
        response["Content-Length"] = content_length
    response["Cache-Control"] = "no-store"
    return response




def _is_file_accessible(file_field) -> bool:
    if not file_field or not file_field.name:
        return False

    try:
        exists = file_field.storage.exists(file_field.name)
    except Exception:
        exists = None

    if exists is True:
        return True
    if exists is False:
        try:
            file_url = file_field.url
        except Exception:
            file_url = ""
        if isinstance(file_url, str) and file_url.startswith("http"):
            if _remote_url_accessible(file_url):
                return True
            signed_url = _build_cloudinary_signed_url(file_field, fallback_url=file_url)
            if signed_url and _remote_url_accessible(signed_url):
                return True
        return False

    try:
        return bool(file_field.url)
    except Exception:
        return False


def _schema_guard_response(request, *, force_refresh=False, detail_override=""):
    is_ready, missing_tables, detail = get_consent_schema_status(force_refresh=force_refresh)
    if is_ready:
        return None

    if request.user.is_authenticated:
        messages.error(request, SCHEMA_UNAVAILABLE_MESSAGE)

    return render(
        request,
        "consent/system_unavailable.html",
        {
            "message": SCHEMA_UNAVAILABLE_MESSAGE,
            "missing_tables": missing_tables,
            "detail": detail_override or detail,
        },
        status=503,
    )


def _policy_panel_context():
    return {
        "consent_policy_terms": CONSENT_POLICY_TERMS,
        "consent_policy_references": CONSENT_POLICY_REFERENCES,
        "consent_policy_updated_at": CONSENT_POLICY_UPDATED_AT,
    }


def _build_recipient_stats(recipients):
    total = len(recipients)
    responded = sum(
        1
        for recipient in recipients
        if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED)
    )
    pending = max(total - responded, 0)
    agree = sum(1 for recipient in recipients if recipient.decision == SignatureRecipient.DECISION_AGREE)
    disagree = sum(1 for recipient in recipients if recipient.decision == SignatureRecipient.DECISION_DISAGREE)
    completion_rate = int(round((responded / total) * 100)) if total else 0
    return {
        "total": total,
        "responded": responded,
        "pending": pending,
        "agree": agree,
        "disagree": disagree,
        "completion_rate": completion_rate,
    }


def _issue_access_token():
    while True:
        token = secrets.token_urlsafe(24)
        if not SignatureRecipient.objects.filter(access_token=token).exists():
            return token


def _is_active_link_expired(recipient: SignatureRecipient) -> bool:
    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        return False
    return recipient.request.is_link_expired


def _is_public_link_released(recipient: SignatureRecipient) -> bool:
    return recipient.request.status in (
        SignatureRequest.STATUS_SENT,
        SignatureRequest.STATUS_COMPLETED,
    )


def _link_not_ready_response(request, recipient: SignatureRecipient):
    return render(
        request,
        "consent/link_not_ready.html",
        {
            "recipient": recipient,
            "consent_request": recipient.request,
        },
        status=403,
    )


def _expired_link_response(request, recipient: SignatureRecipient):
    return render(
        request,
        "consent/link_expired.html",
        {
            "recipient": recipient,
            "consent_request": recipient.request,
            "expires_at": recipient.request.link_expires_at,
        },
        status=410,
    )


@login_required
def consent_dashboard(request):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    requests = (
        SignatureRequest.objects.filter(created_by=request.user)
        .select_related("document")
        .annotate(recipient_count=Count("recipients"))
    )
    context = {
        "requests": requests,
        **_policy_panel_context(),
    }
    return render(request, "consent/dashboard.html", context)


@login_required
@transaction.atomic
def consent_delete_request(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(
        SignatureRequest,
        request_id=request_id,
        created_by=request.user,
    )
    if request.method != "POST":
        return redirect("consent:dashboard")

    title = consent_request.title
    consent_request.delete()
    messages.success(request, f"'{title}' 동의서를 삭제했습니다. 제출 응답 기록도 함께 삭제되었습니다.")
    return redirect("consent:dashboard")


@login_required
def consent_create(request):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block
    return redirect("consent:create_step1")


@login_required
@transaction.atomic
def consent_create_step1(request):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    sheetbook_seed_token = (
        request.POST.get("sheetbook_seed_token")
        or request.GET.get("sb_seed")
        or ""
    ).strip()
    sheetbook_seed = _peek_sheetbook_seed(
        request,
        sheetbook_seed_token,
        expected_action="consent",
    )
    seed_data = sheetbook_seed.get("data", {}) if isinstance(sheetbook_seed, dict) else {}
    seed_recipients = _parse_recipients(seed_data.get("recipients_text", "")) if seed_data else []
    prefill_recipients_count = len(seed_recipients)
    prefill_recipients_preview = [
        f"{recipient['student_name']} - {recipient['parent_name']}"
        for recipient in seed_recipients[:5]
    ]

    if request.method == "POST":
        document_form = ConsentDocumentForm(request.POST, request.FILES)
        request_form = ConsentRequestForm(request.POST)
        if document_form.is_valid() and request_form.is_valid():
            document = document_form.save(commit=False)
            document.created_by = request.user
            document.file_type = guess_file_type(document.original_file.name)
            doc_name, doc_size, doc_sha256 = _snapshot_file_metadata(document.original_file)
            consent_request = request_form.save(commit=False)
            consent_request.created_by = request.user
            consent_request.status = SignatureRequest.STATUS_DRAFT
            consent_request.consent_text_version = "v1"
            consent_request.document_name_snapshot = doc_name
            consent_request.document_size_snapshot = doc_size
            consent_request.document_sha256_snapshot = doc_sha256
            if not (consent_request.legal_notice or "").strip():
                consent_request.legal_notice = DEFAULT_LEGAL_NOTICE
            try:
                # Isolate DB write failures so outer atomic block can continue safely.
                with transaction.atomic():
                    document.save()
                    consent_request.document = document
                    consent_request.save()
            except (OperationalError, ProgrammingError) as exc:
                return _schema_guard_response(request, force_refresh=True, detail_override=str(exc))
            except DataError as exc:
                logger.warning("[consent] step1 data error user_id=%s err=%s", request.user.id, exc)
                if "character varying(100)" in str(exc):
                    document_form.add_error(
                        "original_file",
                        "파일 경로가 너무 길어 저장할 수 없습니다. 파일명을 짧게 바꿔 다시 업로드해 주세요.",
                    )
                else:
                    document_form.add_error("original_file", "문서 업로드 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
            except Exception:
                logger.exception("[consent] step1 create failed user_id=%s", request.user.id)
                document_form.add_error("original_file", "문서 업로드 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
            else:
                consumed_seed = _pop_sheetbook_seed(
                    request,
                    sheetbook_seed_token,
                    expected_action="consent",
                )
                consumed_seed_data = consumed_seed.get("data", {}) if isinstance(consumed_seed, dict) else {}
                recipients_text = str(consumed_seed_data.get("recipients_text") or "").strip()
                apply_seed_recipients = str(request.POST.get("apply_seed_recipients", "1")).strip().lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )
                if recipients_text and apply_seed_recipients:
                    recipients = _parse_recipients(recipients_text)
                    created = 0
                    for rec in recipients:
                        _, was_created = SignatureRecipient.objects.get_or_create(
                            request=consent_request,
                            **rec,
                        )
                        if was_created:
                            created += 1
                    if created:
                        messages.info(
                            request,
                            f"교무수첩에서 가져온 수신자 {created}명을 미리 넣어두었어요.",
                        )
                elif recipients_text:
                    messages.info(
                        request,
                        "교무수첩 수신자 자동 넣기는 꺼두었어요. 다음 단계에서 직접 추가해 주세요.",
                    )
                return redirect("consent:recipients", request_id=consent_request.request_id)
    else:
        document_form = ConsentDocumentForm(
            initial={
                "title": (seed_data.get("document_title") or "").strip(),
            }
        )
        initial_request = {
            "title": (seed_data.get("title") or "").strip(),
            "message": (seed_data.get("message") or "").strip(),
            "legal_notice": DEFAULT_LEGAL_NOTICE,
        }
        request_form = ConsentRequestForm(
            initial=initial_request,
        )

    return render(
        request,
        "consent/create_step1.html",
        {
            "document_form": document_form,
            "request_form": request_form,
            "sheetbook_seed_token": sheetbook_seed_token,
            "sheetbook_prefill_active": bool(seed_data),
            "prefill_recipients_count": prefill_recipients_count,
            "prefill_recipients_preview": prefill_recipients_preview,
            **_policy_panel_context(),
        },
    )


@login_required
@transaction.atomic
def consent_setup_positions(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    messages.info(request, "위치 설정 단계는 현재 사용하지 않습니다. 수신자 등록 단계로 이동합니다.")
    return redirect("consent:recipients", request_id=consent_request.request_id)


@login_required
@transaction.atomic
def consent_recipients(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    try:
        consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    except (OperationalError, ProgrammingError) as exc:
        return _schema_guard_response(request, force_refresh=True, detail_override=str(exc))
    form_kwargs = {"owner": request.user}
    if request.method != "POST" and consent_request.shared_roster_group_id:
        form_kwargs["initial"] = {"shared_roster_group": consent_request.shared_roster_group_id}
    form = RecipientBulkForm(request.POST or None, request.FILES or None, **form_kwargs)

    if request.method == "POST" and form.is_valid():
        selected_roster_group = form.cleaned_data.get("shared_roster_group")
        if selected_roster_group and selected_roster_group.owner_id != request.user.id:
            form.add_error("shared_roster_group", "내 명단만 선택할 수 있습니다.")
        else:
            if consent_request.shared_roster_group_id != (selected_roster_group.id if selected_roster_group else None):
                consent_request.shared_roster_group = selected_roster_group
                consent_request.save(update_fields=["shared_roster_group"])

        if not form.errors:
            text_recipients = _parse_recipients(form.cleaned_data.get("recipients_text", ""))
            csv_recipients, invalid_rows = _parse_recipients_csv(form.cleaned_data.get("recipients_csv"))
            roster_recipients = _build_recipients_from_shared_roster(selected_roster_group)
            all_recipients = text_recipients + csv_recipients + roster_recipients

            if not all_recipients:
                form.add_error(None, "등록 가능한 수신자가 없습니다. 공유 명단, 입력값 또는 CSV 파일을 확인해 주세요.")
            else:
                created = 0
                try:
                    for rec in all_recipients:
                        _, was_created = SignatureRecipient.objects.get_or_create(request=consent_request, **rec)
                        if was_created:
                            created += 1
                except (OperationalError, ProgrammingError) as exc:
                    return _schema_guard_response(request, force_refresh=True, detail_override=str(exc))
                except Exception:
                    logger.exception(
                        "[consent] recipient bulk create failed request_id=%s user_id=%s",
                        consent_request.request_id,
                        request.user.id,
                    )
                    form.add_error(None, "수신자 저장 중 오류가 발생했습니다. 입력값을 확인한 뒤 다시 시도해 주세요.")
                else:
                    if invalid_rows and invalid_rows != [0]:
                        messages.warning(
                            request,
                            f"CSV {len(invalid_rows)}개 행은 형식 오류로 제외되었습니다. (행 번호: {', '.join(map(str, invalid_rows[:10]))})",
                        )
                    elif invalid_rows == [0]:
                        messages.error(request, "CSV 인코딩을 읽지 못했습니다. UTF-8 또는 CP949 형식으로 다시 저장해 주세요.")

                    skipped = max(len(all_recipients) - created, 0)
                    if selected_roster_group:
                        messages.success(
                            request,
                            f"{created}명 등록 완료 (중복/제외 {skipped}명). 공유 명단 '{selected_roster_group.name}' 연동됨",
                        )
                    else:
                        messages.success(request, f"{created}명 등록 완료 (중복 {skipped}명 제외)")
                    return redirect("consent:detail", request_id=consent_request.request_id)

    recipients = consent_request.recipients.all().order_by("student_name")
    return render(
        request,
        "consent/create_step3_recipients.html",
        {"consent_request": consent_request, "form": form, "recipients": recipients},
    )


@login_required
def consent_recipients_csv_template(request):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="consent_recipients_template.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["학생명", "학부모명"])
    writer.writerow(["김하늘", "김하늘 보호자"])
    writer.writerow(["박나래", "박나래 보호자"])
    return response


@login_required
def consent_detail(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(
        SignatureRequest.objects.select_related("document"),
        request_id=request_id,
        created_by=request.user,
    )
    recipients = list(consent_request.recipients.all().order_by("student_name"))
    recipient_stats = _build_recipient_stats(recipients)
    links_released = consent_request.status in (
        SignatureRequest.STATUS_SENT,
        SignatureRequest.STATUS_COMPLETED,
    )
    source_file_available = _is_file_accessible(consent_request.document.original_file)
    recipient_rows = []
    for recipient in recipients:
        sign_url = request.build_absolute_uri(reverse("consent:sign", kwargs={"token": recipient.access_token}))
        recipient_rows.append(
            {
                "recipient": recipient,
                "sign_url": sign_url,
                "qr_code_base64": _generate_qr_base64(sign_url),
                "copy_message": _compose_parent_message(consent_request, recipient, sign_url),
            }
        )
    return render(
        request,
        "consent/detail.html",
        {
            "consent_request": consent_request,
            "recipient_rows": recipient_rows,
            "host_base": request.build_absolute_uri("/")[:-1],
            "link_expires_at": consent_request.link_expires_at,
            "source_file_available": source_file_available,
            "recipient_stats": recipient_stats,
            "links_released": links_released,
        },
    )


@login_required
def consent_preview_positions(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    messages.info(request, "위치 미리보기 기능은 사용하지 않습니다.")
    return redirect("consent:detail", request_id=consent_request.request_id)


@login_required
def consent_send(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    if not consent_request.recipients.exists():
        messages.error(request, "수신자를 먼저 등록해 주세요.")
        return redirect("consent:recipients", request_id=consent_request.request_id)
    if not _is_file_accessible(consent_request.document.original_file):
        messages.error(request, "안내문 파일을 찾을 수 없어 발송 링크를 생성할 수 없습니다. 문서를 다시 업로드해 주세요.")
        return redirect("consent:detail", request_id=consent_request.request_id)

    already_released = consent_request.status in (
        SignatureRequest.STATUS_SENT,
        SignatureRequest.STATUS_COMPLETED,
    )
    if consent_request.status != SignatureRequest.STATUS_COMPLETED:
        consent_request.status = SignatureRequest.STATUS_SENT
    consent_request.sent_at = timezone.now()
    update_fields = ["sent_at"]
    if consent_request.status != SignatureRequest.STATUS_COMPLETED:
        update_fields.append("status")
    consent_request.save(update_fields=update_fields)
    ConsentAuditLog.objects.create(
        request=consent_request,
        event_type=ConsentAuditLog.EVENT_REQUEST_SENT,
        event_meta={
            "recipient_count": consent_request.recipients.count(),
            "resend": already_released,
            "link_expire_days": consent_request.link_expire_days,
            "expires_at": (
                timezone.localtime(consent_request.link_expires_at).isoformat()
                if consent_request.link_expires_at
                else None
            ),
        },
    )
    if already_released:
        messages.success(request, "발송 시각을 갱신했습니다. 수신자별 링크를 다시 전달해 주세요.")
    else:
        messages.success(request, "학부모 링크 발송을 시작했습니다. 수신자별 링크를 복사해 전달해 주세요.")
    return redirect("consent:detail", request_id=consent_request.request_id)


@login_required
def consent_download_csv(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="consent_result_{consent_request.request_id}.csv"'
    )
    response.write("\ufeff")
    evidence = _request_document_evidence(consent_request)
    request_id_text = str(consent_request.request_id)
    request_title = consent_request.title or ""
    document_title = consent_request.document.title or ""
    document_name = evidence.get("document_name") or ""
    document_sha256 = evidence.get("document_sha256") or ""
    document_size = evidence.get("document_size")
    request_created_at = timezone.localtime(consent_request.created_at).strftime("%Y-%m-%d %H:%M:%S")
    sent_at_text = (
        timezone.localtime(consent_request.sent_at).strftime("%Y-%m-%d %H:%M:%S")
        if consent_request.sent_at
        else ""
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "학생명",
            "학부모명",
            "상태",
            "동의결과",
            "처리시각",
            "비동의사유",
            "요청ID",
            "동의서제목",
            "안내문제목",
            "안내문파일명",
            "안내문SHA256",
            "안내문파일크기(byte)",
            "요청생성시각",
            "발송시각",
        ]
    )
    for recipient in consent_request.recipients.order_by("student_name", "id"):
        writer.writerow(
            [
                recipient.student_name,
                recipient.parent_name,
                recipient.get_status_display(),
                recipient.get_decision_display() if recipient.decision else "",
                timezone.localtime(recipient.signed_at).strftime("%Y-%m-%d %H:%M:%S")
                if recipient.signed_at
                else "",
                recipient.decline_reason or "",
                request_id_text,
                request_title,
                document_title,
                document_name,
                document_sha256,
                document_size if document_size is not None else "",
                request_created_at,
                sent_at_text,
            ]
        )
    return response


@login_required
def consent_download_summary_pdf(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    try:
        summary_file = generate_summary_pdf(consent_request)
        filename = _build_summary_download_filename(consent_request)
        if hasattr(summary_file, "seek"):
            summary_file.seek(0)
        pdf_bytes = summary_file.read() if hasattr(summary_file, "read") else b""
        if not pdf_bytes:
            raise ValueError("summary pdf is empty")

        # 다운로드는 생성 직후 메모리 바이트를 우선 사용해 스토리지 open 실패에 영향받지 않도록 한다.
        try:
            consent_request.merged_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        except Exception:
            logger.exception(
                "[consent] summary save failed but download fallback used request_id=%s",
                consent_request.request_id,
            )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        response["Cache-Control"] = "no-store"
        return response
    except Exception:
        logger.exception("[consent] summary download failed request_id=%s", consent_request.request_id)
        messages.error(request, "요약 PDF 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        return redirect("consent:detail", request_id=consent_request.request_id)


@login_required
def consent_download_merged(request, request_id):
    return consent_download_summary_pdf(request, request_id)


@login_required
def consent_download_recipient_pdf(request, recipient_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    get_object_or_404(SignatureRecipient, id=recipient_id, request__created_by=request.user)
    raise Http404("개별 PDF 다운로드는 지원하지 않습니다. 요약 PDF를 사용해 주세요.")


@login_required
def consent_document_source(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(
        SignatureRequest.objects.select_related("document"),
        request_id=request_id,
        created_by=request.user,
    )
    file_field = consent_request.document.original_file
    try:
        return _build_file_response(file_field, inline=True, filename_hint=consent_request.document.title)
    except Exception:
        logger.exception("[consent] teacher document source open failed request_id=%s", consent_request.request_id)
        raise Http404("문서 파일을 찾을 수 없습니다.")


def consent_verify(request, token):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block
    return redirect("consent:sign", token=token)


def consent_sign(request, token):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request__document"), access_token=token)
    if not _is_public_link_released(recipient):
        return _link_not_ready_response(request, recipient)
    evidence = _request_document_evidence(recipient.request)
    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        return redirect("consent:complete", token=token)
    if _is_active_link_expired(recipient):
        return _expired_link_response(request, recipient)

    if request.method == "POST":
        form = ConsentSignForm(request.POST)
        if form.is_valid():
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(",")[0].strip()
            else:
                ip_address = request.META.get("REMOTE_ADDR")
            user_agent = request.META.get("HTTP_USER_AGENT", "")

            decision = form.cleaned_data["decision"]
            recipient.decision = decision
            recipient.decline_reason = form.cleaned_data.get("decline_reason", "").strip()
            recipient.signature_data = form.cleaned_data["signature_data"]
            recipient.signed_at = timezone.now()
            recipient.status = (
                SignatureRecipient.STATUS_SIGNED
                if decision == SignatureRecipient.DECISION_AGREE
                else SignatureRecipient.STATUS_DECLINED
            )
            recipient.ip_address = ip_address
            recipient.user_agent = user_agent
            recipient.save(update_fields=[
                "decision", "decline_reason", "signature_data",
                "signed_at", "status", "ip_address", "user_agent",
            ])

            ConsentAuditLog.objects.create(
                request=recipient.request,
                recipient=recipient,
                event_type=ConsentAuditLog.EVENT_SIGN_SUBMITTED,
                event_meta={
                    "decision": recipient.decision,
                    **evidence,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

            if not recipient.request.recipients.exclude(
                status__in=[SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED]
            ).exists():
                recipient.request.status = SignatureRequest.STATUS_COMPLETED
                recipient.request.save(update_fields=["status"])

            return redirect("consent:complete", token=token)
    else:
        form = ConsentSignForm()

    return render(
        request,
        "consent/sign.html",
        {
            "recipient": recipient,
            "consent_request": recipient.request,
            "form": form,
            "expires_at": recipient.request.link_expires_at,
            "is_expired": False,
            "document_evidence": evidence,
            "file_type": recipient.request.document.file_type,
        },
    )


def consent_public_document(request, token):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request__document"), access_token=token)
    if not _is_public_link_released(recipient):
        return _link_not_ready_response(request, recipient)
    if _is_active_link_expired(recipient):
        return _expired_link_response(request, recipient)

    file_field = recipient.request.document.original_file
    try:
        # 학부모 화면은 인라인 뷰어 대신 다운로드를 기본값으로 제공한다.
        return _build_file_response(
            file_field,
            inline=False,
            filename_hint=recipient.request.document.title,
        )
    except Exception:
        logger.exception("[consent] public document open failed token=%s", token)
        return render(
            request,
            "consent/document_unavailable.html",
            {
                "recipient": recipient,
                "consent_request": recipient.request,
            },
            status=404,
        )


def consent_public_document_inline(request, token):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(
        SignatureRecipient.objects.select_related("request__document"),
        access_token=token,
    )
    if not _is_public_link_released(recipient):
        return _link_not_ready_response(request, recipient)
    if _is_active_link_expired(recipient):
        return _expired_link_response(request, recipient)

    file_field = recipient.request.document.original_file
    try:
        return _build_file_response(
            file_field,
            inline=True,
            filename_hint=recipient.request.document.title,
        )
    except Exception:
        logger.exception("[consent] public document inline open failed token=%s", token)
        return render(
            request,
            "consent/document_unavailable.html",
            {
                "recipient": recipient,
                "consent_request": recipient.request,
            },
            status=404,
        )


@login_required
@transaction.atomic
def consent_regenerate_link(request, recipient_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(
        SignatureRecipient.objects.select_related("request"),
        id=recipient_id,
        request__created_by=request.user,
    )
    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        messages.error(request, "이미 응답 완료된 수신자는 재발급할 수 없습니다.")
        return redirect("consent:detail", request_id=recipient.request.request_id)

    recipient.access_token = _issue_access_token()
    recipient.status = SignatureRecipient.STATUS_PENDING
    recipient.save(update_fields=["access_token", "status"])
    ConsentAuditLog.objects.create(
        request=recipient.request,
        recipient=recipient,
        event_type=ConsentAuditLog.EVENT_LINK_CREATED,
    )
    messages.success(request, f"{recipient.student_name} 수신자 링크를 재발급했습니다.")
    return redirect("consent:detail", request_id=recipient.request.request_id)


@login_required
@transaction.atomic
def consent_update_recipient(request, recipient_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(
        SignatureRecipient.objects.select_related("request"),
        id=recipient_id,
        request__created_by=request.user,
    )
    if request.method != "POST":
        return redirect("consent:detail", request_id=recipient.request.request_id)

    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        messages.error(request, "이미 응답이 완료된 수신자는 수정할 수 없습니다.")
        return redirect("consent:detail", request_id=recipient.request.request_id)

    student_name = (request.POST.get("student_name") or "").strip()
    parent_name = (request.POST.get("parent_name") or "").strip()
    phone_number = (request.POST.get("phone_number") or "").strip()

    if not student_name or not parent_name:
        messages.error(request, "학생명과 학부모명은 필수입니다.")
        return redirect("consent:detail", request_id=recipient.request.request_id)
    if len(phone_number) > 20:
        messages.error(request, "전화번호는 20자 이내로 입력해 주세요.")
        return redirect("consent:detail", request_id=recipient.request.request_id)

    duplicate_exists = SignatureRecipient.objects.filter(
        request=recipient.request,
        student_name=student_name,
        parent_name=parent_name,
        phone_number=phone_number,
    ).exclude(id=recipient.id).exists()
    if duplicate_exists:
        messages.error(request, "동일한 수신자 정보가 이미 등록되어 있습니다.")
        return redirect("consent:detail", request_id=recipient.request.request_id)

    recipient.student_name = student_name
    recipient.parent_name = parent_name
    recipient.phone_number = phone_number
    recipient.save(update_fields=["student_name", "parent_name", "phone_number"])
    messages.success(request, f"{recipient.student_name} 수신자 정보를 수정했습니다.")
    return redirect("consent:detail", request_id=recipient.request.request_id)


@login_required
@transaction.atomic
def consent_delete_recipient(request, recipient_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(
        SignatureRecipient.objects.select_related("request"),
        id=recipient_id,
        request__created_by=request.user,
    )
    if request.method != "POST":
        return redirect("consent:detail", request_id=recipient.request.request_id)

    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        messages.error(request, "이미 응답이 완료된 수신자는 삭제할 수 없습니다.")
        return redirect("consent:detail", request_id=recipient.request.request_id)

    request_id = recipient.request.request_id
    student_name = recipient.student_name
    recipient.delete()
    messages.success(request, f"{student_name} 수신자를 삭제했습니다.")
    return redirect("consent:detail", request_id=request_id)


def consent_complete(request, token):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request"), access_token=token)
    return render(request, "consent/complete.html", {"recipient": recipient})
