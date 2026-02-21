from django.urls import path

from . import views

app_name = "ppobgi"

urlpatterns = [
    path("", views.main, name="main"),
    path("api/roster-names/", views.roster_names, name="roster_names"),
]
