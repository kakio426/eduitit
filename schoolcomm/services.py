import calendar as calendar_module
import hashlib
import json
import os
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import date as date_cls, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent, EventPageBlock
from classcalendar.message_capture import parse_message_capture_draft
from products.models import ManualSection, Product, ProductFeature, ServiceManual

from .models import (
    CalendarSuggestion,
    CommunityRoom,
    MessageAssetLink,
    MessageReaction,
    RoomMessage,
    RoomParticipant,
    SchoolMembership,
    SchoolWorkspace,
    SharedCalendarEvent,
    SharedCalendarEventCopy,
    SharedAsset,
    StoredAssetBlob,
    UserAssetCategory,
    UserRoomState,
    WorkspaceInvite,
)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


SERVICE_ROUTE = "schoolcomm:main"
SERVICE_TITLE = "끼리끼리 채팅방"
CALENDAR_COPY_INTEGRATION_SOURCE = "schoolcomm_calendar_copy"
SHARED_CALENDAR_DEFAULT_COLORS = {"emerald", "indigo", "sky", "amber", "rose"}
SERVICE_PRODUCT_DEFAULTS = {
    "lead_text": "동학년 선생님부터 편하게 공지, 자료, 대화를 나누는 가벼운 채팅방입니다.",
    "description": (
        "끼리끼리 채팅방은 공지와 자료를 나누고, 1:1·소규모 대화를 이어가며, 받은 파일을 개인 기준으로 다시 분류하고 "
        "끼리끼리 캘린더에 추천 일정을 모은 뒤 내 메인 캘린더로 필요한 일정만 보내는 대화 공간입니다."
    ),
    "price": 0.00,
    "is_active": True,
    "is_featured": False,
    "is_guest_allowed": False,
    "icon": "💬",
    "color_theme": "blue",
    "card_size": "small",
    "display_order": 16,
    "service_type": "classroom",
    "external_url": "",
    "launch_route_name": SERVICE_ROUTE,
    "solve_text": "동학년 선생님들과 공지, 자료, 일정을 편하게 나누고 싶어요",
    "result_text": "끼리끼리 채팅방",
    "time_text": "1분",
}
ADMIN_MANAGED_PRODUCT_FIELDS = {"is_active", "service_type", "display_order", "color_theme", "card_size"}
NOTICE_ROOM_NAME = "공지"
SHARED_ROOM_NAME = "자료공유"
USER_SOCKET_GROUP_TEMPLATE = "schoolcomm-user-{user_id}"
ROOM_SOCKET_GROUP_TEMPLATE = "schoolcomm-room-{room_id}"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
CATEGORY_LABELS = {
    UserAssetCategory.Category.UNCLASSIFIED: "미분류",
    UserAssetCategory.Category.LESSON: "수업자료",
    UserAssetCategory.Category.ASSESSMENT: "평가자료",
    UserAssetCategory.Category.WORK: "업무",
    UserAssetCategory.Category.OTHER: "기타",
}
HEURISTIC_CATEGORY_HINTS = [
    (UserAssetCategory.Category.ASSESSMENT, ("평가", "시험", "중간", "기말", "수행", "채점", "정답", "문항")),
    (UserAssetCategory.Category.LESSON, ("수업", "차시", "활동지", "학습", "교과", "지도안", "worksheet", "lesson")),
    (UserAssetCategory.Category.WORK, ("업무", "공문", "기안", "회의", "결재", "행정", "출장", "안내")),
]


class SchoolcommError(Exception):
    """Base exception for school community service operations."""


class MembershipRequiredError(SchoolcommError):
    """Raised when the user does not belong to the workspace."""


class RoomAccessError(SchoolcommError):
    """Raised when the user cannot access the room."""


class ValidationError(SchoolcommError):
    """Raised when submitted data is invalid."""


class CategoryClassifierError(SchoolcommError):
    """Raised when DeepSeek category classification fails."""


def _safe_profile(user):
    try:
        return user.userprofile
    except Exception:
        return None


def user_display_name(user):
    if not user:
        return "알 수 없음"
    profile = _safe_profile(user)
    nickname = str(getattr(profile, "nickname", "") or "").strip()
    if nickname:
        return nickname
    full_name = str(user.get_full_name() or "").strip()
    if full_name:
        return full_name
    return str(getattr(user, "username", "") or "").strip() or "알 수 없음"


def user_secondary_label(user):
    if not user:
        return ""
    parts = [str(getattr(user, "username", "") or "").strip()]
    email = str(getattr(user, "email", "") or "").strip()
    if email:
        parts.append(email)
    return " · ".join(part for part in parts if part)


def _truncate(text, limit=72):
    raw = " ".join(str(text or "").split())
    if len(raw) <= limit:
        return raw
    return f"{raw[: limit - 3]}..."


def _format_datetime_label(value):
    if not value:
        return ""
    localized = timezone.localtime(value)
    return localized.strftime("%m월 %d일 %H:%M")


def _format_iso_datetime_label(raw_value):
    if not raw_value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(raw_value))
    except ValueError:
        return str(raw_value)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return _format_datetime_label(parsed)


def _format_date_label(value):
    if not value:
        return ""
    return value.strftime("%m월 %d일")


