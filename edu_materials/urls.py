from django.urls import path

from . import views

app_name = "edu_materials"


urlpatterns = [
    path("", views.main_view, name="main"),
    path("create/", views.create_material, name="create"),
    path("<uuid:pk>/", views.material_detail, name="detail"),
    path("<uuid:material_id>/publish/", views.toggle_material_publish, name="toggle_publish"),
    path("<uuid:pk>/run/", views.run_material, name="run"),
]
