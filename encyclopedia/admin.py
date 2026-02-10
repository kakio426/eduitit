from django.contrib import admin
from .models import NotebookEntry


@admin.register(NotebookEntry)
class NotebookEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'creator', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'description']
    raw_id_fields = ['creator']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creator')
