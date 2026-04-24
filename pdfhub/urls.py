from django.urls import path

from . import views


app_name = "pdfhub"

urlpatterns = [
    path("", views.main, name="main"),
]
