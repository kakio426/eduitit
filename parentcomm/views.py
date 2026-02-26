import csv
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from products.models import Product

from .forms import (
    ConsultationProposalForm,
    ConsultationRequestForm,
    ConsultationSlotForm,
    ParentContactBulkTextForm,
    ParentContactForm,
    ParentContactCsvImportForm,
    ParentNoticeForm,
    ParentThreadCreateForm,
    ParentThreadMessageForm,
    ParentUrgentAlertForm,
)
from .models import (
    ConsultationProposal,
    ConsultationRequest,
    ParentCommunicationPolicy,
    ParentContact,
    ParentNotice,
    ParentThread,
    ParentThreadMessage,
    ParentUrgentAlert,
)


SERVICE_TITLE = "학부모 소통 허브"
TAB_TODAY = "today"
TAB_NOTICES = "notices"
TAB_MESSAGES = "messages"
TAB_CONSULT = "consult"
TAB_CONTACTS = "contacts"
ALLOWED_TABS = {TAB_TODAY, TAB_NOTICES, TAB_MESSAGES, TAB_CONSULT, TAB_CONTACTS}
CONTACT_HEADER_ALIASES = {
    "student_name": {"studentname", "학생이름", "학생명", "학생"},
    "parent_name": {"parentname", "학부모이름", "학부모명", "보호자이름", "보호자명", "학부모", "보호자"},
    "contact_phone": {"contactphone", "phone", "연락처", "전화번호", "휴대폰"},
    "contact_email": {"contactemail", "email", "이메일", "메일"},
    "student_grade": {"studentgrade", "grade", "학년"},
    "student_classroom": {"studentclassroom", "classroom", "반", "학급"},
    "relationship": {"relationship", "관계"},
}


def _get_service():
    service = Product.objects.filter(launch_route_name="parentcomm:main").first()
    if service:
        return service
    return Product.objects.filter(title=SERVICE_TITLE).first()


