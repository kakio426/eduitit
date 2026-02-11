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
    path('<uuid:request_id>/detail/', views.request_detail, name='request_detail'),
    path('<uuid:request_id>/submissions-partial/', views.submissions_partial, name='submissions_partial'),
    path('<uuid:request_id>/toggle/', views.request_toggle, name='request_toggle'),
    path('<uuid:request_id>/delete/', views.request_delete, name='request_delete'),
    path('<uuid:request_id>/export-csv/', views.export_csv, name='export_csv'),

    # 제출자용 (비로그인)
    path('s/<str:code>/', views.short_link, name='short_link'),
    path('<uuid:request_id>/submit/', views.submit, name='submit'),
    path('<uuid:request_id>/submit/process/', views.submit_process, name='submit_process'),
    path('<uuid:request_id>/template-download/', views.template_download, name='template_download'),
]
