from django.urls import path

from . import views

app_name = "hwpxchat"

urlpatterns = [
    path("", views.main, name="main"),
    path("process/", views.chat_process, name="chat_process"),
    path("reset/", views.chat_reset, name="chat_reset"),
    path("download/", views.download_markdown, name="download_markdown"),
    path("documents/<uuid:document_id>/", views.document_detail, name="document_detail"),
    path("documents/<uuid:document_id>/ask/", views.ask_document, name="ask_document"),
]
