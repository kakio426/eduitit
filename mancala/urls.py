from django.urls import path

from . import views

app_name = "mancala"

urlpatterns = [
    path("", views.main, name="main"),
    path("api/state/", views.api_state, name="api_state"),
    path("api/move/", views.api_move, name="api_move"),
]
