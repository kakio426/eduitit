import json
import logging
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import F
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import DocMembership, DocRevision, DocRoom, DocWorksheet
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
    save_room_revision,
    serialize_edit_event,
    serialize_edit_history,
    serialize_presence_list,
    serialize_revision,
)
from .worksheet_llm import WorksheetLlmError
from .worksheet_hwp_builder import WorksheetBuildError
from .worksheet_service import (
    clone_published_worksheet,
    create_generated_worksheet_room,
    generate_single_page_worksheet,
    owned_worksheet_queryset,
    public_worksheet_queryset,
    publish_generated_worksheet,
    release_worksheet_daily_limit,
    reserve_worksheet_daily_limit,
    worksheet_daily_limit_message,
    worksheet_daily_limit_per_user,
    worksheet_daily_limit_used,
    worksheet_is_publicly_accessible,
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


def _is_json_request(request):
    accept = str(request.headers.get("Accept", "") or "")
    requested_with = str(request.headers.get("X-Requested-With", "") or "")
    content_type = str(request.content_type or "")
    return (
        "application/json" in accept
        or requested_with == "XMLHttpRequest"
        or "application/json" in content_type
    )


def _validation_message(exc):
    messages = list(getattr(exc, "messages", []) or [])
    if messages:
        return str(messages[0])
    return str(exc)


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
    worksheet = getattr(room, "worksheet", None)
    if membership is None and worksheet and worksheet_is_publicly_accessible(room):
        return {
            "share_title": "공개 학습지",
            "share_copy": "다운로드 가능",
            "access_label": "공개",
        }
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


def _worksheet_status_label(worksheet):
    if worksheet.bootstrap_status != DocWorksheet.BootstrapStatus.READY:
        return "생성 중"
    if worksheet.is_library_published:
        return "공개"
    return "비공개"


def _worksheet_download_url(worksheet, *, public_only=False):
    if public_only:
        revision = worksheet.room.revisions.filter(is_published=True).order_by("-revision_number").first()
    else:
        revision = worksheet.room.revisions.order_by("-revision_number").first()
    if revision is None:
        return ""
    return reverse("doccollab:download_revision", kwargs={"room_id": worksheet.room_id, "revision_id": revision.id})


def _worksheet_card(worksheet, *, public_card=False):
    room = worksheet.room
    published_revision = room.revisions.filter(is_published=True).order_by("-revision_number").first()
    current_revision = room.revisions.order_by("-revision_number").first()
    visible_revision = published_revision if public_card and published_revision else current_revision
    return {
        "id": room.id,
        "title": room.title,
        "topic": worksheet.topic,
        "summary_text": worksheet.summary_text,
        "url": reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
        "status_label": _worksheet_status_label(worksheet),
        "activity_label": _activity_label(room.last_activity_at),
        "owner_label": _teacher_name_label(room.created_by),
        "download_url": _worksheet_download_url(worksheet, public_only=public_card),
        "clone_url": reverse("doccollab:worksheet_clone", kwargs={"room_id": room.id}),
        "publish_url": reverse("doccollab:worksheet_publish", kwargs={"room_id": room.id}),
        "delete_url": reverse("doccollab:remove_room", kwargs={"room_id": room.id}),
        "is_public": worksheet.is_library_published,
        "is_ready": worksheet.bootstrap_status == DocWorksheet.BootstrapStatus.READY,
        "revision_label": f"r{visible_revision.revision_number}" if visible_revision else "초안",
    }


def _build_dashboard_context(request):
    rooms = accessible_rooms_queryset(request.user).order_by("-last_activity_at")
    document_rooms_qs = rooms.exclude(origin_kind=DocRoom.OriginKind.GENERATED_WORKSHEET)
    my_rooms_qs = document_rooms_qs.filter(created_by=request.user)
    shared_rooms_qs = document_rooms_qs.exclude(created_by=request.user)
    today_rooms_qs = document_rooms_qs.filter(last_activity_at__date=timezone.localdate())
    my_rooms = my_rooms_qs[:8]
    shared_rooms = shared_rooms_qs[:8]
    recent_revisions = DocRevision.objects.filter(room__in=rooms).select_related("room").order_by("-created_at")[:8]
    today_rooms = today_rooms_qs[:8]
    my_worksheets = owned_worksheet_queryset(request.user)[:8]
    public_worksheets = public_worksheet_queryset()[:8]
    worksheet_creation_enabled = True
    worksheet_creation_reason = "생성 가능 · 편집은 데스크톱 Chrome"
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
        "my_worksheet_cards": [_worksheet_card(item) for item in my_worksheets],
        "public_worksheet_cards": [_worksheet_card(item, public_card=True) for item in public_worksheets],
        "worksheet_daily_used": worksheet_daily_limit_used(request.user.id),
        "worksheet_daily_limit": worksheet_daily_limit_per_user(),
        "worksheet_creation_enabled": worksheet_creation_enabled,
        "worksheet_creation_reason": worksheet_creation_reason,
    }


