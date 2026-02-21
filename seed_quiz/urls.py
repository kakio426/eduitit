from django.urls import path

from seed_quiz import views

app_name = "seed_quiz"

urlpatterns = [
    # 랜딩 (제품 카드 클릭 시)
    path("", views.landing, name="landing"),

    # 교사 영역
    path("class/<uuid:classroom_id>/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("class/<uuid:classroom_id>/csv-template/", views.download_csv_template, name="download_csv_template"),
    path("class/<uuid:classroom_id>/htmx/bank/", views.htmx_bank_browse, name="htmx_bank_browse"),
    path("class/<uuid:classroom_id>/htmx/bank/random-select/", views.htmx_bank_random_select, name="htmx_bank_random_select"),
    path("class/<uuid:classroom_id>/htmx/bank/select/<uuid:bank_id>/", views.htmx_bank_select, name="htmx_bank_select"),
    path("class/<uuid:classroom_id>/htmx/csv/upload/", views.htmx_csv_upload, name="htmx_csv_upload"),
    path("class/<uuid:classroom_id>/htmx/csv/confirm/", views.htmx_csv_confirm, name="htmx_csv_confirm"),
    path("class/<uuid:classroom_id>/htmx/rag/generate/", views.htmx_rag_generate, name="htmx_rag_generate"),
    path("class/<uuid:classroom_id>/htmx/generate/", views.htmx_generate, name="htmx_generate"),
    path("class/<uuid:classroom_id>/htmx/publish/<uuid:set_id>/", views.htmx_publish, name="htmx_publish"),
    path("class/<uuid:classroom_id>/htmx/progress/", views.htmx_progress, name="htmx_progress"),
    path("class/<uuid:classroom_id>/htmx/topic-summary/", views.htmx_topic_summary, name="htmx_topic_summary"),

    # 학생 영역
    path("gate/<slug:class_slug>/", views.student_gate, name="student_gate"),
    path("gate/<slug:class_slug>/start/", views.student_start, name="student_start"),
    path("play/", views.student_play_shell, name="student_play"),
    path("htmx/play/current/", views.htmx_play_current, name="htmx_play_current"),
    path("htmx/play/answer/", views.htmx_play_answer, name="htmx_play_answer"),
    path("htmx/play/result/", views.htmx_play_result, name="htmx_play_result"),
]
