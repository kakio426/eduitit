import csv
import io
import logging
import mimetypes
import secrets
import qrcode
import base64

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.http import FileResponse, Http404, HttpResponse
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


def _build_file_response(file_field, *, inline=True):
    filename = (file_field.name or "").split("/")[-1] or "document.pdf"
    guessed_content_type = mimetypes.guess_type(file_field.name)[0]
    content_type = guessed_content_type or "application/octet-stream"

    file_obj = file_field.open("rb")
    response = FileResponse(
        file_obj,
        content_type=content_type,
        as_attachment=not inline,
        filename=filename,
    )
    response["Cache-Control"] = "no-store"
    return response


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


def _issue_access_token():
    while True:
        token = secrets.token_urlsafe(24)
        if not SignatureRecipient.objects.filter(access_token=token).exists():
            return token


def _is_active_link_expired(recipient: SignatureRecipient) -> bool:
    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        return False
    return recipient.request.is_link_expired


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

    requests = SignatureRequest.objects.filter(created_by=request.user).select_related("document")
    context = {
        "requests": requests,
        **_policy_panel_context(),
    }
    return render(request, "consent/dashboard.html", context)


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

    if request.method == "POST":
        document_form = ConsentDocumentForm(request.POST, request.FILES)
        request_form = ConsentRequestForm(request.POST)
        if document_form.is_valid() and request_form.is_valid():
            document = document_form.save(commit=False)
            document.created_by = request.user
            document.file_type = guess_file_type(document.original_file.name)
            consent_request = request_form.save(commit=False)
            consent_request.created_by = request.user
            consent_request.status = SignatureRequest.STATUS_DRAFT
            consent_request.consent_text_version = "v1"
            if not (consent_request.legal_notice or "").strip():
                consent_request.legal_notice = DEFAULT_LEGAL_NOTICE
            try:
                document.save()
                consent_request.document = document
                consent_request.save()
            except (OperationalError, ProgrammingError) as exc:
                return _schema_guard_response(request, force_refresh=True, detail_override=str(exc))
            return redirect("consent:recipients", request_id=consent_request.request_id)
    else:
        document_form = ConsentDocumentForm()
        request_form = ConsentRequestForm(
            initial={
                "legal_notice": DEFAULT_LEGAL_NOTICE,
            }
        )

    return render(
        request,
        "consent/create_step1.html",
        {
            "document_form": document_form,
            "request_form": request_form,
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

    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    form = RecipientBulkForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        text_recipients = _parse_recipients(form.cleaned_data.get("recipients_text", ""))
        csv_recipients, invalid_rows = _parse_recipients_csv(form.cleaned_data.get("recipients_csv"))
        all_recipients = text_recipients + csv_recipients

        if not all_recipients:
            form.add_error(None, "등록 가능한 수신자가 없습니다. 입력값 또는 CSV 파일을 확인해 주세요.")
        else:
            created = 0
            for rec in all_recipients:
                _, was_created = SignatureRecipient.objects.get_or_create(request=consent_request, **rec)
                if was_created:
                    created += 1

            if invalid_rows and invalid_rows != [0]:
                messages.warning(
                    request,
                    f"CSV {len(invalid_rows)}개 행은 형식 오류로 제외되었습니다. (행 번호: {', '.join(map(str, invalid_rows[:10]))})",
                )
            elif invalid_rows == [0]:
                messages.error(request, "CSV 인코딩을 읽지 못했습니다. UTF-8 또는 CP949 형식으로 다시 저장해 주세요.")

            skipped = max(len(all_recipients) - created, 0)
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
    recipients = consent_request.recipients.all().order_by("student_name")
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

    consent_request.status = SignatureRequest.STATUS_SENT
    consent_request.sent_at = timezone.now()
    consent_request.save(update_fields=["status", "sent_at"])
    ConsentAuditLog.objects.create(
        request=consent_request,
        event_type=ConsentAuditLog.EVENT_REQUEST_SENT,
        event_meta={
            "recipient_count": consent_request.recipients.count(),
            "link_expire_days": consent_request.link_expire_days,
            "expires_at": (
                timezone.localtime(consent_request.link_expires_at).isoformat()
                if consent_request.link_expires_at
                else None
            ),
        },
    )
    messages.success(request, "발송 링크 생성이 완료되었습니다. 수신자별 링크를 복사해 전달해 주세요.")
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
    writer = csv.writer(response)
    writer.writerow(["학생명", "학부모명", "상태", "동의결과", "처리시각", "비동의사유"])
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
            ]
        )
    return response


@login_required
def consent_download_summary_pdf(request, request_id):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    summary_file = generate_summary_pdf(consent_request)
    consent_request.merged_pdf.save(summary_file.name, summary_file, save=True)
    return FileResponse(
        consent_request.merged_pdf.open("rb"),
        as_attachment=True,
        filename=consent_request.merged_pdf.name.split("/")[-1],
    )


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
        return _build_file_response(file_field, inline=True)
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
    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        return redirect("consent:complete", token=token)
    if _is_active_link_expired(recipient):
        return _expired_link_response(request, recipient)

    if request.method == "POST":
        form = ConsentSignForm(request.POST)
        if form.is_valid():
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
            recipient.save(update_fields=["decision", "decline_reason", "signature_data", "signed_at", "status"])

            ConsentAuditLog.objects.create(
                request=recipient.request,
                recipient=recipient,
                event_type=ConsentAuditLog.EVENT_SIGN_SUBMITTED,
                event_meta={"decision": recipient.decision},
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
            "is_expired": _is_active_link_expired(recipient),
        },
    )


def consent_public_document(request, token):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request__document"), access_token=token)
    if _is_active_link_expired(recipient):
        return _expired_link_response(request, recipient)

    file_field = recipient.request.document.original_file
    try:
        return _build_file_response(file_field, inline=True)
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


def consent_complete(request, token):
    schema_block = _schema_guard_response(request)
    if schema_block:
        return schema_block

    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request"), access_token=token)
    return render(request, "consent/complete.html", {"recipient": recipient})
