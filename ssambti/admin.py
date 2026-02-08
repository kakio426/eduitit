from django.contrib import admin
from .models import SsambtiResult


@admin.register(SsambtiResult)
class SsambtiResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'mbti_type', 'animal_name', 'created_at')
    list_filter = ('mbti_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'mbti_type', 'animal_name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
