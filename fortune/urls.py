from django.urls import path
from django.views.generic import RedirectView
from . import views, views_zoo

app_name = 'fortune'

urlpatterns = [
    path('', views.saju_view, name='saju'),
    path('saju/', views.saju_view, name='saju_alt'),
    path('api/', views.saju_api_view, name='saju_api'),
    path('api/streaming/', views.saju_streaming_api, name='saju_streaming_api'),
    path('api/daily/', views.daily_fortune_api, name='daily_fortune_api'),
    path('api/save/', views.save_fortune_api, name='save_fortune_api'),
    path('history/', views.saju_history, name='history'),
    path('history/<int:pk>/', views.saju_history_detail, name='history_detail'),
    path('history/<int:pk>/delete/', views.delete_history_api, name='delete_history_api'),

    # 프로필 관리 API
    path('api/profiles/', views.profile_list_api, name='profile_list_api'),
    path('api/profiles/create/', views.profile_create_api, name='profile_create_api'),
    path('api/profiles/<int:pk>/update/', views.profile_update_api, name='profile_update_api'),
    path('api/profiles/<int:pk>/delete/', views.profile_delete_api, name='profile_delete_api'),
    path('api/profiles/<int:pk>/set-default/', views.profile_set_default_api, name='profile_set_default_api'),

    # 즐겨찾기 및 통계 API
    path('api/favorites/', views.favorite_dates_api, name='favorite_dates_api'),
    path('api/favorites/add/', views.favorite_date_add_api, name='favorite_date_add_api'),
    path('api/favorites/<int:pk>/delete/', views.favorite_date_delete_api, name='favorite_date_delete_api'),
    path('api/statistics/', views.statistics_api, name='statistics_api'),
    
    # 티처블 동물원 (Animal MBTI) - Redirects to /ssambti/
    path('zoo/', RedirectView.as_view(url='/ssambti/', permanent=True), name='zoo_main'),
    path('zoo/analyze/', RedirectView.as_view(url='/ssambti/analyze/', permanent=True), name='zoo_analyze'),
    path('zoo/history/', RedirectView.as_view(url='/ssambti/history/', permanent=True), name='zoo_history'),
    path('zoo/result/<int:pk>/', RedirectView.as_view(url='/ssambti/result/%(pk)s/', permanent=True), name='zoo_detail'),
]
