from django.urls import path
from . import views

app_name = 'school_violence'

urlpatterns = [
    # 채팅 관련
    path('', views.chat_view, name='chat'),
    path('send/', views.send_message, name='send_message'),
    path('set-mode/', views.set_mode, name='set_mode'),
    path('clear/', views.clear_chat, name='clear_chat'),

    # 관리자 문서 관리
    path('docs/', views.manage_docs, name='manage_docs'),
    path('docs/<int:pk>/process/', views.process_document, name='process_document'),
    path('docs/<int:pk>/delete/', views.delete_document, name='delete_document'),
]
