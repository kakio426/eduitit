from django.urls import path

from . import views


app_name = "ocrdesk"

urlpatterns = [
    path("", views.main, name="main"),
]