def _normalize_month_value(raw_value):
    text = str(raw_value or "").strip()
    if not text:
        now_local = timezone.localtime()
        return date_cls(now_local.year, now_local.month, 1)
    try:
        return datetime.strptime(text, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise ValidationError("월 형식이 올바르지 않습니다.") from exc


def _normalize_date_value(raw_value, *, fallback=None):
    text = str(raw_value or "").strip()
    if not text:
        return fallback
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("날짜 형식이 올바르지 않습니다.") from exc


def _normalize_local_datetime(raw_value):
    text = str(raw_value or "").strip()
    if not text:
        raise ValidationError("일정 시간을 입력해 주세요.")
    parsed = datetime.fromisoformat(text)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _normalize_shared_calendar_color(raw_value):
    color = str(raw_value or "").strip().lower() or "emerald"
    if color not in SHARED_CALENDAR_DEFAULT_COLORS:
        return "emerald"
    return color


def _shared_event_date_bounds(event):
    start_date = timezone.localtime(event.start_time).date()
    end_date = timezone.localtime(event.end_time).date()
    if end_date < start_date:
        end_date = start_date
    return start_date, end_date


def _shared_event_overlaps_date(event, target_date):
    start_date, end_date = _shared_event_date_bounds(event)
    return start_date <= target_date <= end_date


def _shared_event_time_label(event):
    start_local = timezone.localtime(event.start_time)
    end_local = timezone.localtime(event.end_time)
    if event.is_all_day:
        if start_local.date() == end_local.date():
            return f"{start_local:%m월 %d일} 하루 종일"
        return f"{start_local:%m월 %d일} ~ {end_local:%m월 %d일} 하루 종일"
    if start_local.date() == end_local.date():
        return f"{start_local:%m월 %d일 %H:%M} ~ {end_local:%H:%M}"
    return f"{start_local:%m월 %d일 %H:%M} ~ {end_local:%m월 %d일 %H:%M}"


def build_main_calendar_event_url(event):
    params = [("open_event", str(event.id))]
    if event.start_time:
        params.insert(0, ("date", timezone.localtime(event.start_time).date().isoformat()))
    return f"{reverse('classcalendar:main')}?{urlencode(params)}"


def _find_service_product():
    return (
        Product.objects.filter(launch_route_name=SERVICE_ROUTE).order_by("id").first()
        or Product.objects.filter(title=SERVICE_TITLE).order_by("id").first()
    )


def get_service_product():
    return _find_service_product()


def ensure_service_product():
    product = _find_service_product()
    if product is None:
        product = Product.objects.create(title=SERVICE_TITLE, **SERVICE_PRODUCT_DEFAULTS)
    else:
        changed_fields = []
        if product.title != SERVICE_TITLE:
            product.title = SERVICE_TITLE
            changed_fields.append("title")
        for field_name, value in SERVICE_PRODUCT_DEFAULTS.items():
            if field_name in ADMIN_MANAGED_PRODUCT_FIELDS:
                continue
            if getattr(product, field_name) != value:
                setattr(product, field_name, value)
                changed_fields.append(field_name)
        if changed_fields:
            product.save(update_fields=list(dict.fromkeys(changed_fields)))

    feature_specs = [
        {
            "icon": "📣",
            "title": "공지와 읽음 확인",
            "description": "관리자 공지와 확인 반응을 같은 화면에서 정리합니다.",
        },
        {
            "icon": "📎",
            "title": "자료공유와 개인 분류",
            "description": "같은 파일도 교사마다 다른 카테고리로 다시 정리할 수 있습니다.",
        },
        {
            "icon": "📅",
            "title": "끼리끼리 캘린더",
            "description": "추천 일정을 공유 캘린더에 모으고, 필요한 일정만 내 메인 캘린더로 보냅니다.",
        },
    ]
    for item in feature_specs:
        ProductFeature.objects.update_or_create(
            product=product,
            title=item["title"],
            defaults={"icon": item["icon"], "description": item["description"]},
        )

    manual, _ = ServiceManual.objects.get_or_create(
        product=product,
        defaults={
            "title": "끼리끼리 채팅방 시작 가이드",
            "description": "채팅방 만들기부터 공지, 자료공유, 끼리끼리 캘린더까지 빠르게 익힐 수 있습니다.",
            "is_published": True,
        },
    )
    manual.title = "끼리끼리 채팅방 시작 가이드"
    manual.description = "채팅방 만들기부터 공지, 자료공유, 끼리끼리 캘린더까지 빠르게 익힐 수 있습니다."
    manual.is_published = True
    manual.save(update_fields=["title", "description", "is_published", "updated_at"])

    sections = [
        ("처음 만들기", "이름 제안값을 확인해 채팅방 공간을 만들고, 초대 링크로 함께 쓸 선생님을 초대합니다.", 1),
        ("공지와 자료공유", "공지방은 관리자만 글을 올리고, 자료공유방에서는 파일과 메모를 함께 나눕니다.", 2),
        ("대화와 캘린더", "1:1·그룹 대화 중 필요한 메시지는 끼리끼리 캘린더에 넣고, 필요한 일정만 내 메인 캘린더로 보냅니다.", 3),
    ]
    for title, content, order in sections:
        ManualSection.objects.update_or_create(
            manual=manual,
            title=title,
            defaults={"content": content, "display_order": order},
        )
    return product


def workspace_group_name(room):
    return ROOM_SOCKET_GROUP_TEMPLATE.format(room_id=room.id)


def user_group_name(user):
    return USER_SOCKET_GROUP_TEMPLATE.format(user_id=user.id)


def _send_group_message(group_name, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        group_name,
        {"type": "schoolcomm_event", "message": payload},
    )


def broadcast_room_event(room, event_type, payload=None):
    _send_group_message(
        workspace_group_name(room),
        {"type": event_type, "payload": payload or {}},
    )


def broadcast_user_summary(user):
    summary = build_notification_summary(user)
    _send_group_message(
        user_group_name(user),
        {"type": "notification.summary", "payload": summary},
    )


def school_name_suggestion_for_user(user):
    return "예) 3학년 끼리끼리"


def current_academic_year(now=None):
    current = timezone.localtime(now or timezone.now())
    return str(current.year if current.month >= 3 else current.year - 1)


def _generate_workspace_slug(name):
    base = slugify(str(name or "").strip())[:110]
    if not base:
        base = f"school-{uuid.uuid4().hex[:8]}"
    slug = base
    counter = 2
    while SchoolWorkspace.objects.filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


@transaction.atomic
def create_workspace_for_user(user, *, name="", academic_year=""):
    workspace_name = str(name or "").strip() or school_name_suggestion_for_user(user)
    workspace = SchoolWorkspace.objects.create(
        name=workspace_name,
        slug=_generate_workspace_slug(workspace_name),
        academic_year=str(academic_year or current_academic_year()).strip(),
        created_by=user,
    )
    membership = SchoolMembership.objects.create(
        workspace=workspace,
        user=user,
        role=SchoolMembership.Role.OWNER,
        status=SchoolMembership.Status.ACTIVE,
        joined_at=timezone.now(),
        approved_by=user,
    )
    ensure_default_rooms(workspace, created_by=user)
    return workspace, membership


def ensure_user_room_state(room, user):
    state, _ = UserRoomState.objects.get_or_create(room=room, user=user)
    return state


def ensure_default_rooms(workspace, created_by=None):
    notice_room, _ = CommunityRoom.objects.get_or_create(
        workspace=workspace,
        room_kind=CommunityRoom.RoomKind.NOTICE,
        defaults={"name": NOTICE_ROOM_NAME, "is_system_room": True, "created_by": created_by},
    )
    shared_room, _ = CommunityRoom.objects.get_or_create(
        workspace=workspace,
        room_kind=CommunityRoom.RoomKind.SHARED,
        defaults={"name": SHARED_ROOM_NAME, "is_system_room": True, "created_by": created_by},
    )
    active_memberships = workspace.memberships.filter(status=SchoolMembership.Status.ACTIVE).select_related("user")
    for room in (notice_room, shared_room):
        for membership in active_memberships:
            RoomParticipant.objects.get_or_create(room=room, membership=membership)
            ensure_user_room_state(room, membership.user)
    return notice_room, shared_room


def _activate_membership(membership, *, approver=None):
    membership.status = SchoolMembership.Status.ACTIVE
    membership.joined_at = membership.joined_at or timezone.now()
    update_fields = ["status", "joined_at", "updated_at"]
    if approver is not None or membership.approved_by_id:
        membership.approved_by = approver or membership.approved_by
        update_fields.append("approved_by")
    membership.save(update_fields=update_fields)
    notice_room, shared_room = ensure_default_rooms(membership.workspace, created_by=membership.workspace.created_by)
    for room in (notice_room, shared_room):
        RoomParticipant.objects.get_or_create(room=room, membership=membership)
        ensure_user_room_state(room, membership.user)
    broadcast_user_summary(membership.user)
    return membership


def get_user_memberships(user, *, statuses=None):
    if not getattr(user, "is_authenticated", False):
        return SchoolMembership.objects.none()
    queryset = SchoolMembership.objects.select_related("workspace", "user").filter(user=user)
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    return queryset.order_by("workspace__name", "-created_at")


def get_default_workspace_for_user(user, *, create=False):
    membership = (
        get_user_memberships(user, statuses=[SchoolMembership.Status.ACTIVE])
        .select_related("workspace")
        .first()
    )
    if membership:
        ensure_default_rooms(membership.workspace, created_by=membership.workspace.created_by)
        return membership.workspace
    if create:
        workspace, _ = create_workspace_for_user(user)
        return workspace
    return None


def get_membership(workspace, user, *, include_pending=False):
    statuses = [SchoolMembership.Status.ACTIVE]
    if include_pending:
        statuses.append(SchoolMembership.Status.PENDING)
    return (
        SchoolMembership.objects.select_related("workspace", "user")
        .filter(workspace=workspace, user=user, status__in=statuses)
        .first()
    )


def membership_can_manage_workspace(membership):
    return membership and membership.status == SchoolMembership.Status.ACTIVE and membership.role in {
        SchoolMembership.Role.OWNER,
        SchoolMembership.Role.ADMIN,
    }


def membership_can_post_notice(membership):
    return membership_can_manage_workspace(membership)


def membership_can_access_room(membership, room):
    if not membership or membership.status != SchoolMembership.Status.ACTIVE:
        return False
    if membership.workspace_id != room.workspace_id:
        return False
    return RoomParticipant.objects.filter(room=room, membership=membership).exists()


def get_room(room_id):
    return CommunityRoom.objects.select_related("workspace", "created_by").filter(id=room_id).first()


def get_room_for_user(room_id, user):
    room = get_room(room_id)
    if room is None:
        return None, None
    membership = get_membership(room.workspace, user)
    if not membership_can_access_room(membership, room):
        return room, None
    return room, membership


def build_participants_signature(memberships):
    member_user_ids = sorted(str(membership.user_id) for membership in memberships)
    return ",".join(member_user_ids)


@transaction.atomic
def get_or_create_dm_room(workspace, memberships, *, created_by, name=""):
    unique_memberships = list({membership.user_id: membership for membership in memberships}.values())
    count = len(unique_memberships)
    if count < 2:
        raise ValidationError("대화방에는 최소 2명이 필요합니다.")
    if count > 5:
        raise ValidationError("그룹 대화는 최대 5명까지 허용됩니다.")

    room_kind = CommunityRoom.RoomKind.DM if count == 2 else CommunityRoom.RoomKind.GROUP_DM
    signature = build_participants_signature(unique_memberships)
    existing_room = (
        CommunityRoom.objects.filter(
            workspace=workspace,
            room_kind=room_kind,
            participants_signature=signature,
        )
        .order_by("created_at")
        .first()
    )
    if existing_room:
        return existing_room

    room_name = str(name or "").strip()
    if not room_name:
        room_name = ", ".join(user_display_name(membership.user) for membership in unique_memberships if membership.user)
    room = CommunityRoom.objects.create(
        workspace=workspace,
        room_kind=room_kind,
        name=room_name[:120],
        created_by=created_by,
        participants_signature=signature,
    )
    for membership in unique_memberships:
        RoomParticipant.objects.create(room=room, membership=membership)
        ensure_user_room_state(room, membership.user)
    return room


def _latest_room_message(room):
    return room.messages.select_related("sender").order_by("-created_at", "-id").first()


@transaction.atomic
def mark_room_read(user, room, latest_message=None):
    state = ensure_user_room_state(room, user)
    message = latest_message or _latest_room_message(room)
    if message:
        state.last_read_message = message
        state.last_read_at = message.created_at
    elif state.last_read_at is None:
        state.last_read_at = timezone.now()
    state.unread_count_cache = 0
    state.save(update_fields=["last_read_message", "last_read_at", "unread_count_cache", "updated_at"])
    broadcast_user_summary(user)
    return state


def _sync_room_participants_with_workspace(room):
    if room.room_kind not in {CommunityRoom.RoomKind.NOTICE, CommunityRoom.RoomKind.SHARED}:
        return
    active_memberships = room.workspace.memberships.filter(status=SchoolMembership.Status.ACTIVE).select_related("user")
    for membership in active_memberships:
        RoomParticipant.objects.get_or_create(room=room, membership=membership)
        ensure_user_room_state(room, membership.user)


def get_default_room(workspace, room_kind):
    ensure_default_rooms(workspace, created_by=workspace.created_by)
    return CommunityRoom.objects.filter(workspace=workspace, room_kind=room_kind).first()


def build_notification_summary(user, workspace=None):
    queryset = UserRoomState.objects.filter(user=user, room__workspace__memberships__user=user).select_related("room")
    if workspace is not None:
        queryset = queryset.filter(room__workspace=workspace)
    room_unreads = {}
    total_unread = 0
    notice_unread = 0
    for state in queryset:
        room_unreads[str(state.room_id)] = int(state.unread_count_cache or 0)
        total_unread += int(state.unread_count_cache or 0)
        if state.room.room_kind == CommunityRoom.RoomKind.NOTICE:
            notice_unread += int(state.unread_count_cache or 0)
    suggestion_query = CalendarSuggestion.objects.filter(user=user, status=CalendarSuggestion.Status.PENDING)
    if workspace is not None:
        suggestion_query = suggestion_query.filter(source_message__room__workspace=workspace)
    return {
        "total_unread": total_unread,
        "notice_unread": notice_unread,
        "suggestion_count": suggestion_query.count(),
        "room_unreads": room_unreads,
    }


def _shared_calendar_event_queryset(workspace):
    return (
        SharedCalendarEvent.objects
        .filter(workspace=workspace)
        .select_related(
            "created_by_membership__user",
            "updated_by_membership__user",
        )
        .prefetch_related("copies__personal_event")
        .order_by("start_time", "created_at", "id")
    )


def get_shared_calendar_event_for_user(event_id, user):
    event = (
        SharedCalendarEvent.objects
        .select_related(
            "workspace",
            "created_by_membership__user",
            "updated_by_membership__user",
        )
        .prefetch_related("copies__personal_event")
        .filter(id=event_id)
        .first()
    )
    if event is None:
        return None, None
    membership = get_membership(event.workspace, user)
    if membership is None:
        return event, None
    return event, membership


def serialize_shared_calendar_event(event, *, user):
    copy_record = next((copy for copy in event.copies.all() if copy.user_id == user.id), None)
    personal_event = getattr(copy_record, "personal_event", None)
    return {
        "id": str(event.id),
        "title": event.title,
        "note": event.note,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "time_label": _shared_event_time_label(event),
        "is_all_day": event.is_all_day,
        "color": event.color or "emerald",
        "created_by_name": user_display_name(getattr(event.created_by_membership, "user", None)),
        "updated_by_name": user_display_name(getattr(event.updated_by_membership, "user", None)),
        "copy_to_main_url": reverse("schoolcomm:api_shared_calendar_event_copy_to_main", kwargs={"event_id": event.id}),
        "update_url": reverse("schoolcomm:api_shared_calendar_event_update", kwargs={"event_id": event.id}),
        "delete_url": reverse("schoolcomm:api_shared_calendar_event_delete", kwargs={"event_id": event.id}),
        "is_copied_to_main": bool(personal_event),
        "personal_event_id": str(personal_event.id) if personal_event else "",
        "personal_event_url": build_main_calendar_event_url(personal_event) if personal_event else "",
        "copy_button_label": "내 메인 캘린더에서 보기" if personal_event else "내 메인 캘린더로 보내기",
    }


def _build_shared_calendar_month_grid(events, *, current_month, selected_date):
    calendar_iter = calendar_module.Calendar(firstweekday=6)
    today = timezone.localtime().date()
    counts = {}
    for event in events:
        start_date, end_date = _shared_event_date_bounds(event)
        cursor = max(start_date, current_month)
        month_end = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        final_date = min(end_date, month_end)
        while cursor <= final_date:
            counts[cursor.isoformat()] = counts.get(cursor.isoformat(), 0) + 1
            cursor += timedelta(days=1)

    days = []
    for day in calendar_iter.itermonthdates(current_month.year, current_month.month):
        day_key = day.isoformat()
        days.append(
            {
                "date": day_key,
                "label": str(day.day),
                "is_current_month": day.month == current_month.month,
                "is_selected": day == selected_date,
                "is_today": day == today,
                "event_count": counts.get(day_key, 0),
                "has_events": counts.get(day_key, 0) > 0,
            }
        )
    return days


def build_shared_calendar_panel(workspace, user, *, month_value="", selected_date_value=""):
    membership = get_membership(workspace, user)
    if membership is None:
        raise MembershipRequiredError("채팅방 멤버만 끼리끼리 캘린더를 볼 수 있습니다.")

    current_month = _normalize_month_value(month_value)
    selected_date = _normalize_date_value(selected_date_value)
    today = timezone.localtime().date()
    if selected_date is None:
        if today.year == current_month.year and today.month == current_month.month:
            selected_date = today
        else:
            selected_date = current_month
    elif selected_date.month != current_month.month or selected_date.year != current_month.year:
        selected_date = current_month
    month_start = timezone.make_aware(datetime.combine(current_month, time.min), timezone.get_current_timezone())
    next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    next_month_start = timezone.make_aware(datetime.combine(next_month, time.min), timezone.get_current_timezone())
    month_events = list(
        _shared_calendar_event_queryset(workspace)
        .filter(start_time__lt=next_month_start, end_time__gte=month_start)
    )

    selected_events = [
        serialize_shared_calendar_event(event, user=user)
        for event in month_events
        if _shared_event_overlaps_date(event, selected_date)
    ]
    previous_month = (current_month - timedelta(days=1)).replace(day=1)
    return {
        "month": current_month.strftime("%Y-%m"),
        "month_label": current_month.strftime("%Y년 %m월"),
        "selected_date": selected_date.isoformat(),
        "selected_date_label": _format_date_label(selected_date),
        "previous_month": previous_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
        "days": _build_shared_calendar_month_grid(month_events, current_month=current_month, selected_date=selected_date),
        "selected_events": selected_events,
        "month_event_count": len(month_events),
    }


@transaction.atomic
def create_shared_calendar_event(
    workspace,
    membership,
    *,
    title,
    note="",
    start_time,
    end_time,
    is_all_day=False,
    color="emerald",
):
    if membership is None or membership.workspace_id != workspace.id or membership.status != SchoolMembership.Status.ACTIVE:
        raise MembershipRequiredError("채팅방 멤버만 끼리끼리 캘린더를 사용할 수 있습니다.")
    normalized_title = str(title or "").strip()
    if not normalized_title:
        raise ValidationError("일정 제목을 입력해 주세요.")
    if end_time < start_time:
        raise ValidationError("종료 시간이 시작 시간보다 빠를 수 없습니다.")
    return SharedCalendarEvent.objects.create(
        workspace=workspace,
        title=normalized_title[:200],
        note=str(note or "").strip(),
        start_time=start_time,
        end_time=end_time,
        is_all_day=bool(is_all_day),
        color=_normalize_shared_calendar_color(color),
        created_by_membership=membership,
        updated_by_membership=membership,
    )


@transaction.atomic
def update_shared_calendar_event(
    event,
    membership,
    *,
    title,
    note="",
    start_time,
    end_time,
    is_all_day=False,
    color="emerald",
):
    if membership is None or membership.workspace_id != event.workspace_id or membership.status != SchoolMembership.Status.ACTIVE:
        raise MembershipRequiredError("이 일정을 수정할 수 없습니다.")
    normalized_title = str(title or "").strip()
    if not normalized_title:
        raise ValidationError("일정 제목을 입력해 주세요.")
    if end_time < start_time:
        raise ValidationError("종료 시간이 시작 시간보다 빠를 수 없습니다.")
    event.title = normalized_title[:200]
    event.note = str(note or "").strip()
    event.start_time = start_time
    event.end_time = end_time
    event.is_all_day = bool(is_all_day)
    event.color = _normalize_shared_calendar_color(color)
    event.updated_by_membership = membership
    event.save(
        update_fields=[
            "title",
            "note",
            "start_time",
            "end_time",
            "is_all_day",
            "color",
            "updated_by_membership",
            "updated_at",
        ]
    )
    return event


@transaction.atomic
def delete_shared_calendar_event(event, membership):
    if membership is None or membership.workspace_id != event.workspace_id or membership.status != SchoolMembership.Status.ACTIVE:
        raise MembershipRequiredError("이 일정을 삭제할 수 없습니다.")
    event.delete()


@transaction.atomic
def copy_shared_calendar_event_to_main(event, user):
    membership = get_membership(event.workspace, user)
    if membership is None or membership.status != SchoolMembership.Status.ACTIVE:
        raise MembershipRequiredError("채팅방 멤버만 내 메인 캘린더로 보낼 수 있습니다.")

    copy_record, _ = SharedCalendarEventCopy.objects.select_for_update().get_or_create(
        shared_event=event,
        user=user,
    )
    previous_personal_event_id = copy_record.personal_event_id
    personal_event = copy_record.personal_event
    if personal_event and not CalendarEvent.objects.filter(id=personal_event.id, author=user).exists():
        personal_event = None
        copy_record.personal_event = None

    created = False
    if personal_event is None:
        personal_event = CalendarEvent.objects.create(
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            is_all_day=event.is_all_day,
            color=event.color or "emerald",
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            author=user,
            classroom=None,
            source=CalendarEvent.SOURCE_LOCAL,
            is_locked=False,
            integration_source=CALENDAR_COPY_INTEGRATION_SOURCE,
            integration_key=str(event.id),
        )
        if event.note:
            EventPageBlock.objects.create(
                event=personal_event,
                block_type="text",
                content={"text": event.note},
                order=0,
            )
        copy_record.personal_event = personal_event
        created = True

    copy_record.last_opened_at = timezone.now()
    update_fields = ["last_opened_at"]
    if previous_personal_event_id != getattr(personal_event, "id", None):
        copy_record.personal_event = personal_event
        update_fields.append("personal_event")
    copy_record.save(update_fields=update_fields)
    return personal_event, created


@transaction.atomic
def apply_calendar_suggestion_to_shared_calendar(suggestion, user):
    if suggestion.user_id != user.id:
        raise MembershipRequiredError("이 추천을 처리할 권한이 없습니다.")
    if suggestion.status != CalendarSuggestion.Status.PENDING:
        raise ValidationError("이미 처리한 추천입니다.")
    payload = suggestion.suggested_payload or {}
    source_message = suggestion.source_message
    workspace = getattr(getattr(source_message, "room", None), "workspace", None) or get_default_workspace_for_user(user, create=False)
    if workspace is None:
        raise ValidationError("추천 일정을 넣을 채팅방을 찾지 못했습니다.")
    membership = get_membership(workspace, user)
    if membership is None:
        raise MembershipRequiredError("채팅방 멤버만 추천 일정을 저장할 수 있습니다.")
    try:
        start_time = datetime.fromisoformat(str(payload.get("start_time") or ""))
        end_time = datetime.fromisoformat(str(payload.get("end_time") or ""))
    except ValueError as exc:
        raise ValidationError("추천 일정 시간이 올바르지 않습니다.") from exc
    if timezone.is_naive(start_time):
        start_time = timezone.make_aware(start_time, timezone.get_current_timezone())
    if timezone.is_naive(end_time):
        end_time = timezone.make_aware(end_time, timezone.get_current_timezone())
    shared_event = create_shared_calendar_event(
        workspace,
        membership,
        title=str(payload.get("title") or "끼리끼리 일정"),
        note=str(payload.get("note") or "").strip(),
        start_time=start_time,
        end_time=end_time,
        is_all_day=bool(payload.get("is_all_day")),
        color="emerald",
    )
    suggestion.status = CalendarSuggestion.Status.APPLIED
    suggestion.applied_at = timezone.now()
    suggestion.save(update_fields=["status", "applied_at", "updated_at"])
    broadcast_user_summary(user)
    return shared_event


def _normalize_category_code(raw_value):
    value = str(raw_value or "").strip().lower()
    mapping = {
        "수업자료": UserAssetCategory.Category.LESSON,
        "lesson": UserAssetCategory.Category.LESSON,
        "평가자료": UserAssetCategory.Category.ASSESSMENT,
        "assessment": UserAssetCategory.Category.ASSESSMENT,
        "업무": UserAssetCategory.Category.WORK,
        "work": UserAssetCategory.Category.WORK,
        "기타": UserAssetCategory.Category.OTHER,
        "other": UserAssetCategory.Category.OTHER,
        "미분류": UserAssetCategory.Category.UNCLASSIFIED,
        "unclassified": UserAssetCategory.Category.UNCLASSIFIED,
    }
    return mapping.get(value, UserAssetCategory.Category.UNCLASSIFIED)


def _run_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:  # pragma: no cover
            raise CategoryClassifierError("분류 요청이 시간 초과되었습니다.") from exc


def _call_category_classifier_llm(*, payload, timeout_seconds=20):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key or OpenAI is None:
        raise CategoryClassifierError("DeepSeek API key is not configured.")

    prompt = (
        "당신은 학교 교사들이 주고받은 파일을 분류하는 도우미입니다. "
        "반드시 JSON 객체만 반환하세요. category, confidence, reason 세 필드만 포함하세요. "
        "category는 lesson, assessment, work, other, unclassified 중 하나만 허용합니다. "
        "판단 시 파일명에 포함된 연도, 학기, 고사명, 과목명 규칙을 최우선으로 해석하세요."
    )

    def _request():
        client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=30.0)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            stream=False,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise CategoryClassifierError("DeepSeek returned an empty response.")
        return text

    raw_text = _run_with_timeout(_request, timeout_seconds=timeout_seconds)
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise CategoryClassifierError("DeepSeek returned invalid JSON.") from exc
    return {
        "category": _normalize_category_code(result.get("category")),
        "confidence": Decimal(str(result.get("confidence") or "0")),
        "reason": str(result.get("reason") or "").strip(),
    }


