from django.urls import path

from . import views

app_name = 'guide_recorder'

urlpatterns = [
    # 페이지 뷰
    path('', views.session_list_view, name='session_list'),
    path('session/<int:pk>/', views.session_detail_view, name='session_detail'),
    path('session/<int:pk>/delete/', views.delete_session_view, name='delete_session'),
    path('session/<int:pk>/publish/', views.publish_session_view, name='publish_session'),
    path('share/<str:token>/', views.share_view, name='share'),

    # API 엔드포인트
    path('api/session/start/', views.api_start_session, name='api_start_session'),
    path('api/session/<int:pk>/step/', views.api_add_step, name='api_add_step'),
    path('api/session/<int:pk>/finish/', views.api_finish_session, name='api_finish_session'),
    path('api/step/<int:pk>/description/', views.api_update_description, name='api_update_description'),
    path('api/step/<int:pk>/delete/', views.api_delete_step, name='api_delete_step'),
]
