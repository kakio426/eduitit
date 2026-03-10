from django.urls import path

from . import views

app_name = "classcalendar"

urlpatterns = [
    # Teacher views
    path("", views.main_view, name="main"),
    path("entry/", views.main_entry, name="sheetbook_entry"),
    path("legacy/", views.legacy_main_redirect, name="legacy_main"),
    path("collaborators/add/", views.collaborator_add, name="collaborator_add"),
    path("collaborators/<int:collaborator_id>/remove/", views.collaborator_remove, name="collaborator_remove"),
    path("share/enable/", views.share_enable, name="share_enable"),
    path("share/disable/", views.share_disable, name="share_disable"),
    path("share/rotate/", views.share_rotate, name="share_rotate"),
    path("shared/<uuid:share_uuid>/", views.shared_view, name="shared"),
    path("api/events/", views.api_events, name="api_events"),
    path("api/integration-settings/", views.api_integration_settings, name="api_integration_settings"),
    path("api/retention-notice/dismiss/", views.api_dismiss_retention_notice, name="api_dismiss_retention_notice"),
    path("api/events/create/", views.api_create_event, name="api_create_event"),
    path("api/events/<uuid:event_id>/update/", views.api_update_event, name="api_update_event"),
    path("api/events/<uuid:event_id>/delete/", views.api_delete_event, name="api_delete_event"),
    path("api/message-captures/parse/", views.api_message_capture_parse, name="api_message_capture_parse"),
    path("api/message-captures/archive/", views.api_message_capture_archive, name="api_message_capture_archive"),
    path(
        "api/message-captures/<uuid:capture_id>/archive-detail/",
        views.api_message_capture_archive_detail,
        name="api_message_capture_archive_detail",
    ),
    path(
        "api/message-captures/<uuid:capture_id>/commit/",
        views.api_message_capture_commit,
        name="api_message_capture_commit",
    ),
]