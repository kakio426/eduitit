import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from classcalendar.models import CalendarEvent, EventPageBlock
from core.active_classroom import get_active_classroom_for_request

from .models import CalendarSuggestion, MessageReaction, RoomMessage, SchoolMembership, SharedAsset, WorkspaceInvite
from .services import (
    MembershipRequiredError,
    ValidationError,
    accept_invite,
    approve_membership,
    build_notification_summary,
    build_room_summary,
    build_workspace_dashboard,
    create_invite,
    create_room_message,
    create_workspace_for_user,
    get_default_room,
    get_default_workspace_for_user,
    get_membership,
    get_or_create_dm_room,
    get_room_for_user,
    get_service_product,
    get_user_memberships,
    mark_room_read,
    membership_can_manage_workspace,
    membership_can_post_notice,
    school_name_suggestion_for_user,
    search_workspace,
    search_workspace_assets,
    serialize_asset,
    serialize_calendar_suggestion,
    serialize_message,
    toggle_ack_reaction,
    update_user_asset_category,
    user_can_download_asset,
)


logger = logging.getLogger(__name__)

SERVICE_PUBLIC_NAME = "우리끼리 채팅방"
SERVICE_UNAVAILABLE_MESSAGE = "지금은 채팅방을 준비하는 중입니다. 잠시 후 다시 열어 주세요."


