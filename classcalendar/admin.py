from django.contrib import admin

from .models import CalendarCollaborator, CalendarEvent, CalendarIntegrationSetting, EventPageBlock


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "classroom",
        "start_time",
        "end_time",
        "source",
        "integration_source",
        "is_locked",
        "visibility",
    )
    list_filter = ("source", "integration_source", "is_locked", "visibility", "is_all_day")
    search_fields = ("title", "author__username", "classroom__name")
    ordering = ("-start_time",)


@admin.register(EventPageBlock)
class EventPageBlockAdmin(admin.ModelAdmin):
    list_display = ("event", "block_type", "order")
    list_filter = ("block_type",)
    search_fields = ("event__title",)
    ordering = ("event", "order")


@admin.register(CalendarIntegrationSetting)
class CalendarIntegrationSettingAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "collect_deadline_enabled",
        "consent_expiry_enabled",
        "reservation_enabled",
        "signatures_training_enabled",
        "share_enabled",
        "share_uuid",
        "updated_at",
    )
    search_fields = ("user__username", "user__email")


@admin.register(CalendarCollaborator)
class CalendarCollaboratorAdmin(admin.ModelAdmin):
    list_display = ("owner", "collaborator", "can_edit", "created_at")
    list_filter = ("can_edit",)
    search_fields = ("owner__username", "owner__email", "collaborator__username", "collaborator__email")
