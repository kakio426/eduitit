import csv
import io
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from products.models import Product

from .forms import (
    HandoffMemberBulkAddForm,
    HandoffRosterGroupForm,
    HandoffSessionCreateForm,
    HandoffSessionEditForm,
)
from .models import HandoffReceipt, HandoffRosterGroup, HandoffRosterMember, HandoffSession
from .shared_roster import normalize_phone_last4, roster_service_summary


def _get_service():
    return (
        Product.objects.filter(launch_route_name="handoff:landing").first()
        or Product.objects.filter(title="배부 체크").first()
    )


def _wants_json(request):
    accept = request.headers.get("Accept", "")
    requested_with = request.headers.get("X-Requested-With", "")
    return requested_with == "XMLHttpRequest" or "application/json" in accept


def _split_bulk_member_line(raw_line: str) -> tuple[str, str]:
    line = (raw_line or "").strip()
    if not line:
        return "", ""

    if "\t" in line:
        name, note = line.split("\t", 1)
        return name.strip(), note.strip()[:120]
    if "," in line:
        name, note = line.split(",", 1)
        return name.strip(), note.strip()[:120]
    return line, ""


def _compact_member_header_value(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
    )


def _member_header_field(token: str) -> str | None:
    name_headers = {"이름", "성명", "name", "teachername", "membername", "studentname", "student"}
    affiliation_headers = {
        "직위",
        "직책",
        "학년반",
        "직위학년반",
        "소속",
        "소속학년반",
        "반",
        "note",
        "affiliation",
    }
    guardian_headers = {"학부모", "보호자", "guardian", "guardianname", "parent", "parentname"}
    phone_headers = {
        "연락처",
        "전화",
        "전화번호",
        "연락처뒤4자리",
        "전화뒤4자리",
        "연락처끝4자리",
        "last4",
        "phone",
        "phone4",
        "phonelast4",
        "phonenumber",
    }
    number_headers = {"번호", "학번", "number", "no", "studentnumber", "studentno"}
    note_headers = {"비고", "메모", "memo"}

    if token in name_headers:
        return "display_name"
    if token in affiliation_headers:
        return "affiliation"
    if token in guardian_headers:
        return "guardian_name"
    if token in phone_headers:
        return "phone_last4"
    if token in number_headers:
        return "student_number"
    if token in note_headers:
        return "note"
    return None


def _is_member_comment_row(name: str) -> bool:
    return str(name or "").strip().startswith("#")


def _is_member_header_row(name: str, note: str) -> bool:
    normalized_name = _compact_member_header_value(name)
    normalized_note = _compact_member_header_value(note)
    return bool(_member_header_field(normalized_name)) and (
        not normalized_note or bool(_member_header_field(normalized_note))
    )


