import logging
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import DocEditEvent, DocMembership, DocRevision
from .services import (
    accessible_rooms_queryset,
    assert_editor_membership,
    assert_owner_membership,
    broadcast_room_event,
    create_room_from_upload,
    create_snapshot,
    display_name_for_user,
    get_room_for_user,
    publish_revision,
    record_edit_events,
    room_payload_for_template,
    serialize_edit_event,
    save_room_revision,
    serialize_presence_list,
    serialize_revision,
)

logger = logging.getLogger(__name__)


def _is_mobile_user_agent(request):
    ua = str(request.META.get("HTTP_USER_AGENT", "") or "")
    lowered = ua.lower()
    return any(token in lowered for token in ("iphone", "ipad", "android", "mobile"))


def _is_desktop_chrome(request):
    ua = str(request.META.get("HTTP_USER_AGENT", "") or "")
    lowered = ua.lower()
    return "chrome" in lowered and "mobile" not in lowered and "edg/" not in lowered and "opr/" not in lowered


def _membership_for_room(room, user):
    for membership in room.workspace.memberships.all():
        if membership.user_id == getattr(user, "id", None) and membership.status == DocMembership.Status.ACTIVE:
            return membership
    return None


def _activity_label(dt):
    local_dt = timezone.localtime(dt)
    if local_dt.date() == timezone.localdate():
        return f"오늘 {local_dt:%H:%M}"
    return local_dt.strftime("%m.%d %H:%M")


def _teacher_name_label(user):
    name = display_name_for_user(user) or "선생님"
    return name if str(name).endswith("선생님") else f"{name} 선생님"


def _room_card(room, user):
    membership = _membership_for_room(room, user)
    revisions = list(room.revisions.all())
    current_revision = revisions[0] if revisions else None
    owner_name = _teacher_name_label(room.created_by)
    is_mine = room.created_by_id == getattr(user, "id", None)
    can_edit = is_mine or getattr(membership, "role", "") in {DocMembership.Role.OWNER, DocMembership.Role.EDITOR}
    return {
        "id": room.id,
        "title": room.title,
        "url": reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
        "open_label": "수정" if can_edit else "보기",
        "delete_label": "삭제" if is_mine else "제거",
        "delete_url": reverse("doccollab:remove_room", kwargs={"room_id": room.id}),
        "is_today": timezone.localtime(room.last_activity_at).date() == timezone.localdate(),
        "scope_label": "내 문서" if is_mine else "공유받은 문서",
        "role_label": membership.get_role_display() if membership else "보기",
        "owner_label": "내 문서" if is_mine else owner_name,
        "revision_label": f"r{current_revision.revision_number}" if current_revision else "원본",
        "activity_label": _activity_label(room.last_activity_at),
    }


def _dashboard_room_cards(rooms, user, limit=8):
    return [_room_card(room, user) for room in rooms[:limit]]


def _shared_members_for_room(room):
    connected_user_ids = {
        user_id
        for user_id in room.presences.filter(is_connected=True).values_list("user_id", flat=True)
        if user_id is not None
    }
    members = []
    for membership in room.workspace.memberships.select_related("user").order_by("created_at", "user__username"):
        member_user = membership.user
        is_owner = membership.role == DocMembership.Role.OWNER
        members.append(
            {
                "display_name": display_name_for_user(member_user) or member_user.username,
                "role_label": membership.get_role_display(),
                "is_owner": is_owner,
                "is_online": member_user.id in connected_user_ids,
                "status_label": "문서 주인" if is_owner else ("편집 가능" if membership.role == DocMembership.Role.EDITOR else "보기 전용"),
            }
        )
    return members


def _room_access_context(room, membership):
    if getattr(membership, "role", "") == DocMembership.Role.OWNER:
        return {
            "share_title": "내 문서",
            "share_copy": "바로 수정 가능",
            "access_label": "바로 수정 가능",
        }
    if getattr(membership, "role", "") == DocMembership.Role.EDITOR:
        return {
            "share_title": "공유받은 문서",
            "share_copy": "편집 가능",
            "access_label": "편집 가능",
        }
    return {
        "share_title": "공유받은 문서",
        "share_copy": "보기만 가능",
        "access_label": "보기만 가능",
    }


