from django.urls import path
from . import views

app_name = 'collect'

urlpatterns = [
    # 공개 랜딩
    path('', views.landing, name='landing'),
    path('join/', views.join, name='join'),

    # 교사용 (로그인 필수)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create/', views.request_create, name='request_create'),
    path('<uuid:request_id>/edit/', views.request_edit, name='request_edit'),
    path('<uuid:request_id>/detail/', views.request_detail, name='request_detail'),
    path('<uuid:request_id>/submissions-partial/', views.submissions_partial, name='submissions_partial'),
    path('<uuid:request_id>/choice-stats-partial/', views.choice_stats_partial, name='choice_stats_partial'),
    path('<uuid:request_id>/toggle/', views.request_toggle, name='request_toggle'),
    path('<uuid:request_id>/extend-deadline/', views.request_extend_deadline, name='request_extend_deadline'),
    path('<uuid:request_id>/extend-retention/', views.request_extend_retention, name='request_extend_retention'),
    path('<uuid:request_id>/delete/', views.request_delete, name='request_delete'),
    path('<uuid:request_id>/export-csv/', views.export_csv, name='export_csv'),

    # 제출자용 (비로그인)
    path('s/<str:code>/', views.short_link, name='short_link'),
    path('<uuid:request_id>/submit/', views.submit, name='submit'),
    path('<uuid:request_id>/submit/process/', views.submit_process, name='submit_process'),
    path('<uuid:request_id>/template-download/', views.template_download, name='template_download'),
    
    # 제출물 관리 및 파일 다운로드
    path('submission/<uuid:management_id>/', views.submission_manage, name='submission_manage'),
    path('submission/<uuid:management_id>/edit/', views.submission_edit, name='submission_edit'),
    path('submission/<uuid:management_id>/delete/', views.submission_delete, name='submission_delete'),
    path('submission/<uuid:submission_id>/download/', views.submission_download, name='submission_download'),
]
