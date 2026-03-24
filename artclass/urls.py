from django.urls import path
from . import views

app_name = 'artclass'

urlpatterns = [
    path('', views.setup_view, name='setup'),
    path('setup/<int:pk>/', views.setup_view, name='setup_edit'),
    path('setup/from-library/<int:pk>/', views.clone_for_edit_view, name='setup_clone'),
    path('launcher-release-manager/', views.launcher_release_manager_view, name='launcher_release_manager'),
    path('launcher-updates/windows/', views.launcher_update_index_view, name='launcher_update_index'),
    path('launcher-updates/windows/<str:filename>', views.launcher_update_asset_view, name='launcher_update_asset'),
    path('classroom/<int:pk>/', views.classroom_view, name='classroom'),
    path('delete/<int:pk>/', views.delete_class_view, name='delete'),
    path('api/classroom/<int:pk>/steps/<int:step_id>/text/', views.update_step_text_api, name='update_step_text_api'),
    path('api/classroom/<int:pk>/playback-mode/', views.update_playback_mode_api, name='update_playback_mode_api'),
    path('api/classroom/<int:pk>/launcher-start/', views.start_launcher_session_api, name='start_launcher_session_api'),
    path('api/launcher-release-config/', views.launcher_release_config_api, name='launcher_release_config_api'),
    path('api/video-advice/', views.video_advice_api, name='video_advice_api'),
    path('api/parse-gemini-steps/', views.parse_gemini_steps_api, name='parse_gemini_steps_api'),
    path('library/', views.library_view, name='library'),
]
