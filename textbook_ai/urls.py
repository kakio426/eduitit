from django.urls import path

from . import views


app_name = "textbook_ai"


urlpatterns = [
    path("", views.main_view, name="main"),
    path("upload/", views.upload_document_view, name="upload"),
    path("<uuid:document_id>/", views.document_detail_view, name="detail"),
    path("<uuid:document_id>/reparse/", views.reparse_document_view, name="reparse"),
    path("<uuid:document_id>/search/", views.document_search_view, name="search"),
    path("<uuid:document_id>/pdf/", views.document_pdf_view, name="pdf"),
]
