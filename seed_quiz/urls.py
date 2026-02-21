from django.urls import path

from seed_quiz import views

app_name = "seed_quiz"

urlpatterns = [
    # 랜딩 (제품 카드 클릭 시)
    path("", views.landing, name="landing"),

    # 교사 영역
    path("class/<uuid:classroom_id>/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("class/<uuid:classroom_id>/htmx/generate/", views.htmx_generate, name="htmx_generate"),
    path("class/<uuid:classroom_id>/htmx/publish/<uuid:set_id>/", views.htmx_publish, name="htmx_publish"),
    path("class/<uuid:classroom_id>/htmx/progress/", views.htmx_progress, name="htmx_progress"),

    # 학생 영역
    path("gate/<slug:class_slug>/", views.student_gate, name="student_gate"),
    path("gate/<slug:class_slug>/start/", views.student_start, name="student_start"),
    path("play/", views.student_play_shell, name="student_play"),
    path("htmx/play/current/", views.htmx_play_current, name="htmx_play_current"),
    path("htmx/play/answer/", views.htmx_play_answer, name="htmx_play_answer"),
    path("htmx/play/result/", views.htmx_play_result, name="htmx_play_result"),
]
