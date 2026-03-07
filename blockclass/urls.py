from django.urls import path

from . import views

app_name = "blockclass"

urlpatterns = [
    path("", views.main, name="main"),
]