def _load_room_or_404(request, room_id, *, allow_public_library=False):
    room, membership = get_room_for_user(room_id, request.user)
    if room is None and allow_public_library:
        room = (
            DocRoom.objects.select_related("workspace", "created_by", "worksheet")
            .prefetch_related("workspace__memberships__user", "revisions")
            .filter(id=room_id)
            .first()
        )
        if room is not None and not worksheet_is_publicly_accessible(room):
            room = None
        membership = None
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
        messages.error(request, _validation_message(exc))
        return redirect("doccollab:main")
    except Exception:
        logger.exception("doccollab create_room failed for user=%s", getattr(request.user, "id", None))
        messages.error(request, "문서를 여는 중 오류가 발생했습니다. 다시 시도해 주세요.")
        return redirect("doccollab:main")
    messages.success(request, "편집 화면을 열었습니다.")
    return redirect("doccollab:room_detail", room_id=room.id)


@login_required
@require_POST
def generate_worksheet(request):
    if not reserve_worksheet_daily_limit(request.user.id):
        message_text = worksheet_daily_limit_message()
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=429)
        messages.error(request, message_text)
        return redirect("doccollab:main")

    topic = str(request.POST.get("topic") or "").strip()
    try:
        room, _worksheet, revision = create_generated_worksheet_room(user=request.user, topic=topic)
    except ValidationError as exc:
        release_worksheet_daily_limit(request.user.id)
        if _is_json_request(request):
            return JsonResponse({"message": _validation_message(exc)}, status=400)
        messages.error(request, _validation_message(exc))
        return redirect("doccollab:main")
    except WorksheetLlmError as exc:
        release_worksheet_daily_limit(request.user.id)
        logger.warning(
            "doccollab generate_worksheet llm failed user=%s error=%s",
            getattr(request.user, "id", None),
            exc,
        )
        message_text = "학습지 초안을 만드는 중 잠시 멈췄어요. 다시 시도해 주세요."
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=503)
        messages.error(request, message_text)
        return redirect("doccollab:main")
    except WorksheetBuildError as exc:
        release_worksheet_daily_limit(request.user.id)
        logger.warning(
            "doccollab generate_worksheet builder failed user=%s error=%s",
            getattr(request.user, "id", None),
            exc,
        )
        message_text = "학습지 HWP를 만드는 중 잠시 멈췄어요. 다시 시도해 주세요."
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=503)
        messages.error(request, message_text)
        return redirect("doccollab:main")
    except Exception:
        release_worksheet_daily_limit(request.user.id)
        logger.exception("doccollab generate_worksheet failed user=%s", getattr(request.user, "id", None))
        message_text = "학습지 초안을 만드는 중 오류가 발생했습니다. 다시 시도해 주세요."
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=500)
        messages.error(request, message_text)
        return redirect("doccollab:main")

    daily_used = worksheet_daily_limit_used(request.user.id)
    if _is_json_request(request):
        return JsonResponse(
            {
                "room_id": str(room.id),
                "room_url": reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
                "revision_id": str(revision.id),
                "download_url": reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": revision.id}),
                "daily_used": daily_used,
                "daily_limit": worksheet_daily_limit_per_user(),
            }
        )
    messages.success(request, "학습지 초안을 만들었어요.")
    return redirect("doccollab:room_detail", room_id=room.id)


