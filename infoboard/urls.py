from django.urls import path

from . import views

app_name = 'infoboard'

urlpatterns = [
    # ── 교사 대시보드 ──
    path('', views.dashboard, name='dashboard'),

    # ── 보드 CRUD ──
    path('board/create/', views.board_create, name='board_create'),
    path('board/<uuid:board_id>/', views.board_detail, name='board_detail'),
    path('board/<uuid:board_id>/layout/', views.board_layout, name='board_layout'),
    path('board/<uuid:board_id>/edit/', views.board_edit, name='board_edit'),
    path('board/<uuid:board_id>/delete/', views.board_delete, name='board_delete'),

    # ── 카드 CRUD ──
    path('board/<uuid:board_id>/card/add/', views.card_add, name='card_add'),
    path('card/<uuid:card_id>/edit/', views.card_edit, name='card_edit'),
    path('card/<uuid:card_id>/delete/', views.card_delete, name='card_delete'),
    path('card/<uuid:card_id>/pin/', views.card_toggle_pin, name='card_toggle_pin'),
    path('card/<uuid:card_id>/comments/', views.card_comments, name='card_comments'),
    path('card/<uuid:card_id>/comment/', views.card_comment_create, name='card_comment_create'),
    path('comment/<int:comment_id>/hide/', views.comment_hide, name='comment_hide'),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),

    # ── 태그 ──
    path('tags/json/', views.tags_json, name='tags_json'),

    # ── 공유 보드 (비로그인) ──
    path('s/<uuid:link_id>/', views.public_board, name='public_board'),
    path('s/<uuid:link_id>/submit/', views.student_submit, name='student_submit'),
    path('s/<uuid:link_id>/card/<uuid:card_id>/comments/', views.public_card_comments, name='public_card_comments'),
    path('s/<uuid:link_id>/card/<uuid:card_id>/comment/', views.public_comment_create, name='public_comment_create'),

    # ── 공유 링크 관리 ──
    path('board/<uuid:board_id>/share/', views.share_panel, name='share_panel'),
    path('board/<uuid:board_id>/share/create/', views.share_create, name='share_create'),

    # ── 검색 ──
    path('search/', views.search, name='search'),

    # ── 파일 다운로드 ──
    path('card/<uuid:card_id>/download/', views.card_download, name='card_download'),

    # ── 컬렉션 CRUD ──
    path('collections/', views.collection_list, name='collection_list'),
    path('collections/create/', views.collection_create, name='collection_create'),
    path('collections/<uuid:collection_id>/', views.collection_detail, name='collection_detail'),
    path('collections/<uuid:collection_id>/edit/', views.collection_edit, name='collection_edit'),
    path('collections/<uuid:collection_id>/delete/', views.collection_delete, name='collection_delete'),
    path('collections/<uuid:collection_id>/toggle-board/', views.collection_toggle_board, name='collection_toggle_board'),

    # ── OG 메타 추출 API ──
    path('api/og-meta/', views.fetch_og_meta, name='fetch_og_meta'),

    # ── 내보내기 ──
    path('board/<uuid:board_id>/export/csv/', views.board_export_csv, name='board_export_csv'),
]