def _build_dashboard_context(request):
    rooms = accessible_rooms_queryset(request.user).order_by("-last_activity_at")
    my_rooms_qs = rooms.filter(created_by=request.user)
    shared_rooms_qs = rooms.exclude(created_by=request.user)
    today_rooms_qs = rooms.filter(last_activity_at__date=timezone.localdate())
    my_rooms = my_rooms_qs[:8]
    shared_rooms = shared_rooms_qs[:8]
    recent_revisions = DocRevision.objects.filter(room__in=rooms).select_related("room").order_by("-created_at")[:8]
    today_rooms = today_rooms_qs[:8]
    return {
        "service_title": "잇티한글",
        "my_rooms": my_rooms,
        "shared_rooms": shared_rooms,
        "recent_revisions": recent_revisions,
        "today_rooms": today_rooms,
        "my_room_cards": _dashboard_room_cards(my_rooms_qs, request.user),
        "shared_room_cards": _dashboard_room_cards(shared_rooms_qs, request.user, limit=6),
        "today_room_count": today_rooms_qs.count(),
        "shared_room_count": shared_rooms_qs.count(),
    }


def _load_room_or_404(request, room_id):
    room, membership = get_room_for_user(room_id, request.user)
    if room is None:
        raise Http404("문서를 찾을 수 없습니다.")
    return room, membership


@login_required
@require_GET
def main(request):
    return render(request, "doccollab/main.html", _build_dashboard_context(request))


