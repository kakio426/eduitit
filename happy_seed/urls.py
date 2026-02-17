from django.urls import path

from . import views

app_name = 'happy_seed'

urlpatterns = [
    # Landing (public)
    path('', views.landing, name='landing'),

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

    # Consent
    path('<uuid:classroom_id>/consent/', views.consent_manage, name='consent_manage'),
    path('student/<uuid:student_id>/consent/update/', views.consent_update, name='consent_update'),

    # Prize
    path('<uuid:classroom_id>/prizes/', views.prize_manage, name='prize_manage'),

    # Bloom
    path('<uuid:classroom_id>/bloom/grant/', views.bloom_grant, name='bloom_grant'),
    path('<uuid:classroom_id>/bloom/run/', views.bloom_run, name='bloom_run'),
    path('draw/<uuid:student_id>/execute/', views.bloom_draw, name='bloom_draw'),

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
]
