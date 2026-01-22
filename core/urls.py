from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('prompts/', views.prompt_lab, name='prompt_lab'),
    path('tools/', views.tool_guide, name='tool_guide'),
    path('about/', views.about, name='about'),
    path('settings/', views.settings_view, name='settings'),
]