def _heuristic_category(asset, *, message_text="", room_kind=""):
    basis = " ".join(
        part
        for part in [
            str(asset.original_name or ""),
            str(asset.file_extension or ""),
            str(getattr(asset.blob, "mime_type", "") or ""),
            str(message_text or ""),
            str(room_kind or ""),
        ]
        if str(part or "").strip()
    ).lower()
    for category, hints in HEURISTIC_CATEGORY_HINTS:
        if any(hint.lower() in basis for hint in hints):
            return category, Decimal("0.88")
    return UserAssetCategory.Category.OTHER, Decimal("0.55")


def classify_asset(asset, *, message_text="", room_kind=""):
    payload = {
        "filename": asset.original_name,
        "extension": asset.file_extension,
        "mime_type": getattr(asset.blob, "mime_type", ""),
        "message_text": str(message_text or "")[:4000],
        "room_kind": room_kind,
    }
    try:
        result = _call_category_classifier_llm(payload=payload)
        category = _normalize_category_code(result.get("category"))
        confidence = Decimal(str(result.get("confidence") or "0"))
        if category == UserAssetCategory.Category.UNCLASSIFIED:
            fallback_category, fallback_confidence = _heuristic_category(asset, message_text=message_text, room_kind=room_kind)
            if fallback_category != UserAssetCategory.Category.OTHER:
                return fallback_category, max(confidence, fallback_confidence)
        return category, confidence
    except CategoryClassifierError:
        return _heuristic_category(asset, message_text=message_text, room_kind=room_kind)


