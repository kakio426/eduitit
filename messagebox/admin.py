from django.contrib import admin

from core.admin_helpers import ReadOnlyModelAdmin

from .models import DeveloperChatMessage, DeveloperChatReadState, DeveloperChatThread


admin.site.register(
    [DeveloperChatThread, DeveloperChatMessage, DeveloperChatReadState],
    ReadOnlyModelAdmin,
)
