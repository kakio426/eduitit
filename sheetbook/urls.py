from django.urls import path

from . import views

app_name = "sheetbook"

urlpatterns = [
    path("", views.index, name="index"),
    path("search/suggest/", views.search_suggest, name="search_suggest"),
    path("metrics/", views.metrics_dashboard, name="metrics_dashboard"),
    path("create/", views.create_sheetbook, name="create"),
    path("quick-create/", views.quick_create_sheetbook, name="quick_create"),
    path("quick-sample/", views.quick_sample_sheetbook, name="quick_sample"),
    path("quick-copy/", views.quick_copy_sheetbook, name="quick_copy"),
    path("bulk-archive/", views.bulk_archive_update, name="bulk_archive_update"),
    path("<int:pk>/archive/", views.archive_sheetbook, name="archive"),
    path("<int:pk>/unarchive/", views.unarchive_sheetbook, name="unarchive"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/tabs/create/", views.create_tab, name="create_tab"),
    path("<int:pk>/tabs/<int:tab_pk>/rename/", views.rename_tab, name="rename_tab"),
    path("<int:pk>/tabs/<int:tab_pk>/delete/", views.delete_tab, name="delete_tab"),
    path("<int:pk>/tabs/<int:tab_pk>/move-up/", views.move_tab_up, name="move_tab_up"),
    path("<int:pk>/tabs/<int:tab_pk>/move-down/", views.move_tab_down, name="move_tab_down"),
    path("<int:pk>/tabs/<int:tab_pk>/rows/create/", views.create_grid_row, name="create_grid_row"),
    path("<int:pk>/tabs/<int:tab_pk>/columns/create/", views.create_grid_column, name="create_grid_column"),
    path("<int:pk>/tabs/<int:tab_pk>/views/create/", views.create_saved_view, name="create_saved_view"),
    path(
        "<int:pk>/tabs/<int:tab_pk>/views/<int:view_pk>/delete/",
        views.delete_saved_view,
        name="delete_saved_view",
    ),
    path(
        "<int:pk>/tabs/<int:tab_pk>/views/<int:view_pk>/favorite/",
        views.toggle_saved_view_favorite,
        name="toggle_saved_view_favorite",
    ),
    path(
        "<int:pk>/tabs/<int:tab_pk>/views/<int:view_pk>/default/",
        views.set_saved_view_default,
        name="set_saved_view_default",
    ),
    path("<int:pk>/tabs/<int:tab_pk>/grid/", views.grid_data, name="grid_data"),
    path("<int:pk>/tabs/<int:tab_pk>/cells/update/", views.update_cell, name="update_cell"),
    path("<int:pk>/tabs/<int:tab_pk>/cells/paste/", views.paste_cells, name="paste_cells"),
    path("<int:pk>/tabs/<int:tab_pk>/import/", views.import_grid_tab_file, name="import_grid_tab_file"),
    path("<int:pk>/tabs/<int:tab_pk>/export/csv/", views.export_grid_tab_csv, name="export_grid_tab_csv"),
    path("<int:pk>/tabs/<int:tab_pk>/export/xlsx/", views.export_grid_tab_xlsx, name="export_grid_tab_xlsx"),
    path("<int:pk>/tabs/<int:tab_pk>/actions/execute/", views.execute_grid_action, name="execute_grid_action"),
    path("<int:pk>/tabs/<int:tab_pk>/actions/consent/review/", views.consent_seed_review, name="consent_seed_review"),
    path("<int:pk>/tabs/<int:tab_pk>/actions/history/", views.action_history, name="action_history"),
    path("<int:pk>/tabs/<int:tab_pk>/calendar/sync-from-schedule/", views.sync_calendar_from_schedule, name="sync_calendar_from_schedule"),
]
