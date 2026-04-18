from django.urls import path

from . import views


app_name = "messagebox"


urlpatterns = [
    path("", views.main_view, name="main"),
    path("developer-chat/", views.developer_chat_view, name="developer_chat"),
    path("developer-chat/api/threads/", views.developer_chat_threads_api, name="developer_chat_threads"),
    path(
        "developer-chat/api/threads/<int:thread_id>/",
        views.developer_chat_thread_detail_api,
        name="developer_chat_thread_detail",
    ),
    path(
        "developer-chat/api/threads/<int:thread_id>/messages/",
        views.developer_chat_send_message_api,
        name="developer_chat_send_message",
    ),
    path(
        "developer-chat/api/threads/<int:thread_id>/read/",
        views.developer_chat_mark_read_api,
        name="developer_chat_mark_read",
    ),
    path(
        "developer-chat/api/threads/<int:thread_id>/delete/",
        views.developer_chat_delete_thread_api,
        name="developer_chat_delete_thread",
    ),
    path(
        "developer-chat/api/threads/<int:thread_id>/grant-quota/",
        views.developer_chat_grant_quota_api,
        name="developer_chat_grant_quota",
    ),
]
