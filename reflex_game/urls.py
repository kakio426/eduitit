from django.urls import path

from . import views

app_name = "reflex_game"

urlpatterns = [
    path("", views.main, name="main"),
]