@login_required
@require_POST
def generate_worksheet_file(request):
    if not reserve_worksheet_daily_limit(request.user.id):
        message_text = worksheet_daily_limit_message()
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=429)
        messages.error(request, message_text)
        return redirect("doccollab:main")

    topic = str(request.POST.get("topic") or "").strip()
    try:
        generated = generate_single_page_worksheet(topic=topic)
    except ValidationError as exc:
        release_worksheet_daily_limit(request.user.id)
        if _is_json_request(request):
            return JsonResponse({"message": _validation_message(exc)}, status=400)
        messages.error(request, _validation_message(exc))
        return redirect("doccollab:main")
    except WorksheetLlmError as exc:
        release_worksheet_daily_limit(request.user.id)
        logger.warning(
            "doccollab generate_worksheet_file llm failed user=%s error=%s",
            getattr(request.user, "id", None),
            exc,
        )
        message_text = "학습지 초안을 만드는 중 잠시 멈췄어요. 다시 시도해 주세요."
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=503)
        messages.error(request, message_text)
        return redirect("doccollab:main")
    except WorksheetBuildError as exc:
        release_worksheet_daily_limit(request.user.id)
        logger.warning(
            "doccollab generate_worksheet_file builder failed user=%s error=%s",
            getattr(request.user, "id", None),
            exc,
        )
        message_text = "학습지 HWP를 만드는 중 잠시 멈췄어요. 다시 시도해 주세요."
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=503)
        messages.error(request, message_text)
        return redirect("doccollab:main")
    except Exception:
        release_worksheet_daily_limit(request.user.id)
        logger.exception("doccollab generate_worksheet_file failed user=%s", getattr(request.user, "id", None))
        message_text = "학습지 HWP를 만드는 중 오류가 발생했습니다. 다시 시도해 주세요."
        if _is_json_request(request):
            return JsonResponse({"message": message_text}, status=500)
        messages.error(request, message_text)
        return redirect("doccollab:main")

    response = FileResponse(
        BytesIO(generated["hwp_bytes"]),
        as_attachment=True,
        filename=str(generated.get("file_name") or "worksheet.hwp"),
        content_type="application/x-hwp",
    )
    response["X-Worksheet-Daily-Used"] = str(worksheet_daily_limit_used(request.user.id))
    response["X-Worksheet-Daily-Limit"] = str(worksheet_daily_limit_per_user())
    response["X-Worksheet-Layout-Profile"] = str(generated.get("used_profile") or "")
    return response


