from django.urls import path

from . import views

app_name = "signatures"

urlpatterns = [
    # Existing training-signature track.
    path("", views.session_list, name="list"),
    path("create/", views.session_create, name="create"),
    path("create/prepare-roster-return/", views.prepare_roster_return, name="prepare_roster_return"),
    path("<uuid:uuid>/", views.session_detail, name="detail"),
    path("<uuid:uuid>/edit/", views.session_edit, name="edit"),
    path("<uuid:uuid>/delete/", views.session_delete, name="delete"),
    path(
        "<uuid:uuid>/attachments/<int:attachment_id>/download/",
        views.session_attachment_download,
        name="attachment_download",
    ),
    path("<uuid:uuid>/print/download/", views.print_pdf_download, name="print_pdf"),
    path("<uuid:uuid>/print/", views.print_view, name="print"),
    path("<uuid:uuid>/signature-sort-mode/", views.update_signature_sort_mode, name="update_signature_sort_mode"),
    path("<uuid:uuid>/toggle/", views.toggle_active, name="toggle"),
    path("<uuid:uuid>/access-code/", views.update_access_code, name="update_access_code"),
    path("sign/<uuid:uuid>/", views.sign, name="sign"),
    path(
        "sign/<uuid:uuid>/attachments/<int:attachment_id>/download/",
        views.sign_attachment_download,
        name="sign_attachment_download",
    ),
    path("signature/<int:pk>/delete/", views.delete_signature, name="delete_signature"),
    path("styles/", views.style_list, name="style_list"),
    path("styles/save/", views.save_style_api, name="save_style_api"),
    path("api/save_image/", views.save_signature_image_api, name="save_image_api"),
    path("api/my_signatures/", views.get_my_signatures_api, name="get_my_signatures_api"),
    path("api/my_signatures/<int:pk>/delete/", views.delete_saved_signature_api, name="delete_saved_signature_api"),
    path("styles/<int:pk>/delete/", views.delete_style_api, name="delete_style_api"),
    path("maker/", views.signature_maker, name="maker"),
    path("<uuid:uuid>/participants/add/", views.add_expected_participants, name="add_participants"),
    path("<uuid:uuid>/participants/sync-roster/", views.sync_expected_participants_from_roster, name="sync_roster"),
    path("<uuid:uuid>/participants/upload/", views.upload_participants_file, name="upload_participants_file"),
    path("<uuid:uuid>/participants/", views.get_expected_participants, name="get_participants"),
    path("<uuid:uuid>/participants/<int:participant_id>/delete/", views.delete_expected_participant, name="delete_participant"),
    path(
        "<uuid:uuid>/participants/<int:participant_id>/manual-order/",
        views.update_expected_participant_manual_order,
        name="update_participant_manual_order",
    ),
    path(
        "<uuid:uuid>/participants/<int:participant_id>/correct-affiliation/",
        views.correct_expected_participant_affiliation,
        name="correct_participant_affiliation",
    ),
    path("<uuid:uuid>/signatures/<int:signature_id>/match/", views.match_signature, name="match_signature"),
    path(
        "<uuid:uuid>/signatures/<int:signature_id>/manual-order/",
        views.update_signature_manual_order,
        name="update_signature_manual_order",
    ),
    path(
        "<uuid:uuid>/signatures/<int:signature_id>/correct-affiliation/",
        views.correct_signature_affiliation,
        name="correct_signature_affiliation",
    ),
    path("<uuid:uuid>/affiliations/bulk-correct/", views.bulk_correct_affiliation, name="bulk_correct_affiliation"),
    path("template/csv/", views.download_participant_template, {"format": "csv"}, name="download_template_csv"),
    path("template/excel/", views.download_participant_template, {"format": "excel"}, name="download_template_excel"),
]
