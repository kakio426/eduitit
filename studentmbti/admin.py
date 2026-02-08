from django.contrib import admin
from django.db.models import Count
from .models import TestSession, StudentMBTIResult


@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ['session_name', 'teacher', 'result_count_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'teacher']
    search_fields = ['session_name', 'teacher__username']
    readonly_fields = ['id', 'created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('teacher').annotate(
            _result_count=Count('results', distinct=True)
        )

    def result_count_display(self, obj):
        return obj._result_count
    result_count_display.short_description = '결과 수'
    result_count_display.admin_order_field = '_result_count'


@admin.register(StudentMBTIResult)
class StudentMBTIResultAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'mbti_type', 'animal_name', 'session', 'created_at']
    list_filter = ['mbti_type', 'session', 'created_at']
    search_fields = ['student_name', 'mbti_type']
    readonly_fields = ['id', 'created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session')
