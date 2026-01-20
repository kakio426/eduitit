from django.contrib import admin
from .models import Insight

@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'is_featured')
    search_fields = ('title', 'content', 'kakio_note')
    list_filter = ('is_featured', 'created_at')
