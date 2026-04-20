import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from core.home_agent_registry import resolve_home_agent_conversation_actions
from core.seo import build_route_page_seo

from .models import CalendarSuggestion, MessageReaction, RoomMessage, SchoolMembership, SharedAsset, UserAssetCategory, WorkspaceInvite
from .services import (
    MembershipRequiredError,
    ValidationError,
    accept_invite,
    apply_calendar_suggestion_to_shared_calendar,
    approve_membership,
    build_main_calendar_event_url,
    build_notification_summary,
    build_room_summary,
    build_shared_calendar_panel,
    build_workspace_dashboard,
    copy_shared_calendar_event_to_main,
    create_invite,
    create_room_message,
    create_shared_calendar_event,
    create_workspace_for_user,
    delete_shared_calendar_event,
    get_default_room,
    get_default_workspace_for_user,
    get_membership,
    get_or_create_dm_room,
    get_room_for_user,
    get_shared_calendar_event_for_user,
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
    serialize_shared_calendar_event,
    toggle_ack_reaction,
    update_user_asset_category,
    update_shared_calendar_event,
    user_display_name,
    user_can_download_asset,
)


logger = logging.getLogger(__name__)

SERVICE_PUBLIC_NAME = "끼리끼리 채팅방"
SERVICE_UNAVAILABLE_MESSAGE = "지금은 채팅방을 준비하는 중입니다. 잠시 후 다시 열어 주세요."
SHARED_BOARD_FILTERS = (
    ("all", "전체"),
    (UserAssetCategory.Category.LESSON, "수업"),
    (UserAssetCategory.Category.ASSESSMENT, "평가"),
    (UserAssetCategory.Category.WORK, "행정"),
    ("social", "친목"),
    (UserAssetCategory.Category.OTHER, "기타"),
    (UserAssetCategory.Category.UNCLASSIFIED, "미분류"),
)


def _build_noindex_seo(request, *, title, description):
    return build_route_page_seo(
        request,
        title=title,
        description=description,
        route_name="schoolcomm:main" if request is None else "",
        current_path=getattr(request, "path", ""),
        robots="noindex,nofollow",
    )