def _json_error(message, *, status=400, code="validation_error", extra=None):
    payload = {"status": "error", "code": code, "error": message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")


def _pending_workspace_memberships(user):
    return (
        get_user_memberships(user, statuses=[SchoolMembership.Status.PENDING])
        .select_related("workspace")
        .order_by("workspace__name")
    )


def _resolve_workspace(request):
    workspace_id = request.GET.get("workspace") or request.POST.get("workspace_id")
    active_memberships = get_user_memberships(request.user, statuses=[SchoolMembership.Status.ACTIVE]).select_related("workspace")
    if workspace_id:
        membership = active_memberships.filter(workspace_id=workspace_id).first()
        if membership:
            return membership.workspace
    return get_default_workspace_for_user(request.user, create=False)


def _room_message_queryset(room):
    return (
        room.messages.select_related("sender", "sender_membership", "parent_message")
        .prefetch_related(
            "asset_links__asset__blob",
            "reactions",
            "replies__asset_links__asset__blob",
            "replies__reactions",
        )
        .order_by("created_at", "id")
    )


def _build_room_items(room, user):
    top_messages = _room_message_queryset(room).filter(parent_message__isnull=True)
    items = []
    for message in top_messages:
        item = serialize_message(message, user=user)
        item["replies"] = [serialize_message(reply, user=user) for reply in message.replies.all()]
        items.append(item)
    return items


def _build_search_display(search_results, user):
    if not search_results:
        return None
    message_cards = []
    for message in search_results["messages_page"].object_list if search_results["messages_page"] else []:
        message_cards.append(
            {
                "room_name": message.room.name,
                "body": message.body,
                "url": f"{reverse('schoolcomm:room_detail', kwargs={'room_id': message.room.id})}#message-{message.id}",
            }
        )

    asset_cards = []
    for asset in search_results["assets_page"].object_list if search_results["assets_page"] else []:
        asset_cards.append(serialize_asset(asset, user=user))

    messages_page = search_results["messages_page"]
    assets_page = search_results["assets_page"]
    has_previous = bool((messages_page and messages_page.has_previous()) or (assets_page and assets_page.has_previous()))
    has_next = bool((messages_page and messages_page.has_next()) or (assets_page and assets_page.has_next()))
    current_page = messages_page.number if messages_page else (assets_page.number if assets_page else 1)
    return {
        "query": search_results["query"],
        "room_matches": [build_room_summary(room, user=user) for room in search_results["room_matches"]],
        "message_cards": message_cards,
        "asset_cards": asset_cards,
        "current_page": current_page,
        "has_previous": has_previous,
        "has_next": has_next,
        "previous_page": current_page - 1 if has_previous else None,
        "next_page": current_page + 1 if has_next else None,
    }


def _build_ws_path(path):
    return f"/{path.lstrip('/')}"


def _service_unavailable_context():
    return {
        "page_title": SERVICE_PUBLIC_NAME,
        "service_unavailable": True,
        "service_unavailable_message": SERVICE_UNAVAILABLE_MESSAGE,
        "user_ws_url": "",
        "current_query": "",
    }


def _json_service_unavailable():
    return _json_error(
        SERVICE_UNAVAILABLE_MESSAGE,
        status=503,
        code="service_unavailable",
    )


@login_required
@require_GET
def main(request):
    try:
        workspace = _resolve_workspace(request)
        active_memberships = get_user_memberships(request.user, statuses=[SchoolMembership.Status.ACTIVE]).select_related("workspace")
        pending_memberships = _pending_workspace_memberships(request.user)
        search_results = None
        dashboard = None
        latest_invite_url = request.session.pop("schoolcomm_latest_invite_url", "")
        if workspace is not None:
            dashboard = build_workspace_dashboard(workspace, request.user)
            if (request.GET.get("q") or "").strip():
                search_results = search_workspace(
                    workspace,
                    request.user,
                    request.GET.get("q"),
                    page_number=request.GET.get("page") or 1,
                )
                search_results = _build_search_display(search_results, request.user)

        context = {
            "page_title": SERVICE_PUBLIC_NAME,
            "service_product": get_service_product(),
            "workspace": workspace,
            "workspace_name_suggestion": school_name_suggestion_for_user(request.user),
            "active_memberships": active_memberships,
            "pending_memberships_only": pending_memberships,
            "dashboard": dashboard,
            "search_results": search_results,
            "latest_invite_url": latest_invite_url,
            "user_ws_url": _build_ws_path("schoolcomm/ws/users/me/"),
            "current_query": request.GET.get("q", ""),
        }
        return render(request, "schoolcomm/main.html", context)
    except DatabaseError:
        logger.exception("[schoolcomm] main unavailable")
        return render(request, "schoolcomm/main.html", _service_unavailable_context())


@login_required
@require_POST
def create_workspace(request):
    try:
        name = (request.POST.get("name") or "").strip()
        academic_year = (request.POST.get("academic_year") or "").strip()
        workspace, _ = create_workspace_for_user(request.user, name=name, academic_year=academic_year)
        messages.success(request, "우리끼리 채팅방을 시작했어요.")
        return redirect(f"{reverse('schoolcomm:main')}?workspace={workspace.id}")
    except DatabaseError:
        logger.exception("[schoolcomm] create_workspace unavailable")
        messages.error(request, SERVICE_UNAVAILABLE_MESSAGE)
        return redirect(reverse("schoolcomm:main"))


@login_required
def invite_accept(request, token):
    try:
        invite = get_object_or_404(WorkspaceInvite.objects.select_related("workspace", "invited_by"), token=token)
        membership = get_membership(invite.workspace, request.user, include_pending=True)
        accepted_membership = None
        if request.method == "POST":
            try:
                accepted_membership = accept_invite(invite, request.user)
                messages.success(request, "초대를 수락했어요. 승인 후 입장할 수 있습니다.")
            except ValidationError as exc:
                messages.error(request, str(exc))
        context = {
            "invite": invite,
            "membership": accepted_membership or membership,
            "page_title": "초대 수락",
        }
        return render(request, "schoolcomm/invite_accept.html", context)
    except DatabaseError:
        logger.exception("[schoolcomm] invite_accept unavailable")
        messages.error(request, SERVICE_UNAVAILABLE_MESSAGE)
        return redirect(reverse("schoolcomm:main"))


@login_required
@require_GET
def room_detail(request, room_id):
    try:
        room, membership = get_room_for_user(room_id, request.user)
        if room is None:
            raise Http404("방을 찾을 수 없습니다.")
        if membership is None:
            return HttpResponseForbidden("이 방에 접근할 수 없습니다.")

        latest_message = room.messages.order_by("-created_at", "-id").first()
        mark_room_read(request.user, room, latest_message=latest_message)
        room_items = _build_room_items(room, request.user)
        workspace = room.workspace
        dashboard = build_workspace_dashboard(workspace, request.user)
        context = {
            "page_title": room.name,
            "room": room,
            "membership": membership,
            "workspace": workspace,
            "room_items": room_items,
            "dashboard": dashboard,
            "can_post_top_level": membership_can_post_notice(membership) or room.room_kind != room.RoomKind.NOTICE,
            "room_ws_url": _build_ws_path(f"schoolcomm/ws/rooms/{room.id}/"),
            "room_refresh_url": f"{reverse('schoolcomm:room_detail', kwargs={'room_id': room.id})}?fragment=content",
            "user_ws_url": _build_ws_path("schoolcomm/ws/users/me/"),
        }
        if request.GET.get("fragment") == "content":
            return render(request, "schoolcomm/partials/room_content.html", context)
        return render(request, "schoolcomm/room_detail.html", context)
    except DatabaseError:
        logger.exception("[schoolcomm] room_detail unavailable")
        if request.GET.get("fragment") == "content":
            return render(
                request,
                "schoolcomm/partials/room_unavailable.html",
                {"service_unavailable_message": SERVICE_UNAVAILABLE_MESSAGE},
            )
        messages.error(request, SERVICE_UNAVAILABLE_MESSAGE)
        return redirect(reverse("schoolcomm:main"))


@login_required
@require_POST
def api_create_invite(request):
    try:
        workspace = _resolve_workspace(request)
        if workspace is None:
            return _json_error("먼저 채팅방을 만들어 주세요.")
        role = (request.POST.get("role") or SchoolMembership.Role.MEMBER).strip()
        email = (request.POST.get("email") or "").strip()
        try:
            invite = create_invite(workspace, inviter=request.user, email=email, role=role)
        except MembershipRequiredError as exc:
            return _json_error(str(exc), status=403, code="permission_denied")
        invite_url = request.build_absolute_uri(reverse("schoolcomm:invite_accept", kwargs={"token": invite.token}))
        if not _wants_json(request):
            request.session["schoolcomm_latest_invite_url"] = invite_url
            messages.success(request, "초대 링크를 만들었어요.")
            return redirect(f"{reverse('schoolcomm:main')}?workspace={workspace.id}")
        return JsonResponse(
            {
                "status": "success",
                "invite": {
                    "id": str(invite.id),
                    "url": invite_url,
                    "role": invite.role,
                    "email": invite.email,
                },
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_create_invite unavailable")
        return _json_service_unavailable()


@login_required
@require_POST
def api_approve_membership(request, membership_id):
    try:
        membership = get_object_or_404(SchoolMembership.objects.select_related("workspace", "user"), id=membership_id)
        try:
            approve_membership(membership, request.user)
        except MembershipRequiredError as exc:
            return _json_error(str(exc), status=403, code="permission_denied")
        if not _wants_json(request):
            messages.success(request, f"{membership.user.username}님을 승인했어요.")
            return redirect(f"{reverse('schoolcomm:main')}?workspace={membership.workspace_id}")
        return JsonResponse(
            {
                "status": "success",
                "membership": {
                    "id": str(membership.id),
                    "user": membership.user.username,
                    "status": membership.status,
                },
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_approve_membership unavailable")
        return _json_service_unavailable()


@login_required
def api_dms(request):
    try:
        workspace = _resolve_workspace(request)
        if workspace is None:
            return _json_error("먼저 채팅방을 선택해 주세요.")
        membership = get_membership(workspace, request.user)
        if membership is None:
            return _json_error("채팅방 멤버만 사용할 수 있습니다.", status=403, code="permission_denied")

        if request.method == "GET":
            rooms = (
                workspace.rooms.filter(
                    room_kind__in=[workspace.rooms.model.RoomKind.DM, workspace.rooms.model.RoomKind.GROUP_DM],
                    participants__membership=membership,
                )
                .distinct()
                .order_by("-last_message_at", "name")
            )
            return JsonResponse({"status": "success", "rooms": [build_room_summary(room, user=request.user) for room in rooms]})

        raw_ids = request.POST.getlist("user_ids") or (request.POST.get("user_ids") or "").split(",")
        user_ids = {str(value).strip() for value in raw_ids if str(value).strip()}
        candidate_memberships = list(
            workspace.memberships.select_related("user")
            .filter(status=SchoolMembership.Status.ACTIVE, user_id__in=user_ids)
        )
        candidate_memberships.append(membership)
        try:
            room = get_or_create_dm_room(
                workspace,
                candidate_memberships,
                created_by=request.user,
                name=(request.POST.get("name") or "").strip(),
            )
        except ValidationError as exc:
            return _json_error(str(exc))
        if not _wants_json(request):
            return redirect(reverse("schoolcomm:room_detail", kwargs={"room_id": room.id}))
        return JsonResponse({"status": "success", "room": build_room_summary(room, user=request.user)})
    except DatabaseError:
        logger.exception("[schoolcomm] api_dms unavailable")
        return _json_service_unavailable()


@login_required
def api_room_messages(request, room_id):
    try:
        room, membership = get_room_for_user(room_id, request.user)
        if room is None:
            raise Http404("방을 찾을 수 없습니다.")
        if membership is None:
            return _json_error("이 방에 접근할 수 없습니다.", status=403, code="permission_denied")

        if request.method == "GET":
            latest_message = room.messages.order_by("-created_at", "-id").first()
            mark_room_read(request.user, room, latest_message=latest_message)
            messages_payload = _build_room_items(room, request.user)
            return JsonResponse({"status": "success", "messages": messages_payload})

        parent_message = None
        parent_message_id = (request.POST.get("parent_message_id") or "").strip()
        if parent_message_id:
            parent_message = get_object_or_404(RoomMessage, id=parent_message_id, room=room, parent_message__isnull=True)
        uploads = request.FILES.getlist("files")
        text = (request.POST.get("text") or request.POST.get("body") or "").strip()
        try:
            message = create_room_message(room, membership, text=text, parent_message=parent_message, uploads=uploads)
        except ValidationError as exc:
            return _json_error(str(exc))
        payload = serialize_message(message, user=request.user)
        if not _wants_json(request):
            anchor = f"#message-{parent_message.id if parent_message else message.id}"
            return redirect(f"{reverse('schoolcomm:room_detail', kwargs={'room_id': room.id})}{anchor}")
        return JsonResponse(
            {
                "status": "success",
                "message": payload,
                "session": {"current_text": message.body},
            },
            status=201,
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_room_messages unavailable")
        return _json_service_unavailable()


@login_required
@require_GET
def api_message_thread(request, message_id):
    try:
        message = get_object_or_404(RoomMessage.objects.select_related("room"), id=message_id)
        room, membership = get_room_for_user(message.room_id, request.user)
        if room is None or membership is None:
            return _json_error("이 스레드에 접근할 수 없습니다.", status=403, code="permission_denied")
        thread_messages = [serialize_message(reply, user=request.user) for reply in message.replies.all()]
        return JsonResponse({"status": "success", "message": serialize_message(message, user=request.user), "replies": thread_messages})
    except DatabaseError:
        logger.exception("[schoolcomm] api_message_thread unavailable")
        return _json_service_unavailable()


@login_required
@require_POST
def api_message_reactions(request, message_id):
    try:
        message = get_object_or_404(RoomMessage.objects.select_related("room"), id=message_id)
        room, membership = get_room_for_user(message.room_id, request.user)
        if room is None or membership is None:
            return _json_error("이 메시지에 반응할 수 없습니다.", status=403, code="permission_denied")
        is_active = toggle_ack_reaction(message, request.user)
        ack_count = message.reactions.filter(reaction_type=MessageReaction.ReactionType.ACK).count()
        if not _wants_json(request):
            return redirect(f"{reverse('schoolcomm:room_detail', kwargs={'room_id': room.id})}#message-{message.id}")
        return JsonResponse({"status": "success", "is_active": is_active, "ack_count": ack_count})
    except DatabaseError:
        logger.exception("[schoolcomm] api_message_reactions unavailable")
        return _json_service_unavailable()


@login_required
@require_GET
def api_asset_download(request, asset_id):
    try:
        asset = get_object_or_404(SharedAsset.objects.select_related("blob"), id=asset_id)
        if not user_can_download_asset(request.user, asset):
            return HttpResponseForbidden("이 파일을 내려받을 수 없습니다.")
        asset.blob.file.open("rb")
        response = FileResponse(asset.blob.file, as_attachment=True, filename=asset.original_name)
        return response
    except DatabaseError:
        logger.exception("[schoolcomm] api_asset_download unavailable")
        return HttpResponse(SERVICE_UNAVAILABLE_MESSAGE, status=503)


@login_required
@require_POST
def api_asset_category(request, asset_id):
    try:
        asset = get_object_or_404(SharedAsset.objects.select_related("blob"), id=asset_id)
        if not user_can_download_asset(request.user, asset):
            return _json_error("이 자료를 분류할 수 없습니다.", status=403, code="permission_denied")
        category = update_user_asset_category(request.user, asset, request.POST.get("category"))
        if not _wants_json(request):
            link = asset.message_links.select_related("message").first()
            room_id = getattr(getattr(link, "message", None), "room_id", "")
            redirect_url = reverse("schoolcomm:room_detail", kwargs={"room_id": room_id}) if room_id else reverse("schoolcomm:main")
            return redirect(redirect_url)
        return JsonResponse(
            {
                "status": "success",
                "category": category.category,
                "category_label": category.get_category_display(),
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_asset_category unavailable")
        return _json_service_unavailable()


@login_required
@require_GET
def api_search(request):
    try:
        workspace = _resolve_workspace(request)
        if workspace is None:
            return _json_error("먼저 채팅방을 선택해 주세요.")
        try:
            results = search_workspace(workspace, request.user, request.GET.get("q"), page_number=request.GET.get("page") or 1)
        except MembershipRequiredError as exc:
            return _json_error(str(exc), status=403, code="permission_denied")
        return JsonResponse(
            {
                "status": "success",
                "query": results["query"],
                "rooms": [build_room_summary(room, user=request.user) for room in results["room_matches"]],
                "messages": [serialize_message(message, user=request.user) for message in (results["messages_page"].object_list if results["messages_page"] else [])],
                "assets": [serialize_asset(asset, user=request.user) for asset in (results["assets_page"].object_list if results["assets_page"] else [])],
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_search unavailable")
        return _json_service_unavailable()


@login_required
@require_GET
def api_asset_search(request):
    try:
        workspace = _resolve_workspace(request)
        if workspace is None:
            return _json_error("먼저 채팅방을 선택해 주세요.")
        try:
            page_obj = search_workspace_assets(workspace, request.user, request.GET.get("q"), page_number=request.GET.get("page") or 1)
        except MembershipRequiredError as exc:
            return _json_error(str(exc), status=403, code="permission_denied")
        return JsonResponse(
            {
                "status": "success",
                "assets": [serialize_asset(asset, user=request.user) for asset in page_obj.object_list],
                "page": page_obj.number,
                "num_pages": page_obj.paginator.num_pages,
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_asset_search unavailable")
        return _json_service_unavailable()


@login_required
@require_GET
def api_notifications_summary(request):
    try:
        workspace = _resolve_workspace(request)
        summary = build_notification_summary(request.user, workspace=workspace)
        return JsonResponse({"status": "success", "summary": summary})
    except DatabaseError:
        logger.exception("[schoolcomm] api_notifications_summary unavailable")
        return _json_service_unavailable()


@login_required
@require_POST
def api_apply_calendar_suggestion(request, suggestion_id):
    try:
        suggestion = get_object_or_404(CalendarSuggestion, id=suggestion_id, user=request.user)
        if suggestion.status != CalendarSuggestion.Status.PENDING:
            return _json_error("이미 처리한 추천입니다.")
        payload = suggestion.suggested_payload or {}
        start_time = parse_datetime(str(payload.get("start_time") or ""))
        end_time = parse_datetime(str(payload.get("end_time") or ""))
        if start_time is None or end_time is None:
            return _json_error("추천 일정 시간이 올바르지 않습니다.")

        classroom = get_active_classroom_for_request(request)
        event = CalendarEvent.objects.create(
            title=str(payload.get("title") or "우리끼리 채팅방 일정"),
            start_time=start_time,
            end_time=end_time,
            is_all_day=bool(payload.get("is_all_day")),
            color="indigo",
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            author=request.user,
            classroom=classroom,
            source=CalendarEvent.SOURCE_LOCAL,
        )
        note = str(payload.get("note") or "").strip()
        if note:
            EventPageBlock.objects.create(
                event=event,
                block_type="paragraph",
                content={"text": note},
                order=0,
            )
        suggestion.status = CalendarSuggestion.Status.APPLIED
        suggestion.applied_at = timezone.now()
        suggestion.save(update_fields=["status", "applied_at", "updated_at"])
        if not _wants_json(request):
            messages.success(request, "캘린더에 추천 일정을 저장했어요.")
            room_id = (payload.get("source_room_id") or "").strip()
            if room_id:
                return redirect(reverse("schoolcomm:room_detail", kwargs={"room_id": room_id}))
            return redirect(reverse("schoolcomm:main"))
        return JsonResponse(
            {
                "status": "success",
                "event": {
                    "id": str(event.id),
                    "title": event.title,
                },
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_apply_calendar_suggestion unavailable")
        return _json_service_unavailable()
