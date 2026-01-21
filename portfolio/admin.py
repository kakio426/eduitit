from django.contrib import admin
from .models import Achievement, LectureProgram, LectureHistory, Inquiry

@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('title', 'issuer', 'date_awarded', 'is_featured')
    list_filter = ('is_featured', 'date_awarded')
    search_fields = ('title', 'issuer')

@admin.register(LectureProgram)
class LectureProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_audience', 'duration', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')

@admin.register(LectureHistory)
class LectureHistoryAdmin(admin.ModelAdmin):
    list_display = ('date', 'client_name', 'program', 'participants_count')
    list_filter = ('date', 'program')
    search_fields = ('client_name',)

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'topic', 'requested_date', 'created_at', 'is_reviewed')
    list_filter = ('is_reviewed', 'created_at')
    search_fields = ('name', 'organization', 'topic')
    readonly_fields = ('created_at',)
    
    actions = ['mark_as_reviewed']

    def mark_as_reviewed(self, request, queryset):
        queryset.update(is_reviewed=True)
    mark_as_reviewed.short_description = "선택한 요청을 검토 완료로 표시"
