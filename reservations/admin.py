from django.contrib import admin
from .models import School, SchoolConfig, SpecialRoom, Reservation, RecurringSchedule, BlackoutDate

class SchoolConfigInline(admin.StackedInline):
    model = SchoolConfig
    can_delete = False
    verbose_name_plural = 'config'

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'owner_username')
    search_fields = ('name', 'slug', 'owner__username')
    prepopulated_fields = {'slug': ('name',)}
    inlines = (SchoolConfigInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner')

    def owner_username(self, obj):
        return obj.owner.username
    owner_username.admin_order_field = 'owner__username'
    owner_username.short_description = 'Owner'

@admin.register(SpecialRoom)
class SpecialRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'school_name', 'icon', 'color')
    list_filter = ('school',)
    search_fields = ('name', 'school__name')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('school')

    def school_name(self, obj):
        return obj.school.name
    school_name.admin_order_field = 'school__name'
    school_name.short_description = 'School'

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('date', 'period', 'room_info', 'grade', 'class_no', 'name', 'created_at')
    list_filter = ('date', 'room__school', 'room')
    search_fields = ('name', 'memo', 'room__name')
    date_hierarchy = 'date'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('room', 'room__school')

    def room_info(self, obj):
        return f"{obj.room.school.name} - {obj.room.name}"
    room_info.admin_order_field = 'room__name'
    room_info.short_description = 'Room'

@admin.register(RecurringSchedule)
class RecurringScheduleAdmin(admin.ModelAdmin):
    list_display = ('room_info', 'day_of_week', 'period', 'name')
    list_filter = ('room__school', 'day_of_week')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('room', 'room__school')

    def room_info(self, obj):
        return f"{obj.room.school.name} - {obj.room.name}"
    room_info.admin_order_field = 'room__name'

@admin.register(BlackoutDate)
class BlackoutDateAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'start_date', 'end_date', 'reason')
    list_filter = ('school',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('school')

    def school_name(self, obj):
        return obj.school.name
    school_name.admin_order_field = 'school__name'
