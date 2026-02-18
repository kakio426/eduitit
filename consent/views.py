import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    ConsentDocumentForm,
    ConsentRequestForm,
    ConsentSignForm,
    PositionPayloadForm,
    RecipientBulkForm,
    VerifyIdentityForm,
)
from .models import ConsentAuditLog, SignaturePosition, SignatureRecipient, SignatureRequest
from .services import (
    generate_merged_pdf,
    generate_position_preview_pdf,
    generate_signed_pdf,
    guess_file_type,
)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:500]


def _parse_recipients(text):
    recipients = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        recipients.append(
            {
                "student_name": parts[0],
                "parent_name": parts[1],
                "phone_number": parts[2],
            }
        )
    return recipients


@login_required
def consent_dashboard(request):
    requests = SignatureRequest.objects.filter(created_by=request.user).select_related("document")
    return render(request, "consent/dashboard.html", {"requests": requests})


@login_required
def consent_create(request):
    return redirect("consent:create_step1")


@login_required
@transaction.atomic
def consent_create_step1(request):
    if request.method == "POST":
        document_form = ConsentDocumentForm(request.POST, request.FILES)
        request_form = ConsentRequestForm(request.POST)
        if document_form.is_valid() and request_form.is_valid():
            document = document_form.save(commit=False)
            document.created_by = request.user
            document.file_type = guess_file_type(document.original_file.name)
            document.save()

            consent_request = request_form.save(commit=False)
            consent_request.created_by = request.user
            consent_request.document = document
            consent_request.status = SignatureRequest.STATUS_DRAFT
            consent_request.save()
            return redirect("consent:setup_positions", request_id=consent_request.request_id)
    else:
        document_form = ConsentDocumentForm()
        request_form = ConsentRequestForm(initial={"consent_text_version": "v1"})

    return render(
        request,
        "consent/create_step1.html",
        {"document_form": document_form, "request_form": request_form},
    )


@login_required
@transaction.atomic
def consent_setup_positions(request, request_id):
    consent_request = get_object_or_404(SignatureRequest.objects.select_related("document"), request_id=request_id, created_by=request.user)
    form = PositionPayloadForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        raw = form.cleaned_data["positions_json"]
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            form.add_error(None, "좌표 데이터가 올바르지 않습니다.")
            payload = []

        if payload:
            consent_request.positions.all().delete()
            for item in payload:
                SignaturePosition.objects.create(
                    request=consent_request,
                    page=max(1, int(item.get("page", 1))),
                    x=float(item.get("x", 0.0)),
                    y=float(item.get("y", 0.0)),
                    width=float(item.get("width", 0.0)),
                    height=float(item.get("height", 0.0)),
                    x_ratio=float(item.get("x_ratio", 0.0)),
                    y_ratio=float(item.get("y_ratio", 0.0)),
                    w_ratio=float(item.get("w_ratio", 0.0)),
                    h_ratio=float(item.get("h_ratio", 0.0)),
                )
            messages.success(request, "서명 위치를 저장했습니다.")
            return redirect("consent:recipients", request_id=consent_request.request_id)

    initial_positions = [
        {
            "page": p.page,
            "x_ratio": p.x_ratio,
            "y_ratio": p.y_ratio,
            "w_ratio": p.w_ratio,
            "h_ratio": p.h_ratio,
        }
        for p in consent_request.positions.all()
    ]
    return render(
        request,
        "consent/create_step2_positions.html",
        {
            "consent_request": consent_request,
            "form": form,
            "initial_positions_json": json.dumps(initial_positions, ensure_ascii=False),
            "document_url": consent_request.document.original_file.url,
            "document_file_type": consent_request.document.file_type,
        },
    )


@login_required
@transaction.atomic
def consent_recipients(request, request_id):
    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    form = RecipientBulkForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        created = 0
        for rec in _parse_recipients(form.cleaned_data["recipients_text"]):
            _, was_created = SignatureRecipient.objects.get_or_create(request=consent_request, **rec)
            if was_created:
                created += 1
        messages.success(request, f"{created}명의 수신자를 등록했습니다.")
        return redirect("consent:detail", request_id=consent_request.request_id)

    recipients = consent_request.recipients.all().order_by("student_name")
    return render(
        request,
        "consent/create_step3_recipients.html",
        {"consent_request": consent_request, "form": form, "recipients": recipients},
    )


@login_required
def consent_detail(request, request_id):
    consent_request = get_object_or_404(
        SignatureRequest.objects.select_related("document"),
        request_id=request_id,
        created_by=request.user,
    )
    recipients = consent_request.recipients.all().order_by("student_name")
    return render(
        request,
        "consent/detail.html",
        {
            "consent_request": consent_request,
            "recipients": recipients,
            "host_base": request.build_absolute_uri("/")[:-1],
        },
    )


@login_required
def consent_preview_positions(request, request_id):
    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    if not consent_request.positions.exists():
        messages.error(request, "서명 위치를 먼저 설정해 주세요.")
        return redirect("consent:setup_positions", request_id=request_id)

    preview = generate_position_preview_pdf(consent_request)
    consent_request.preview_checked_at = timezone.now()
    consent_request.save(update_fields=["preview_checked_at"])
    return FileResponse(preview, as_attachment=True, filename=preview.name)


