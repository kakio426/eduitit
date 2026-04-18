from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.home_agent_quota import build_home_agent_quota_snapshot

from .models import DeveloperChatMessage, DeveloperChatReadState, DeveloperChatThread


THREAD_URL_PLACEHOLDER = 123456789
THREAD_LIST_PAGE_SIZE = 60
HOME_PREVIEW_THREAD_LIMIT = 3


def is_developer_chat_admin(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    )


def _safe_profile(user):
    try:
        return user.userprofile
    except Exception:
        return None


def user_display_name(user):
    profile = _safe_profile(user)
    nickname = str(getattr(profile, "nickname", "") or "").strip()
    if nickname:
        return nickname
    full_name = str(user.get_full_name() or "").strip()
    if full_name:
        return full_name
    return user.username


def user_secondary_label(user):
    parts = [str(user.username or "").strip()]
    email = str(getattr(user, "email", "") or "").strip()
    if email:
        parts.append(email)
    return " · ".join(part for part in parts if part)


def get_developer_chat_page_url(*, thread_id=None):
    try:
        base_url = reverse("messagebox:developer_chat")
    except NoReverseMatch:
        return ""
    if thread_id:
        return f"{base_url}?thread={thread_id}"
    return base_url


def build_developer_chat_api_urls():
    return {
        "list": reverse("messagebox:developer_chat_threads"),
        "detail_template": reverse(
            "messagebox:developer_chat_thread_detail",
            kwargs={"thread_id": THREAD_URL_PLACEHOLDER},
        ).replace(str(THREAD_URL_PLACEHOLDER), "__thread_id__"),
        "send_template": reverse(
            "messagebox:developer_chat_send_message",
            kwargs={"thread_id": THREAD_URL_PLACEHOLDER},
        ).replace(str(THREAD_URL_PLACEHOLDER), "__thread_id__"),
        "read_template": reverse(
            "messagebox:developer_chat_mark_read",
            kwargs={"thread_id": THREAD_URL_PLACEHOLDER},
        ).replace(str(THREAD_URL_PLACEHOLDER), "__thread_id__"),
        "delete_template": reverse(
            "messagebox:developer_chat_delete_thread",
            kwargs={"thread_id": THREAD_URL_PLACEHOLDER},
        ).replace(str(THREAD_URL_PLACEHOLDER), "__thread_id__"),
        "grant_template": reverse(
            "messagebox:developer_chat_grant_quota",
            kwargs={"thread_id": THREAD_URL_PLACEHOLDER},
        ).replace(str(THREAD_URL_PLACEHOLDER), "__thread_id__"),
    }


def get_or_create_developer_chat_thread(user):
    thread, _ = DeveloperChatThread.objects.get_or_create(participant=user)
    return thread


def get_existing_developer_chat_thread(user):
    return (
        DeveloperChatThread.objects
        .select_related("participant", "assigned_admin", "participant__userprofile", "assigned_admin__userprofile")
        .filter(participant=user)
        .first()
    )


def get_developer_chat_thread_queryset():
    return DeveloperChatThread.objects.select_related(
        "participant",
        "assigned_admin",
        "participant__userprofile",
        "assigned_admin__userprofile",
    )


def user_can_access_developer_chat_thread(user, thread):
    if not getattr(user, "is_authenticated", False):
        return False
    if is_developer_chat_admin(user):
        return True
    return thread.participant_id == user.id


def _participant_search_query(raw_query):
    query = str(raw_query or "").strip()
    if not query:
        return Q()
    return (
        Q(participant__username__icontains=query)
        | Q(participant__email__icontains=query)
        | Q(participant__first_name__icontains=query)
        | Q(participant__last_name__icontains=query)
        | Q(participant__userprofile__nickname__icontains=query)
    )


def list_developer_chat_threads_for_user(
    user,
    *,
    query="",
    include_empty_user_thread=False,
    unread_only=False,
    limit=THREAD_LIST_PAGE_SIZE,
):
    if is_developer_chat_admin(user):
        queryset = get_developer_chat_thread_queryset().exclude(last_message_at__isnull=True)
        if str(query or "").strip():
            queryset = queryset.filter(_participant_search_query(query))
        if not unread_only:
            return list(queryset[:limit] if limit is not None else queryset)

        threads = []
        for thread in queryset:
            if get_thread_unread_count(thread, user) <= 0:
                continue
            threads.append(thread)
            if limit is not None and len(threads) >= limit:
                break
        return threads

    thread = get_or_create_developer_chat_thread(user) if include_empty_user_thread else get_existing_developer_chat_thread(user)
    if not thread:
        return []
    if unread_only and get_thread_unread_count(thread, user) <= 0:
        return []
    return [thread]


def get_thread_read_state(thread, user):
    return DeveloperChatReadState.objects.filter(thread=thread, user=user).first()


def get_thread_unread_count(thread, user):
    if not getattr(user, "is_authenticated", False):
        return 0

    queryset = thread.messages.exclude(sender_id=user.id)
    read_state = get_thread_read_state(thread, user)
    if read_state and read_state.last_read_at:
        queryset = queryset.filter(created_at__gt=read_state.last_read_at)
    return queryset.count()


