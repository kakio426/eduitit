from django.urls import path

from . import views

app_name = "classcalendar"

urlpatterns = [
    # Teacher views
    path("", views.center_view, name="main"),
    path("center/", views.center_view, name="center"),
    path("today/", views.today_view, name="today"),
    path("entry/", views.main_entry, name="entry"),
    path("legacy/", views.legacy_main_redirect, name="legacy_main"),
    path("collaborators/add/", views.collaborator_add, name="collaborator_add"),
    path("collaborators/<int:collaborator_id>/remove/", views.collaborator_remove, name="collaborator_remove"),
    path("share/enable/", views.share_enable, name="share_enable"),
    path("share/disable/", views.share_disable, name="share_disable"),
    path("share/rotate/", views.share_rotate, name="share_rotate"),
    path("external/calendar.ics", views.external_ical_feed, name="external_ical_feed"),
    path("external/calendar/webhook/", views.external_calendar_webhook, name="external_calendar_webhook"),
    path("shared/<uuid:share_uuid>/", views.shared_view, name="shared"),
    path("api/events/", views.api_events, name="api_events"),
    path("api/holidays/", views.api_holidays, name="api_holidays"),
    path("api/integration-settings/", views.api_integration_settings, name="api_integration_settings"),
    path("api/events/create/", views.api_create_event, name="api_create_event"),
    path("api/events/<uuid:event_id>/update/", views.api_update_event, name="api_update_event"),
    path("api/events/<uuid:event_id>/delete/", views.api_delete_event, name="api_delete_event"),
    path("api/tasks/<uuid:task_id>/delete/", views.api_delete_task, name="api_delete_task"),
    path("api/message-captures/save/", views.api_message_capture_save, name="api_message_capture_save"),
    path("api/message-captures/parse/", views.api_message_capture_parse, name="api_message_capture_parse"),
    path(
        "api/message-captures/<uuid:capture_id>/parse-saved/",
        views.api_message_capture_parse_saved,
        name="api_message_capture_parse_saved",
    ),
    path("api/message-captures/archive/", views.api_message_capture_archive, name="api_message_capture_archive"),
    path(
        "api/message-captures/<uuid:capture_id>/archive-detail/",
        views.api_message_capture_archive_detail,
        name="api_message_capture_archive_detail",
    ),
    path(
        "api/message-captures/<uuid:capture_id>/delete/",
        views.api_message_capture_delete,
        name="api_message_capture_delete",
    ),
    path(
        "api/message-captures/<uuid:capture_id>/link/",
        views.api_message_capture_link,
        name="api_message_capture_link",
    ),
    path(
        "api/message-captures/<uuid:capture_id>/commit/",
        views.api_message_capture_commit,
        name="api_message_capture_commit",
    ),
    path(
        "api/message-captures/<uuid:capture_id>/complete/",
        views.api_message_capture_complete,
        name="api_message_capture_complete",
    ),
]
