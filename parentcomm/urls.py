from django.urls import path

from . import views

app_name = "parentcomm"

urlpatterns = [
    path("", views.main, name="main"),
    path("urgent/<uuid:access_id>/", views.urgent_entry, name="urgent_entry"),
    path("urgent-alerts/<int:alert_id>/ack/", views.acknowledge_urgent_alert, name="acknowledge_urgent_alert"),
]

