from django.contrib import admin

from .models import TimetableSyncLog


@admin.register(TimetableSyncLog)
class TimetableSyncLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "school_name",
        "sync_mode",
        "status",
        "applied_count",
        "updated_count",
        "conflict_count",
        "overwrite_existing",
    )
    list_filter = ("sync_mode", "status", "overwrite_existing", "created_at")
    search_fields = ("school_name", "school_slug", "summary_text", "user__username")
    readonly_fields = ("created_at",)
