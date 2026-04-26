from django.contrib import admin

from .models import DailyNoticeRecommendation, NoticeGenerationAttempt, NoticeGenerationCache


@admin.register(NoticeGenerationCache)
class NoticeGenerationCacheAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target",
        "topic",
        "tone",
        "prompt_version",
        "hit_count",
        "last_used_at",
    )
    list_filter = ("target", "topic", "tone", "prompt_version")
    search_fields = ("keywords_norm", "context_norm", "result_text")
    readonly_fields = ("created_at", "last_used_at")


@admin.register(NoticeGenerationAttempt)
class NoticeGenerationAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "session_key",
        "target",
        "topic",
        "charged",
        "status",
        "created_at",
    )
    list_filter = ("target", "topic", "charged", "status")
    search_fields = ("user__username", "session_key", "error_code", "key_hash")
    readonly_fields = ("created_at",)


@admin.register(DailyNoticeRecommendation)
class DailyNoticeRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "recommendation_date",
        "topic_key",
        "context_label",
        "status",
        "served_count",
        "last_served_at",
    )
    list_filter = ("status", "topic_key", "recommendation_date")
    search_fields = ("topic_key", "context_label", "result_text", "error_code")
    readonly_fields = ("created_at", "updated_at", "last_served_at")
