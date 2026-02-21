import uuid
import random
import csv
import io
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from consent.forms import RecipientBulkForm
from consent.models import ConsentAuditLog, SignatureDocument, SignatureRecipient, SignatureRequest

from .forms import (
    HSActivityForm,
    HSClassroomConfigForm,
    HSClassroomForm,
    HSPrizeForm,
    HSStudentForm,
    StudentBulkAddForm,
)
from .models import (
    HSActivity,
    HSActivityScore,
    HSBloomDraw,
    HSClassEventLog,
    HSClassroom,
    HSClassroomConfig,
    HSGuardianConsent,
    HSInterventionLog,
    HSStudentGroup,
    HSStudent,
)
from .services.engine import (
    ConsentRequiredError,
    InsufficientTicketsError,
    NoPrizeAvailableError,
    add_seeds,
    execute_bloom_draw,
    get_garden_data,
    grant_tickets,
    log_class_event,
)


def _request_id(request):
    return request.headers.get("X-Request-Id") or str(uuid.uuid4())


def _api_ok(request, data, status=200):
    return JsonResponse(
        {"ok": True, "data": data, "error": None, "request_id": _request_id(request)},
        status=status,
    )


def _api_err(request, code, message, status=400, details=None):
    return JsonResponse(
        {
            "ok": False,
            "data": None,
            "error": {"code": code, "message": message, "details": details or {}},
            "request_id": _request_id(request),
        },
        status=status,
    )


def get_teacher_classroom(request, classroom_id):
    return get_object_or_404(
        HSClassroom,
        id=classroom_id,
        teacher=request.user,
        is_active=True,
    )


DEFAULT_HAPPY_SEED_LEGAL_NOTICE = (
    "본 동의서는 행복의 씨앗 학급 운영(긍정 행동 기록, 보상 운영)을 위한 목적 범위 내에서만 사용됩니다.\n"
    "수집 정보(학생명, 보호자명, 동의 결과, 서명 이미지, 처리 시각)는 관련 법령 및 학교 내부 규정에 따라 "
    "보관 및 파기됩니다."
)


def _resolve_pdf_font_name():
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except Exception:
        return "Helvetica"

    for candidate in ("HYGothic-Medium", "HYSMyeongJo-Medium"):
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(candidate))
            return candidate
        except Exception:
            continue
    return "Helvetica"


def _build_happy_seed_notice_pdf(classroom, recipient_rows):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        body = (
            "Happy Seed Guardian Consent Notice\n"
            f"Classroom: {classroom.name}\n"
            f"School: {classroom.school_name or '-'}\n"
            f"Recipients: {len(recipient_rows)}\n"
        )
        filename = f"happy_seed_notice_{classroom.id}.pdf"
        return ContentFile(body.encode("utf-8"), name=filename)

    font_name = _resolve_pdf_font_name()
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    y = height - 48

    c.setFont(font_name, 16)
    c.drawString(40, y, "행복의 씨앗 보호자 동의 안내문")
    y -= 26

    c.setFont(font_name, 10)
    c.drawString(40, y, f"학급: {classroom.name}")
    y -= 16
    c.drawString(40, y, f"학교: {classroom.school_name or '-'}")
    y -= 16
    c.drawString(40, y, f"생성일시: {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')}")
    y -= 24

    lines = [
        "안녕하세요. 행복의 씨앗 학급 운영을 위해 보호자 동의를 요청드립니다.",
        "아래 링크에서 안내문을 확인하시고 동의/비동의 및 서명을 제출해 주세요.",
        "수집 정보는 동의 관리 목적 외에는 사용하지 않습니다.",
        "",
        f"요청 대상 학생 수: {len(recipient_rows)}명",
    ]
    for line in lines:
        c.drawString(40, y, line)
        y -= 16

    c.setFont(font_name, 9)
    y -= 8
    c.drawString(40, y, "[대상 학생 목록]")
    y -= 14
    for idx, row in enumerate(recipient_rows, start=1):
        if y < 60:
            c.showPage()
            y = height - 48
            c.setFont(font_name, 9)
            c.drawString(40, y, "[대상 학생 목록 - 계속]")
            y -= 14
        c.drawString(48, y, f"{idx}. {row['student_name']} / {row['parent_name']}")
        y -= 14

    c.showPage()
    c.save()
    packet.seek(0)
    filename = f"happy_seed_notice_{classroom.id}_{timezone.localtime(timezone.now()).strftime('%Y%m%d%H%M%S')}.pdf"
    return ContentFile(packet.read(), name=filename)


def _parse_guardian_rows_from_text(text):
    rows = []
    invalid_rows = []
    for idx, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            invalid_rows.append(idx)
            continue
        rows.append(
            {
                "student_name": parts[0],
                "parent_name": parts[1],
                "phone_number": parts[2] if len(parts) >= 3 else "",
            }
        )
    return rows, invalid_rows