@login_required
@require_POST
def create_room(request):
    try:
        room, _revision = create_room_from_upload(
            user=request.user,
            title=request.POST.get("title"),
            uploaded_file=request.FILES.get("source_file"),
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("doccollab:main")
    except Exception:
        logger.exception("doccollab create_room failed for user=%s", getattr(request.user, "id", None))
        messages.error(request, "문서를 여는 중 오류가 발생했습니다. 다시 시도해 주세요.")
        return redirect("doccollab:main")
    messages.success(request, "편집 화면을 열었습니다.")
    return redirect("doccollab:room_detail", room_id=room.id)


@login_required
@require_GET
def room_detail(request, room_id):
    room, membership = _load_room_or_404(request, room_id)
    editing_supported = _is_desktop_chrome(request)
    read_only_reason = ""
    if _is_mobile_user_agent(request):
        read_only_reason = "휴대폰에서는 보기만 가능합니다."
    elif not editing_supported:
        read_only_reason = "데스크톱 Chrome에서 편집 가능합니다."
    revisions = room.revisions.order_by("-revision_number")[:10]
    edit_history = DocEditEvent.objects.filter(room=room).order_by("-created_at")[:20]
    current_revision = revisions[0] if revisions else None
    published_revision = room.revisions.filter(is_published=True).order_by("-revision_number").first()
    access_context = _room_access_context(room, membership)
    context = {
        "room": room,
        "membership": membership,
        "revisions": revisions,
        "edit_history": edit_history,
        "current_revision": current_revision,
        "published_revision": published_revision,
        "participants": serialize_presence_list(room),
        "shared_members": _shared_members_for_room(room),
        "editing_supported": editing_supported,
        "read_only_reason": read_only_reason,
        "room_payload": room_payload_for_template(
            room=room,
            membership=membership,
            request=request,
            editing_supported=editing_supported,
        ),
        "can_edit": getattr(membership, "role", "") in {DocMembership.Role.OWNER, DocMembership.Role.EDITOR},
        "can_manage": getattr(membership, "role", "") == DocMembership.Role.OWNER,
        "display_name": display_name_for_user(request.user),
        "share_title": access_context["share_title"],
        "share_copy": access_context["share_copy"],
        "access_label": access_context["access_label"],
    }
    return render(request, "doccollab/room.html", context)


@login_required
@require_GET
def room_revisions(request, room_id):
    room, membership = _load_room_or_404(request, room_id)
    return render(
        request,
        "doccollab/revisions.html",
        {
            "room": room,
            "membership": membership,
            "revisions": room.revisions.order_by("-revision_number"),
        },
    )


@login_required
@require_POST
def remove_room(request, room_id):
    room, membership = _load_room_or_404(request, room_id)
    is_owner = getattr(membership, "role", "") == DocMembership.Role.OWNER and room.created_by_id == request.user.id

    if is_owner:
        room.status = room.Status.ARCHIVED
        room.save(update_fields=["status", "updated_at"])
        room.workspace.status = room.workspace.Status.ARCHIVED
        room.workspace.save(update_fields=["status", "updated_at"])
        room.workspace.memberships.update(status=DocMembership.Status.DISABLED)
        messages.success(request, "문서를 목록에서 지웠습니다.")
    else:
        if membership is None:
            raise Http404("문서를 찾을 수 없습니다.")
        membership.status = DocMembership.Status.DISABLED
        membership.save(update_fields=["status", "updated_at"])
        messages.success(request, "공유 문서를 목록에서 뺐습니다.")
    return redirect("doccollab:main")


@login_required
@require_GET
def download_revision(request, room_id, revision_id):
    room, _membership = _load_room_or_404(request, room_id)
    revision = get_object_or_404(room.revisions, id=revision_id)
    try:
        handle = revision.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("파일을 찾을 수 없습니다.") from exc
    return FileResponse(handle, as_attachment=True, filename=revision.original_name)


@login_required
@require_GET
def download_source(request, room_id):
    room, _membership = _load_room_or_404(request, room_id)
    try:
        handle = room.source_file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("파일을 찾을 수 없습니다.") from exc
    return FileResponse(handle, as_attachment=True, filename=room.source_name)


@login_required
@require_POST
def save_revision(request, room_id):
    room, membership = _load_room_or_404(request, room_id)
    assert_editor_membership(membership)
    uploaded_file = request.FILES.get("export_file")
    if uploaded_file is None:
        return JsonResponse({"message": "저장할 파일이 없습니다."}, status=400)
    snapshot_json = request.POST.get("snapshot_json")
    note = request.POST.get("note") or "문서 저장"
    try:
        revision = save_room_revision(
            room=room,
            user=request.user,
            uploaded_file=uploaded_file,
            export_format=DocRevision.ExportFormat.HWP_EXPORT,
            note=note,
        )
        if snapshot_json:
            create_snapshot(
                room=room,
                created_by=request.user,
                state_json=json.loads(snapshot_json),
                snapshot_kind="manual",
                revision=revision,
            )
    except ValidationError as exc:
        return JsonResponse({"message": str(exc)}, status=400)
    except Exception:
        logger.exception(
            "doccollab save_revision failed for room=%s user=%s",
            room.id,
            getattr(request.user, "id", None),
        )
        return JsonResponse({"message": "저장 중 오류가 발생했습니다. 다시 시도해 주세요."}, status=500)
    edit_events = record_edit_events(
        room=room,
        user=request.user,
        display_name=display_name_for_user(request.user),
        commands=[
            {
                "id": f"save:{revision.id}",
                "type": "save_revision",
                "revision_number": revision.revision_number,
                "export_format": revision.export_format,
            }
        ],
    )
    serialized_edit_events = [serialize_edit_event(event) for event in edit_events]
    broadcast_room_event(
        room,
        "revision.saved",
        {"revision": serialize_revision(revision), "edit_events": serialized_edit_events},
    )
    return JsonResponse(
        {
            "revision": serialize_revision(revision),
            "edit_events": serialized_edit_events,
            "download_url": reverse(
                "doccollab:download_revision",
                kwargs={"room_id": room.id, "revision_id": revision.id},
            ),
        }
    )


@login_required
@require_POST
def publish_revision_view(request, room_id, revision_id):
    room, membership = _load_room_or_404(request, room_id)
    assert_owner_membership(membership)
    revision = get_object_or_404(room.revisions, id=revision_id)
    publish_revision(room, revision)
    broadcast_room_event(
        room,
        "revision.saved",
        {"revision": serialize_revision(revision), "published": True},
    )
    messages.success(request, f"r{revision.revision_number}을 배포본으로 지정했습니다.")
    return redirect("doccollab:room_revisions", room_id=room.id)


@login_required
@require_POST
def create_snapshot_view(request, room_id):
    room, membership = _load_room_or_404(request, room_id)
    assert_editor_membership(membership)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"message": "스냅샷 형식이 올바르지 않습니다."}, status=400)
    snapshot = create_snapshot(
        room=room,
        created_by=request.user,
        state_json=payload,
        snapshot_kind="auto",
    )
    return JsonResponse({"snapshot_id": str(snapshot.id), "created_at": snapshot.created_at.isoformat()})


@login_required
@require_POST
def add_member(request, room_id):
    room, membership = _load_room_or_404(request, room_id)
    assert_owner_membership(membership)
    username = str(request.POST.get("username") or "").strip()
    role = str(request.POST.get("role") or DocMembership.Role.VIEWER).strip()
    if role not in {choice for choice, _label in DocMembership.Role.choices}:
        messages.error(request, "권한이 올바르지 않습니다.")
        return redirect("doccollab:room_detail", room_id=room.id)
    target_user = User.objects.filter(username=username).first()
    if target_user is None:
        messages.error(request, "사용자를 찾지 못했습니다.")
        return redirect("doccollab:room_detail", room_id=room.id)
    DocMembership.objects.update_or_create(
        workspace=room.workspace,
        user=target_user,
        defaults={
            "role": role,
            "status": DocMembership.Status.ACTIVE,
            "invited_by": request.user,
        },
    )
    messages.success(request, f"{target_user.username} 님을 추가했습니다.")
    return redirect("doccollab:room_detail", room_id=room.id)
