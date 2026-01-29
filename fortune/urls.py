from django.urls import path
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
    
    # 티처블 동물원 (Animal MBTI)
    path('zoo/', views_zoo.zoo_main_view, name='zoo_main'),
    path('zoo/analyze/', views_zoo.zoo_analyze_view, name='zoo_analyze'),
    path('zoo/history/', views_zoo.zoo_history_view, name='zoo_history'),
    path('zoo/result/<int:pk>/', views_zoo.zoo_detail_view, name='zoo_detail'),
]