def mark_thread_as_read(thread, user, *, read_at=None):
    if not getattr(user, "is_authenticated", False):
        return None

    timestamp = read_at or timezone.now()
    read_state, _ = DeveloperChatReadState.objects.get_or_create(thread=thread, user=user)
    if read_state.last_read_at and read_state.last_read_at >= timestamp:
        return read_state
    read_state.last_read_at = timestamp
    read_state.save(update_fields=["last_read_at", "updated_at"])
    return read_state


def create_developer_chat_message(thread, user, body):
    body_text = str(body or "").strip()
    if not body_text:
        raise ValueError("메시지 내용을 입력해 주세요.")

    message = DeveloperChatMessage.objects.create(
        thread=thread,
        sender=user,
        sender_role=(
            DeveloperChatMessage.SenderRole.ADMIN
            if is_developer_chat_admin(user)
            else DeveloperChatMessage.SenderRole.USER
        ),
        body=body_text,
    )
    mark_thread_as_read(thread, user, read_at=message.created_at)
    return message


def _thread_status_label(thread, viewer):
    if not thread.last_message_at:
        return "대화 시작 전"
    if is_developer_chat_admin(viewer):
        return "답변 필요" if thread.last_message_sender_role == DeveloperChatMessage.SenderRole.USER else "관리자 응답"
    return "보낸 문의" if thread.last_message_sender_role == DeveloperChatMessage.SenderRole.USER else "개발자 답장"


def serialize_thread_summary(thread, viewer):
    is_admin_viewer = is_developer_chat_admin(viewer)
    unread_count = get_thread_unread_count(thread, viewer)
    participant_name = user_display_name(thread.participant)
    assigned_admin_name = user_display_name(thread.assigned_admin) if thread.assigned_admin else ""
    return {
        "id": thread.id,
        "title": participant_name if is_admin_viewer else "개발자야 도와줘",
        "subtitle": (
            user_secondary_label(thread.participant)
            if is_admin_viewer
            else (f"{assigned_admin_name}님이 보고 있어요." if assigned_admin_name else "문의와 오류, 개선 요청을 바로 남길 수 있어요.")
        ),
        "participant_name": participant_name,
        "participant_username": thread.participant.username,
        "participant_email": str(thread.participant.email or "").strip(),
        "last_message_preview": thread.last_message_preview or ("아직 메시지가 없어요." if not is_admin_viewer else "아직 시작되지 않은 대화입니다."),
        "last_message_at": thread.last_message_at.isoformat() if thread.last_message_at else "",
        "last_message_sender_role": thread.last_message_sender_role or "",
        "status_label": _thread_status_label(thread, viewer),
        "unread_count": unread_count,
        "detail_url": get_developer_chat_page_url(thread_id=thread.id),
    }


def serialize_chat_message(message, viewer):
    viewer_is_admin = is_developer_chat_admin(viewer)
    sender_name = user_display_name(message.sender)
    is_mine = (
        message.sender_role == DeveloperChatMessage.SenderRole.ADMIN
        if viewer_is_admin
        else message.sender_id == viewer.id
    )
    return {
        "id": message.id,
        "sender_role": message.sender_role,
        "sender_name": sender_name,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "is_mine": is_mine,
    }


def serialize_thread_detail(thread, viewer):
    messages = [
        serialize_chat_message(message, viewer)
        for message in thread.messages.select_related("sender").all()
    ]
    participant_name = user_display_name(thread.participant)
    assigned_admin_name = user_display_name(thread.assigned_admin) if thread.assigned_admin else ""
    quota_snapshot = build_home_agent_quota_snapshot(thread.participant)
    return {
        **serialize_thread_summary(thread, viewer),
        "participant": {
            "id": thread.participant_id,
            "display_name": participant_name,
            "secondary_label": user_secondary_label(thread.participant),
            "home_agent_quota": {
                **quota_snapshot,
                "grant_url": reverse(
                    "messagebox:developer_chat_grant_quota",
                    kwargs={"thread_id": thread.id},
                ) if is_developer_chat_admin(viewer) else "",
            },
        },
        "assigned_admin_name": assigned_admin_name,
        "messages": messages,
        "can_delete": True,
    }


def build_developer_chat_home_card_context(user):
    card = {
        "enabled": bool(getattr(user, "is_authenticated", False)),
        "title": "개발자야 도와줘",
        "summary": "",
        "cta_label": "메시지 열기",
        "url": get_developer_chat_page_url(),
        "preview_threads": [],
        "is_admin": False,
        "unread_count": 0,
        "unread_thread_count": 0,
    }
    if not card["enabled"]:
        return card

    is_admin_view = is_developer_chat_admin(user)
    card["is_admin"] = is_admin_view
    unread_threads = list_developer_chat_threads_for_user(
        user,
        include_empty_user_thread=False,
        unread_only=True,
        limit=None,
    )
    serialized_unread_threads = [serialize_thread_summary(thread, user) for thread in unread_threads]
    unread_count = sum(item["unread_count"] for item in serialized_unread_threads)
    unread_thread_count = len(serialized_unread_threads)

    card["preview_threads"] = serialized_unread_threads[:HOME_PREVIEW_THREAD_LIMIT]
    card["unread_count"] = unread_count
    card["unread_thread_count"] = unread_thread_count

    if is_admin_view:
        if unread_thread_count:
            card["summary"] = f"새로 확인할 대화 {unread_thread_count}명, 안 읽은 메시지 {unread_count}건입니다."
        return card

    if unread_count:
        card["summary"] = "새 답장이 도착했어요."
    return card