def ensure_user_asset_category(user, asset, *, message_text="", room_kind=""):
    category = UserAssetCategory.objects.filter(user=user, asset=asset).first()
    if category and category.source == UserAssetCategory.Source.MANUAL:
        return category
    guessed_category, confidence = classify_asset(asset, message_text=message_text, room_kind=room_kind)
    if category is None:
        return UserAssetCategory.objects.create(
            user=user,
            asset=asset,
            category=guessed_category,
            confidence=confidence,
            source=UserAssetCategory.Source.AUTO,
        )
    category.category = guessed_category
    category.confidence = confidence
    category.source = UserAssetCategory.Source.AUTO
    category.save(update_fields=["category", "confidence", "source", "updated_at"])
    return category


def update_user_asset_category(user, asset, category_code):
    normalized = _normalize_category_code(category_code)
    category, _ = UserAssetCategory.objects.get_or_create(user=user, asset=asset)
    category.category = normalized
    category.confidence = Decimal("1.00")
    category.source = UserAssetCategory.Source.MANUAL
    category.save(update_fields=["category", "confidence", "source", "updated_at"])
    return category


def _file_extension(filename):
    return os.path.splitext(str(filename or ""))[1].lower()


def _uploaded_file_bytes_and_checksum(uploaded_file):
    hasher = hashlib.sha256()
    chunks = []
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
        chunks.append(chunk)
    return b"".join(chunks), hasher.hexdigest()


