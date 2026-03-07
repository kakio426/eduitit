from django.urls import path

from . import views

app_name = "docviewer"

urlpatterns = [
    path("", views.main, name="main"),
]
