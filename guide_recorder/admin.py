from django.contrib import admin

from .models import GuideSession, GuideStep


class GuideStepInline(admin.TabularInline):
    model = GuideStep
    extra = 0
    fields = ('order', 'description', 'screenshot', 'click_x', 'click_y')
    readonly_fields = ('order', 'click_x', 'click_y', 'created_at')


@admin.register(GuideSession)
class GuideSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'step_count', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'created_by__username')
    readonly_fields = ('share_token', 'step_count', 'created_at', 'updated_at')
    raw_id_fields = ('created_by',)
    inlines = [GuideStepInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(GuideStep)
class GuideStepAdmin(admin.ModelAdmin):
    list_display = ('session', 'order', 'description', 'created_at')
    list_filter = ('session',)
    search_fields = ('session__title', 'description')
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session')