@login_required
@require_GET
def room_detail(request, room_id):
    room, membership = _load_room_or_404(request, room_id, allow_public_library=True)
    worksheet = getattr(room, "worksheet", None)
    public_library_view = bool(
        worksheet
        and membership is None
        and worksheet_is_publicly_accessible(room)
        and room.created_by_id != request.user.id
    )
    if public_library_view and worksheet is not None:
        DocWorksheet.objects.filter(id=worksheet.id).update(view_count=F("view_count") + 1)
        worksheet.refresh_from_db(fields=["view_count"])
    editing_supported = _is_desktop_chrome(request)
    read_only_reason = ""
    if _is_mobile_user_agent(request):
        read_only_reason = "휴대폰에서는 보기만 가능합니다."
    elif not editing_supported:
        read_only_reason = "데스크톱 Chrome에서 편집 가능합니다."
    revisions = (
        room.revisions.filter(is_published=True).order_by("-revision_number")[:10]
        if public_library_view
        else room.revisions.order_by("-revision_number")[:10]
    )
    edit_history = serialize_edit_history(room, limit=10)
    latest_revision = room.revisions.order_by("-revision_number").first()
    published_revision = room.revisions.filter(is_published=True).order_by("-revision_number").first()
    current_revision = published_revision if public_library_view and published_revision else latest_revision
    access_context = _room_access_context(room, membership)
    source_download_url = reverse("doccollab:download_source", kwargs={"room_id": room.id}) if room.source_file else ""
    fallback_download_url = (
        reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": current_revision.id})
        if current_revision
        else source_download_url
    )
    context = {
        "room": room,
        "worksheet": worksheet,
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
        "is_generated_worksheet": room.origin_kind == DocRoom.OriginKind.GENERATED_WORKSHEET,
        "public_library_view": public_library_view,
        "source_download_url": source_download_url,
        "fallback_download_url": fallback_download_url,
        "worksheet_publish_url": reverse("doccollab:worksheet_publish", kwargs={"room_id": room.id}) if worksheet else "",
        "worksheet_clone_url": reverse("doccollab:worksheet_clone", kwargs={"room_id": room.id}) if worksheet else "",
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
    room, membership = _load_room_or_404(request, room_id, allow_public_library=True)
    revision = get_object_or_404(room.revisions, id=revision_id)
    if membership is None and not revision.is_published:
        raise Http404("파일을 찾을 수 없습니다.")
    try:
        handle = revision.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("파일을 찾을 수 없습니다.") from exc
    return FileResponse(handle, as_attachment=True, filename=revision.original_name)


@login_required
@require_GET
def download_source(request, room_id):
    room, _membership = _load_room_or_404(request, room_id)
    if not room.source_file:
        raise Http404("파일을 찾을 수 없습니다.")
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
        return JsonResponse({"message": _validation_message(exc)}, status=400)
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
    serialized_edit_history = serialize_edit_history(room, limit=10)
    broadcast_room_event(
        room,
        "revision.saved",
        {
            "revision": serialize_revision(revision),
            "edit_events": serialized_edit_events,
            "edit_history": serialized_edit_history,
        },
    )
    return JsonResponse(
        {
            "revision": serialize_revision(revision),
            "edit_events": serialized_edit_events,
            "edit_history": serialized_edit_history,
            "download_url": reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": revision.id}),
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


@login_required
@require_POST
def worksheet_publish(request, room_id):
    room, membership = _load_room_or_404(request, room_id)
    assert_owner_membership(membership)
    worksheet = getattr(room, "worksheet", None)
    if worksheet is None or room.origin_kind != DocRoom.OriginKind.GENERATED_WORKSHEET:
        raise Http404("학습지를 찾을 수 없습니다.")
    try:
        publish_generated_worksheet(worksheet=worksheet)
    except ValidationError as exc:
        if _is_json_request(request):
            return JsonResponse({"message": str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect("doccollab:room_detail", room_id=room.id)
    if _is_json_request(request):
        return JsonResponse({"published": True})
    messages.success(request, "공개 학습지로 올렸습니다.")
    return redirect("doccollab:room_detail", room_id=room.id)


@login_required
@require_POST
def worksheet_clone(request, room_id):
    room, _membership = _load_room_or_404(request, room_id, allow_public_library=True)
    worksheet = getattr(room, "worksheet", None)
    if worksheet is None:
        raise Http404("학습지를 찾을 수 없습니다.")
    try:
        cloned_room, _cloned_worksheet, _revision = clone_published_worksheet(worksheet=worksheet, user=request.user)
    except ValidationError as exc:
        if _is_json_request(request):
            return JsonResponse({"message": str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect("doccollab:main")
    if _is_json_request(request):
        return JsonResponse(
            {
                "room_id": str(cloned_room.id),
                "room_url": reverse("doccollab:room_detail", kwargs={"room_id": cloned_room.id}),
            }
        )
    messages.success(request, "내 학습지로 가져왔습니다.")
    return redirect("doccollab:room_detail", room_id=cloned_room.id)


@login_required
@require_GET
def worksheet_library(request):
    return render(
        request,
        "doccollab/worksheet_library.html",
        {
            "service_title": "잇티한글",
            "worksheet_daily_used": worksheet_daily_limit_used(request.user.id),
            "worksheet_daily_limit": worksheet_daily_limit_per_user(),
            "public_worksheet_cards": [_worksheet_card(item, public_card=True) for item in public_worksheet_queryset()],
        },
    )
