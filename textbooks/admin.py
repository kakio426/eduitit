from django.contrib import admin

from .models import (
    TextbookLiveEvent,
    TextbookLivePageState,
    TextbookLiveParticipant,
    TextbookLiveSession,
    TextbookMaterial,
)


@admin.register(TextbookMaterial)
class TextbookMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "teacher",
        "subject",
        "grade",
        "source_type",
        "is_published",
        "page_count",
        "created_at",
    )
    list_filter = ("source_type", "subject", "is_published")
    search_fields = ("title", "unit_title", "teacher__username")
    readonly_fields = ("pdf_sha256", "page_count", "created_at", "updated_at")


@admin.register(TextbookLiveSession)
class TextbookLiveSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "material",
        "teacher",
        "status",
        "join_code",
        "current_page",
        "follow_mode",
        "started_at",
        "ended_at",
    )
    list_filter = ("status", "follow_mode", "allow_student_annotation")
    search_fields = ("material__title", "teacher__username", "join_code")
    readonly_fields = ("last_seq", "started_at", "ended_at", "last_heartbeat")


@admin.register(TextbookLivePageState)
class TextbookLivePageStateAdmin(admin.ModelAdmin):
    list_display = ("session", "page_index", "revision", "updated_at")
    list_filter = ("updated_at",)


@admin.register(TextbookLiveEvent)
class TextbookLiveEventAdmin(admin.ModelAdmin):
    list_display = ("session", "seq", "event_type", "page_index", "actor_role", "created_at")
    list_filter = ("event_type", "actor_role", "created_at")
    search_fields = ("session__id",)


@admin.register(TextbookLiveParticipant)
class TextbookLiveParticipantAdmin(admin.ModelAdmin):
    list_display = ("session", "display_name", "role", "is_connected", "joined_at", "last_seen_at")
    list_filter = ("role", "is_connected")
    search_fields = ("display_name", "device_id", "session__id")