def _parse_student_number(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def _normalize_member_pairs(raw_pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    members = []
    seen = set()
    for raw_name, raw_note in raw_pairs:
        name = str(raw_name or "").strip()
        note = str(raw_note or "").strip()[:120]
        if not name:
            continue
        if _is_member_comment_row(name):
            continue
        if _is_member_header_row(name, note):
            continue
        key = (name, note)
        if key in seen:
            continue
        seen.add(key)
        members.append(key)
    return members


def _normalize_bulk_members(raw_text: str) -> list[tuple[str, str]]:
    parsed_pairs = []
    for raw in (raw_text or "").splitlines():
        parsed_pairs.append(_split_bulk_member_line(raw))
    return _normalize_member_pairs(parsed_pairs)


def _decode_uploaded_csv(file_obj) -> str:
    raw_bytes = file_obj.read()
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", raw_bytes, 0, len(raw_bytes), "지원하지 않는 CSV 인코딩입니다.")


def _normalize_csv_members(file_obj) -> list[tuple[str, str]]:
    decoded_text = _decode_uploaded_csv(file_obj)
    reader = csv.reader(io.StringIO(decoded_text))
    header_map = None
    members = []

    for row in reader:
        cols = [str(cell or "").strip() for cell in row]
        if not any(cols):
            continue
        if header_map is None:
            detected_map = {}
            for idx, cell in enumerate(cols):
                field_name = _member_header_field(_compact_member_header_value(cell))
                if field_name and field_name not in detected_map:
                    detected_map[field_name] = idx
            if "display_name" in detected_map:
                header_map = detected_map
                continue
            header_map = {}

        if header_map:
            member = {
                field_name: cols[idx] if idx < len(cols) else ""
                for field_name, idx in header_map.items()
            }
        else:
            member = {
                "display_name": cols[0] if len(cols) > 0 else "",
                "affiliation": cols[1] if len(cols) > 1 else "",
                "guardian_name": cols[2] if len(cols) > 2 else "",
                "phone_last4": cols[3] if len(cols) > 3 else "",
                "student_number": cols[4] if len(cols) > 4 else "",
                "note": cols[5] if len(cols) > 5 else "",
            }

        if _is_member_comment_row(member.get("display_name", "")):
            continue
        if _is_member_header_row(member.get("display_name", ""), member.get("affiliation", "")):
            continue
        if not str(member.get("display_name") or "").strip():
            continue
        members.append(member)
    return members


def _build_member_payload(group: HandoffRosterGroup, members) -> tuple[list[HandoffRosterMember], int]:
    existing_keys = set(
        group.members.values_list(
            "display_name",
            "affiliation",
            "guardian_name",
            "phone_last4",
            "student_number",
            "note",
        )
    )
    last_order = group.members.aggregate(max_order=Max("sort_order")).get("max_order") or 0
    payload = []
    skipped_existing = 0
    for member in members:
        if isinstance(member, dict):
            name = str(member.get("display_name") or "").strip()
            affiliation = str(member.get("affiliation") or "").strip()[:120]
            guardian_name = str(member.get("guardian_name") or "").strip()[:100]
            phone_last4 = normalize_phone_last4(member.get("phone_last4"))
            student_number = _parse_student_number(member.get("student_number"))
            note = str(member.get("note") or "").strip()[:120]
        else:
            name = str(member[0] or "").strip()
            affiliation = str(member[1] or "").strip()[:120]
            guardian_name = ""
            phone_last4 = ""
            student_number = None
            note = ""

        key = (name, affiliation, guardian_name, phone_last4, student_number, note)
        if key in existing_keys:
            skipped_existing += 1
            continue
        existing_keys.add(key)
        payload.append(
            HandoffRosterMember(
                group=group,
                display_name=name,
                affiliation=affiliation,
                guardian_name=guardian_name,
                phone_last4=phone_last4,
                student_number=student_number,
                note=note,
                sort_order=last_order + len(payload) + 1,
            )
        )
    return payload, skipped_existing


def _session_counts(session: HandoffSession):
    aggregate = session.receipts.aggregate(
        total=Count("id"),
        received=Count("id", filter=Q(state="received")),
        pending=Count("id", filter=Q(state="pending")),
    )
    return {
        "total": aggregate["total"] or 0,
        "received": aggregate["received"] or 0,
        "pending": aggregate["pending"] or 0,
    }


def _session_summary_text(session: HandoffSession, pending_names: Iterable[str]):
    pending = [name for name in pending_names if name]
    if not pending:
        return f"[{session.title}] 전원 수령 확인 완료되었습니다."
    joined = ", ".join(pending)
    return f"[{session.title}] 아직 수령 확인이 필요한 분: {joined}"


def _append_query_params(url, **params):
    split_result = urlsplit(url)
    query = dict(parse_qsl(split_result.query, keep_blank_values=True))
    for key, value in params.items():
        if value in (None, ""):
            query.pop(key, None)
            continue
        query[str(key)] = str(value)
    return urlunsplit(
        (
            split_result.scheme,
            split_result.netloc,
            split_result.path,
            urlencode(query),
            split_result.fragment,
        )
    )


def _get_safe_return_to(request):
    raw_value = (
        request.POST.get("return_to")
        or request.GET.get("return_to")
        or ""
    ).strip()
    if not raw_value:
        return ""
    if not url_has_allowed_host_and_scheme(
        raw_value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""
    split_result = urlsplit(raw_value)
    return urlunsplit(("", "", split_result.path or "/", split_result.query, ""))


def _redirect_with_return(target_url, return_to):
    if return_to:
        return redirect(_append_query_params(target_url, return_to=return_to))
    return redirect(target_url)


def landing(request):
    if request.user.is_authenticated:
        return redirect("handoff:dashboard")
    return render(request, "handoff/landing.html", {"service": _get_service()})


@login_required
def dashboard(request):
    owner = request.user
    return_to = _get_safe_return_to(request)
    groups = list(
        HandoffRosterGroup.objects.filter(owner=owner)
        .annotate(
            active_member_count=Count("members", filter=Q(members__is_active=True)),
            total_member_count=Count("members"),
        )
        .order_by("-is_favorite", "name")
    )
    for group in groups:
        group.manage_url = _append_query_params(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to=return_to,
        )
        group.continue_url = (
            _append_query_params(return_to, shared_roster_group=group.id)
            if return_to and group.active_member_count > 0
            else ""
        )
    sessions = (
        HandoffSession.objects.filter(owner=owner)
        .select_related("roster_group")
        .annotate(
            total_count=Count("receipts"),
            received_count=Count("receipts", filter=Q(receipts__state="received")),
            pending_count=Count("receipts", filter=Q(receipts__state="pending")),
        )
        .order_by("-created_at")
    )
    return render(
        request,
        "handoff/dashboard.html",
        {
            "service": _get_service(),
            "groups": groups,
            "sessions": sessions,
            "group_form": HandoffRosterGroupForm(),
            "session_form": HandoffSessionCreateForm(owner=owner),
            "return_to": return_to,
        },
    )


@login_required
@require_POST
def group_create(request):
    return_to = _get_safe_return_to(request)
    form = HandoffRosterGroupForm(request.POST)
    if not form.is_valid():
        for _, error_list in form.errors.items():
            for error in error_list:
                messages.error(request, error)
        return _redirect_with_return(reverse("handoff:dashboard"), return_to)

    group = form.save(commit=False)
    group.owner = request.user
    try:
        group.save()
    except IntegrityError:
        messages.error(request, "같은 이름의 명단이 이미 있습니다.")
        return _redirect_with_return(reverse("handoff:dashboard"), return_to)

    messages.success(request, f"공용 명부 '{group.name}'을 만들었습니다.")
    return _redirect_with_return(
        reverse("handoff:group_detail", kwargs={"group_id": group.id}),
        return_to,
    )


@login_required
def group_detail(request, group_id):
    return_to = _get_safe_return_to(request)
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    members = group.members.order_by("sort_order", "id")
    active_member_count = group.members.filter(is_active=True).count()
    return render(
        request,
        "handoff/group_detail.html",
        {
            "service": _get_service(),
            "group": group,
            "members": members,
            "active_member_count": active_member_count,
            "group_form": HandoffRosterGroupForm(instance=group),
            "bulk_form": HandoffMemberBulkAddForm(),
            "sessions_count": group.sessions.count(),
            "service_summary": roster_service_summary(group),
            "linked_service_counts": {
                "handoff": group.sessions.count(),
                "signatures": group.signature_sessions.count(),
                "consent": group.consent_requests.count(),
                "infoboard": group.infoboard_boards.count(),
                "happy_seed": group.hs_classrooms.count(),
            },
            "return_to": return_to,
            "continue_to_signatures_url": (
                _append_query_params(return_to, shared_roster_group=group.id)
                if return_to and active_member_count > 0
                else ""
            ),
        },
    )


@login_required
@require_POST
def group_update(request, group_id):
    return_to = _get_safe_return_to(request)
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    form = HandoffRosterGroupForm(request.POST, instance=group)
    if not form.is_valid():
        for _, error_list in form.errors.items():
            for error in error_list:
                messages.error(request, error)
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    try:
        form.save()
    except IntegrityError:
        messages.error(request, "같은 이름의 명단이 이미 있습니다.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    messages.success(request, "공용 명부 정보를 수정했습니다.")
    return _redirect_with_return(
        reverse("handoff:group_detail", kwargs={"group_id": group.id}),
        return_to,
    )


@login_required
@require_POST
def group_delete(request, group_id):
    return_to = _get_safe_return_to(request)
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    name = group.name
    group.delete()
    messages.success(request, f"공용 명부 '{name}'을 삭제했습니다.")
    return _redirect_with_return(reverse("handoff:dashboard"), return_to)


@login_required
@require_POST
def group_members_add(request, group_id):
    return_to = _get_safe_return_to(request)
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    form = HandoffMemberBulkAddForm(request.POST)
    if not form.is_valid():
        messages.error(request, "이름 목록을 확인해주세요.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    members = _normalize_bulk_members(form.cleaned_data["names_text"])
    if not members:
        messages.error(request, "추가할 이름이 없습니다.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    payload, skipped_existing = _build_member_payload(group, members)
    if not payload:
        messages.info(request, "이미 들어 있는 이름/소속 조합이라서 새로 추가할 멤버가 없었습니다.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    HandoffRosterMember.objects.bulk_create(payload)
    if skipped_existing:
        messages.success(
            request,
            f"{len(payload)}명을 추가했습니다. 같은 이름/소속 조합 {skipped_existing}명은 건너뛰었습니다.",
        )
    else:
        messages.success(request, f"{len(payload)}명을 추가했습니다.")
    return _redirect_with_return(
        reverse("handoff:group_detail", kwargs={"group_id": group.id}),
        return_to,
    )


@login_required
@require_POST
def group_members_upload(request, group_id):
    return_to = _get_safe_return_to(request)
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    file_obj = request.FILES.get("csv_file")
    if not file_obj:
        messages.error(request, "CSV 파일을 선택해 주세요.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )
    if not str(file_obj.name or "").lower().endswith(".csv"):
        messages.error(request, "CSV 파일(.csv)만 업로드할 수 있습니다.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    try:
        members = _normalize_csv_members(file_obj)
    except UnicodeDecodeError:
        messages.error(request, "CSV 인코딩을 읽지 못했습니다. UTF-8 또는 엑셀 CSV로 다시 저장해 주세요.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )
    except csv.Error:
        messages.error(request, "CSV 형식을 읽지 못했습니다. 이름 열은 꼭 넣고, 나머지 열은 소속/보호자/전화 뒤 4자리/번호/메모를 맞춰 주세요.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    if not members:
        messages.error(request, "CSV에서 추가할 이름을 찾지 못했습니다.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    payload, skipped_existing = _build_member_payload(group, members)
    if not payload:
        messages.info(request, "CSV 내용이 이미 모두 들어 있어 새로 추가할 멤버가 없었습니다.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    HandoffRosterMember.objects.bulk_create(payload)
    if skipped_existing:
        messages.success(
            request,
            f"CSV에서 {len(payload)}명을 추가했습니다. 같은 이름/소속 조합 {skipped_existing}명은 건너뛰었습니다.",
        )
    else:
        messages.success(request, f"CSV에서 {len(payload)}명을 추가했습니다.")
    return _redirect_with_return(
        reverse("handoff:group_detail", kwargs={"group_id": group.id}),
        return_to,
    )


@login_required
def group_members_template_download(request, group_id):
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{group.name}_명단_양식.csv"'

    writer = csv.writer(response)
    writer.writerow(["이름", "소속/학년반", "보호자명", "연락처 뒤 4자리", "번호", "메모"])
    writer.writerow(["김민수", "3-1", "김민수 보호자", "5678", "1", "동의서/행복씨앗 같이 사용"])
    writer.writerow(["이서연", "3-2", "이서연 보호자", "1234", "2", ""])
    writer.writerow(["박지훈", "교감", "", "", "", "사인/배부 체크용"])
    return response


@login_required
@require_POST
def group_member_update(request, group_id, member_id):
    return_to = _get_safe_return_to(request)
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    member = get_object_or_404(HandoffRosterMember, id=member_id, group=group)

    display_name = (request.POST.get("display_name") or "").strip()
    if not display_name:
        messages.error(request, "이름은 비울 수 없습니다.")
        return _redirect_with_return(
            reverse("handoff:group_detail", kwargs={"group_id": group.id}),
            return_to,
        )

    member.display_name = display_name
    member.affiliation = (request.POST.get("affiliation") or "").strip()[:120]
    member.guardian_name = (request.POST.get("guardian_name") or "").strip()[:100]
    member.phone_last4 = normalize_phone_last4(request.POST.get("phone_last4"))
    member.student_number = _parse_student_number(request.POST.get("student_number"))
    member.note = (request.POST.get("note") or "").strip()[:120]
    member.is_active = bool(request.POST.get("is_active"))
    member.save(
        update_fields=[
            "display_name",
            "affiliation",
            "guardian_name",
            "phone_last4",
            "student_number",
            "note",
            "is_active",
            "updated_at",
        ]
    )
    messages.success(request, f"{member.display_name} 정보가 저장되었습니다.")
    return _redirect_with_return(
        reverse("handoff:group_detail", kwargs={"group_id": group.id}),
        return_to,
    )


@login_required
@require_POST
def group_member_delete(request, group_id, member_id):
    return_to = _get_safe_return_to(request)
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    member = get_object_or_404(HandoffRosterMember, id=member_id, group=group)
    name = member.display_name
    member.delete()
    messages.success(request, f"{name}을(를) 삭제했습니다.")
    return _redirect_with_return(
        reverse("handoff:group_detail", kwargs={"group_id": group.id}),
        return_to,
    )


@login_required
@require_POST
def session_create(request):
    form = HandoffSessionCreateForm(request.POST, owner=request.user)
    if not form.is_valid():
        for _, error_list in form.errors.items():
            for error in error_list:
                messages.error(request, error)
        return redirect("handoff:dashboard")

    group = form.cleaned_data["roster_group"]
    active_members = list(group.members.filter(is_active=True).order_by("sort_order", "id"))
    if not active_members:
        messages.error(request, "명단에 활성 멤버가 없습니다. 멤버를 먼저 추가해주세요.")
        return redirect("handoff:group_detail", group_id=group.id)

    session = form.save(commit=False)
    session.owner = request.user
    session.roster_group_name = group.name
    session.save()

    HandoffReceipt.objects.bulk_create(
        [
            HandoffReceipt(
                session=session,
                member=member,
                member_name_snapshot=member.display_name,
                member_order_snapshot=member.sort_order,
            )
            for member in active_members
        ]
    )

    messages.success(request, f"배부 세션 '{session.title}'을 시작했습니다.")
    return redirect("handoff:session_detail", session_id=session.id)


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(
        HandoffSession.objects.select_related("roster_group"),
        id=session_id,
        owner=request.user,
    )
    receipts = list(session.receipts.order_by("member_order_snapshot", "id"))
    counts = _session_counts(session)
    pending_names = [row.member_name_snapshot for row in receipts if row.state == "pending"]
    return render(
        request,
        "handoff/session_detail.html",
        {
            "service": _get_service(),
            "session": session,
            "receipts": receipts,
            "counts": counts,
            "pending_notice_text": _session_summary_text(session, pending_names),
            "is_session_open": session.status == "open",
        },
    )


@login_required
def session_edit(request, session_id):
    session = get_object_or_404(HandoffSession, id=session_id, owner=request.user)

    if request.method == "POST":
        form = HandoffSessionEditForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, "세션 정보를 수정했습니다.")
            return redirect("handoff:session_detail", session_id=session.id)
        for _, error_list in form.errors.items():
            for error in error_list:
                messages.error(request, error)
    else:
        form = HandoffSessionEditForm(instance=session)

    return render(
        request,
        "handoff/session_edit.html",
        {
            "service": _get_service(),
            "session": session,
            "form": form,
        },
    )


@login_required
@require_POST
def session_delete(request, session_id):
    session = get_object_or_404(HandoffSession, id=session_id, owner=request.user)
    title = session.title
    session.delete()
    messages.success(request, f"세션 '{title}'을 삭제했습니다.")
    return redirect("handoff:dashboard")


@login_required
@require_POST
def session_toggle_status(request, session_id):
    session = get_object_or_404(HandoffSession, id=session_id, owner=request.user)
    target = (request.POST.get("status") or "").strip()
    if target not in {"open", "closed"}:
        messages.error(request, "세션 상태 값이 올바르지 않습니다.")
        return redirect("handoff:session_detail", session_id=session.id)

    session.status = target
    session.closed_at = timezone.now() if target == "closed" else None
    session.save(update_fields=["status", "closed_at", "updated_at"])
    if target == "closed":
        messages.success(request, "세션을 마감했습니다.")
    else:
        messages.success(request, "세션을 다시 열었습니다.")
    return redirect("handoff:session_detail", session_id=session.id)


@login_required
@require_POST
def receipt_set_state(request, session_id, receipt_id):
    session = get_object_or_404(HandoffSession, id=session_id, owner=request.user)
    receipt = get_object_or_404(HandoffReceipt, id=receipt_id, session=session)

    state = (request.POST.get("state") or "").strip()
    if state not in {"pending", "received"}:
        if _wants_json(request):
            return JsonResponse({"success": False, "error": "잘못된 상태 값입니다."}, status=400)
        messages.error(request, "잘못된 상태 값입니다.")
        return redirect("handoff:session_detail", session_id=session.id)

    if session.status != "open":
        if _wants_json(request):
            return JsonResponse({"success": False, "error": "마감된 세션은 수정할 수 없습니다."}, status=400)
        messages.error(request, "마감된 세션은 수정할 수 없습니다.")
        return redirect("handoff:session_detail", session_id=session.id)

    if state == "received":
        handoff_type = (request.POST.get("handoff_type") or "self").strip()
        valid_types = {value for value, _ in HandoffReceipt.HANDOFF_TYPE_CHOICES}
        if handoff_type not in valid_types:
            handoff_type = "self"
        receipt.state = "received"
        receipt.received_at = timezone.now()
        receipt.received_by = request.user
        receipt.handoff_type = handoff_type
        receipt.memo = (request.POST.get("memo") or "").strip()[:200]
    else:
        receipt.state = "pending"
        receipt.received_at = None
        receipt.received_by = None
        receipt.handoff_type = "self"
        receipt.memo = ""

    receipt.save(
        update_fields=[
            "state",
            "received_at",
            "received_by",
            "handoff_type",
            "memo",
            "updated_at",
        ]
    )

    counts = _session_counts(session)
    if _wants_json(request):
        received_at_display = timezone.localtime(receipt.received_at).strftime("%m/%d %H:%M") if receipt.received_at else ""
        processed_by = receipt.received_by.username if receipt.received_by else ""
        return JsonResponse(
            {
                "success": True,
                "receipt": {
                    "id": receipt.id,
                    "state": receipt.state,
                    "state_label": receipt.get_state_display(),
                    "member_name": receipt.member_name_snapshot,
                    "received_at_display": received_at_display,
                    "processed_by": processed_by,
                    "memo": receipt.memo,
                    "handoff_type_label": receipt.get_handoff_type_display(),
                },
                "counts": counts,
            }
        )

    messages.success(request, f"{receipt.member_name_snapshot}: {receipt.get_state_display()} 처리했습니다.")
    return redirect("handoff:session_detail", session_id=session.id)


@login_required
def session_export_csv(request, session_id):
    session = get_object_or_404(HandoffSession, id=session_id, owner=request.user)
    receipts = session.receipts.select_related("received_by").order_by("member_order_snapshot", "id")
    filename = f"handoff_{session.created_at.strftime('%Y%m%d')}_{session.title[:30]}.csv"

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["이름", "상태", "수령 시각", "처리자", "수령 방식", "메모"])

    for row in receipts:
        received_at = timezone.localtime(row.received_at).strftime("%Y-%m-%d %H:%M") if row.received_at else ""
        processed_by = row.received_by.username if row.received_by else ""
        writer.writerow(
            [
                row.member_name_snapshot,
                row.get_state_display(),
                received_at,
                processed_by,
                row.get_handoff_type_display() if row.state == "received" else "",
                row.memo if row.state == "received" else "",
            ]
        )

    return response
