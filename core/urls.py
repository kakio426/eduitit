from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:pk>/like/', views.post_like, name='post_like'),
    path('post/<int:pk>/comment/', views.comment_create, name='comment_create'),
    path('post/<int:pk>/delete/', views.post_delete, name='post_delete'),
    path('post/<int:pk>/edit/', views.post_edit, name='post_edit'),
    path('post/<int:pk>/detail/', views.post_detail_partial, name='post_detail_partial'),
    path('comment/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    path('comment/<int:pk>/edit/', views.comment_edit, name='comment_edit'),
    path('comment/<int:pk>/item/', views.comment_item_partial, name='comment_item'),
    path('prompts/', views.prompt_lab, name='prompt_lab'),
    path('tools/', views.tool_guide, name='tool_guide'),
    path('manuals/', views.service_guide_list, name='service_guide_list'),
    path('manuals/<int:pk>/', views.service_guide_detail, name='service_guide_detail'),
    path('about/', views.about, name='about'),
    path('settings/', views.settings_view, name='settings'),
    path('select-role/', views.select_role, name='select_role'),
    path('sso/schoolit/', views.sso_to_schoolit, name='sso_schoolit'),
    path('policy/', views.policy_view, name='policy'),
    path('update-email/', views.update_email, name='update_email'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('feedback/', views.feedback_view, name='feedback'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
]
