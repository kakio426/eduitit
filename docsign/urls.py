from django.urls import path

from . import views


app_name = "docsign"


urlpatterns = [
    path("", views.job_list, name="list"),
    path("create/", views.job_create, name="create"),
    path("<int:job_id>/", views.job_detail, name="detail"),
    path("<int:job_id>/source/", views.job_source_document, name="source_document"),
    path("<int:job_id>/signed/", views.job_signed_document, name="signed_document"),
    path("<int:job_id>/position/", views.job_position, name="position"),
    path("<int:job_id>/sign/", views.job_sign, name="sign"),
    path("<int:job_id>/download/", views.job_download_signed, name="download"),
]
