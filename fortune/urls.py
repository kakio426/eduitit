from django.urls import path
from . import views

app_name = 'fortune'

urlpatterns = [
    path('', views.saju_view, name='saju'),
    path('saju/', views.saju_view, name='saju_alt'),
    path('api/', views.saju_api_view, name='saju_api'),
    path('api/daily/', views.daily_fortune_api, name='daily_fortune_api'),
    path('api/save/', views.save_fortune_api, name='save_fortune_api'),
    path('history/', views.saju_history, name='history'),
    path('history/<int:pk>/', views.saju_history_detail, name='history_detail'),
    path('history/<int:pk>/delete/', views.delete_history_api, name='delete_history_api'),
]
