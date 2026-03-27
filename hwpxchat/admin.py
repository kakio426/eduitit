from django.contrib import admin

from core.admin_helpers import ReadOnlyModelAdmin

from .models import HwpxDocument, HwpxDocumentQuestion, HwpxWorkItem, HwpxWorkItemSync


admin.site.register(
    [HwpxDocument, HwpxDocumentQuestion, HwpxWorkItem, HwpxWorkItemSync],
    ReadOnlyModelAdmin,
)
