from django.urls import path
from . import views

app_name = 'artclass'

urlpatterns = [
    path('', views.setup_view, name='setup'),
    path('setup/<int:pk>/fork/', views.setup_fork_view, name='setup_fork'),
    path('setup/<int:pk>/', views.setup_view, name='setup_edit'),
    path('setup/from-library/<int:pk>/', views.clone_for_edit_view, name='setup_clone'),
    path('classroom/<int:pk>/', views.classroom_view, name='classroom'),
    path('delete/<int:pk>/', views.delete_class_view, name='delete'),
    path('api/classroom/<int:pk>/playback-mode/', views.update_playback_mode_api, name='update_playback_mode_api'),
    path('api/classroom/<int:pk>/launcher-start/', views.start_launcher_session_api, name='start_launcher_session_api'),
    path('api/parse-gemini-steps/', views.parse_gemini_steps_api, name='parse_gemini_steps_api'),
    path('library/', views.library_view, name='library'),
]
