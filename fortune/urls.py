from django.urls import path
from . import views

app_name = 'fortune'

urlpatterns = [
    path('', views.saju_view, name='saju'),
    path('api/', views.saju_api_view, name='saju_api'),
]