@transaction.atomic
def create_shared_asset_from_upload(uploaded_file, *, uploader, message):
    file_bytes, checksum = _uploaded_file_bytes_and_checksum(uploaded_file)
    extension = _file_extension(uploaded_file.name)
    blob = StoredAssetBlob.objects.filter(checksum_sha256=checksum).first()
    if blob is None:
        storage_key = f"schoolcomm/blobs/{checksum[:2]}/{checksum}{extension}"
        blob = StoredAssetBlob(
            checksum_sha256=checksum,
            storage_key=storage_key,
            mime_type=str(getattr(uploaded_file, "content_type", "") or "application/octet-stream"),
            size_bytes=len(file_bytes),
        )
        blob.file.save(storage_key, ContentFile(file_bytes), save=False)
        blob.save()
    asset = SharedAsset.objects.create(
        blob=blob,
        uploader=uploader,
        uploader_name_snapshot=user_display_name(uploader),
        original_name=str(uploaded_file.name or "자료"),
        file_extension=extension,
    )
    MessageAssetLink.objects.create(message=message, asset=asset)
    ensure_user_asset_category(
        uploader,
        asset,
        message_text=message.body,
        room_kind=message.room.room_kind,
    )
    return asset


def _calendar_payload_from_message(message, has_files=False):
    parsed = parse_message_capture_draft(
        message.body,
        now=message.created_at,
        has_files=has_files,
    )
    if not parsed or parsed.get("parse_status") == "failed":
        return None
    start_time = parsed.get("extracted_start_time")
    end_time = parsed.get("extracted_end_time")
    if not start_time or not end_time:
        return None
    return {
        "title": parsed.get("extracted_title") or _truncate(message.body, limit=50) or "끼리끼리 일정",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "is_all_day": bool(parsed.get("extracted_is_all_day")),
        "note": parsed.get("extracted_todo_summary") or _truncate(message.body, limit=120),
        "source_room_id": str(message.room_id),
        "source_message_id": str(message.id),
    }


