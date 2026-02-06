from django.contrib import admin
from .models import TestSession, StudentMBTIResult


@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ['session_name', 'teacher', 'result_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'teacher']
    search_fields = ['session_name', 'teacher__username']
    readonly_fields = ['id', 'created_at']


@admin.register(StudentMBTIResult)
class StudentMBTIResultAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'mbti_type', 'animal_name', 'session', 'created_at']
    list_filter = ['mbti_type', 'session', 'created_at']
    search_fields = ['student_name', 'mbti_type']
    readonly_fields = ['id', 'created_at']
