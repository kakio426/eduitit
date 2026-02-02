from django.urls import path
from . import views

app_name = 'signatures'

urlpatterns = [
    # 관리자용 (로그인 필요)
    path('', views.session_list, name='list'),
    path('create/', views.session_create, name='create'),
    path('<uuid:uuid>/', views.session_detail, name='detail'),
    path('<uuid:uuid>/edit/', views.session_edit, name='edit'),
    path('<uuid:uuid>/delete/', views.session_delete, name='delete'),
    path('<uuid:uuid>/print/', views.print_view, name='print'),
    path('<uuid:uuid>/toggle/', views.toggle_active, name='toggle'),

    # 공개 서명 페이지 (로그인 불필요)
    path('sign/<uuid:uuid>/', views.sign, name='sign'),

    # 서명 삭제 (AJAX)
    path('signature/<int:pk>/delete/', views.delete_signature, name='delete_signature'),
    # 스타일 즐겨찾기
    path('styles/', views.style_list, name='style_list'),
    path('styles/save/', views.save_style_api, name='save_style_api'),
    path('api/save_image/', views.save_signature_image_api, name='save_image_api'), # New
    path('api/my_signatures/', views.get_my_signatures_api, name='get_my_signatures_api'),
    path('styles/<int:pk>/delete/', views.delete_style_api, name='delete_style_api'),
    path('maker/', views.signature_maker, name='maker'),
    
    # Expected Participants (Phase 2)
    path('<uuid:uuid>/participants/add/', views.add_expected_participants, name='add_participants'),
    path('<uuid:uuid>/participants/upload/', views.upload_participants_file, name='upload_participants_file'),
    path('<uuid:uuid>/participants/', views.get_expected_participants, name='get_participants'),
    path('<uuid:uuid>/participants/<int:participant_id>/delete/', views.delete_expected_participant, name='delete_participant'),
    path('<uuid:uuid>/signatures/<int:signature_id>/match/', views.match_signature, name='match_signature'),

    # 참석자 명단 양식 다운로드
    path('template/csv/', views.download_participant_template, {'format': 'csv'}, name='download_template_csv'),
    path('template/excel/', views.download_participant_template, {'format': 'excel'}, name='download_template_excel'),
]
