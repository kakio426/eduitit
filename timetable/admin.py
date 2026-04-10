from django.contrib import admin

from .models import (
    TimetableClassroom,
    TimetableClassEditLink,
    TimetableClassInputStatus,
    TimetableDateOverride,
    TimetablePublishedRecurring,
    TimetableSchoolProfile,
    TimetableSharePortal,
    TimetableRoomPolicy,
    TimetableShareLink,
    TimetableSharedEvent,
    TimetableSlotAssignment,
    TimetableSnapshot,
    TimetableSyncLog,
    TimetableTeacher,
    TimetableWorkspace,
)


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


@admin.register(TimetableWorkspace)
class TimetableWorkspaceAdmin(admin.ModelAdmin):
    list_display = ("title", "school", "school_year", "term", "grade", "term_start_date", "term_end_date", "status", "updated_at")
    list_filter = ("status", "term", "school_year", "grade")
    search_fields = ("title", "school__name")
    autocomplete_fields = ("school", "published_snapshot", "created_by", "updated_by")


@admin.register(TimetableTeacher)
class TimetableTeacherAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "teacher_type", "target_weekly_hours", "is_active")
    list_filter = ("teacher_type", "is_active")
    search_fields = ("name", "school__name")
    autocomplete_fields = ("school",)


@admin.register(TimetableClassroom)
class TimetableClassroomAdmin(admin.ModelAdmin):
    list_display = ("label", "school", "school_year", "homeroom_name", "is_active")
    list_filter = ("school_year", "grade", "is_active")
    search_fields = ("school__name", "homeroom_name")
    autocomplete_fields = ("school",)


@admin.register(TimetableSlotAssignment)
class TimetableSlotAssignmentAdmin(admin.ModelAdmin):
    list_display = ("workspace", "classroom", "day_key", "period_no", "subject_name", "teacher", "special_room", "source")
    list_filter = ("day_key", "period_no", "source")
    search_fields = ("workspace__title", "classroom__homeroom_name", "subject_name", "display_text")
    autocomplete_fields = ("workspace", "classroom", "teacher", "special_room")


@admin.register(TimetableRoomPolicy)
class TimetableRoomPolicyAdmin(admin.ModelAdmin):
    list_display = ("workspace", "special_room", "capacity_per_slot")
    autocomplete_fields = ("workspace", "special_room")


@admin.register(TimetableSnapshot)
class TimetableSnapshotAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "created_by", "created_at")
    search_fields = ("name", "workspace__title")
    autocomplete_fields = ("workspace", "created_by")
    readonly_fields = ("created_at",)


@admin.register(TimetableSharedEvent)
class TimetableSharedEventAdmin(admin.ModelAdmin):
    list_display = ("title", "scope_type", "grade", "school", "school_year", "term", "day_key", "period_start", "period_end", "is_active")
    list_filter = ("scope_type", "school_year", "term", "is_active")
    search_fields = ("title", "school__name", "note")
    autocomplete_fields = ("school", "created_by", "updated_by")


@admin.register(TimetableSchoolProfile)
class TimetableSchoolProfileAdmin(admin.ModelAdmin):
    list_display = ("school", "school_stage", "grade_start", "grade_end", "updated_at")
    list_filter = ("school_stage",)
    search_fields = ("school__name",)
    autocomplete_fields = ("school",)


@admin.register(TimetableClassInputStatus)
class TimetableClassInputStatusAdmin(admin.ModelAdmin):
    list_display = ("workspace", "classroom", "status", "editor_name", "last_saved_at", "submitted_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("workspace__title", "classroom__homeroom_name", "editor_name")
    autocomplete_fields = ("workspace", "classroom")


@admin.register(TimetableClassEditLink)
class TimetableClassEditLinkAdmin(admin.ModelAdmin):
    list_display = ("workspace", "classroom", "is_active", "expires_at", "last_accessed_at")
    list_filter = ("is_active",)
    search_fields = ("token", "workspace__title", "classroom__homeroom_name")
    autocomplete_fields = ("workspace", "classroom", "issued_by")


@admin.register(TimetableDateOverride)
class TimetableDateOverrideAdmin(admin.ModelAdmin):
    list_display = ("workspace", "classroom", "date", "period_no", "subject_name", "teacher", "special_room", "source")
    list_filter = ("date", "source")
    search_fields = ("workspace__title", "classroom__homeroom_name", "subject_name", "display_text")
    autocomplete_fields = ("workspace", "classroom", "teacher", "special_room")


@admin.register(TimetableShareLink)
class TimetableShareLinkAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "audience_type", "classroom", "teacher", "is_active", "expires_at")
    list_filter = ("audience_type", "is_active")
    search_fields = ("token", "snapshot__name", "teacher__name", "classroom__homeroom_name")
    autocomplete_fields = ("snapshot", "classroom", "teacher")


@admin.register(TimetableSharePortal)
class TimetableSharePortalAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "is_active", "expires_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("token", "snapshot__name", "snapshot__workspace__title")
    autocomplete_fields = ("snapshot",)


@admin.register(TimetablePublishedRecurring)
class TimetablePublishedRecurringAdmin(admin.ModelAdmin):
    list_display = ("workspace", "special_room", "day_key", "period_no", "name_snapshot", "updated_at")
    search_fields = ("workspace__title", "special_room__name", "name_snapshot")
    autocomplete_fields = ("workspace", "snapshot", "special_room")