@login_required
def consent_send(request, request_id):
    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    if not consent_request.preview_checked_at:
        messages.error(request, "발송 전 위치 미리보기를 먼저 확인해 주세요.")
        return redirect("consent:detail", request_id=consent_request.request_id)
    if not consent_request.recipients.exists():
        messages.error(request, "수신자를 먼저 등록해 주세요.")
        return redirect("consent:recipients", request_id=consent_request.request_id)

    consent_request.status = SignatureRequest.STATUS_SENT
    consent_request.sent_at = timezone.now()
    consent_request.save(update_fields=["status", "sent_at"])
    ConsentAuditLog.objects.create(
        request=consent_request,
        event_type=ConsentAuditLog.EVENT_REQUEST_SENT,
        event_meta={"recipient_count": consent_request.recipients.count()},
    )
    messages.success(request, "발송 시뮬레이션 처리되었습니다. 링크를 복사해 전달하세요.")
    return redirect("consent:detail", request_id=consent_request.request_id)


@login_required
def consent_download_merged(request, request_id):
    consent_request = get_object_or_404(SignatureRequest, request_id=request_id, created_by=request.user)
    include_decline_summary = request.GET.get("include_decline_summary") == "1"
    merged_file = generate_merged_pdf(consent_request, include_decline_summary=include_decline_summary)
    consent_request.merged_pdf.save(merged_file.name, merged_file, save=True)
    return FileResponse(consent_request.merged_pdf.open("rb"), as_attachment=True, filename=consent_request.merged_pdf.name.split("/")[-1])


@login_required
def consent_download_recipient_pdf(request, recipient_id):
    recipient = get_object_or_404(SignatureRecipient, id=recipient_id, request__created_by=request.user)
    if not recipient.signed_pdf:
        raise Http404("아직 서명 PDF가 없습니다.")
    return FileResponse(recipient.signed_pdf.open("rb"), as_attachment=True, filename=recipient.signed_pdf.name.split("/")[-1])


def consent_verify(request, token):
    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request"), access_token=token)
    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        return redirect("consent:complete", token=token)

    if request.method == "POST":
        form = VerifyIdentityForm(request.POST)
        if form.is_valid():
            parent_name = form.cleaned_data["parent_name"].strip()
            phone_last4 = form.cleaned_data["phone_last4"]
            if parent_name == recipient.parent_name and phone_last4 == recipient.phone_last4:
                request.session[f"consent_verified_{recipient.id}"] = True
                if recipient.status == SignatureRecipient.STATUS_PENDING:
                    recipient.status = SignatureRecipient.STATUS_VERIFIED
                    recipient.save(update_fields=["status"])
                ConsentAuditLog.objects.create(
                    request=recipient.request,
                    recipient=recipient,
                    event_type=ConsentAuditLog.EVENT_VERIFY_SUCCESS,
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
                )
                return redirect("consent:sign", token=token)

            ConsentAuditLog.objects.create(
                request=recipient.request,
                recipient=recipient,
                event_type=ConsentAuditLog.EVENT_VERIFY_FAIL,
                ip_address=_client_ip(request),
                user_agent=_user_agent(request),
            )
            form.add_error(None, "정보가 일치하지 않습니다.")
    else:
        form = VerifyIdentityForm()

    return render(request, "consent/verify.html", {"recipient": recipient, "form": form})


def consent_sign(request, token):
    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request__document"), access_token=token)
    if recipient.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED):
        return redirect("consent:complete", token=token)

    if not request.session.get(f"consent_verified_{recipient.id}", False):
        return redirect("consent:verify", token=token)

    if request.method == "POST":
        form = ConsentSignForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data["decision"]
            recipient.decision = decision
            recipient.decline_reason = form.cleaned_data.get("decline_reason", "").strip()
            recipient.signature_data = form.cleaned_data["signature_data"]
            recipient.ip_address = _client_ip(request)
            recipient.user_agent = _user_agent(request)
            recipient.signed_at = timezone.now()
            recipient.status = SignatureRecipient.STATUS_SIGNED if decision == SignatureRecipient.DECISION_AGREE else SignatureRecipient.STATUS_DECLINED

            signed_file = generate_signed_pdf(recipient)
            recipient.signed_pdf.save(signed_file.name, signed_file, save=False)
            recipient.save()

            ConsentAuditLog.objects.create(
                request=recipient.request,
                recipient=recipient,
                event_type=ConsentAuditLog.EVENT_SIGN_SUBMITTED,
                ip_address=recipient.ip_address,
                user_agent=recipient.user_agent,
                event_meta={"decision": recipient.decision},
            )

            if not recipient.request.recipients.exclude(status__in=[SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED]).exists():
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
        },
    )


def consent_complete(request, token):
    recipient = get_object_or_404(SignatureRecipient.objects.select_related("request"), access_token=token)
    return render(request, "consent/complete.html", {"recipient": recipient})
