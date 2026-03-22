from django.urls import path

from . import views

app_name = "edu_materials"


urlpatterns = [
    path("", views.main_view, name="main"),
    path("create/", views.create_material, name="create"),
    path("<uuid:material_id>/clone/", views.clone_material, name="clone"),
    path("<uuid:pk>/", views.material_detail, name="detail"),
    path("<uuid:material_id>/update/", views.update_material, name="update"),
    path("<uuid:material_id>/metadata/", views.update_material_metadata, name="update_metadata"),
    path("<uuid:material_id>/reclassify/", views.reclassify_material, name="reclassify"),
    path("<uuid:material_id>/delete/", views.delete_material, name="delete"),
    path("<uuid:material_id>/publish/", views.toggle_material_publish, name="toggle_publish"),
    path("<uuid:pk>/render/", views.render_material, name="render"),
    path("<uuid:pk>/run/", views.run_material, name="run"),
]
