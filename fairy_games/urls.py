from django.urls import path

from . import views

app_name = "fairy_games"

urlpatterns = [
    path("", views.index, name="index"),
    # Product.launch_route_name용 고정 진입점 (kwargs 없는 reverse 보장)
    path("dobutsu/play/", views.play, {"variant": "dobutsu"}, name="play_dobutsu"),
    path("cfour/play/", views.play, {"variant": "cfour"}, name="play_cfour"),
    path("isolation/play/", views.play, {"variant": "isolation"}, name="play_isolation"),
    path("ataxx/play/", views.play, {"variant": "ataxx"}, name="play_ataxx"),
    path("breakthrough/play/", views.play, {"variant": "breakthrough"}, name="play_breakthrough"),
    path("<slug:variant>/rules/", views.rules, name="rules"),
    path("<slug:variant>/play/", views.play, name="play"),
]
