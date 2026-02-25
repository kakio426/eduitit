from django.urls import path

from . import views

app_name = "classcalendar"

urlpatterns = [
    # Teacher views
    path("", views.main_view, name="main"),
    path("collaborators/add/", views.collaborator_add, name="collaborator_add"),
    path("collaborators/<int:collaborator_id>/remove/", views.collaborator_remove, name="collaborator_remove"),
    path("share/enable/", views.share_enable, name="share_enable"),
    path("share/disable/", views.share_disable, name="share_disable"),
    path("share/rotate/", views.share_rotate, name="share_rotate"),
    path("shared/<uuid:share_uuid>/", views.shared_view, name="shared"),
    path("api/events/", views.api_events, name="api_events"),
    path("api/integration-settings/", views.api_integration_settings, name="api_integration_settings"),
    path("api/events/create/", views.api_create_event, name="api_create_event"),
    path("api/events/<uuid:event_id>/update/", views.api_update_event, name="api_update_event"),
    path("api/events/<uuid:event_id>/delete/", views.api_delete_event, name="api_delete_event"),
]
