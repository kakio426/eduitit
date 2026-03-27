from django.contrib import admin

from core.admin_helpers import ReadOnlyModelAdmin

from .models import (
    ActionInvocation,
    SavedView,
    SheetCell,
    SheetColumn,
    SheetRow,
    SheetTab,
    Sheetbook,
    SheetbookMetricEvent,
)


admin.site.register(
    [
        Sheetbook,
        SheetTab,
        SheetColumn,
        SheetRow,
        SheetCell,
        SavedView,
        ActionInvocation,
        SheetbookMetricEvent,
    ],
    ReadOnlyModelAdmin,
)
