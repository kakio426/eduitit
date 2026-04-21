from django.urls import path

from . import views


app_name = "doccollab"

urlpatterns = [
    path("", views.main, name="main"),
    path("create/", views.create_room, name="create_room"),
    path("worksheets/generate/", views.generate_worksheet, name="generate_worksheet"),
    path("worksheets/generate-file/", views.generate_worksheet_file, name="generate_worksheet_file"),
    path("worksheets/library/", views.worksheet_library, name="worksheet_library"),
    path("rooms/<uuid:room_id>/remove/", views.remove_room, name="remove_room"),
    path("rooms/<uuid:room_id>/", views.room_detail, name="room_detail"),
    path("rooms/<uuid:room_id>/source/download/", views.download_source, name="download_source"),
    path("rooms/<uuid:room_id>/revisions/", views.room_revisions, name="room_revisions"),
    path("rooms/<uuid:room_id>/revisions/<uuid:revision_id>/download/", views.download_revision, name="download_revision"),
    path("rooms/<uuid:room_id>/revisions/save/", views.save_revision, name="save_revision"),
    path("rooms/<uuid:room_id>/worksheets/publish/", views.worksheet_publish, name="worksheet_publish"),
    path("rooms/<uuid:room_id>/worksheets/clone/", views.worksheet_clone, name="worksheet_clone"),
    path("rooms/<uuid:room_id>/revisions/<uuid:revision_id>/publish/", views.publish_revision_view, name="publish_revision"),
    path("rooms/<uuid:room_id>/snapshots/", views.create_snapshot_view, name="create_snapshot"),
    path("rooms/<uuid:room_id>/members/add/", views.add_member, name="add_member"),
]