def create_calendar_suggestions_for_message(message, *, assets=None):
    assets = list(assets or [])
    payload = _calendar_payload_from_message(message, has_files=bool(assets))
    if not payload:
        return []

    participants = (
        RoomParticipant.objects.select_related("membership__user")
        .filter(room=message.room, membership__status=SchoolMembership.Status.ACTIVE)
    )
    suggestions = []
    for participant in participants:
        suggestion = CalendarSuggestion.objects.create(
            user=participant.membership.user,
            source_message=message,
            source_asset=assets[0] if assets else None,
            suggested_payload=payload,
        )
        suggestions.append(suggestion)
        broadcast_user_summary(participant.membership.user)
    return suggestions


@transaction.atomic
def create_room_message(room, membership, *, text="", parent_message=None, uploads=None):
    uploads = list(uploads or [])
    body = str(text or "").strip()
    if not body and not uploads:
        raise ValidationError("메시지 또는 첨부파일 중 하나는 필요합니다.")
    if room.room_kind == CommunityRoom.RoomKind.NOTICE and parent_message is None and not membership_can_post_notice(membership):
        raise ValidationError("공지방 최상위 글은 관리자만 작성할 수 있습니다.")
    if parent_message and parent_message.parent_message_id:
        raise ValidationError("답글은 한 단계까지만 허용됩니다.")

    message = RoomMessage.objects.create(
        room=room,
        sender=membership.user,
        sender_membership=membership,
        sender_name_snapshot=user_display_name(membership.user),
        sender_membership_snapshot=membership.role,
        parent_message=parent_message,
        body=body,
    )
    room.last_message_at = message.created_at
    room.save(update_fields=["last_message_at", "updated_at"])

    assets = [create_shared_asset_from_upload(upload, uploader=membership.user, message=message) for upload in uploads]

    if parent_message:
        parent_message.reply_count = parent_message.replies.count()
        parent_message.last_replied_at = message.created_at
        parent_message.save(update_fields=["reply_count", "last_replied_at", "updated_at"])

    for participant in room.participants.select_related("membership__user"):
        if participant.membership.status != SchoolMembership.Status.ACTIVE:
            continue
        ensure_user_room_state(room, participant.membership.user)

    ensure_user_room_state(room, membership.user)
    mark_room_read(membership.user, room, latest_message=message)
    (
        UserRoomState.objects
        .filter(room=room)
        .exclude(user=membership.user)
        .update(unread_count_cache=F("unread_count_cache") + 1, updated_at=timezone.now())
    )

    for participant in room.participants.select_related("membership__user"):
        if participant.membership.user_id == membership.user_id:
            continue
        if participant.membership.status != SchoolMembership.Status.ACTIVE:
            continue
        broadcast_user_summary(participant.membership.user)

    create_calendar_suggestions_for_message(message, assets=assets)
    broadcast_room_event(
        room,
        "room.message",
        {
            "room_id": str(room.id),
            "message_id": str(message.id),
            "parent_message_id": str(parent_message.id) if parent_message else "",
        },
    )
    return message


@transaction.atomic
def toggle_ack_reaction(message, user):
    reaction = MessageReaction.objects.filter(
        message=message,
        user=user,
        reaction_type=MessageReaction.ReactionType.ACK,
    ).first()
    is_active = False
    if reaction:
        reaction.delete()
    else:
        MessageReaction.objects.create(
            message=message,
            user=user,
            reaction_type=MessageReaction.ReactionType.ACK,
        )
        is_active = True
    broadcast_room_event(
        message.room,
        "room.reaction",
        {"room_id": str(message.room_id), "message_id": str(message.id)},
    )
    return is_active


