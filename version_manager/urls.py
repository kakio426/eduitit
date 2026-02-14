from django.urls import path

from . import views

app_name = 'version_manager'

urlpatterns = [
    path('', views.document_list_view, name='document_list'),
    path('new/', views.document_create_view, name='document_create'),
    path('<int:document_id>/', views.document_detail_view, name='document_detail'),
    path('<int:document_id>/upload/', views.upload_version_view, name='upload_version'),
    path('<int:document_id>/delete/<int:version_id>/', views.delete_version_view, name='delete_version'),
    path('<int:document_id>/download/latest/', views.download_latest_view, name='download_latest'),
    path('<int:document_id>/download/published/', views.download_published_view, name='download_published'),
    path('<int:document_id>/download/<int:version_id>/', views.download_version_view, name='download_version'),
    path('<int:document_id>/publish/<int:version_id>/', views.set_published_view, name='set_published'),
    path('<int:document_id>/protected-phrases/add/', views.add_protected_phrase_view, name='add_protected_phrase'),
    path('<int:document_id>/protected-phrases/<int:phrase_id>/remove/', views.remove_protected_phrase_view, name='remove_protected_phrase'),
    path('<int:document_id>/share-links/create/', views.create_share_link_view, name='create_share_link'),
    path('<int:document_id>/share-links/<int:link_id>/toggle/', views.toggle_share_link_view, name='toggle_share_link'),
    path('share/<str:token>/', views.shared_upload_view, name='shared_upload'),
]