@login_required
def main(request):
    teacher = request.user
    ParentCommunicationPolicy.objects.get_or_create(teacher=teacher)
    active_tab = (request.GET.get("tab") or TAB_TODAY).strip()
    if active_tab not in ALLOWED_TABS:
        active_tab = TAB_TODAY

    contact_form = ParentContactForm()
    contact_csv_form = ParentContactCsvImportForm()
    contact_bulk_form = ParentContactBulkTextForm()
    notice_form = ParentNoticeForm()
    thread_form = ParentThreadCreateForm(teacher=teacher)
    consultation_request_form = ConsultationRequestForm(teacher=teacher)
    invalid_request_forms = {}
    invalid_slot_forms = {}
    invalid_message_forms = {}

    def _redirect_to(tab_name):
        return redirect(f"{reverse('parentcomm:main')}?tab={tab_name}")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "add_contact":
            active_tab = TAB_CONTACTS
            contact_form = ParentContactForm(request.POST)
            if contact_form.is_valid():
                contact = contact_form.save(commit=False)
                contact.teacher = teacher
                contact.save()
                messages.success(request, "학부모 연락처를 등록했습니다.")
                return _redirect_to(TAB_CONTACTS)
            messages.error(request, "연락처를 저장하지 못했습니다. 입력값을 확인해 주세요.")
        elif action == "add_contact_csv":
            active_tab = TAB_CONTACTS
            contact_csv_form = ParentContactCsvImportForm(request.POST, request.FILES)
            if contact_csv_form.is_valid():
                rows, parse_errors = _parse_contact_csv_rows(contact_csv_form.cleaned_data["csv_file"])
                if parse_errors:
                    for err in parse_errors[:3]:
                        messages.error(request, err)
                elif not rows:
                    messages.warning(request, "CSV에서 등록 가능한 행을 찾지 못했습니다.")
                else:
                    created_count, updated_count = _upsert_parent_contacts(teacher, rows)
                    messages.success(
                        request,
                        f"CSV 등록 완료: 신규 {created_count}명, 업데이트 {updated_count}명",
                    )
                    return _redirect_to(TAB_CONTACTS)
            else:
                messages.error(request, "CSV 파일을 다시 확인해 주세요.")
        elif action == "add_contact_bulk_text":
            active_tab = TAB_CONTACTS
            contact_bulk_form = ParentContactBulkTextForm(request.POST)
            if contact_bulk_form.is_valid():
                rows, parse_errors = _parse_contact_bulk_text_rows(contact_bulk_form.cleaned_data["bulk_text"])
                if parse_errors:
                    for err in parse_errors[:3]:
                        messages.error(request, err)
                elif not rows:
                    messages.warning(request, "입력한 내용에서 등록 가능한 항목을 찾지 못했습니다.")
                else:
                    created_count, updated_count = _upsert_parent_contacts(teacher, rows)
                    messages.success(
                        request,
                        f"빠른 등록 완료: 신규 {created_count}명, 업데이트 {updated_count}명",
                    )
                    return _redirect_to(TAB_CONTACTS)
            else:
                messages.error(request, "빠른 등록 입력값을 확인해 주세요.")
        elif action == "create_notice":
            active_tab = TAB_NOTICES
            notice_form = ParentNoticeForm(request.POST, request.FILES)
            if notice_form.is_valid():
                notice = notice_form.save(commit=False)
                notice.teacher = teacher
                notice.save()
                messages.success(request, "알림장을 등록했습니다.")
                return _redirect_to(TAB_NOTICES)
            messages.error(request, "알림장을 저장하지 못했습니다.")
        elif action == "create_thread":
            active_tab = TAB_MESSAGES
            thread_form = ParentThreadCreateForm(request.POST, teacher=teacher)
            if thread_form.is_valid():
                thread_form.save()
                messages.success(request, "새 쪽지를 시작했습니다.")
                return _redirect_to(TAB_MESSAGES)
            messages.error(request, "쪽지를 시작하지 못했습니다.")
        elif action == "reply_thread":
            active_tab = TAB_MESSAGES
            thread_id = request.POST.get("thread_id")
            thread = get_object_or_404(ParentThread, id=thread_id, teacher=teacher)
            thread_message_form = ParentThreadMessageForm(request.POST)
            if thread_message_form.is_valid():
                thread_message_form.save(
                    thread=thread,
                    sender_role=ParentThreadMessage.SenderRole.TEACHER,
                )
                messages.success(request, "답장을 보냈습니다.")
                return _redirect_to(TAB_MESSAGES)
            invalid_message_forms[thread.id] = thread_message_form
            messages.error(request, "답장을 보내지 못했습니다.")
        elif action == "create_consultation_request":
            active_tab = TAB_CONSULT
            consultation_request_form = ConsultationRequestForm(request.POST, teacher=teacher)
            if consultation_request_form.is_valid():
                consultation_request_form.save()
                messages.success(request, "상담 요청을 등록했습니다.")
                return _redirect_to(TAB_CONSULT)
            messages.error(request, "상담 요청을 등록하지 못했습니다.")
        elif action == "create_proposal":
            active_tab = TAB_CONSULT
            request_id = request.POST.get("consultation_request_id")
            consultation_request = get_object_or_404(
                ConsultationRequest,
                id=request_id,
                teacher=teacher,
            )
            proposal_form = ConsultationProposalForm(
                request.POST,
                teacher=teacher,
                consultation_request=consultation_request,
            )
            if proposal_form.is_valid():
                proposal_form.save()
                messages.success(request, "상담 방식 제안을 저장했습니다.")
                return _redirect_to(TAB_CONSULT)
            invalid_request_forms[consultation_request.id] = proposal_form
            messages.error(request, "상담 방식 제안을 저장하지 못했습니다.")
        elif action == "add_slot":
            active_tab = TAB_CONSULT
            proposal_id = request.POST.get("proposal_id")
            proposal = get_object_or_404(
                ConsultationProposal.objects.select_related("consultation_request"),
                id=proposal_id,
                teacher=teacher,
            )
            slot_form = ConsultationSlotForm(request.POST, proposal=proposal)
            if slot_form.is_valid():
                slot_form.save()
                messages.success(request, "상담 조율 시간을 추가했습니다.")
                return _redirect_to(TAB_CONSULT)
            invalid_slot_forms[proposal.id] = slot_form
            messages.error(request, "상담 조율 시간을 추가하지 못했습니다.")

    contacts = ParentContact.objects.filter(teacher=teacher).order_by("student_name", "parent_name")
    notices = ParentNotice.objects.filter(teacher=teacher).order_by("-published_at")[:10]
    threads = (
        ParentThread.objects.filter(teacher=teacher)
        .select_related("parent_contact")
        .prefetch_related("messages")
        .order_by("-updated_at")[:20]
    )
    consultation_requests = (
        ConsultationRequest.objects.filter(teacher=teacher)
        .select_related("parent_contact", "selected_slot")
        .prefetch_related("proposals__slots")
        .order_by("-requested_at")
    )
    urgent_alerts = (
        ParentUrgentAlert.objects.filter(teacher=teacher)
        .select_related("parent_contact")
        .order_by("is_acknowledged", "-created_at")[:30]
    )
    urgent_unchecked = [item for item in urgent_alerts if not item.is_acknowledged]

    reply_waiting_messages = [item for item in threads if item.status == ParentThread.Status.WAITING_TEACHER]
    consult_waiting_items = [
        item
        for item in consultation_requests
        if item.status in {ConsultationRequest.Status.PROPOSED, ConsultationRequest.Status.AWAITING_PARENT}
    ]

    consultation_status_labels = dict(ConsultationRequest.Status.choices)
    request_proposal_forms = {
        req.id: ConsultationProposalForm(teacher=teacher, consultation_request=req)
        for req in consultation_requests
    }
    request_proposal_forms.update(invalid_request_forms)
    proposal_slot_forms = {}
    for req in consultation_requests:
        for proposal in req.proposals.all():
            proposal_slot_forms[proposal.id] = ConsultationSlotForm(proposal=proposal)
    proposal_slot_forms.update(invalid_slot_forms)
    thread_message_forms = {thread.id: ParentThreadMessageForm() for thread in threads}
    thread_message_forms.update(invalid_message_forms)

    context = {
        "service": _get_service(),
        "active_tab": active_tab,
        "contacts": contacts,
        "notices": notices,
        "threads": threads,
        "reply_waiting_messages": reply_waiting_messages,
        "consultation_requests": consultation_requests,
        "consult_waiting_items": consult_waiting_items,
        "urgent_alerts": urgent_alerts,
        "urgent_unchecked": urgent_unchecked,
        "consultation_status_labels": consultation_status_labels,
        "contact_form": contact_form,
        "contact_csv_form": contact_csv_form,
        "contact_bulk_form": contact_bulk_form,
        "notice_form": notice_form,
        "thread_form": thread_form,
        "thread_message_forms": thread_message_forms,
        "consultation_request_form": consultation_request_form,
        "request_proposal_forms": request_proposal_forms,
        "proposal_slot_forms": proposal_slot_forms,
    }
    return render(request, "parentcomm/main.html", context)


