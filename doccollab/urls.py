from django.urls import path

from . import views


app_name = "doccollab"

urlpatterns = [
    path("", views.main, name="main"),
    path("create/", views.create_room, name="create_room"),
    path("rooms/<uuid:room_id>/", views.room_detail, name="room_detail"),
    path("rooms/<uuid:room_id>/revisions/", views.room_revisions, name="room_revisions"),
    path("rooms/<uuid:room_id>/revisions/<uuid:revision_id>/download/", views.download_revision, name="download_revision"),
    path("rooms/<uuid:room_id>/revisions/save/", views.save_revision, name="save_revision"),
    path("rooms/<uuid:room_id>/revisions/<uuid:revision_id>/publish/", views.publish_revision_view, name="publish_revision"),
    path("rooms/<uuid:room_id>/snapshots/", views.create_snapshot_view, name="create_snapshot"),
    path("rooms/<uuid:room_id>/members/add/", views.add_member, name="add_member"),
]
