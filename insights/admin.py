from django.contrib import admin
from django.db.models import Count
from .models import Insight


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_featured', 'likes_count_display', 'created_at')
    search_fields = ('title', 'content', 'kakio_note', 'tags')
    list_filter = ('is_featured', 'category', 'created_at')
    raw_id_fields = ('likes',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _likes_count=Count('likes', distinct=True)
        )

    def likes_count_display(self, obj):
        return obj._likes_count

    likes_count_display.short_description = '좋아요'
    likes_count_display.admin_order_field = '_likes_count'
