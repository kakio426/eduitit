from django.urls import path

from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.main, name="main"),
    path("template/", views.download_template, name="download_template"),
    path("sync-logs.csv", views.download_sync_logs_csv, name="download_sync_logs_csv"),
]