def _json_error(message, *, status=400, code="validation_error", extra=None):
    payload = {"status": "error", "code": code, "error": message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")


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


def _build_room_chat_items(room, user):
    return [serialize_message(message, user=user) for message in _room_message_queryset(room)]


def _short_preview(text, limit=72):
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _room_kind_label(room_kind):
    labels = {
        "notice": "공지",
        "shared": "자료",
        "dm": "대화",
        "group_dm": "그룹",
    }
    return labels.get(str(room_kind or "").strip().lower(), "대화")


def _room_avatar_label(room):
    name = str(getattr(room, "name", "") or "").strip()
    initials = "".join(part[:1] for part in name.split()[:2]).strip()
    return (initials or name[:2] or _room_kind_label(getattr(room, "room_kind", ""))[:2])[:2]


def _build_room_snapshot(room, user, membership):
    latest_message = room.messages.order_by("-created_at", "-id").first()
    mark_room_read(user, room, latest_message=latest_message)
    room_items = _build_room_items(room, user)
    active_category = "all"
    assets_panel = {
        "active_category": active_category,
        "filter_tabs": [],
        "sections": [],
        "total_asset_count": 0,
        "today_asset_count": 0,
        "unclassified_count": 0,
        "manual_asset_count": 0,
        "has_assets": False,
        "has_visible_assets": False,
        "view_url": reverse("schoolcomm:room_detail", kwargs={"room_id": room.id}),
    }
    if room.room_kind == room.RoomKind.SHARED:
        assets_panel = {
            **_build_shared_room_board(room, room_items, active_category=active_category),
            "view_url": reverse("schoolcomm:room_detail", kwargs={"room_id": room.id}),
        }
    calendar_suggestions = [
        serialize_calendar_suggestion(suggestion)
        for suggestion in (
            CalendarSuggestion.objects.filter(
                user=user,
                status=CalendarSuggestion.Status.PENDING,
                source_message__room=room,
            )
            .order_by("-created_at")[:6]
        )
    ]
    member_options = []
    for workspace_membership in (
        room.workspace.memberships.select_related("user")
        .filter(status=SchoolMembership.Status.ACTIVE)
        .exclude(user=user)
        .order_by("role", "user__username")
    ):
        display_name = user_display_name(workspace_membership.user)
        member_options.append(
            {
                "user_id": str(workspace_membership.user_id),
                "label": display_name,
                "meta": workspace_membership.get_role_display(),
                "search_text": f"{display_name} {workspace_membership.user.username}".strip(),
            }
        )

    context_actions = resolve_home_agent_conversation_actions(room.room_kind)
    can_manage_workspace = membership_can_manage_workspace(membership)
    return {
        "room": {
            "id": str(room.id),
            "name": room.name,
            "room_kind": room.room_kind,
            "room_kind_label": _room_kind_label(room.room_kind),
            "avatar_label": _room_avatar_label(room),
            "workspace_id": str(room.workspace_id),
            "workspace_name": str(room.workspace.name or ""),
            "open_url": reverse("schoolcomm:room_detail", kwargs={"room_id": room.id}),
            "send_url": reverse("schoolcomm:api_room_messages", kwargs={"room_id": room.id}),
            "can_post_top_level": membership_can_post_notice(membership) or room.room_kind != room.RoomKind.NOTICE,
            "composer_placeholder": "메시지 입력",
            "room_ws_url": _build_ws_path(f"schoolcomm/ws/rooms/{room.id}/"),
            "user_ws_url": _build_ws_path("schoolcomm/ws/users/me/"),
        },
        "messages": _build_room_chat_items(room, user),
        "reply_state": {
            "enabled": True,
        },
        "assets_panel": assets_panel,
        "calendar_suggestions": calendar_suggestions,
        "room_actions": {
            "items": (
                {
                    "key": "open-room",
                    "label": "채팅방 열기",
                    "href": reverse("schoolcomm:room_detail", kwargs={"room_id": room.id}),
                    "kind": "link",
                },
            ),
        },
        "context_actions": context_actions,
        "invite_actions": {
            "can_create": can_manage_workspace,
            "create_url": reverse("schoolcomm:api_create_invite") if can_manage_workspace else "",
            "default_role": SchoolMembership.Role.MEMBER,
            "roles": (
                {
                    "value": SchoolMembership.Role.MEMBER,
                    "label": "멤버",
                },
                {
                    "value": SchoolMembership.Role.ADMIN,
                    "label": "관리자",
                },
            ),
        },
        "dm_actions": {
            "create_url": reverse("schoolcomm:api_dms"),
            "max_members": 4,
            "members": member_options,
        },
        "composer_capabilities": {
            "reply": True,
            "file_attach": True,
            "paste": True,
            "drag_drop": True,
            "reactions": True,
        },
    }


def _normalize_shared_board_category(raw_value):
    allowed = {code for code, _label in SHARED_BOARD_FILTERS}
    value = str(raw_value or "").strip()
    if value in allowed:
        return value
    return "all"


def _room_base_url(room):
    return reverse("schoolcomm:room_detail", kwargs={"room_id": room.id})


def _room_refresh_url(request, room):
    params = request.GET.copy()
    params["fragment"] = "content"
    return f"{_room_base_url(room)}?{params.urlencode()}"


def _shared_board_filter_tabs(room, *, active_category, category_counts):
    tabs = []
    room_url = _room_base_url(room)
    for code, label in SHARED_BOARD_FILTERS:
        count = category_counts.get(code, 0)
        tabs.append(
            {
                "code": code,
                "label": label,
                "count": count,
                "is_active": code == active_category,
                "url": room_url if code == "all" else f"{room_url}?{urlencode({'category': code})}",
            }
        )
    return tabs


def _build_shared_board_asset_entry(asset, source_item, *, room):
    created_at = parse_datetime(source_item.get("created_at") or "")
    local_date = timezone.localtime(created_at).date() if created_at else None
    message_id = source_item.get("id")
    return {
        **asset,
        "message_id": message_id,
        "message_url": f"#message-{message_id}" if message_id else "#schoolcomm-room-composer",
        "message_preview": _short_preview(source_item.get("body") or ""),
        "posted_at": source_item.get("created_at") or "",
        "posted_at_label": source_item.get("created_at_label") or "",
        "posted_by": source_item.get("sender_name") or asset.get("uploader_name") or "",
        "is_reply_asset": bool(source_item.get("parent_message_id")),
        "is_today": local_date == timezone.localdate() if local_date else False,
    }


def _build_shared_room_board(room, room_items, *, active_category):
    category_labels = {code: label for code, label in SHARED_BOARD_FILTERS}
    all_assets = []
    for item in room_items:
        for asset in item.get("assets", []):
            all_assets.append(_build_shared_board_asset_entry(asset, item, room=room))
        for reply in item.get("replies", []):
            for asset in reply.get("assets", []):
                all_assets.append(_build_shared_board_asset_entry(asset, reply, room=room))

    all_assets.sort(key=lambda asset_item: asset_item.get("posted_at") or "", reverse=True)
    category_counts = {"all": len(all_assets)}
    for code, _label in SHARED_BOARD_FILTERS:
        if code == "all":
            continue
        category_counts[code] = sum(1 for asset_item in all_assets if asset_item.get("category") == code)

    if active_category == "all":
        section_codes = [code for code, _label in SHARED_BOARD_FILTERS if code != "all" and category_counts.get(code)]
    else:
        section_codes = [active_category]

    sections = []
    for code in section_codes:
        section_items = [asset_item for asset_item in all_assets if asset_item.get("category") == code]
        sections.append(
            {
                "code": code,
                "label": category_labels.get(code, "자료"),
                "count": len(section_items),
                "items": section_items,
            }
        )
    visible_asset_count = sum(len(section["items"]) for section in sections)

    return {
        "active_category": active_category,
        "filter_tabs": _shared_board_filter_tabs(room, active_category=active_category, category_counts=category_counts),
        "sections": sections,
        "total_asset_count": len(all_assets),
        "today_asset_count": sum(1 for asset_item in all_assets if asset_item.get("is_today")),
        "unclassified_count": category_counts.get(UserAssetCategory.Category.UNCLASSIFIED, 0),
        "manual_asset_count": sum(1 for asset_item in all_assets if asset_item.get("category_source") == UserAssetCategory.Source.MANUAL),
        "has_assets": bool(all_assets),
        "has_visible_assets": bool(visible_asset_count),
    }


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


def _build_main_url(workspace_id=None, *, calendar_tab="", calendar_month="", calendar_date="", query="", anchor=""):
    params = []
    if workspace_id:
        params.append(("workspace", str(workspace_id)))
    if query:
        params.append(("q", str(query)))
    if calendar_tab:
        params.append(("calendar_tab", str(calendar_tab)))
    if calendar_month:
        params.append(("calendar_month", str(calendar_month)))
    if calendar_date:
        params.append(("calendar_date", str(calendar_date)))
    base_url = reverse("schoolcomm:main")
    url = base_url if not params else f"{base_url}?{urlencode(params)}"
    anchor_value = str(anchor or "").strip()
    if anchor_value:
        return f"{url}#{anchor_value.lstrip('#')}"
    return url


def _normalize_calendar_tab(raw_value):
    value = str(raw_value or "").strip().lower()
    if value in {"suggestions", "shared"}:
        return value
    return "suggestions"


def _parse_calendar_form_datetimes(request):
    start_raw = str(request.POST.get("start_time") or "").strip()
    end_raw = str(request.POST.get("end_time") or "").strip()
    if not start_raw or not end_raw:
        raise ValidationError("시작 시간과 종료 시간을 모두 입력해 주세요.")
    start_time = parse_datetime(start_raw)
    end_time = parse_datetime(end_raw)
    if start_time is None or end_time is None:
        raise ValidationError("일정 시간 형식이 올바르지 않습니다.")
    if timezone.is_naive(start_time):
        start_time = timezone.make_aware(start_time, timezone.get_current_timezone())
    if timezone.is_naive(end_time):
        end_time = timezone.make_aware(end_time, timezone.get_current_timezone())
    return start_time, end_time


def _service_unavailable_context():
    seo = _build_noindex_seo(
        None,
        title=f"{SERVICE_PUBLIC_NAME} | Eduitit",
        description="동학년 선생님과 공지, 자료, 대화, 캘린더를 한 화면에서 정리하는 교사용 채팅방입니다.",
    )
    return {
        **seo.as_context(),
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
        search_results = None
        dashboard = None
        shared_calendar = None
        inbox_rooms = []
        selected_room = None
        selected_room_summary = None
        chat_items = []
        current_query = request.GET.get("q", "")
        calendar_tab = _normalize_calendar_tab(request.GET.get("calendar_tab"))
        latest_invite_url = request.session.pop("schoolcomm_latest_invite_url", "")
        if workspace is not None:
            dashboard = build_workspace_dashboard(workspace, request.user)
            inbox_rooms = list(dashboard.get("dm_rooms") or [])
            shared_calendar = build_shared_calendar_panel(
                workspace,
                request.user,
                month_value=request.GET.get("calendar_month"),
                selected_date_value=request.GET.get("calendar_date"),
            )
            requested_room_id = str(request.GET.get("room") or "").strip()
            if inbox_rooms:
                selected_room_summary = next(
                    (room for room in inbox_rooms if str(room.get("id") or "") == requested_room_id),
                    None,
                )
                if selected_room_summary is None:
                    selected_room_summary = next(
                        (room for room in inbox_rooms if int(room.get("unread_count") or 0) > 0),
                        inbox_rooms[0],
                    )
                room_id = str(selected_room_summary.get("id") or "").strip()
                room, membership = get_room_for_user(room_id, request.user)
                if room is not None and membership is not None and room.room_kind in {room.RoomKind.DM, room.RoomKind.GROUP_DM}:
                    latest_message = room.messages.order_by("-created_at", "-id").first()
                    mark_room_read(request.user, room, latest_message=latest_message)
                    selected_room_summary = dict(selected_room_summary or {})
                    selected_room_summary["unread_count"] = 0
                    inbox_rooms = [
                        dict(room_summary, unread_count=0) if str(room_summary.get("id") or "") == room_id else room_summary
                        for room_summary in inbox_rooms
                    ]
                    selected_room = room
                    chat_items = _build_room_chat_items(room, request.user)
            if (current_query or "").strip():
                search_results = search_workspace(
                    workspace,
                    request.user,
                    current_query,
                    page_number=request.GET.get("page") or 1,
                )
                search_results = _build_search_display(search_results, request.user)

        if workspace is not None:
            seo = _build_noindex_seo(
                request,
                title=f"{workspace.name} | {SERVICE_PUBLIC_NAME}",
                description="공지, 자료, 대화, 끼리끼리 캘린더를 한 화면에서 빠르게 확인하는 교사용 채팅방입니다.",
            )
        else:
            seo = _build_noindex_seo(
                request,
                title=f"{SERVICE_PUBLIC_NAME} | Eduitit",
                description="동학년 선생님과 공지, 자료, 대화, 끼리끼리 캘린더를 한 화면에서 정리하는 교사용 채팅방입니다.",
            )

        context = {
            **seo.as_context(),
            "service_product": get_service_product(),
            "workspace": workspace,
            "workspace_name_suggestion": school_name_suggestion_for_user(request.user),
            "active_memberships": active_memberships,
            "dashboard": dashboard,
            "inbox_rooms": inbox_rooms,
            "selected_room": selected_room,
            "selected_room_summary": selected_room_summary,
            "chat_items": chat_items,
            "room_is_chat": bool(selected_room),
            "can_post_top_level": True if selected_room else False,
            "room_ws_url": _build_ws_path(f"schoolcomm/ws/rooms/{selected_room.id}/") if selected_room else "",
            "room_base_url": _room_base_url(selected_room) if selected_room else "",
            "room_refresh_url": _room_refresh_url(request, selected_room) if selected_room else "",
            "shared_calendar": shared_calendar,
            "calendar_tab": "shared" if calendar_tab == "shared" else "suggestions",
            "search_results": search_results,
            "latest_invite_url": latest_invite_url,
            "user_ws_url": _build_ws_path("schoolcomm/ws/users/me/"),
            "current_query": current_query,
        }
        if request.GET.get("fragment") == "calendar_panel":
            if workspace is None or dashboard is None or shared_calendar is None:
                return HttpResponse("", status=204)
            return render(request, "schoolcomm/partials/calendar_panel.html", context)
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
        messages.success(request, "끼리끼리 채팅방을 만들었어요.")
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
                messages.success(request, "초대 링크로 바로 들어왔어요.")
                return redirect(f"{reverse('schoolcomm:main')}?workspace={accepted_membership.workspace_id}")
            except ValidationError as exc:
                messages.error(request, str(exc))
        context = {
            **_build_noindex_seo(
                request,
                title="끼리끼리 채팅방 초대 수락 - Eduitit",
                description="초대 링크로 채팅방에 들어가기 전 참여 여부를 확인하는 화면입니다.",
            ).as_context(),
            "invite": invite,
            "membership": accepted_membership or membership,
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

        room_is_chat = room.room_kind in {room.RoomKind.DM, room.RoomKind.GROUP_DM}
        latest_message = room.messages.order_by("-created_at", "-id").first()
        mark_room_read(request.user, room, latest_message=latest_message)
        room_items = [] if room_is_chat else _build_room_items(room, request.user)
        chat_items = _build_room_chat_items(room, request.user) if room_is_chat else []
        active_category = _normalize_shared_board_category(request.GET.get("category"))
        shared_board = (
            _build_shared_room_board(room, room_items, active_category=active_category)
            if room.room_kind == room.RoomKind.SHARED
            else None
        )
        workspace = room.workspace
        dashboard = build_workspace_dashboard(workspace, request.user)
        context = {
            **_build_noindex_seo(
                request,
                title=f"{room.name} | {SERVICE_PUBLIC_NAME}",
                description="채팅방 대화, 공지, 자료를 교사끼리 빠르게 이어가는 내부 업무 화면입니다.",
            ).as_context(),
            "room": room,
            "membership": membership,
            "workspace": workspace,
            "room_items": room_items,
            "chat_items": chat_items,
            "shared_board": shared_board,
            "dashboard": dashboard,
            "room_is_chat": room_is_chat,
            "can_post_top_level": membership_can_post_notice(membership) or room.room_kind != room.RoomKind.NOTICE,
            "room_ws_url": _build_ws_path(f"schoolcomm/ws/rooms/{room.id}/"),
            "room_base_url": _room_base_url(room),
            "room_refresh_url": _room_refresh_url(request, room),
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
@require_GET
def api_room_snapshot(request, room_id):
    try:
        room, membership = get_room_for_user(room_id, request.user)
        if room is None:
            raise Http404("방을 찾을 수 없습니다.")
        if membership is None:
            return _json_error("이 방에 접근할 수 없습니다.", status=403, code="permission_denied")
        snapshot = _build_room_snapshot(room, request.user, membership)
        return JsonResponse({"status": "success", **snapshot})
    except DatabaseError:
        logger.exception("[schoolcomm] api_room_snapshot unavailable")
        return _json_service_unavailable()


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
def api_workspace_calendar_events(request, workspace_id):
    try:
        workspace = get_object_or_404(
            request.user.school_memberships.select_related("workspace").filter(status=SchoolMembership.Status.ACTIVE),
            workspace_id=workspace_id,
        ).workspace
        membership = get_membership(workspace, request.user)
        if membership is None:
            return _json_error("채팅방 멤버만 끼리끼리 캘린더를 사용할 수 있습니다.", status=403, code="permission_denied")

        if request.method == "GET":
            panel = build_shared_calendar_panel(
                workspace,
                request.user,
                month_value=request.GET.get("month"),
                selected_date_value=request.GET.get("date"),
            )
            return JsonResponse({"status": "success", "calendar": panel})

        start_time, end_time = _parse_calendar_form_datetimes(request)
        try:
            event = create_shared_calendar_event(
                workspace,
                membership,
                title=request.POST.get("title"),
                note=request.POST.get("note"),
                start_time=start_time,
                end_time=end_time,
                is_all_day=str(request.POST.get("is_all_day") or "").strip().lower() in {"1", "true", "on", "yes"},
                color=request.POST.get("color"),
            )
        except (MembershipRequiredError, ValidationError) as exc:
            if _wants_json(request):
                status = 403 if isinstance(exc, MembershipRequiredError) else 400
                code = "permission_denied" if isinstance(exc, MembershipRequiredError) else "validation_error"
                return _json_error(str(exc), status=status, code=code)
            messages.error(request, str(exc))
            return redirect(
                _build_main_url(
                    workspace.id,
                    calendar_tab="shared",
                    calendar_month=request.POST.get("redirect_month"),
                    calendar_date=request.POST.get("redirect_date"),
                    query=request.POST.get("redirect_query"),
                    anchor="calendar-panel",
                )
            )
        if not _wants_json(request):
            messages.success(request, "끼리끼리 캘린더에 일정을 넣었어요.")
            return redirect(
                _build_main_url(
                    workspace.id,
                    calendar_tab="shared",
                    calendar_month=request.POST.get("redirect_month") or timezone.localtime(event.start_time).strftime("%Y-%m"),
                    calendar_date=request.POST.get("redirect_date") or timezone.localtime(event.start_time).date().isoformat(),
                    query=request.POST.get("redirect_query"),
                    anchor="calendar-panel",
                )
            )
        return JsonResponse({"status": "success", "event": serialize_shared_calendar_event(event, user=request.user)}, status=201)
    except DatabaseError:
        logger.exception("[schoolcomm] api_workspace_calendar_events unavailable")
        return _json_service_unavailable()


@login_required
@require_POST
def api_shared_calendar_event_update(request, event_id):
    try:
        event, membership = get_shared_calendar_event_for_user(event_id, request.user)
        if event is None:
            raise Http404("일정을 찾을 수 없습니다.")
        if membership is None:
            return _json_error("이 일정을 수정할 수 없습니다.", status=403, code="permission_denied")
        start_time, end_time = _parse_calendar_form_datetimes(request)
        try:
            event = update_shared_calendar_event(
                event,
                membership,
                title=request.POST.get("title"),
                note=request.POST.get("note"),
                start_time=start_time,
                end_time=end_time,
                is_all_day=str(request.POST.get("is_all_day") or "").strip().lower() in {"1", "true", "on", "yes"},
                color=request.POST.get("color"),
            )
        except (MembershipRequiredError, ValidationError) as exc:
            if _wants_json(request):
                status = 403 if isinstance(exc, MembershipRequiredError) else 400
                code = "permission_denied" if isinstance(exc, MembershipRequiredError) else "validation_error"
                return _json_error(str(exc), status=status, code=code)
            messages.error(request, str(exc))
            return redirect(
                _build_main_url(
                    event.workspace_id,
                    calendar_tab="shared",
                    calendar_month=request.POST.get("redirect_month"),
                    calendar_date=request.POST.get("redirect_date"),
                    query=request.POST.get("redirect_query"),
                    anchor="calendar-panel",
                )
            )
        if not _wants_json(request):
            messages.success(request, "끼리끼리 캘린더 일정을 수정했어요.")
            return redirect(
                _build_main_url(
                    event.workspace_id,
                    calendar_tab="shared",
                    calendar_month=request.POST.get("redirect_month") or timezone.localtime(event.start_time).strftime("%Y-%m"),
                    calendar_date=request.POST.get("redirect_date") or timezone.localtime(event.start_time).date().isoformat(),
                    query=request.POST.get("redirect_query"),
                    anchor="calendar-panel",
                )
            )
        return JsonResponse({"status": "success", "event": serialize_shared_calendar_event(event, user=request.user)})
    except DatabaseError:
        logger.exception("[schoolcomm] api_shared_calendar_event_update unavailable")
        return _json_service_unavailable()


@login_required
@require_POST
def api_shared_calendar_event_delete(request, event_id):
    try:
        event, membership = get_shared_calendar_event_for_user(event_id, request.user)
        if event is None:
            raise Http404("일정을 찾을 수 없습니다.")
        if membership is None:
            return _json_error("이 일정을 삭제할 수 없습니다.", status=403, code="permission_denied")
        try:
            delete_shared_calendar_event(event, membership)
        except MembershipRequiredError as exc:
            return _json_error(str(exc), status=403, code="permission_denied")
        if not _wants_json(request):
            messages.success(request, "끼리끼리 캘린더 일정을 삭제했어요.")
            return redirect(
                _build_main_url(
                    event.workspace_id,
                    calendar_tab="shared",
                    calendar_month=request.POST.get("redirect_month"),
                    calendar_date=request.POST.get("redirect_date"),
                    query=request.POST.get("redirect_query"),
                    anchor="calendar-panel",
                )
            )
        return JsonResponse({"status": "success"})
    except DatabaseError:
        logger.exception("[schoolcomm] api_shared_calendar_event_delete unavailable")
        return _json_service_unavailable()


@login_required
@require_POST
def api_shared_calendar_event_copy_to_main(request, event_id):
    try:
        event, membership = get_shared_calendar_event_for_user(event_id, request.user)
        if event is None:
            raise Http404("일정을 찾을 수 없습니다.")
        if membership is None:
            return _json_error("이 일정을 내 메인 캘린더로 보낼 수 없습니다.", status=403, code="permission_denied")
        try:
            personal_event, created = copy_shared_calendar_event_to_main(event, request.user)
        except MembershipRequiredError as exc:
            return _json_error(str(exc), status=403, code="permission_denied")
        target_url = build_main_calendar_event_url(personal_event)
        if not _wants_json(request):
            messages.success(
                request,
                "내 메인 캘린더로 보냈어요. 내 캘린더에서는 독립 일정으로 관리됩니다.",
            )
            return redirect(target_url)
        return JsonResponse(
            {
                "status": "success",
                "created": created,
                "event": {
                    "id": str(personal_event.id),
                    "title": personal_event.title,
                    "url": target_url,
                },
                "message": "내 캘린더에서는 독립 일정으로 관리됩니다.",
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_shared_calendar_event_copy_to_main unavailable")
        return _json_service_unavailable()


@login_required
@require_POST
def api_apply_calendar_suggestion(request, suggestion_id):
    try:
        suggestion = get_object_or_404(CalendarSuggestion, id=suggestion_id, user=request.user)
        try:
            shared_event = apply_calendar_suggestion_to_shared_calendar(suggestion, request.user)
        except MembershipRequiredError as exc:
            return _json_error(str(exc), status=403, code="permission_denied")
        except ValidationError as exc:
            return _json_error(str(exc))
        target_main_copy_url = reverse("schoolcomm:api_shared_calendar_event_copy_to_main", kwargs={"event_id": shared_event.id})
        if not _wants_json(request):
            messages.success(request, "끼리끼리 캘린더에 넣었어요. 내 캘린더에서는 독립 일정으로 관리됩니다.")
            next_url = str(request.POST.get("next") or "").strip()
            if next_url:
                return redirect(next_url)
            return redirect(
                _build_main_url(
                    shared_event.workspace_id,
                    calendar_tab="shared",
                    calendar_month=timezone.localtime(shared_event.start_time).strftime("%Y-%m"),
                    calendar_date=timezone.localtime(shared_event.start_time).date().isoformat(),
                    query=request.POST.get("redirect_query"),
                    anchor="calendar-panel",
                )
            )
        return JsonResponse(
            {
                "status": "success",
                "shared_event": {
                    "id": str(shared_event.id),
                    "title": shared_event.title,
                },
                "copy_to_main_url": target_main_copy_url,
                "message": "끼리끼리 캘린더에 넣었어요. 내 캘린더에서는 독립 일정으로 관리됩니다.",
            }
        )
    except DatabaseError:
        logger.exception("[schoolcomm] api_apply_calendar_suggestion unavailable")
        return _json_service_unavailable()
