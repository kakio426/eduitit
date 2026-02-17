from django.contrib import admin
from django.db.models import Count

from .models import (
    HSBehaviorCategory,
    HSBehaviorLog,
    HSBloomDraw,
    HSClassroom,
    HSClassroomConfig,
    HSGuardianConsent,
    HSInterventionLog,
    HSPrize,
    HSSeedLedger,
    HSStudent,
    HSStudentGroup,
    HSTicketLedger,
)


@admin.register(HSClassroom)
class HSClassroomAdmin(admin.ModelAdmin):
    list_display = ['name', 'school_name', 'teacher_name', 'slug', 'is_active', 'student_count_display', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'school_name', 'teacher__username']
    raw_id_fields = ['teacher']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('teacher').annotate(
            student_count=Count('students', distinct=True),
        )

    def teacher_name(self, obj):
        return obj.teacher.username
    teacher_name.short_description = '교사'
    teacher_name.admin_order_field = 'teacher__username'

    def student_count_display(self, obj):
        return obj.student_count
    student_count_display.short_description = '학생 수'
    student_count_display.admin_order_field = 'student_count'


@admin.register(HSClassroomConfig)
class HSClassroomConfigAdmin(admin.ModelAdmin):
    list_display = ['classroom', 'seeds_per_bloom', 'base_win_rate', 'balance_mode_enabled']
    raw_id_fields = ['classroom']


@admin.register(HSStudent)
class HSStudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'number', 'classroom_name', 'seed_count', 'ticket_count', 'total_wins', 'is_active']
    list_filter = ['is_active', 'classroom']
    search_fields = ['name', 'classroom__name']
    raw_id_fields = ['classroom']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('classroom')

    def classroom_name(self, obj):
        return obj.classroom.name
    classroom_name.short_description = '교실'
    classroom_name.admin_order_field = 'classroom__name'


@admin.register(HSGuardianConsent)
class HSGuardianConsentAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'status', 'requested_at', 'completed_at']
    list_filter = ['status']
    raw_id_fields = ['student']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student')

    def student_name(self, obj):
        return obj.student.name
    student_name.short_description = '학생'


@admin.register(HSPrize)
class HSPrizeAdmin(admin.ModelAdmin):
    list_display = ['name', 'classroom_name', 'total_quantity', 'remaining_quantity', 'is_active', 'display_order']
    list_filter = ['is_active']
    raw_id_fields = ['classroom']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('classroom')

    def classroom_name(self, obj):
        return obj.classroom.name
    classroom_name.short_description = '교실'


@admin.register(HSTicketLedger)
class HSTicketLedgerAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'source', 'amount', 'balance_after', 'created_at']
    list_filter = ['source']
    raw_id_fields = ['student']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student')

    def student_name(self, obj):
        return obj.student.name
    student_name.short_description = '학생'


@admin.register(HSSeedLedger)
class HSSeedLedgerAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'reason', 'amount', 'balance_after', 'created_at']
    list_filter = ['reason']
    raw_id_fields = ['student']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student')

    def student_name(self, obj):
        return obj.student.name
    student_name.short_description = '학생'


@admin.register(HSBloomDraw)
class HSBloomDrawAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'is_win', 'prize', 'effective_probability', 'is_forced', 'drawn_at']
    list_filter = ['is_win', 'is_forced']
    raw_id_fields = ['student', 'prize', 'created_by']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'prize', 'created_by')

    def student_name(self, obj):
        return obj.student.name
    student_name.short_description = '학생'


@admin.register(HSInterventionLog)
class HSInterventionLogAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'action', 'created_by_name', 'created_at']
    list_filter = ['action']
    raw_id_fields = ['classroom', 'student', 'created_by']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'created_by', 'classroom')

    def student_name(self, obj):
        return obj.student.name
    student_name.short_description = '학생'

    def created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else '-'
    created_by_name.short_description = '실행자'
