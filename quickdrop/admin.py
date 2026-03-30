from django.contrib import admin

from core.admin_helpers import HiddenReadOnlyModelAdmin

from .models import QuickdropChannel, QuickdropDevice, QuickdropItem, QuickdropSession


admin.site.register(
    [QuickdropChannel, QuickdropDevice, QuickdropItem, QuickdropSession],
    HiddenReadOnlyModelAdmin,
)
