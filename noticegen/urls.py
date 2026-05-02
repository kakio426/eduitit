from django.urls import path

from . import views

app_name = "noticegen"

urlpatterns = [
    path("", views.main, name="main"),
    path("daily-recommendation/", views.daily_recommendation, name="daily_recommendation"),
    path("generate/", views.generate_notice, name="generate"),
    path("generate-mini/", views.generate_notice_mini, name="generate_mini"),
]
