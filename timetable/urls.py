from django.urls import path

from . import legacy_views, views

app_name = "timetable"

urlpatterns = [
    path("", views.main, name="main"),
    path("import/legacy/", views.legacy_import, name="legacy_import"),
    path("template/", legacy_views.download_template, name="download_template"),
    path("sync-logs.csv", legacy_views.download_sync_logs_csv, name="download_sync_logs_csv"),
    path("edit/<str:token>/", views.class_edit_view, name="class_edit"),
    path("workspaces/<int:workspace_id>/", views.workspace_detail, name="workspace_detail"),
    path("workspaces/<int:workspace_id>/meeting/", views.meeting_view, name="meeting_view"),
    path("api/setup/batch-create", views.api_setup_batch_create, name="api_setup_batch_create"),
    path("api/workspaces/<int:workspace_id>/autosave", views.api_autosave, name="api_autosave"),
    path("api/workspaces/<int:workspace_id>/validate", views.api_validate, name="api_validate"),
    path("api/workspaces/<int:workspace_id>/class-links/issue", views.api_issue_class_link, name="api_issue_class_link"),
    path(
        "api/workspaces/<int:workspace_id>/class-links/<int:link_id>/revoke",
        views.api_revoke_class_link,
        name="api_revoke_class_link",
    ),
    path(
        "api/workspaces/<int:workspace_id>/class-status/<int:classroom_id>/review",
        views.api_review_class_status,
        name="api_review_class_status",
    ),
    path("api/workspaces/<int:workspace_id>/events", views.api_events, name="api_events"),
    path("api/workspaces/<int:workspace_id>/events/<int:event_id>", views.api_event_detail, name="api_event_detail"),
    path("api/workspaces/<int:workspace_id>/snapshots", views.api_snapshots, name="api_snapshots"),
    path(
        "api/workspaces/<int:workspace_id>/snapshots/<int:snapshot_id>/restore",
        views.api_snapshot_restore,
        name="api_snapshot_restore",
    ),
    path("api/workspaces/<int:workspace_id>/publish", views.api_publish, name="api_publish"),
    path("api/workspaces/<int:workspace_id>/meeting/apply", views.api_meeting_apply, name="api_meeting_apply"),
    path(
        "api/edit-links/<str:token>/weekly-autosave",
        views.api_class_edit_weekly_autosave,
        name="api_class_edit_weekly_autosave",
    ),
    path(
        "api/edit-links/<str:token>/date-overrides/autosave",
        views.api_class_edit_date_override_autosave,
        name="api_class_edit_date_override_autosave",
    ),
    path("api/edit-links/<str:token>/submit", views.api_class_edit_submit, name="api_class_edit_submit"),
    path("share/portal/<str:token>/", views.share_portal_view, name="share_portal"),
    path("share/<str:token>/", views.share_view, name="share_view"),
]
