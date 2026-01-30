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
    
    # 티처블 동물원 (Animal MBTI) - Redirects to /ssambti/
    path('zoo/', RedirectView.as_view(url='/ssambti/', permanent=True), name='zoo_main'),
    path('zoo/analyze/', RedirectView.as_view(url='/ssambti/analyze/', permanent=True), name='zoo_analyze'),
    path('zoo/history/', RedirectView.as_view(url='/ssambti/history/', permanent=True), name='zoo_history'),
    path('zoo/result/<int:pk>/', RedirectView.as_view(url='/ssambti/result/%(pk)s/', permanent=True), name='zoo_detail'),
]
