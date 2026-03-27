from django.contrib import admin
from core.admin_helpers import ReadOnlyModelAdmin

from .models import ArtClass, ArtClassAttachment, ArtStep


class ArtStepInline(admin.TabularInline):
    model = ArtStep
    extra = 1
    fields = ['step_number', 'description', 'image']


@admin.register(ArtClass)
class ArtClassAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'title',
        'auto_category',
        'auto_grade_band',
        'auto_confidence',
        'youtube_url',
        'default_interval',
        'created_at',
        'created_by',
    ]
    list_filter = ['created_at', 'auto_category', 'auto_grade_band', 'is_auto_classified']
    search_fields = ['title', 'youtube_url', 'search_text']
    inlines = [ArtStepInline]
    readonly_fields = ['created_at', 'auto_confidence']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(ArtStep)
class ArtStepAdmin(admin.ModelAdmin):
    list_display = ['id', 'art_class', 'step_number', 'description', 'image']
    list_filter = ['art_class']
    search_fields = ['description']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('art_class')


admin.site.register([ArtClassAttachment], ReadOnlyModelAdmin)
