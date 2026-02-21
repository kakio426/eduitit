from django.urls import path

from . import views

app_name = "noticegen"

urlpatterns = [
    path("", views.main, name="main"),
    path("generate/", views.generate_notice, name="generate"),
]