def _parse_guardian_rows_from_csv(file_obj):
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

    rows = []
    invalid_rows = []
    reader = csv.reader(io.StringIO(decoded))
    for idx, row in enumerate(reader, start=1):
        cols = [(cell or "").strip() for cell in row]
        if not any(cols):
            continue

        first = cols[0].lower() if cols else ""
        second = cols[1].lower() if len(cols) > 1 else ""
        if idx == 1 and ("학생" in first or "student" in first or "학부모" in second or "parent" in second):
            continue

        if len(cols) < 2 or not cols[0] or not cols[1]:
            invalid_rows.append(idx)
            continue

        rows.append(
            {
                "student_name": cols[0],
                "parent_name": cols[1],
                "phone_number": cols[2] if len(cols) >= 3 else "",
            }
        )
    return rows, invalid_rows


def _parse_consent_note_payload(note):
    if not note:
        return {}
    try:
        payload = json.loads(note)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_consent_manage_context(request, classroom, recipient_form=None):
    students = list(
        classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    )
    sign_talk_url = ""
    linked_request_id = ""

    for student in students:
        consent = getattr(student, "consent", None)
        if consent and consent.external_url and not sign_talk_url:
            sign_talk_url = consent.external_url
        payload = _parse_consent_note_payload(consent.note if consent else "")
        if payload.get("consent_request_id") and not linked_request_id:
            linked_request_id = payload["consent_request_id"]

    consent_request = None
    if linked_request_id:
        consent_request = (
            SignatureRequest.objects.filter(request_id=linked_request_id, created_by=request.user)
            .prefetch_related("recipients")
            .first()
        )

    unmatched_signatures = []
    consent_request_url = ""
    if consent_request:
        classroom_names = {student.name for student in students}
        recipient_names = set(consent_request.recipients.values_list("student_name", flat=True))
        unmatched_signatures = sorted(name for name in recipient_names if name not in classroom_names)
        consent_request_url = reverse("consent:detail", kwargs={"request_id": consent_request.request_id})

    return {
        "classroom": classroom,
        "students": students,
        "sign_talk_url": sign_talk_url,
        "consent_request_url": consent_request_url,
        "unmatched_signatures": unmatched_signatures,
        "pending_students": [
            student for student in students
            if not getattr(student, "consent", None) or student.consent.status != "approved"
        ],
        "recipient_form": recipient_form or RecipientBulkForm(),
    }


def landing(request):
    return render(request, "happy_seed/landing.html")


@login_required
def teacher_manual(request):
    return render(request, "happy_seed/teacher_manual.html")


@login_required
def dashboard(request):
    classrooms = HSClassroom.objects.filter(
        teacher=request.user,
        is_active=True,
    ).order_by("-created_at")
    return render(request, "happy_seed/dashboard.html", {"classrooms": classrooms})


@login_required
def classroom_create(request):
    if request.method == "POST":
        form = HSClassroomForm(request.POST)
        if form.is_valid():
            classroom = form.save(commit=False)
            classroom.teacher = request.user
            classroom.save()
            HSClassroomConfig.objects.create(classroom=classroom)
            messages.success(request, f'"{classroom.name}" 교실이 생성되었습니다.')
            return redirect("happy_seed:classroom_detail", classroom_id=classroom.id)
    else:
        form = HSClassroomForm()
    return render(request, "happy_seed/classroom_form.html", {"form": form, "is_create": True})


@login_required
def classroom_detail(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/classroom_detail.html",
        {
            "classroom": classroom,
            "config": config,
            "students": students,
        },
    )


@login_required
def classroom_settings(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)

    if request.method == "POST":
        prev_balance_enabled = config.balance_mode_enabled
        form = HSClassroomConfigForm(request.POST, instance=config)
        classroom_form = HSClassroomForm(request.POST, instance=classroom)
        if form.is_valid() and classroom_form.is_valid():
            form.save()
            classroom_form.save()
            if prev_balance_enabled != config.balance_mode_enabled:
                log_class_event(
                    classroom,
                    "WARM_BALANCE_MODE_TOGGLED",
                    meta={"enabled": config.balance_mode_enabled},
                )
            messages.success(request, "설정이 저장되었습니다.")
            return redirect("happy_seed:classroom_settings", classroom_id=classroom.id)
    else:
        form = HSClassroomConfigForm(instance=config)
        classroom_form = HSClassroomForm(instance=classroom)

    return render(
        request,
        "happy_seed/classroom_settings.html",
        {
            "classroom": classroom,
            "config": config,
            "form": form,
            "classroom_form": classroom_form,
        },
    )


@login_required
@require_POST
def student_add(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    form = HSStudentForm(request.POST)
    if form.is_valid():
        student = form.save(commit=False)
        student.classroom = classroom
        student.save()
        HSGuardianConsent.objects.create(student=student)
        students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
        return render(
            request,
            "happy_seed/partials/student_grid.html",
            {
                "classroom": classroom,
                "students": students,
            },
        )
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name"),
            "error": "학생 추가에 실패했습니다.",
        },
    )