def _normalize_contact_header(value):
    return (value or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _decode_csv_text(raw_bytes):
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def _safe_int_or_none(value):
    text = (value or "").strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    number = int(text)
    return number if number > 0 else None


def _build_contact_row_from_values(values):
    student_name = (values[0] if len(values) > 0 else "").strip()
    parent_name = (values[1] if len(values) > 1 else "").strip()
    if not student_name or not parent_name:
        return None

    return {
        "student_name": student_name,
        "parent_name": parent_name,
        "contact_phone": (values[2] if len(values) > 2 else "").strip(),
        "contact_email": (values[3] if len(values) > 3 else "").strip(),
        "student_grade": _safe_int_or_none(values[4] if len(values) > 4 else ""),
        "student_classroom": (values[5] if len(values) > 5 else "").strip(),
        "relationship": (values[6] if len(values) > 6 else "").strip(),
    }


def _parse_contact_bulk_text_rows(raw_text):
    rows = []
    errors = []
    for line_no, raw_line in enumerate((raw_text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [item.strip() for item in line.split(",")]
        row = _build_contact_row_from_values(parts)
        if row:
            rows.append(row)
        else:
            errors.append(f"{line_no}번째 줄 형식이 올바르지 않습니다. (학생이름,학부모이름 필수)")
    return rows, errors


def _parse_contact_csv_rows(csv_file):
    raw_bytes = csv_file.read()
    csv_file.seek(0)
    text = _decode_csv_text(raw_bytes)
    stream = StringIO(text)
    rows = []
    errors = []

    sample = text[:2048]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.reader(stream, delimiter=delimiter)
    all_rows = [[col.strip() for col in row] for row in reader]
    all_rows = [row for row in all_rows if any(cell for cell in row)]
    if not all_rows:
        return [], ["CSV 내용이 비어 있습니다."]

    header = all_rows[0]
    mapping = {}
    for idx, col_name in enumerate(header):
        key = _normalize_contact_header(col_name)
        for field_name, aliases in CONTACT_HEADER_ALIASES.items():
            if key in aliases:
                mapping[field_name] = idx
                break

    has_header = "student_name" in mapping and "parent_name" in mapping
    data_rows = all_rows[1:] if has_header else all_rows

    def _value(row_values, field_name):
        index = mapping.get(field_name)
        if index is None or index >= len(row_values):
            return ""
        return row_values[index].strip()

    for i, row_values in enumerate(data_rows, start=2 if has_header else 1):
        if has_header:
            extracted = {
                "student_name": _value(row_values, "student_name"),
                "parent_name": _value(row_values, "parent_name"),
                "contact_phone": _value(row_values, "contact_phone"),
                "contact_email": _value(row_values, "contact_email"),
                "student_grade": _safe_int_or_none(_value(row_values, "student_grade")),
                "student_classroom": _value(row_values, "student_classroom"),
                "relationship": _value(row_values, "relationship"),
            }
            if not extracted["student_name"] or not extracted["parent_name"]:
                errors.append(f"{i}번째 행에서 학생이름/학부모이름이 비어 있습니다.")
                continue
            rows.append(extracted)
        else:
            parsed = _build_contact_row_from_values(row_values)
            if not parsed:
                errors.append(f"{i}번째 행 형식이 맞지 않습니다. (학생이름,학부모이름 필수)")
                continue
            rows.append(parsed)

    return rows, errors


def _upsert_parent_contacts(teacher, rows):
    created_count = 0
    updated_count = 0
    for row in rows:
        defaults = {
            "contact_phone": row.get("contact_phone", ""),
            "contact_email": row.get("contact_email", ""),
            "student_grade": row.get("student_grade"),
            "student_classroom": row.get("student_classroom", ""),
            "relationship": row.get("relationship", ""),
            "is_active": True,
        }
        _, created = ParentContact.objects.update_or_create(
            teacher=teacher,
            student_name=row["student_name"],
            parent_name=row["parent_name"],
            defaults=defaults,
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
    return created_count, updated_count


def urgent_entry(request, access_id):
    contact = get_object_or_404(
        ParentContact.objects.select_related("teacher"),
        emergency_access_id=access_id,
        is_active=True,
    )

    if request.method == "POST":
        form = ParentUrgentAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.teacher = contact.teacher
            alert.parent_contact = contact
            alert.full_clean()
            alert.save()
            return redirect(f"{reverse('parentcomm:urgent_entry', kwargs={'access_id': access_id})}?sent=1")
    else:
        form = ParentUrgentAlertForm()

    sent = request.GET.get("sent") == "1"
    recent_alerts = ParentUrgentAlert.objects.filter(parent_contact=contact).order_by("-created_at")[:5]
    return render(
        request,
        "parentcomm/urgent_entry.html",
        {
            "contact": contact,
            "form": form,
            "sent": sent,
            "recent_alerts": recent_alerts,
        },
    )


@login_required
@require_POST
def acknowledge_urgent_alert(request, alert_id):
    alert = get_object_or_404(ParentUrgentAlert, id=alert_id, teacher=request.user)
    if not alert.is_acknowledged:
        alert.is_acknowledged = True
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["is_acknowledged", "acknowledged_at"])
        messages.success(request, "긴급 안내를 확인 처리했습니다.")
    return redirect("parentcomm:main")
