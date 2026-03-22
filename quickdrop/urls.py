from django.urls import path

from . import views


app_name = "quickdrop"


urlpatterns = [
    path("", views.landing_view, name="landing"),
    path("open/", views.open_view, name="open"),
    path("c/<slug:slug>/", views.channel_view, name="channel"),
    path("pair/<path:token>/", views.pair_view, name="pair"),
    path("c/<slug:slug>/send-text/", views.send_text_view, name="send_text"),
    path("c/<slug:slug>/send-image/", views.send_image_view, name="send_image"),
    path("c/<slug:slug>/end-session/", views.end_session_view, name="end_session"),
    path("c/<slug:slug>/items/<int:item_id>/image/", views.item_image_view, name="item_image"),
    path("c/<slug:slug>/devices/<slug:device_id>/rename/", views.rename_device_view, name="rename_device"),
    path("c/<slug:slug>/devices/<slug:device_id>/revoke/", views.revoke_device_view, name="revoke_device"),
    path("share-target/", views.share_target_view, name="share_target"),
    path("manifest.webmanifest", views.manifest_view, name="manifest"),
    path("sw.js", views.service_worker_view, name="service_worker"),
]
