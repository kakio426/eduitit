from django.urls import path

from . import views

app_name = "sheetbook"

LEGACY_ROUTE_SPECS = [
    ("", "index"),
    ("search/suggest/", "search_suggest"),
    ("metrics/", "metrics_dashboard"),
    ("create/", "create"),
    ("quick-create/", "quick_create"),
    ("quick-sample/", "quick_sample"),
    ("quick-copy/", "quick_copy"),
    ("bulk-archive/", "bulk_archive_update"),
    ("<int:pk>/archive/", "archive"),
    ("<int:pk>/unarchive/", "unarchive"),
    ("<int:pk>/", "detail"),
    ("<int:pk>/tabs/create/", "create_tab"),
    ("<int:pk>/tabs/<int:tab_pk>/rename/", "rename_tab"),
    ("<int:pk>/tabs/<int:tab_pk>/delete/", "delete_tab"),
    ("<int:pk>/tabs/<int:tab_pk>/move-up/", "move_tab_up"),
    ("<int:pk>/tabs/<int:tab_pk>/move-down/", "move_tab_down"),
    ("<int:pk>/tabs/<int:tab_pk>/rows/create/", "create_grid_row"),
    ("<int:pk>/tabs/<int:tab_pk>/rows/<int:row_pk>/delete/", "delete_grid_row"),
    ("<int:pk>/tabs/<int:tab_pk>/rows/restore/", "restore_grid_row"),
    ("<int:pk>/tabs/<int:tab_pk>/columns/create/", "create_grid_column"),
    ("<int:pk>/tabs/<int:tab_pk>/columns/<int:column_pk>/update/", "update_grid_column"),
    ("<int:pk>/tabs/<int:tab_pk>/columns/<int:column_pk>/delete/", "delete_grid_column"),
    ("<int:pk>/tabs/<int:tab_pk>/columns/restore/", "restore_grid_column"),
    ("<int:pk>/tabs/<int:tab_pk>/views/create/", "create_saved_view"),
    ("<int:pk>/tabs/<int:tab_pk>/views/<int:view_pk>/delete/", "delete_saved_view"),
    ("<int:pk>/tabs/<int:tab_pk>/views/<int:view_pk>/favorite/", "toggle_saved_view_favorite"),
    ("<int:pk>/tabs/<int:tab_pk>/views/<int:view_pk>/default/", "set_saved_view_default"),
    ("<int:pk>/tabs/<int:tab_pk>/grid/", "grid_data"),
    ("<int:pk>/tabs/<int:tab_pk>/cells/update/", "update_cell"),
    ("<int:pk>/tabs/<int:tab_pk>/cells/paste/", "paste_cells"),
    ("<int:pk>/tabs/<int:tab_pk>/import/", "import_grid_tab_file"),
    ("<int:pk>/tabs/<int:tab_pk>/export/csv/", "export_grid_tab_csv"),
    ("<int:pk>/tabs/<int:tab_pk>/export/xlsx/", "export_grid_tab_xlsx"),
    ("<int:pk>/tabs/<int:tab_pk>/actions/execute/", "execute_grid_action"),
    ("<int:pk>/tabs/<int:tab_pk>/actions/consent/review/", "consent_seed_review"),
    ("<int:pk>/tabs/<int:tab_pk>/actions/history/", "action_history"),
    ("<int:pk>/tabs/<int:tab_pk>/calendar/link-settings/", "update_calendar_link_settings"),
    ("<int:pk>/tabs/<int:tab_pk>/calendar/sync-from-schedule/", "sync_calendar_from_schedule"),
]

urlpatterns = [path(route, views.service_retired, name=name) for route, name in LEGACY_ROUTE_SPECS]
urlpatterns.append(path("<path:legacy_path>", views.service_retired, name="legacy_fallback"))
