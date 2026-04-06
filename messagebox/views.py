import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST

from products.models import Product

from classcalendar.views import build_message_capture_ui_context
from .developer_chat import (
    build_developer_chat_api_urls,
    build_developer_chat_home_card_context,
    create_developer_chat_message,
    get_developer_chat_page_url,
    get_or_create_developer_chat_thread,
    get_thread_unread_count,
    get_developer_chat_thread_queryset,
    is_developer_chat_admin,
    list_developer_chat_threads_for_user,
    mark_thread_as_read,
    serialize_thread_detail,
    serialize_thread_summary,
    user_can_access_developer_chat_thread,
)


SERVICE_ROUTE = "messagebox:main"
DEFAULT_SERVICE_TITLE = "AI 업무 메시지 보관함"


def _messagebox_display_title(service):
    base_title = service.title if service else DEFAULT_SERVICE_TITLE
    if base_title.startswith("AI "):
        return base_title[3:]
    return base_title


@login_required
@xframe_options_sameorigin
def main_view(request):
    service = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
    message_capture_ui = build_message_capture_ui_context(request.user)
    initial_capture_id = str(request.GET.get("capture") or "").strip()
    display_title = _messagebox_display_title(service)
    context = {
        "service": service,
        "title": display_title,
        "page_title": display_title,
        "page_subtitle": "",
        "message_capture_enabled": message_capture_ui["enabled"],
        "message_capture_item_types_enabled": message_capture_ui["item_types_enabled"],
        "message_capture_limits_json": message_capture_ui["limits"],
        "message_capture_urls_json": message_capture_ui["urls"],
        "initial_capture_id": initial_capture_id,
        "calendar_main_url": reverse("calendar_main"),
    }
    return render(request, "messagebox/main.html", context)


def _developer_chat_permission_denied():
    return JsonResponse(
        {
            "status": "error",
            "message": "이 대화에 접근할 권한이 없습니다.",
        },
        status=403,
    )


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


@login_required
def developer_chat_view(request):
    is_admin_view = is_developer_chat_admin(request.user)
    requested_thread_id = str(request.GET.get("thread") or "").strip()
    initial_thread_id = ""
    if is_admin_view:
        if requested_thread_id.isdigit():
            initial_thread_id = requested_thread_id
    else:
        initial_thread = get_or_create_developer_chat_thread(request.user)
        initial_thread_id = str(initial_thread.id)

    context = {
        "page_title": "개발자야 도와줘",
        "title": "개발자야 도와줘",
        "page_subtitle": (
            "여러 사용자 문의를 한 화면에서 넘겨보며 답장할 수 있는 관리자용 1:1 채팅함입니다."
            if is_admin_view
            else "불편한 점, 오류, 필요한 기능을 개발자에게 바로 남길 수 있는 1:1 채팅입니다."
        ),
        "developer_chat_is_admin": is_admin_view,
        "developer_chat_initial_thread_id": initial_thread_id,
        "developer_chat_api_urls_json": build_developer_chat_api_urls(),
        "developer_chat_page_url": get_developer_chat_page_url(),
        "developer_chat_home_card": build_developer_chat_home_card_context(request.user),
    }
    return render(request, "messagebox/developer_chat.html", context)


@require_GET
@login_required
def developer_chat_threads_api(request):
    query = str(request.GET.get("q") or "").strip()
    threads = list_developer_chat_threads_for_user(
        request.user,
        query=query,
        include_empty_user_thread=not is_developer_chat_admin(request.user),
    )
    return JsonResponse(
        {
            "status": "ok",
            "threads": [serialize_thread_summary(thread, request.user) for thread in threads],
            "is_admin": is_developer_chat_admin(request.user),
        }
    )


@require_GET
@login_required
def developer_chat_thread_detail_api(request, thread_id):
    thread = get_object_or_404(get_developer_chat_thread_queryset(), id=thread_id)
    if not user_can_access_developer_chat_thread(request.user, thread):
        return _developer_chat_permission_denied()
    return JsonResponse(
        {
            "status": "ok",
            "thread": serialize_thread_detail(thread, request.user),
        }
    )


@require_POST
@login_required
def developer_chat_send_message_api(request, thread_id):
    thread = get_object_or_404(get_developer_chat_thread_queryset(), id=thread_id)
    if not user_can_access_developer_chat_thread(request.user, thread):
        return _developer_chat_permission_denied()

    payload = _json_body(request)
    if payload is None:
        return JsonResponse(
            {
                "status": "error",
                "message": "잘못된 요청 형식입니다.",
            },
            status=400,
        )

    try:
        create_developer_chat_message(thread, request.user, payload.get("body"))
    except ValueError as exc:
        return JsonResponse(
            {
                "status": "error",
                "message": str(exc),
            },
            status=400,
        )

    thread = get_object_or_404(get_developer_chat_thread_queryset(), id=thread.id)
    return JsonResponse(
        {
            "status": "ok",
            "thread": serialize_thread_detail(thread, request.user),
        },
        status=201,
    )


@require_POST
@login_required
def developer_chat_mark_read_api(request, thread_id):
    thread = get_object_or_404(get_developer_chat_thread_queryset(), id=thread_id)
    if not user_can_access_developer_chat_thread(request.user, thread):
        return _developer_chat_permission_denied()

    read_state = mark_thread_as_read(thread, request.user)
    return JsonResponse(
        {
            "status": "ok",
            "thread_id": thread.id,
            "last_read_at": read_state.last_read_at.isoformat() if read_state and read_state.last_read_at else "",
            "unread_count": get_thread_unread_count(thread, request.user),
        }
    )


@require_POST
@login_required
def developer_chat_delete_thread_api(request, thread_id):
    thread = get_object_or_404(get_developer_chat_thread_queryset(), id=thread_id)
    if not user_can_access_developer_chat_thread(request.user, thread):
        return _developer_chat_permission_denied()

    deleted_thread_id = thread.id
    thread.delete()
    return JsonResponse(
        {
            "status": "ok",
            "thread_id": deleted_thread_id,
        }
    )
