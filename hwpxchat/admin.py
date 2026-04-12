from django.contrib import admin

from core.admin_helpers import ReadOnlyModelAdmin

from .models import HwpxDocument, HwpxDocumentQuestion, HwpxWorkItem


admin.site.register(
    [HwpxDocument, HwpxDocumentQuestion, HwpxWorkItem],
    ReadOnlyModelAdmin,
)