@login_required
def student_bulk_add(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    if request.method == "POST":
        form = StudentBulkAddForm(request.POST)
        if form.is_valid():
            parsed = form.parse_students()
            created_count = 0
            for item in parsed:
                student, created = HSStudent.objects.get_or_create(
                    classroom=classroom,
                    number=item["number"],
                    defaults={"name": item["name"]},
                )
                if created:
                    HSGuardianConsent.objects.create(student=student)
                    created_count += 1
            messages.success(request, f"{created_count}명의 학생을 추가했습니다.")
            return redirect("happy_seed:classroom_detail", classroom_id=classroom.id)
    else:
        form = StudentBulkAddForm()
    return render(
        request,
        "happy_seed/student_bulk_add.html",
        {
            "classroom": classroom,
            "form": form,
        },
    )


@login_required
@require_POST
def student_edit(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    form = HSStudentForm(request.POST, instance=student)
    if form.is_valid():
        form.save()
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": students,
        },
    )


@login_required
def consent_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    context = _build_consent_manage_context(request, classroom)
    return render(request, "happy_seed/consent_manage.html", context)


@login_required
@require_POST
@transaction.atomic
def consent_request_via_sign_talk(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    recipient_form = RecipientBulkForm(request.POST, request.FILES)
    if not recipient_form.is_valid():
        context = _build_consent_manage_context(request, classroom, recipient_form=recipient_form)
        return render(request, "happy_seed/consent_manage.html", context, status=400)

    text_rows, invalid_text_rows = _parse_guardian_rows_from_text(
        recipient_form.cleaned_data.get("recipients_text", "")
    )
    csv_rows, invalid_csv_rows = _parse_guardian_rows_from_csv(
        recipient_form.cleaned_data.get("recipients_csv")
    )
    raw_rows = text_rows + csv_rows
    if not raw_rows:
        recipient_form.add_error(None, "등록 가능한 명단이 없습니다. 텍스트 또는 CSV를 확인해 주세요.")
        context = _build_consent_manage_context(request, classroom, recipient_form=recipient_form)
        return render(request, "happy_seed/consent_manage.html", context, status=400)

    seen_student_names = set()
    duplicate_upload_names = []
    cleaned_rows = []
    for row in raw_rows:
        student_name = (row.get("student_name") or "").strip()
        parent_name = (row.get("parent_name") or "").strip()
        phone_number = (row.get("phone_number") or "").strip()
        if not student_name or not parent_name:
            continue
        if student_name in seen_student_names:
            duplicate_upload_names.append(student_name)
            continue
        seen_student_names.add(student_name)
        cleaned_rows.append(
            {
                "student_name": student_name,
                "parent_name": parent_name,
                "phone_number": phone_number,
            }
        )

    if duplicate_upload_names:
        recipient_form.add_error(
            None,
            f"업로드 명단에 동일 학생명이 중복되었습니다: {', '.join(sorted(set(duplicate_upload_names)))}",
        )
        context = _build_consent_manage_context(request, classroom, recipient_form=recipient_form)
        return render(request, "happy_seed/consent_manage.html", context, status=400)

    students = list(classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name"))
    student_name_map = {}
    for student in students:
        student_name_map.setdefault(student.name.strip(), []).append(student)

    missing_students = []
    ambiguous_students = []
    matched_pairs = []
    for row in cleaned_rows:
        matches = student_name_map.get(row["student_name"], [])
        if len(matches) == 1:
            matched_pairs.append((matches[0], row))
        elif len(matches) == 0:
            missing_students.append(row["student_name"])
        else:
            ambiguous_students.append(row["student_name"])

    if missing_students:
        recipient_form.add_error(
            None,
            f"학급에 없는 학생명이 포함되어 있습니다: {', '.join(sorted(set(missing_students)))}",
        )
    if ambiguous_students:
        recipient_form.add_error(
            None,
            f"동명이인으로 매칭할 수 없는 학생이 있습니다: {', '.join(sorted(set(ambiguous_students)))}",
        )
    if recipient_form.errors:
        context = _build_consent_manage_context(request, classroom, recipient_form=recipient_form)
        return render(request, "happy_seed/consent_manage.html", context, status=400)

    now = timezone.now()
    title = f"[행복의 씨앗] {classroom.name} 보호자 동의서"
    document = SignatureDocument(
        created_by=request.user,
        title=f"{title} 안내문",
        file_type=SignatureDocument.FILE_TYPE_PDF,
    )
    notice_pdf = _build_happy_seed_notice_pdf(classroom, [row for _, row in matched_pairs])
    document.original_file.save(notice_pdf.name, notice_pdf, save=False)
    document.save()

    consent_request = SignatureRequest.objects.create(
        created_by=request.user,
        document=document,
        title=title,
        message=(
            f"{classroom.name} 보호자 동의서입니다. 아래 링크에서 안내문 확인 후 동의 여부와 서명을 제출해 주세요."
        ),
        legal_notice=DEFAULT_HAPPY_SEED_LEGAL_NOTICE,
        consent_text_version="v1",
        status=SignatureRequest.STATUS_SENT,
        sent_at=now,
    )

    for student, row in matched_pairs:
        recipient = SignatureRecipient.objects.create(
            request=consent_request,
            student_name=row["student_name"],
            parent_name=row["parent_name"],
            phone_number=row["phone_number"],
            status=SignatureRecipient.STATUS_PENDING,
        )
        sign_url = request.build_absolute_uri(
            reverse("consent:sign", kwargs={"token": recipient.access_token})
        )
        consent, _ = HSGuardianConsent.objects.get_or_create(student=student)
        consent.status = "pending"
        consent.external_url = sign_url
        consent.requested_at = now
        consent.completed_at = None
        consent.note = json.dumps(
            {
                "consent_request_id": str(consent_request.request_id),
                "recipient_id": recipient.id,
                "parent_name": recipient.parent_name,
                "phone_number": recipient.phone_number,
            },
            ensure_ascii=False,
        )
        consent.save()

        log_class_event(
            classroom,
            "CONSENT_REQUEST_SENT",
            student=student,
            meta={
                "external_url": sign_url,
                "consent_request_id": str(consent_request.request_id),
            },
        )

    ConsentAuditLog.objects.create(
        request=consent_request,
        event_type=ConsentAuditLog.EVENT_REQUEST_SENT,
        event_meta={
            "source": "happy_seed",
            "classroom_id": str(classroom.id),
            "recipient_count": len(matched_pairs),
        },
    )

    if invalid_csv_rows == [0]:
        messages.warning(request, "CSV 인코딩을 읽지 못해 CSV 일부를 제외했습니다. UTF-8 또는 CP949 형식으로 다시 저장해 주세요.")
    elif invalid_text_rows or invalid_csv_rows:
        invalid_total = len(invalid_text_rows) + len(invalid_csv_rows)
        messages.warning(request, f"형식 오류 {invalid_total}행은 제외하고 처리했습니다.")

    messages.success(
        request,
        f"동의 링크를 {len(matched_pairs)}명에게 자동 생성했습니다. "
        "안내문 PDF도 시스템이 자동으로 만들어 consent 요청에 연결했습니다.",
    )
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_resend(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    consent, _ = HSGuardianConsent.objects.get_or_create(student=student)
    if not consent.external_url:
        messages.error(request, "먼저 동의 링크를 생성해 주세요.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)
    consent.requested_at = timezone.now()
    consent.save(update_fields=["requested_at", "updated_at"])
    log_class_event(classroom, "CONSENT_REQUEST_SENT", student=student, meta={"resend": True})
    messages.success(request, f"{student.name} 학생 동의 요청을 재발송 처리했습니다.")
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_sync_from_sign_talk(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    students = list(classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name"))
    consent_request_id = ""
    for student in students:
        consent = getattr(student, "consent", None)
        payload = _parse_consent_note_payload(consent.note if consent else "")
        if payload.get("consent_request_id"):
            consent_request_id = payload["consent_request_id"]
            break

    if not consent_request_id:
        messages.error(request, "연동된 consent 요청이 없어 동기화할 수 없습니다.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)

    consent_request = (
        SignatureRequest.objects.filter(request_id=consent_request_id, created_by=request.user)
        .prefetch_related("recipients")
        .first()
    )
    if not consent_request:
        messages.error(request, "consent 요청을 찾을 수 없습니다.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)

    recipient_map = {}
    for recipient in consent_request.recipients.all():
        recipient_map.setdefault(recipient.student_name, []).append(recipient)

    approved_updated = 0
    rejected_updated = 0
    ambiguous_student_count = 0
    now = timezone.now()
    for student in students:
        consent = getattr(student, "consent", None)
        if not consent:
            consent = HSGuardianConsent.objects.create(student=student)
        matches = recipient_map.get(student.name, [])
        if len(matches) != 1:
            if len(matches) > 1:
                ambiguous_student_count += 1
            continue

        recipient = matches[0]
        consent.external_url = request.build_absolute_uri(
            reverse("consent:sign", kwargs={"token": recipient.access_token})
        )
        payload = _parse_consent_note_payload(consent.note)
        payload.update(
            {
                "consent_request_id": str(consent_request.request_id),
                "recipient_id": recipient.id,
                "parent_name": recipient.parent_name,
                "phone_number": recipient.phone_number,
            }
        )
        consent.note = json.dumps(payload, ensure_ascii=False)
        if not consent.requested_at:
            consent.requested_at = consent_request.sent_at or now

        if recipient.status == SignatureRecipient.STATUS_SIGNED and recipient.decision == SignatureRecipient.DECISION_AGREE:
            if consent.status != "approved":
                approved_updated += 1
                log_class_event(classroom, "CONSENT_SIGNED", student=student, meta={"by": "consent_sync"})
            consent.status = "approved"
            consent.completed_at = recipient.signed_at or now
            if not student.is_active:
                student.is_active = True
                student.save(update_fields=["is_active"])
        elif recipient.status in (SignatureRecipient.STATUS_DECLINED, SignatureRecipient.STATUS_SIGNED) and (
            recipient.decision == SignatureRecipient.DECISION_DISAGREE
        ):
            if consent.status != "rejected":
                rejected_updated += 1
            consent.status = "rejected"
            consent.completed_at = recipient.signed_at or now

        consent.save()

    classroom_names = {student.name for student in students}
    recipient_names = set(consent_request.recipients.values_list("student_name", flat=True))
    unmatched_signature_count = len([name for name in recipient_names if name not in classroom_names])
    messages.success(
        request,
        "동의 결과를 동기화했습니다. "
        f"동의 완료 {approved_updated}명, 비동의 반영 {rejected_updated}명, "
        f"명단 미일치 {unmatched_signature_count}건, 중복매칭 불가 {ambiguous_student_count}건",
    )
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_manual_approve(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    student_id = request.POST.get("student_id", "")
    signer_name = request.POST.get("signer_name", "").strip()
    student = HSStudent.objects.filter(id=student_id, classroom=classroom, is_active=True).select_related("consent").first()
    if not student:
        messages.error(request, "학생을 찾을 수 없습니다.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)
    student.consent.status = "approved"
    student.consent.completed_at = timezone.now()
    student.consent.save(update_fields=["status", "completed_at", "updated_at"])
    log_class_event(
        classroom,
        "CONSENT_SIGNED",
        student=student,
        meta={"by": "teacher_manual_review", "signer_name": signer_name},
    )
    messages.success(request, f"수동 확인 승인 완료: {student.name} (서명자: {signer_name or '-'})")
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_update(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    consent, _ = HSGuardianConsent.objects.get_or_create(student=student)

    new_status = request.POST.get("status", "")
    if new_status in dict(HSGuardianConsent.STATUS_CHOICES):
        consent.status = new_status
        if new_status == "approved":
            consent.completed_at = timezone.now()
            student.is_active = True
            log_class_event(classroom, "CONSENT_SIGNED", student=student, meta={"by": "teacher_manual"})
        if new_status == "withdrawn":
            student.is_active = False
            student.save()
        consent.save()

    return render(
        request,
        "happy_seed/partials/consent_row.html",
        {
            "student": student,
            "classroom": classroom,
        },
    )


@login_required
def prize_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)

    if request.method == "POST":
        form = HSPrizeForm(request.POST)
        if form.is_valid():
            prize = form.save(commit=False)
            prize.classroom = classroom
            prize.save()
            messages.success(request, f'보상 "{prize.name}"을 추가했습니다.')
            return redirect("happy_seed:prize_manage", classroom_id=classroom.id)
    else:
        form = HSPrizeForm()

    prizes = classroom.prizes.all()
    return render(
        request,
        "happy_seed/prize_manage.html",
        {
            "classroom": classroom,
            "prizes": prizes,
            "form": form,
        },
    )


@login_required
@require_POST
def bloom_grant(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    student_id = request.POST.get("student_id")
    source = request.POST.get("source", "participation")
    amount = int(request.POST.get("amount", 1))

    student = get_object_or_404(HSStudent, id=student_id, classroom=classroom)

    try:
        grant_tickets(student, source, amount, detail=f"{source} 인정")
        event_type = "TOKEN_GRANTED_SCORE_BONUS" if source == "achievement" else "TOKEN_GRANTED_DILIGENT"
        log_class_event(classroom, event_type, student=student, meta={"amount": amount, "source": source})
        messages.success(request, f"{student.name}에게 블룸 티켓 {amount}장을 부여했습니다.")
    except ConsentRequiredError:
        messages.error(request, f"{student.name}은(는) 보호자 동의가 필요합니다.")

    return redirect("happy_seed:classroom_detail", classroom_id=classroom.id)


@login_required
def bloom_run(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    has_rewards = classroom.has_available_rewards
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)
    students_with_tickets = classroom.students.filter(
        is_active=True,
        ticket_count__gt=0,
    ).select_related("consent").order_by("number", "name")
    groups = HSStudentGroup.objects.filter(classroom=classroom).prefetch_related("members__consent").order_by("name")
    group_infos = []
    for g in groups:
        eligible = [
            m for m in g.members.all()
            if m.is_active and getattr(m, "consent", None) and m.consent.status == "approved"
        ]
        group_infos.append({"group": g, "eligible_count": len(eligible), "member_count": g.members.count()})
    draw = None
    token = ""
    draw_id = request.GET.get("draw", "")
    if draw_id:
        draw = HSBloomDraw.objects.filter(id=draw_id, student__classroom=classroom).select_related("student", "prize").first()
        if draw:
            token = str(draw.celebration_token)
    return render(
        request,
        "happy_seed/bloom_run.html",
        {
            "classroom": classroom,
            "students": students_with_tickets,
            "has_rewards": has_rewards,
            "group_infos": group_infos,
            "default_group_draw_count": max(1, min(2, config.group_draw_count)),
            "last_draw": draw,
            "last_draw_token": token,
        },
    )


@login_required
@require_POST
def bloom_draw(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)

    request_id_str = request.POST.get("request_id", "")
    try:
        request_id = uuid.UUID(request_id_str) if request_id_str else uuid.uuid4()
    except ValueError:
        request_id = uuid.uuid4()

    try:
        draw = execute_bloom_draw(student, classroom, request.user, request_id)
        return redirect(f"{reverse('happy_seed:bloom_run', kwargs={'classroom_id': classroom.id})}?draw={draw.id}")
    except ConsentRequiredError:
        messages.error(request, f"{student.name}은(는) 보호자 동의가 필요합니다.")
    except InsufficientTicketsError:
        messages.error(request, f"{student.name}의 티켓이 부족합니다.")
    except NoPrizeAvailableError:
        messages.error(request, "사용 가능한 보상이 없습니다. 보상을 먼저 등록하거나 재고를 확인해 주세요.")

    return redirect("happy_seed:bloom_run", classroom_id=classroom.id)


@login_required
@require_POST
def seed_grant(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)

    amount = int(request.POST.get("amount", 1))
    detail = request.POST.get("detail", "교사 부여")

    add_seeds(student, amount, "teacher_grant", detail)
    log_class_event(classroom, "SEED_GRANTED_MANUAL", student=student, meta={"amount": amount, "detail": detail})

    student.refresh_from_db()
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": students,
        },
    )


def celebration(request, draw_id):
    draw = get_object_or_404(HSBloomDraw, id=draw_id)
    token = request.GET.get("token", "")

    if str(draw.celebration_token) != token:
        return HttpResponseForbidden("접근 권한이 없습니다.")

    if draw.celebration_closed:
        return render(
            request,
            "happy_seed/celebration.html",
            {
                "draw": draw,
                "closed": True,
            },
        )

    return render(
        request,
        "happy_seed/celebration.html",
        {
            "draw": draw,
            "closed": False,
        },
    )


@login_required
@require_POST
def close_celebration(request, draw_id):
    draw = get_object_or_404(HSBloomDraw, id=draw_id)
    classroom = get_teacher_classroom(request, draw.student.classroom_id)
    draw.celebration_closed = True
    draw.celebration_token = uuid.uuid4()
    draw.save()
    return redirect(f"{reverse('happy_seed:bloom_run', kwargs={'classroom_id': classroom.id})}?draw={draw.id}")


def garden_public(request, slug):
    classroom = get_object_or_404(HSClassroom, slug=slug, is_active=True)
    flowers = get_garden_data(classroom)
    return render(
        request,
        "happy_seed/garden_public.html",
        {
            "classroom": classroom,
            "flowers": flowers,
        },
    )


@login_required
def activity_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    activities = HSActivity.objects.filter(classroom=classroom).order_by("-id")[:20]

    if request.method == "POST":
        form = HSActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.classroom = classroom
            activity.save()

            for student in students:
                if student.consent.status != "approved":
                    continue
                diligent = request.POST.get(f"diligent_{student.id}") == "on"
                manual_bonus = request.POST.get(f"bonus_manual_{student.id}") == "on"
                score_val = request.POST.get(f"score_{student.id}", "").strip()
                score = int(score_val) if score_val.isdigit() else 0
                HSActivityScore.objects.update_or_create(
                    activity=activity,
                    student=student,
                    defaults={"score": score},
                )
                if diligent:
                    grant_tickets(student, "participation", 1, detail=f"[{activity.title}] 성실 참여")
                    log_class_event(
                        classroom,
                        "TOKEN_GRANTED_DILIGENT",
                        student=student,
                        meta={"activity_id": activity.id, "activity_title": activity.title},
                    )
                if manual_bonus or score >= activity.threshold_score:
                    grant_tickets(
                        student,
                        "achievement",
                        activity.extra_bloom_count,
                        detail=f"[{activity.title}] 우수 성취",
                    )
                    HSActivityScore.objects.filter(activity=activity, student=student).update(bloom_granted=True)
                    log_class_event(
                        classroom,
                        "TOKEN_GRANTED_SCORE_BONUS",
                        student=student,
                        meta={
                            "activity_id": activity.id,
                            "activity_title": activity.title,
                            "score": score,
                            "threshold": activity.threshold_score,
                            "extra": activity.extra_bloom_count,
                            "manual_bonus": manual_bonus,
                        },
                    )

            messages.success(request, "활동 저장 및 지급 적용이 완료되었습니다.")
            return redirect("happy_seed:activity_manage", classroom_id=classroom.id)
    else:
        form = HSActivityForm()

    return render(
        request,
        "happy_seed/activity_manage.html",
        {
            "classroom": classroom,
            "students": students,
            "activities": activities,
            "form": form,
        },
    )


@login_required
def analysis_dashboard(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    lookback_days = int(request.GET.get("days", "30"))
    since = timezone.now() - timezone.timedelta(days=lookback_days)
    students = list(classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name"))
    draws = HSBloomDraw.objects.filter(student__classroom=classroom, drawn_at__gte=since)
    wins = draws.filter(is_win=True).count()
    total = draws.count()
    win_rate = round((wins / total) * 100, 2) if total else 0

    stats = []
    for student in students:
        s_draws = draws.filter(student=student)
        s_wins = s_draws.filter(is_win=True).count()
        loss_streak = 0
        for d in s_draws.order_by("-drawn_at"):
            if d.is_win:
                break
            loss_streak += 1
        stats.append(
            {
                "student": student,
                "wins": s_wins,
                "draws": s_draws.count(),
                "loss_streak": loss_streak,
                "seed_count": student.seed_count,
            }
        )

    alerts = []
    long_no_win = [s for s in stats if s["draws"] >= 3 and s["wins"] == 0]
    if long_no_win:
        alerts.append(f"최근 {lookback_days}일 기준 장기 미당첨 학생 {len(long_no_win)}명")
    if stats:
        sorted_wins = sorted(stats, key=lambda x: x["wins"], reverse=True)
        top2 = sum(item["wins"] for item in sorted_wins[:2])
        if wins > 0 and top2 / wins >= 0.6:
            alerts.append("당첨 편중 가능성이 있습니다. 상위 2명 집중도를 확인해 주세요.")
        seed_stagnant = [s for s in stats if s["seed_count"] == 0 and s["draws"] == 0]
        if seed_stagnant:
            alerts.append(f"씨앗/추첨 기록이 없는 학생 {len(seed_stagnant)}명")

    intervention_logs = HSInterventionLog.objects.filter(classroom=classroom).select_related("student", "created_by")[:20]
    return render(
        request,
        "happy_seed/analysis_dashboard.html",
        {
            "classroom": classroom,
            "lookback_days": lookback_days,
            "total_draws": total,
            "wins": wins,
            "win_rate": win_rate,
            "stats": stats,
            "alerts": alerts,
            "intervention_logs": intervention_logs,
        },
    )


@login_required
def group_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    groups = HSStudentGroup.objects.filter(classroom=classroom).prefetch_related("members").order_by("name")
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create":
            name = request.POST.get("group_name", "").strip()
            if not name:
                messages.error(request, "모둠 이름을 입력해 주세요.")
            else:
                HSStudentGroup.objects.create(classroom=classroom, name=name)
                messages.success(request, f"모둠 '{name}' 생성 완료")
            return redirect("happy_seed:group_manage", classroom_id=classroom.id)
        if action == "delete":
            group = HSStudentGroup.objects.filter(classroom=classroom, id=request.POST.get("group_id")).first()
            if group:
                group.delete()
                messages.success(request, "모둠을 삭제했습니다.")
            return redirect("happy_seed:group_manage", classroom_id=classroom.id)
        if action == "save_members":
            group = HSStudentGroup.objects.filter(classroom=classroom, id=request.POST.get("group_id")).first()
            if not group:
                messages.error(request, "모둠을 찾을 수 없습니다.")
                return redirect("happy_seed:group_manage", classroom_id=classroom.id)
            member_ids = request.POST.getlist("member_ids")
            members = HSStudent.objects.filter(classroom=classroom, id__in=member_ids, is_active=True)
            group.members.set(members)
            messages.success(request, f"{group.name} 구성 저장 완료")
            return redirect("happy_seed:group_manage", classroom_id=classroom.id)

    return render(
        request,
        "happy_seed/group_manage.html",
        {
            "classroom": classroom,
            "groups": groups,
            "students": students,
        },
    )


@login_required
@require_POST
def set_teacher_override(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    reason = request.POST.get("reason", "").strip()
    student.pending_forced_win = True
    student.save(update_fields=["pending_forced_win"])
    HSInterventionLog.objects.create(
        classroom=classroom,
        student=student,
        action="forced_win_next",
        detail=reason,
        created_by=request.user,
    )
    log_class_event(
        classroom,
        "TEACHER_OVERRIDE_SET",
        student=student,
        meta={"reason": reason},
    )
    messages.success(request, f"{student.name} 학생에게 다음 꽃피움 강제당첨을 예약했습니다.")
    next_url = request.POST.get("next") or reverse("happy_seed:bloom_run", kwargs={"classroom_id": classroom.id})
    return redirect(next_url)


@login_required
@require_POST
def group_mission_success(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    group_id = request.POST.get("group_id", "")
    draw_count = request.POST.get("draw_count", "1")
    try:
        draw_count = int(draw_count)
    except ValueError:
        draw_count = 1
    draw_count = 1 if draw_count < 1 else 2 if draw_count > 2 else draw_count

    group = HSStudentGroup.objects.filter(classroom=classroom, id=group_id).prefetch_related("members__consent").first()
    if not group:
        messages.error(request, "모둠을 선택해 주세요.")
        return redirect("happy_seed:bloom_run", classroom_id=classroom.id)

    eligible = [
        m for m in group.members.all()
        if m.is_active and getattr(m, "consent", None) and m.consent.status == "approved"
    ]
    if len(eligible) < draw_count:
        messages.error(request, "모둠 인원이 부족합니다. (동의 완료 학생 기준)")
        return redirect("happy_seed:bloom_run", classroom_id=classroom.id)

    winners = random.sample(eligible, draw_count)
    winner_names = []
    for student in winners:
        grant_tickets(student, "group_draw", 1, detail=f"[{group.name}] 모둠 미션 성공")
        log_class_event(
            classroom,
            "GROUP_MISSION_REWARD",
            student=student,
            group=group,
            meta={"group_name": group.name, "draw_count": draw_count},
        )
        winner_names.append(student.name)

    messages.success(request, f"모둠 미션 성공: {group.name}에서 {', '.join(winner_names)} 학생에게 티켓 +1 지급")
    return redirect("happy_seed:bloom_run", classroom_id=classroom.id)


@login_required
@require_POST
def api_execute_draw(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return _api_err(request, "ERR_INVALID_REQUEST", "요청 본문(JSON)을 확인해 주세요.", status=400)

    student_id = body.get("student_id")
    if not student_id:
        return _api_err(request, "ERR_INVALID_REQUEST", "student_id가 필요합니다.", status=400)
    student = HSStudent.objects.filter(id=student_id, classroom=classroom).first()
    if not student:
        return _api_err(request, "ERR_NOT_FOUND", "학생을 찾을 수 없습니다.", status=404)

    raw_key = request.headers.get("Idempotency-Key") or body.get("idempotency_key") or str(uuid.uuid4())
    try:
        request_id = uuid.UUID(str(raw_key))
    except ValueError:
        request_id = uuid.uuid4()

    try:
        draw = execute_bloom_draw(student, classroom, request.user, request_id=request_id)
    except ConsentRequiredError:
        return _api_err(request, "ERR_CONSENT_REQUIRED", "동의 완료 후 사용할 수 있습니다.", status=400)
    except InsufficientTicketsError:
        return _api_err(request, "ERR_TOKEN_INSUFFICIENT", "꽃피움권이 부족합니다.", status=400)
    except NoPrizeAvailableError:
        return _api_err(request, "ERR_REWARD_EMPTY", "사용 가능한 보상이 없습니다.", status=400)

    student.refresh_from_db()
    return _api_ok(
        request,
        {
            "event_id": str(draw.id),
            "result": "WIN" if draw.is_win else "LOSE",
            "reward": (
                {"reward_id": str(draw.prize.id), "title_text": draw.prize.name}
                if draw.prize
                else None
            ),
            "student_state": {
                "student_id": str(student.id),
                "tokens_available": student.ticket_count,
                "seeds_balance": student.seed_count,
            },
            "display_overlay": {
                "show": True,
                "student_name": student.name,
                "message_footer": "나의 작은 행동 하나하나가 나의 미래, 너의 미래, 우리 모두의 미래를 행복으로 바꿉니다.",
            },
        },
    )


@login_required
@require_POST
def api_group_mission_success(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return _api_err(request, "ERR_INVALID_REQUEST", "요청 본문(JSON)을 확인해 주세요.", status=400)

    group_id = body.get("group_id")
    winners_count = int(body.get("winners_count", 1))
    winners_count = 1 if winners_count < 1 else 2 if winners_count > 2 else winners_count
    group = HSStudentGroup.objects.filter(classroom=classroom, id=group_id).prefetch_related("members__consent").first()
    if not group:
        return _api_err(request, "ERR_NOT_FOUND", "모둠을 찾을 수 없습니다.", status=404)

    eligible = [
        m for m in group.members.all()
        if m.is_active and getattr(m, "consent", None) and m.consent.status == "approved"
    ]
    if len(eligible) < winners_count:
        return _api_err(
            request,
            "ERR_GROUP_TOO_SMALL",
            "모둠 인원이 부족합니다.",
            status=400,
            details={"eligible_count": len(eligible), "requested_count": winners_count},
        )

    winners = random.sample(eligible, winners_count)
    for student in winners:
        grant_tickets(student, "group_draw", 1, detail=f"[{group.name}] 모둠 미션 성공")
        log_class_event(
            classroom,
            "GROUP_MISSION_REWARD",
            student=student,
            group=group,
            meta={"group_name": group.name, "draw_count": winners_count},
        )
    return _api_ok(
        request,
        {
            "group_id": str(group.id),
            "group_name": group.name,
            "winner_student_ids": [str(s.id) for s in winners],
            "winner_names": [s.name for s in winners],
        },
    )


@login_required
@require_POST
def api_consent_sync_sign_talk(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    before = HSGuardianConsent.objects.filter(student__classroom=classroom, status="approved").count()
    response = consent_sync_from_sign_talk(request, classroom_id)
    after = HSGuardianConsent.objects.filter(student__classroom=classroom, status="approved").count()
    if isinstance(response, JsonResponse):
        return response
    return _api_ok(
        request,
        {
            "approved_before": before,
            "approved_after": after,
            "approved_delta": max(0, after - before),
        },
    )


@login_required
def student_grid_partial(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": students,
        },
    )


def garden_partial(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, is_active=True)
    flowers = get_garden_data(classroom)
    return render(
        request,
        "happy_seed/partials/garden_flowers.html",
        {
            "classroom": classroom,
            "flowers": flowers,
        },
    )


def student_tooltip_partial(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id, is_active=True)
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=student.classroom)
    return render(
        request,
        "happy_seed/partials/student_tooltip.html",
        {
            "student": student,
            "config": config,
        },
    )
