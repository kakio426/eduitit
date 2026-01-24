from django.contrib import admin
from .models import PadletDocument, PadletBotSettings, LinkedPadletBoard


@admin.register(PadletDocument)
class PadletDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'file_type', 'is_processed', 'chunk_count', 'uploaded_by', 'created_at']
    list_filter = ['file_type', 'is_processed', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['is_processed', 'chunk_count', 'created_at', 'updated_at']


@admin.register(LinkedPadletBoard)
class LinkedPadletBoardAdmin(admin.ModelAdmin):
    list_display = ['title', 'board_id', 'post_count', 'is_processed', 'chunk_count', 'last_synced']
    list_filter = ['is_processed', 'created_at']
    search_fields = ['title', 'board_id']
    readonly_fields = ['board_id', 'is_processed', 'chunk_count', 'post_count', 'last_synced', 'created_at', 'updated_at']


@admin.register(PadletBotSettings)
class PadletBotSettingsAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
