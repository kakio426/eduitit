from django.urls import path

from . import views

app_name = "math_games"

urlpatterns = [
    path("", views.index, name="index"),
    path("nim/", views.nim_page, name="nim"),
    path("24/", views.twenty_four_page, name="twenty_four"),
    path("2048/", views.game_2048_page, name="game_2048"),
    path("api/nim/start/", views.api_nim_start, name="api_nim_start"),
    path("api/nim/<uuid:session_id>/status/", views.api_nim_status, name="api_nim_status"),
    path("api/nim/<uuid:session_id>/move/", views.api_nim_move, name="api_nim_move"),
    path("api/24/start/", views.api_twenty_four_start, name="api_twenty_four_start"),
    path("api/24/<uuid:session_id>/answer/", views.api_twenty_four_answer, name="api_twenty_four_answer"),
    path("api/24/<uuid:session_id>/hint/", views.api_twenty_four_hint, name="api_twenty_four_hint"),
    path("api/2048/start/", views.api_2048_start, name="api_2048_start"),
    path("api/2048/<uuid:session_id>/status/", views.api_2048_status, name="api_2048_status"),
    path("api/2048/<uuid:session_id>/move/", views.api_2048_move, name="api_2048_move"),
]
