from django.urls import path

from . import views

app_name = "textbooks"


urlpatterns = [
    path("", views.main_view, name="main"),
    path("create/", views.create_material, name="create"),
    path("<uuid:pk>/", views.material_detail, name="detail"),
    path("<uuid:pk>/html-preview/", views.html_preview_window, name="html_preview_window"),
    path("<uuid:material_id>/publish/", views.toggle_material_publish, name="toggle_publish"),
    path("<uuid:material_id>/pdf/", views.material_pdf, name="material_pdf"),
    path("<uuid:material_id>/live/start/", views.start_live_session, name="start_live"),
    path("live/<uuid:session_id>/teacher/", views.teacher_session_view, name="teacher_session"),
    path("live/<uuid:session_id>/display/", views.display_session_view, name="display_session"),
    path("live/<uuid:session_id>/join/", views.join_session_view, name="join_session"),
    path("live/<uuid:session_id>/join/verify/", views.verify_join_code, name="verify_join"),
    path("live/<uuid:session_id>/bootstrap/", views.bootstrap_session, name="bootstrap_session"),
    path("live/<uuid:session_id>/end/", views.end_live_session, name="end_live"),
]
