from django.urls import path

from . import views

app_name = "fairy_games"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:variant>/rules/", views.rules, name="rules"),
    path("<slug:variant>/play/", views.play, name="play"),
]