def serialize_asset(asset, *, user):
    link = asset.message_links.select_related("message__room").first()
    category = ensure_user_asset_category(
        user,
        asset,
        message_text=(link.message.body if link else ""),
        room_kind=(link.message.room.room_kind if link else ""),
    )
    return {
        "id": str(asset.id),
        "original_name": asset.original_name,
        "extension": asset.file_extension,
        "uploader_name": asset.uploader_name_snapshot,
        "download_url": reverse("schoolcomm:api_asset_download", kwargs={"asset_id": asset.id}),
        "category_update_url": reverse("schoolcomm:api_asset_category", kwargs={"asset_id": asset.id}),
        "category": category.category,
        "category_label": CATEGORY_LABELS.get(category.category, "미분류"),
        "category_source": category.source,
        "confidence": float(category.confidence or 0),
        "room_id": str(link.message.room_id) if link and link.message else "",
        "room_name": link.message.room.name if link and link.message and link.message.room else "",
        "room_url": reverse("schoolcomm:room_detail", kwargs={"room_id": link.message.room_id}) if link and link.message else "",
    }


def serialize_message(message, *, user):
    assets = [serialize_asset(link.asset, user=user) for link in message.asset_links.select_related("asset__blob").all()]
    ack_user_ids = list(
        message.reactions.filter(reaction_type=MessageReaction.ReactionType.ACK).values_list("user_id", flat=True)
    )
    parent_message = getattr(message, "parent_message", None)
    return {
        "id": str(message.id),
        "room_id": str(message.room_id),
        "parent_message_id": str(message.parent_message_id) if message.parent_message_id else "",
        "parent_sender_name": parent_message.sender_name_snapshot if parent_message else "",
        "parent_preview": _truncate(parent_message.body, limit=40) if parent_message and parent_message.body else "",
        "sender_name": message.sender_name_snapshot,
        "sender_role": message.sender_membership_snapshot,
        "is_mine": bool(user and message.sender_id == user.id),
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "created_at_label": _format_datetime_label(message.created_at),
        "reply_count": message.reply_count,
        "last_replied_at": message.last_replied_at.isoformat() if message.last_replied_at else "",
        "ack_count": len(ack_user_ids),
        "acked_by_me": user.id in ack_user_ids,
        "assets": assets,
        "reaction_url": reverse("schoolcomm:api_message_reactions", kwargs={"message_id": message.id}),
        "thread_url": reverse("schoolcomm:api_message_thread", kwargs={"message_id": message.id}),
        "reply_post_url": reverse("schoolcomm:api_room_messages", kwargs={"room_id": message.room_id}),
    }


def build_room_summary(room, *, user):
    latest_message = _latest_room_message(room)
    state = UserRoomState.objects.filter(room=room, user=user).first()
    summary = ""
    if latest_message:
        summary = latest_message.body or (
            latest_message.asset_links.select_related("asset").first().asset.original_name
            if latest_message.asset_links.exists()
            else ""
        )
    return {
        "id": str(room.id),
        "name": room.name,
        "room_kind": room.room_kind,
        "url": reverse("schoolcomm:room_detail", kwargs={"room_id": room.id}),
        "unread_count": int(getattr(state, "unread_count_cache", 0) or 0),
        "summary": _truncate(summary, limit=60),
        "last_message_at": latest_message.created_at if latest_message else room.updated_at,
    }


def serialize_calendar_suggestion(suggestion):
    payload = suggestion.suggested_payload or {}
    return {
        "id": str(suggestion.id),
        "title": str(payload.get("title") or "추천 일정"),
        "start_time": str(payload.get("start_time") or ""),
        "start_time_label": _format_iso_datetime_label(payload.get("start_time")),
        "end_time": str(payload.get("end_time") or ""),
        "is_all_day": bool(payload.get("is_all_day")),
        "note": str(payload.get("note") or ""),
        "status": suggestion.status,
        "apply_url": reverse("schoolcomm:api_apply_calendar_suggestion", kwargs={"suggestion_id": suggestion.id}),
        "apply_label": "끼리끼리 캘린더에 넣기",
        "helper_text": "내 캘린더에서는 독립 일정으로 관리됩니다.",
    }


def _workspace_rooms_for_user(workspace, user):
    membership = get_membership(workspace, user)
    if membership is None:
        return CommunityRoom.objects.none()
    ensure_default_rooms(workspace, created_by=workspace.created_by)
    _sync_room_participants_with_workspace(get_default_room(workspace, CommunityRoom.RoomKind.NOTICE))
    _sync_room_participants_with_workspace(get_default_room(workspace, CommunityRoom.RoomKind.SHARED))
    return (
        CommunityRoom.objects
        .filter(participants__membership=membership)
        .distinct()
        .order_by("-last_message_at", "name")
    )


def build_workspace_dashboard(workspace, user):
    membership = get_membership(workspace, user)
    if membership is None:
        raise MembershipRequiredError("채팅방 멤버가 아닙니다.")

    notice_room = get_default_room(workspace, CommunityRoom.RoomKind.NOTICE)
    shared_room = get_default_room(workspace, CommunityRoom.RoomKind.SHARED)
    rooms = _workspace_rooms_for_user(workspace, user)
    dm_rooms = rooms.filter(room_kind__in=[CommunityRoom.RoomKind.DM, CommunityRoom.RoomKind.GROUP_DM])[:12]
    suggestions = CalendarSuggestion.objects.filter(
        user=user,
        status=CalendarSuggestion.Status.PENDING,
        source_message__room__workspace=workspace,
    )[:8]
    pending_memberships = []
    if membership_can_manage_workspace(membership):
        pending_memberships = list(
            workspace.memberships.select_related("user")
            .filter(status=SchoolMembership.Status.PENDING)
            .order_by("created_at")
        )
    active_members = list(
        workspace.memberships.select_related("user")
        .filter(status=SchoolMembership.Status.ACTIVE)
        .order_by("role", "user__username")
    )
    return {
        "workspace": workspace,
        "membership": membership,
        "can_manage": membership_can_manage_workspace(membership),
        "member_count": len(active_members),
        "pending_count": len(pending_memberships),
        "notice_room": build_room_summary(notice_room, user=user) if notice_room else None,
        "shared_room": build_room_summary(shared_room, user=user) if shared_room else None,
        "dm_rooms": [build_room_summary(room, user=user) for room in dm_rooms],
        "members": active_members,
        "pending_memberships": pending_memberships,
        "notification_summary": build_notification_summary(user, workspace=workspace),
        "calendar_suggestions": [serialize_calendar_suggestion(suggestion) for suggestion in suggestions],
    }


def search_workspace(workspace, user, query, *, page_number=1, per_page=12):
    membership = get_membership(workspace, user)
    if membership is None:
        raise MembershipRequiredError("채팅방 멤버만 검색할 수 있습니다.")
    query_text = str(query or "").strip()
    if not query_text:
        return {"query": "", "messages_page": None, "assets_page": None, "room_matches": []}

    accessible_room_ids = RoomParticipant.objects.filter(membership=membership).values_list("room_id", flat=True)
    room_matches = list(
        CommunityRoom.objects.filter(id__in=accessible_room_ids, name__icontains=query_text).order_by("name")[:8]
    )
    message_queryset = (
        RoomMessage.objects.select_related("room")
        .filter(room_id__in=accessible_room_ids, parent_message__isnull=True, body__icontains=query_text)
        .order_by("-created_at")
    )
    asset_queryset = (
        SharedAsset.objects.select_related("blob")
        .filter(message_links__message__room_id__in=accessible_room_ids)
        .prefetch_related("message_links__message__room")
        .filter(
            Q(original_name__icontains=query_text)
            | Q(file_extension__icontains=query_text)
            | Q(uploader_name_snapshot__icontains=query_text)
            | Q(message_links__message__body__icontains=query_text)
        )
        .distinct()
        .order_by("-created_at")
    )
    return {
        "query": query_text,
        "messages_page": Paginator(message_queryset, per_page).get_page(page_number),
        "assets_page": Paginator(asset_queryset, per_page).get_page(page_number),
        "room_matches": room_matches,
    }


