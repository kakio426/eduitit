from django.urls import path
from . import views

app_name = 'studentmbti'

urlpatterns = [
    # 공개 랜딩 페이지
    path('', views.landing_page, name='landing'),
    
    # 교사용 대시보드
    path('dashboard/', views.dashboard, name='dashboard'),
    path('session/create/', views.session_create, name='session_create'),
    path('session/<uuid:session_id>/detail/', views.session_detail, name='session_detail'),
    path('session/<uuid:session_id>/results-partial/', views.session_results_partial, name='session_results_partial'),
    path('session/<uuid:session_id>/toggle/', views.session_toggle_active, name='session_toggle'),
    path('session/<uuid:session_id>/export/', views.export_excel, name='export_excel'),
    path('result/<uuid:result_id>/teacher/', views.result_detail_teacher, name='result_detail_teacher'),
    
    # 학생용 (비회원)
    path('session/<uuid:session_id>/', views.session_test, name='session_test'),
    path('session/<uuid:session_id>/analyze/', views.analyze, name='analyze'),
    path('result/<uuid:result_id>/', views.result, name='result'),
]
