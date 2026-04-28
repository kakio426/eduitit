from django.contrib import admin

from .models import (
    BambooComment,
    BambooCommentReport,
    BambooConsent,
    BambooLike,
    BambooReport,
    BambooStory,
)


@admin.register(BambooStory)
class BambooStoryAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "anon_handle",
        "author",
        "is_public",
        "is_hidden_by_report",
        "like_count",
        "comment_count",
        "view_count",
        "created_at",
    )
    list_filter = ("is_public", "is_hidden_by_report", "created_at")
    search_fields = ("title", "anon_handle", "fable_output", "author__username")
    readonly_fields = ("uuid", "created_at")
    exclude = ("input_masked",)


@admin.register(BambooLike)
class BambooLikeAdmin(admin.ModelAdmin):
    list_display = ("user", "story", "created_at")
    search_fields = ("user__username", "story__anon_handle")


@admin.register(BambooReport)
class BambooReportAdmin(admin.ModelAdmin):
    list_display = ("user", "story", "reason", "created_at", "reviewed_at", "reviewed_by")
    list_filter = ("created_at", "reviewed_at")
    search_fields = ("user__username", "story__anon_handle", "reason")


@admin.register(BambooComment)
class BambooCommentAdmin(admin.ModelAdmin):
    list_display = ("anon_handle", "story", "author", "is_hidden_by_report", "created_at")
    list_filter = ("is_hidden_by_report", "created_at")
    search_fields = ("anon_handle", "body_masked", "author__username", "story__title")


@admin.register(BambooCommentReport)
class BambooCommentReportAdmin(admin.ModelAdmin):
    list_display = ("user", "comment", "reason", "created_at", "reviewed_at", "reviewed_by")
    list_filter = ("created_at", "reviewed_at")
    search_fields = ("user__username", "comment__anon_handle", "comment__body_masked", "reason")


@admin.register(BambooConsent)
class BambooConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "accepted_at")
    search_fields = ("user__username", "user__email")
