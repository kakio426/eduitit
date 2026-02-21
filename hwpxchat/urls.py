from django.urls import path

from . import views

app_name = "hwpxchat"

urlpatterns = [
    path("", views.main, name="main"),
    path("process/", views.chat_process, name="chat_process"),
    path("reset/", views.chat_reset, name="chat_reset"),
]

