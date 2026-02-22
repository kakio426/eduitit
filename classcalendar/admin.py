from django.contrib import admin

from .models import CalendarEvent, EventPageBlock


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
