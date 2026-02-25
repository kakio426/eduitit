from django.urls import path

from . import views

app_name = "handoff"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("groups/create/", views.group_create, name="group_create"),
    path("groups/<uuid:group_id>/", views.group_detail, name="group_detail"),
    path("groups/<uuid:group_id>/update/", views.group_update, name="group_update"),
    path("groups/<uuid:group_id>/delete/", views.group_delete, name="group_delete"),
    path("groups/<uuid:group_id>/members/add/", views.group_members_add, name="group_members_add"),
    path("groups/<uuid:group_id>/members/<int:member_id>/update/", views.group_member_update, name="group_member_update"),
    path("groups/<uuid:group_id>/members/<int:member_id>/delete/", views.group_member_delete, name="group_member_delete"),
    path("sessions/create/", views.session_create, name="session_create"),
    path("sessions/<uuid:session_id>/", views.session_detail, name="session_detail"),
    path("sessions/<uuid:session_id>/edit/", views.session_edit, name="session_edit"),
    path("sessions/<uuid:session_id>/delete/", views.session_delete, name="session_delete"),
    path("sessions/<uuid:session_id>/status/", views.session_toggle_status, name="session_toggle_status"),
    path("sessions/<uuid:session_id>/export-csv/", views.session_export_csv, name="session_export_csv"),
    path(
        "sessions/<uuid:session_id>/receipts/<int:receipt_id>/state/",
        views.receipt_set_state,
        name="receipt_set_state",
    ),
]
