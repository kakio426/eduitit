from django.urls import path

from . import views

app_name = "classcalendar"

urlpatterns = [
    # Teacher views
    path("", views.main_view, name="main"),
    path("api/events/", views.api_events, name="api_events"),
    path("api/events/create/", views.api_create_event, name="api_create_event"),
    path("api/events/<uuid:event_id>/update/", views.api_update_event, name="api_update_event"),
    path("api/events/<uuid:event_id>/delete/", views.api_delete_event, name="api_delete_event"),
]
