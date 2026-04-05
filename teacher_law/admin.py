from django.contrib import admin

from .models import LegalChatMessage, LegalChatSession, LegalCitation, LegalQueryAudit


@admin.register(LegalChatSession)
class LegalChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "is_active", "last_message_at", "updated_at")
    search_fields = ("user__username", "user__email", "title")
    list_filter = ("is_active",)


@admin.register(LegalChatMessage)
class LegalChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "is_quick_question", "created_at")
    search_fields = ("body", "normalized_question", "session__user__username")
    list_filter = ("role", "is_quick_question")


@admin.register(LegalCitation)
class LegalCitationAdmin(admin.ModelAdmin):
    list_display = ("id", "law_name", "article_label", "fetched_at", "display_order")
    search_fields = ("law_name", "article_label", "quote")


@admin.register(LegalQueryAudit)
class LegalQueryAuditAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "topic",
        "scope_supported",
        "cache_hit",
        "search_attempt_count",
        "detail_fetch_count",
        "elapsed_ms",
        "created_at",
    )
    search_fields = ("original_question", "normalized_question", "failure_reason", "error_message")
    list_filter = ("scope_supported", "cache_hit", "topic")

