from django.urls import path

from . import views


app_name = "schoolcomm"

urlpatterns = [
    path("", views.main, name="main"),
    path("create/", views.create_workspace, name="create_workspace"),
    path("invite/<str:token>/", views.invite_accept, name="invite_accept"),
    path("rooms/<uuid:room_id>/", views.room_detail, name="room_detail"),
    path("api/invites/", views.api_create_invite, name="api_create_invite"),
    path("api/memberships/<uuid:membership_id>/approve/", views.api_approve_membership, name="api_approve_membership"),
    path("api/dms/", views.api_dms, name="api_dms"),
    path("api/rooms/<uuid:room_id>/messages/", views.api_room_messages, name="api_room_messages"),
    path("api/messages/<uuid:message_id>/thread/", views.api_message_thread, name="api_message_thread"),
    path("api/messages/<uuid:message_id>/reactions/", views.api_message_reactions, name="api_message_reactions"),
    path("api/assets/<uuid:asset_id>/download/", views.api_asset_download, name="api_asset_download"),
    path("api/assets/<uuid:asset_id>/category/", views.api_asset_category, name="api_asset_category"),
    path("api/search/", views.api_search, name="api_search"),
    path("api/assets/search/", views.api_asset_search, name="api_asset_search"),
    path("api/notifications/summary/", views.api_notifications_summary, name="api_notifications_summary"),
    path("api/calendar-suggestions/<uuid:suggestion_id>/apply/", views.api_apply_calendar_suggestion, name="api_apply_calendar_suggestion"),
]
