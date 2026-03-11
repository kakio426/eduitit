from django.urls import path

from . import views

app_name = "noticegen"

urlpatterns = [
    path("", views.main, name="main"),
    path("generate/", views.generate_notice, name="generate"),
    path("generate-mini/", views.generate_notice_mini, name="generate_mini"),
    path("workflow/consent/", views.start_consent_followup, name="start_consent_followup"),
    path("workflow/signatures/", views.start_signature_followup, name="start_signature_followup"),
]
