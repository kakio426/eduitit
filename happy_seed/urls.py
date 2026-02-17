from django.urls import path

from . import views

app_name = 'happy_seed'

urlpatterns = [
    # Landing (public)
    path('', views.landing, name='landing'),
    path('manual/teacher/', views.teacher_manual, name='teacher_manual'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Classroom CRUD
    path('classroom/create/', views.classroom_create, name='classroom_create'),
    path('<uuid:classroom_id>/', views.classroom_detail, name='classroom_detail'),
    path('<uuid:classroom_id>/settings/', views.classroom_settings, name='classroom_settings'),

    # Student CRUD
    path('<uuid:classroom_id>/students/add/', views.student_add, name='student_add'),
    path('<uuid:classroom_id>/students/bulk-add/', views.student_bulk_add, name='student_bulk_add'),
    path('student/<uuid:student_id>/edit/', views.student_edit, name='student_edit'),
    path('student/<uuid:student_id>/override/', views.set_teacher_override, name='set_teacher_override'),

    # Consent
    path('<uuid:classroom_id>/consent/', views.consent_manage, name='consent_manage'),
    path('<uuid:classroom_id>/consent/request-sign-talk/', views.consent_request_via_sign_talk, name='consent_request_via_sign_talk'),
    path('<uuid:classroom_id>/consent/sync-sign-talk/', views.consent_sync_from_sign_talk, name='consent_sync_from_sign_talk'),
    path('<uuid:classroom_id>/consent/manual-approve/', views.consent_manual_approve, name='consent_manual_approve'),
    path('student/<uuid:student_id>/consent/resend/', views.consent_resend, name='consent_resend'),
    path('student/<uuid:student_id>/consent/update/', views.consent_update, name='consent_update'),

    # Group manage
    path('<uuid:classroom_id>/groups/', views.group_manage, name='group_manage'),

    # Prize
    path('<uuid:classroom_id>/prizes/', views.prize_manage, name='prize_manage'),

    # Bloom
    path('<uuid:classroom_id>/bloom/grant/', views.bloom_grant, name='bloom_grant'),
    path('<uuid:classroom_id>/bloom/run/', views.bloom_run, name='bloom_run'),
    path('<uuid:classroom_id>/group/mission-success/', views.group_mission_success, name='group_mission_success'),
    path('draw/<uuid:student_id>/execute/', views.bloom_draw, name='bloom_draw'),

    # Activities / Analysis
    path('<uuid:classroom_id>/activities/', views.activity_manage, name='activity_manage'),
    path('<uuid:classroom_id>/analysis/', views.analysis_dashboard, name='analysis_dashboard'),

    # Celebration
    path('draw/<uuid:draw_id>/celebrate/', views.celebration, name='celebration'),
    path('draw/<uuid:draw_id>/close/', views.close_celebration, name='close_celebration'),

    # Seed
    path('student/<uuid:student_id>/seed/grant/', views.seed_grant, name='seed_grant'),

    # Public Garden
    path('garden/<slug:slug>/', views.garden_public, name='garden_public'),

    # HTMX Partials
    path('<uuid:classroom_id>/partials/student-grid/', views.student_grid_partial, name='student_grid_partial'),
    path('<uuid:classroom_id>/partials/garden/', views.garden_partial, name='garden_partial'),
    path('student/<uuid:student_id>/partials/tooltip/', views.student_tooltip_partial, name='student_tooltip_partial'),

    # API v1 (additive, existing UI flow 유지)
    path('api/v1/classes/<uuid:classroom_id>/live:execute-draw', views.api_execute_draw, name='api_execute_draw'),
    path('api/v1/classes/<uuid:classroom_id>/live:group-mission-success', views.api_group_mission_success, name='api_group_mission_success'),
    path('api/v1/classes/<uuid:classroom_id>/consents:sync-sign-talk', views.api_consent_sync_sign_talk, name='api_consent_sync_sign_talk'),
]
