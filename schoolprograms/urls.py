from django.urls import path

from . import views


app_name = "schoolprograms"


urlpatterns = [
    path("", views.landing, name="landing"),
    path("listings/<str:slug>/", views.listing_detail, name="listing_detail"),
    path(
        "listings/<str:slug>/attachments/<int:attachment_id>/download/",
        views.download_listing_attachment,
        name="download_listing_attachment",
    ),
    path("listings/<str:slug>/inquire/", views.create_inquiry, name="create_inquiry"),
    path("listings/<str:slug>/save/", views.toggle_saved_listing, name="toggle_saved_listing"),
    path("listings/<str:slug>/compare/", views.toggle_compare_listing, name="toggle_compare_listing"),
    path("providers/<str:slug>/", views.provider_detail, name="provider_detail"),
    path("saved/", views.teacher_saved_listings, name="teacher_saved_listings"),
    path("compare/", views.teacher_compare_listings, name="teacher_compare_listings"),
    path("compare/<str:slug>/inquire/", views.create_compare_inquiry, name="create_compare_inquiry"),
    path("inquiries/", views.teacher_inquiries, name="teacher_inquiries"),
    path("inquiries/<uuid:thread_id>/", views.teacher_inquiry_detail, name="teacher_inquiry_detail"),
    path("vendor/", views.vendor_dashboard, name="vendor_dashboard"),
    path("vendor/profile/", views.vendor_profile_edit, name="vendor_profile_edit"),
    path("vendor/listings/new/", views.vendor_listing_create, name="vendor_listing_create"),
    path("vendor/listings/<str:slug>/edit/", views.vendor_listing_edit, name="vendor_listing_edit"),
    path("vendor/inquiries/", views.vendor_inquiries, name="vendor_inquiries"),
    path("vendor/inquiries/<uuid:thread_id>/", views.vendor_inquiry_detail, name="vendor_inquiry_detail"),
]
