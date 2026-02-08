from django.contrib import admin
from .models import GuidelineDocument, ConsultationMode


@admin.register(GuidelineDocument)
class GuidelineDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_processed', 'chunk_count', 'uploaded_by', 'created_at']
    list_filter = ['category', 'is_processed', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['is_processed', 'chunk_count', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploaded_by')


@admin.register(ConsultationMode)
class ConsultationModeAdmin(admin.ModelAdmin):
    list_display = ['mode_key', 'display_name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['display_name', 'description']
