from django.urls import path
from . import views

app_name = 'ssambti'

urlpatterns = [
    path('', views.main_view, name='main'),
    path('analyze/', views.analyze_view, name='analyze'),
    path('history/', views.history_view, name='history'),
    path('result/<int:pk>/', views.detail_view, name='detail'),
]
