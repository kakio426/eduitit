from django.urls import path
from . import views

app_name = 'padlet_bot'

urlpatterns = [
    # 채팅 관련
    path('', views.chat_view, name='chat'),
    path('send/', views.send_message, name='send_message'),
    path('clear/', views.clear_chat, name='clear_chat'),

    # 관리자 문서 관리 (파일 업로드)
    path('docs/', views.manage_docs, name='manage_docs'),
    path('docs/<int:pk>/process/', views.process_document, name='process_document'),
    path('docs/<int:pk>/delete/', views.delete_document, name='delete_document'),

    # 패들릿 API 연동
    path('api/', views.api_connect, name='api_connect'),
    path('api/link/', views.link_padlet, name='link_padlet'),
    path('api/<int:pk>/sync/', views.sync_padlet, name='sync_padlet'),
    path('api/<int:pk>/unlink/', views.unlink_padlet, name='unlink_padlet'),
]
