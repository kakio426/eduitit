from django.urls import path

from . import views


app_name = "teacher_law"


urlpatterns = [
    path("", views.main_view, name="main"),
    path("ask/", views.ask_question_api, name="ask"),
]

