from django.urls import path

from . import views

app_name = "edu_materials_next"


urlpatterns = [
    path("", views.main_view, name="main"),
    path("join/", views.join_material, name="join"),
    path("j/", views.join_material, name="join_short"),
    path("create/", views.create_material, name="create"),
    path("import/<uuid:legacy_uuid>/", views.import_legacy_material, name="import_legacy"),
    path("<uuid:pk>/share-board/", views.share_board, name="share_board"),
    path("<uuid:pk>/", views.material_detail, name="detail"),
    path("<uuid:material_id>/update/", views.update_material, name="update"),
    path("<uuid:material_id>/delete/", views.delete_material, name="delete"),
    path("<uuid:pk>/render/", views.render_material, name="render"),
    path("<uuid:pk>/run/", views.run_material, name="run"),
]

