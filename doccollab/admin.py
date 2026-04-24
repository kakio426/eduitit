from django.contrib import admin

from .models import (
    DocAnalysis,
    DocAssistantQuestion,
    DocEditEvent,
    DocMembership,
    DocPresence,
    DocRevision,
    DocRoom,
    DocSnapshot,
    DocWorkspace,
)


@admin.register(DocWorkspace)
class DocWorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_by", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "created_by__username")


@admin.register(DocMembership)
class DocMembershipAdmin(admin.ModelAdmin):
    list_display = ("workspace", "user", "role", "status", "updated_at")
    list_filter = ("role", "status")
    search_fields = ("workspace__name", "user__username")


@admin.register(DocRoom)
class DocRoomAdmin(admin.ModelAdmin):
    list_display = ("title", "workspace", "source_format", "status", "created_by", "last_activity_at")
    list_filter = ("source_format", "status")
    search_fields = ("title", "workspace__name", "created_by__username")


@admin.register(DocRevision)
class DocRevisionAdmin(admin.ModelAdmin):
    list_display = ("room", "revision_number", "export_format", "is_published", "created_at")
    list_filter = ("export_format", "is_published")
    search_fields = ("room__title", "original_name")


@admin.register(DocAnalysis)
class DocAnalysisAdmin(admin.ModelAdmin):
    list_display = ("room", "status", "engine", "source_revision", "updated_at")
    list_filter = ("status", "engine")
    search_fields = ("room__title", "summary_text", "error_message")


@admin.register(DocAssistantQuestion)
class DocAssistantQuestionAdmin(admin.ModelAdmin):
    list_display = ("analysis", "question", "provider", "has_insufficient_evidence", "created_at")
    list_filter = ("provider", "has_insufficient_evidence")
    search_fields = ("analysis__room__title", "question", "answer")


@admin.register(DocSnapshot)
class DocSnapshotAdmin(admin.ModelAdmin):
    list_display = ("room", "snapshot_kind", "command_count", "created_at")
    list_filter = ("snapshot_kind",)
    search_fields = ("room__title",)


@admin.register(DocEditEvent)
class DocEditEventAdmin(admin.ModelAdmin):
    list_display = ("room", "display_name", "command_type", "summary", "created_at")
    list_filter = ("command_type",)
    search_fields = ("room__title", "display_name", "summary", "command_id")


@admin.register(DocPresence)
class DocPresenceAdmin(admin.ModelAdmin):
    list_display = ("room", "display_name", "role", "is_connected", "last_seen_at")
    list_filter = ("role", "is_connected")
    search_fields = ("room__title", "display_name")
