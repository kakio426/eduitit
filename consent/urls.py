from django.urls import path

from . import views

app_name = "consent"

urlpatterns = [
    path("", views.consent_dashboard, name="dashboard"),
    path("create/", views.consent_create, name="create"),
    path("create/step1/", views.consent_create_step1, name="create_step1"),
    path("<uuid:request_id>/setup/", views.consent_setup_positions, name="setup_positions"),
    path("<uuid:request_id>/recipients/", views.consent_recipients, name="recipients"),
    path("<uuid:request_id>/", views.consent_detail, name="detail"),
    path("<uuid:request_id>/preview/", views.consent_preview_positions, name="preview_positions"),
    path("<uuid:request_id>/document/source/", views.consent_document_source, name="document_source"),
    path("<uuid:request_id>/send/", views.consent_send, name="send"),
    path("<uuid:request_id>/download/merged/", views.consent_download_merged, name="download_merged"),
    path("recipient/<int:recipient_id>/download/", views.consent_download_recipient_pdf, name="download_recipient_pdf"),
    path("public/<str:token>/verify/", views.consent_verify, name="verify"),
    path("public/<str:token>/sign/", views.consent_sign, name="sign"),
    path("public/<str:token>/complete/", views.consent_complete, name="complete"),
]
