import csv
from typing import Iterable

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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


def _get_service():
    return (
        Product.objects.filter(launch_route_name="handoff:landing").first()
        or Product.objects.filter(title="배부 체크").first()
    )


def _wants_json(request):
    accept = request.headers.get("Accept", "")
    requested_with = request.headers.get("X-Requested-With", "")
    return requested_with == "XMLHttpRequest" or "application/json" in accept


def _normalize_bulk_names(raw_text: str) -> list[str]:
    names = []
    seen = set()
    for raw in (raw_text or "").splitlines():
        name = raw.strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


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


def landing(request):
    if request.user.is_authenticated:
        return redirect("handoff:dashboard")
    return render(request, "handoff/landing.html", {"service": _get_service()})


@login_required
def dashboard(request):
    owner = request.user
    groups = (
        HandoffRosterGroup.objects.filter(owner=owner)
        .annotate(
            active_member_count=Count("members", filter=Q(members__is_active=True)),
            total_member_count=Count("members"),
        )
        .order_by("-is_favorite", "name")
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
        },
    )


@login_required
@require_POST
def group_create(request):
    form = HandoffRosterGroupForm(request.POST)
    if not form.is_valid():
        for _, error_list in form.errors.items():
            for error in error_list:
                messages.error(request, error)
        return redirect("handoff:dashboard")

    group = form.save(commit=False)
    group.owner = request.user
    try:
        group.save()
    except IntegrityError:
        messages.error(request, "같은 이름의 명단이 이미 있습니다.")
        return redirect("handoff:dashboard")

    messages.success(request, f"명단 '{group.name}'을 만들었습니다.")
    return redirect("handoff:group_detail", group_id=group.id)


@login_required
def group_detail(request, group_id):
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
        },
    )


@login_required
@require_POST
def group_update(request, group_id):
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    form = HandoffRosterGroupForm(request.POST, instance=group)
    if not form.is_valid():
        for _, error_list in form.errors.items():
            for error in error_list:
                messages.error(request, error)
        return redirect("handoff:group_detail", group_id=group.id)

    try:
        form.save()
    except IntegrityError:
        messages.error(request, "같은 이름의 명단이 이미 있습니다.")
        return redirect("handoff:group_detail", group_id=group.id)

    messages.success(request, "명단 정보를 수정했습니다.")
    return redirect("handoff:group_detail", group_id=group.id)


@login_required
@require_POST
def group_delete(request, group_id):
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    name = group.name
    group.delete()
    messages.success(request, f"명단 '{name}'을 삭제했습니다.")
    return redirect("handoff:dashboard")


@login_required
@require_POST
def group_members_add(request, group_id):
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    form = HandoffMemberBulkAddForm(request.POST)
    if not form.is_valid():
        messages.error(request, "이름 목록을 확인해주세요.")
        return redirect("handoff:group_detail", group_id=group.id)

    names = _normalize_bulk_names(form.cleaned_data["names_text"])
    if not names:
        messages.error(request, "추가할 이름이 없습니다.")
        return redirect("handoff:group_detail", group_id=group.id)

    last_order = group.members.aggregate(max_order=Max("sort_order")).get("max_order") or 0
    payload = [
        HandoffRosterMember(
            group=group,
            display_name=name,
            sort_order=last_order + idx,
        )
        for idx, name in enumerate(names, start=1)
    ]
    HandoffRosterMember.objects.bulk_create(payload)
    messages.success(request, f"{len(payload)}명을 추가했습니다.")
    return redirect("handoff:group_detail", group_id=group.id)


@login_required
@require_POST
def group_member_update(request, group_id, member_id):
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    member = get_object_or_404(HandoffRosterMember, id=member_id, group=group)

    display_name = (request.POST.get("display_name") or "").strip()
    if not display_name:
        messages.error(request, "이름은 비울 수 없습니다.")
        return redirect("handoff:group_detail", group_id=group.id)

    member.display_name = display_name
    member.note = (request.POST.get("note") or "").strip()[:120]
    member.is_active = bool(request.POST.get("is_active"))
    member.save(update_fields=["display_name", "note", "is_active", "updated_at"])
    messages.success(request, f"{member.display_name} 정보가 저장되었습니다.")
    return redirect("handoff:group_detail", group_id=group.id)


@login_required
@require_POST
def group_member_delete(request, group_id, member_id):
    group = get_object_or_404(HandoffRosterGroup, id=group_id, owner=request.user)
    member = get_object_or_404(HandoffRosterMember, id=member_id, group=group)
    name = member.display_name
    member.delete()
    messages.success(request, f"{name}을(를) 삭제했습니다.")
    return redirect("handoff:group_detail", group_id=group.id)


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
