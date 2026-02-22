from django.contrib import admin

from .models import CalendarEvent, EventExternalMap, EventPageBlock, GoogleAccount, GoogleSyncState


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "classroom", "start_time", "end_time", "source", "visibility")
    list_filter = ("source", "visibility", "is_all_day")
    search_fields = ("title", "author__username", "classroom__name")
    ordering = ("-start_time",)


@admin.register(EventPageBlock)
class EventPageBlockAdmin(admin.ModelAdmin):
    list_display = ("event", "block_type", "order")
    list_filter = ("block_type",)
    search_fields = ("event__title",)
    ordering = ("event", "order")


@admin.register(GoogleAccount)
class GoogleAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "updated_at")
    search_fields = ("user__username", "email")


@admin.register(GoogleSyncState)
class GoogleSyncStateAdmin(admin.ModelAdmin):
    list_display = ("account", "google_calendar_id", "last_sync")
    search_fields = ("account__user__username", "google_calendar_id")


@admin.register(EventExternalMap)
class EventExternalMapAdmin(admin.ModelAdmin):
    list_display = ("event", "account", "google_calendar_id", "google_event_id")
    search_fields = ("event__title", "google_event_id", "google_calendar_id")
