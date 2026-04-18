from django.urls import path

from seed_quiz import views, views_game

app_name = "seed_quiz"

urlpatterns = [
    # 랜딩 (제품 카드 클릭 시)
    path("", views.landing, name="landing"),

    # 교사 영역
    path("class/<uuid:classroom_id>/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path(
        "class/<uuid:classroom_id>/game/create/",
        views_game.teacher_game_create,
        name="teacher_game_create",
    ),
    path(
        "class/<uuid:classroom_id>/game/<uuid:room_id>/",
        views_game.teacher_game_room,
        name="teacher_game_room",
    ),
    path(
        "class/<uuid:classroom_id>/game/<uuid:room_id>/panel/",
        views_game.htmx_teacher_game_panel,
        name="htmx_teacher_game_panel",
    ),
    path(
        "class/<uuid:classroom_id>/game/<uuid:room_id>/advance/",
        views_game.htmx_teacher_game_advance,
        name="htmx_teacher_game_advance",
    ),
    path(
        "class/<uuid:classroom_id>/game/<uuid:room_id>/questions/<uuid:question_id>/review/",
        views_game.htmx_teacher_game_review,
        name="htmx_teacher_game_review",
    ),
    path(
        "class/<uuid:classroom_id>/student-dashboard/",
        views.teacher_student_dashboard,
        name="teacher_student_dashboard",
    ),
    path(
        "class/<uuid:classroom_id>/analysis/",
        views.teacher_result_analysis,
        name="teacher_result_analysis",
    ),
    path("class/<uuid:classroom_id>/csv-template/", views.download_csv_template, name="download_csv_template"),
    path("class/<uuid:classroom_id>/xlsx-template/", views.download_xlsx_template, name="download_xlsx_template"),
    path("class/<uuid:classroom_id>/csv-guide/", views.download_csv_guide, name="download_csv_guide"),
    path("class/<uuid:classroom_id>/csv-sample-pack/", views.download_csv_sample_pack, name="download_csv_sample_pack"),
    path(
        "class/<uuid:classroom_id>/csv-error-report/<slug:token>/",
        views.download_csv_error_report,
        name="download_csv_error_report",
    ),
    path("class/<uuid:classroom_id>/htmx/bank/", views.htmx_bank_browse, name="htmx_bank_browse"),
    path("class/<uuid:classroom_id>/htmx/bank/select/<uuid:bank_id>/", views.htmx_bank_select, name="htmx_bank_select"),
    path("class/<uuid:classroom_id>/htmx/csv/upload/", views.htmx_csv_upload, name="htmx_csv_upload"),
    path("class/<uuid:classroom_id>/htmx/text/upload/", views.htmx_text_upload, name="htmx_text_upload"),
    path("class/<uuid:classroom_id>/htmx/csv/confirm/", views.htmx_csv_confirm, name="htmx_csv_confirm"),
    path("class/<uuid:classroom_id>/htmx/csv/history/", views.htmx_csv_history, name="htmx_csv_history"),
    path("class/<uuid:classroom_id>/htmx/rag/generate/", views.htmx_rag_generate, name="htmx_rag_generate"),
    path("class/<uuid:classroom_id>/htmx/generate/", views.htmx_generate, name="htmx_generate"),
    path("class/<uuid:classroom_id>/htmx/set/preview/<uuid:set_id>/", views.htmx_set_preview, name="htmx_set_preview"),
    path("class/<uuid:classroom_id>/htmx/set/edit/<uuid:set_id>/", views.htmx_set_edit, name="htmx_set_edit"),
    path("class/<uuid:classroom_id>/htmx/set/update/<uuid:set_id>/", views.htmx_set_update, name="htmx_set_update"),
    path("class/<uuid:classroom_id>/htmx/publish/<uuid:set_id>/", views.htmx_publish, name="htmx_publish"),
    path("class/<uuid:classroom_id>/htmx/set/archive/<uuid:set_id>/", views.htmx_set_archive, name="htmx_set_archive"),
    path("class/<uuid:classroom_id>/htmx/publish/rollback/", views.htmx_publish_rollback, name="htmx_publish_rollback"),
    path("class/<uuid:classroom_id>/htmx/progress/", views.htmx_progress, name="htmx_progress"),
    path("class/<uuid:classroom_id>/htmx/topic-summary/", views.htmx_topic_summary, name="htmx_topic_summary"),

    # 학생 영역
    path("game/join/", views_game.student_game_join, name="student_game_join"),
    path("game/join/<slug:join_code>/", views_game.student_game_join, name="student_game_join_code"),
    path("game/start/", views_game.student_game_start, name="student_game_start"),
    path("game/play/", views_game.student_game_shell, name="student_game_shell"),
    path("htmx/game/state/", views_game.htmx_student_game_state, name="htmx_student_game_state"),
    path(
        "htmx/game/choices/",
        views_game.htmx_student_game_generate_choices,
        name="htmx_student_game_generate_choices",
    ),
    path(
        "htmx/game/question/submit/",
        views_game.htmx_student_game_submit_question,
        name="htmx_student_game_submit_question",
    ),
    path(
        "htmx/game/question/<uuid:question_id>/status/",
        views_game.htmx_student_game_question_status,
        name="htmx_student_game_question_status",
    ),
    path(
        "htmx/game/question/<uuid:question_id>/answer/",
        views_game.htmx_student_game_answer,
        name="htmx_student_game_answer",
    ),
    path("gate/<slug:class_slug>/", views.student_gate, name="student_gate"),
    path("gate/<slug:class_slug>/start/", views.student_start, name="student_start"),
    path("play/", views.student_play_shell, name="student_play"),
    path("htmx/play/current/", views.htmx_play_current, name="htmx_play_current"),
    path("htmx/play/answer/", views.htmx_play_answer, name="htmx_play_answer"),
    path("htmx/play/next/", views.htmx_play_next, name="htmx_play_next"),
    path("htmx/play/result/", views.htmx_play_result, name="htmx_play_result"),
    path("htmx/play/claim-reward/", views.htmx_play_claim_reward, name="htmx_play_claim_reward"),
]