def search_workspace_assets(workspace, user, query, *, page_number=1, per_page=16):
    membership = get_membership(workspace, user)
    if membership is None:
        raise MembershipRequiredError("워크스페이스 멤버만 검색할 수 있습니다.")
    query_text = str(query or "").strip()
    accessible_room_ids = RoomParticipant.objects.filter(membership=membership).values_list("room_id", flat=True)
    queryset = (
        SharedAsset.objects.select_related("blob")
        .filter(message_links__message__room_id__in=accessible_room_ids)
        .distinct()
        .order_by("-created_at")
    )
    if query_text:
        queryset = queryset.filter(
            Q(original_name__icontains=query_text)
            | Q(file_extension__icontains=query_text)
            | Q(uploader_name_snapshot__icontains=query_text)
        )
    return Paginator(queryset, per_page).get_page(page_number)


def build_home_card(user):
    product = get_service_product()
    if product is None:
        return None

    workspace = get_default_workspace_for_user(user, create=False)
    if workspace is None:
        return {
            "title": getattr(product, "public_service_name", "") or SERVICE_TITLE,
            "summary": "동학년 선생님부터 편하게 공지, 자료, 일정을 나눠 보세요.",
            "workspace_name": "",
            "manage_url": reverse("schoolcomm:main"),
            "open_url": reverse("schoolcomm:main"),
            "shortcut_url": reverse("schoolcomm:main"),
            "shortcut_aria_label": "끼리끼리 채팅방 열기",
            "shortcut_symbol": "+",
            "secondary_url": reverse("schoolcomm:main"),
            "secondary_label": "채팅방 만들기",
            "icon_text": "💬",
            "primary_label": "채팅방 열기",
            "total_unread": 0,
            "notice_unread": 0,
            "suggestion_count": 0,
        }

    dashboard = build_workspace_dashboard(workspace, user)
    notification_summary = dashboard["notification_summary"]
    notice_room = get_default_room(workspace, CommunityRoom.RoomKind.NOTICE)
    shared_room = get_default_room(workspace, CommunityRoom.RoomKind.SHARED)
    latest_message = _latest_room_message(notice_room) or (_latest_room_message(shared_room) if shared_room else None)
    summary = ""
    if latest_message:
        summary = _truncate(latest_message.body or "", limit=72)
    if not summary:
        summary = f"미확인 {notification_summary['total_unread']}건 · 추천 {notification_summary['suggestion_count']}건"
    secondary_url = reverse("schoolcomm:room_detail", kwargs={"room_id": notice_room.id}) if notification_summary["notice_unread"] and notice_room else (
        reverse("schoolcomm:room_detail", kwargs={"room_id": shared_room.id}) if shared_room else reverse("schoolcomm:main")
    )
    secondary_label = "공지 확인" if notification_summary["notice_unread"] and notice_room else "자료공유 열기"
    return {
        "title": getattr(product, "public_service_name", "") or SERVICE_TITLE,
        "workspace_name": workspace.name,
        "summary": summary,
        "manage_url": reverse("schoolcomm:main"),
        "open_url": reverse("schoolcomm:main"),
        "shortcut_url": reverse("schoolcomm:main"),
        "shortcut_aria_label": "끼리끼리 채팅방 열기",
        "shortcut_symbol": "+",
        "secondary_url": secondary_url,
        "secondary_label": secondary_label,
        "icon_text": "💬",
        "primary_label": "채팅방 열기",
        "total_unread": notification_summary["total_unread"],
        "notice_unread": notification_summary["notice_unread"],
        "suggestion_count": notification_summary["suggestion_count"],
    }


@transaction.atomic
def create_invite(workspace, *, inviter, email="", role=SchoolMembership.Role.MEMBER, expires_at=None):
    membership = get_membership(workspace, inviter)
    if not membership_can_manage_workspace(membership):
        raise MembershipRequiredError("초대 링크를 만들 권한이 없습니다.")
    return WorkspaceInvite.objects.create(
        workspace=workspace,
        token=secrets.token_urlsafe(24),
        email=str(email or "").strip(),
        invited_by=inviter,
        role=role,
        expires_at=expires_at or (timezone.now() + timedelta(days=14)),
    )


@transaction.atomic
def accept_invite(invite, user):
    if invite.status in {WorkspaceInvite.Status.REVOKED, WorkspaceInvite.Status.EXPIRED}:
        raise ValidationError("이 초대 링크는 더 이상 사용할 수 없습니다.")
    if invite.expires_at and invite.expires_at < timezone.now():
        invite.status = WorkspaceInvite.Status.EXPIRED
        invite.save(update_fields=["status", "updated_at"])
        raise ValidationError("초대 링크가 만료되었습니다.")
    approver = invite.invited_by or invite.workspace.created_by
    membership, _ = SchoolMembership.objects.get_or_create(
        workspace=invite.workspace,
        user=user,
        defaults={
            "role": invite.role,
            "status": SchoolMembership.Status.ACTIVE,
            "invited_by": invite.invited_by,
            "approved_by": approver,
            "joined_at": timezone.now(),
        },
    )
    update_fields = []
    if membership.status != SchoolMembership.Status.ACTIVE:
        membership.role = invite.role
        update_fields.append("role")
    if membership.invited_by_id != getattr(invite.invited_by, "id", None):
        membership.invited_by = invite.invited_by
        update_fields.append("invited_by")
    if update_fields:
        membership.save(update_fields=[*update_fields, "updated_at"])
    membership = _activate_membership(membership, approver=approver)
    invite.status = WorkspaceInvite.Status.ACCEPTED
    invite.accepted_by = user
    invite.accepted_at = timezone.now()
    invite.save(update_fields=["status", "accepted_by", "accepted_at", "updated_at"])
    return membership


@transaction.atomic
def approve_membership(membership, approver):
    approver_membership = get_membership(membership.workspace, approver)
    if not membership_can_manage_workspace(approver_membership):
        raise MembershipRequiredError("멤버 승인 권한이 없습니다.")
    return _activate_membership(membership, approver=approver)


def user_can_download_asset(user, asset):
    return SharedAsset.objects.filter(
        id=asset.id,
        message_links__message__room__participants__membership__user=user,
        message_links__message__room__participants__membership__status=SchoolMembership.Status.ACTIVE,
    ).exists()
