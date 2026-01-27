from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:pk>/like/', views.post_like, name='post_like'),
    path('post/<int:pk>/delete/', views.post_delete, name='post_delete'),
    path('prompts/', views.prompt_lab, name='prompt_lab'),
    path('tools/', views.tool_guide, name='tool_guide'),
    path('about/', views.about, name='about'),
    path('settings/', views.settings_view, name='settings'),
    path('select-role/', views.select_role, name='select_role'),
    path('sso/schoolit/', views.sso_to_schoolit, name='sso_schoolit'),
    path('policy/', views.policy_view, name='policy'),
]
