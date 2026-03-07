from django.urls import path

from . import views

app_name = "slidesmith"

urlpatterns = [
    path("", views.main, name="main"),
    path("present/", views.present, name="present"),
]
