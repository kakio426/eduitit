from django.contrib import admin
from .models import (
    Stem, Branch, SixtyJiazi, SajuProfile, NatalChart,
    InterpretationRule, FortuneResult, ZooResult,
    UserSajuProfile, FavoriteDate, DailyFortuneLog,
)


@admin.register(Stem)
class StemAdmin(admin.ModelAdmin):
    list_display = ['character', 'name', 'element', 'polarity']
    list_filter = ['element', 'polarity']


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['character', 'name', 'element', 'polarity']
    list_filter = ['element', 'polarity']


@admin.register(SixtyJiazi)
class SixtyJiaziAdmin(admin.ModelAdmin):
    list_display = ['name', 'stem', 'branch', 'na_yin_element']
    list_filter = ['na_yin_element']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('stem', 'branch')


@admin.register(SajuProfile)
class SajuProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gender', 'birth_date_gregorian', 'birth_city']
    search_fields = ['user__username', 'birth_city']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(NatalChart)
class NatalChartAdmin(admin.ModelAdmin):
    list_display = ['saju_profile', 'year_pillar', 'month_pillar', 'day_pillar', 'hour_pillar', 'day_master_strength', 'created_at']
    list_filter = ['day_master_strength', 'created_at']
    raw_id_fields = ['saju_profile']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'saju_profile__user',
            'year_stem', 'year_branch',
            'month_stem', 'month_branch',
            'day_stem', 'day_branch',
            'hour_stem', 'hour_branch',
        )

    def year_pillar(self, obj):
        return f"{obj.year_stem}{obj.year_branch}"
    year_pillar.short_description = '년주'

    def month_pillar(self, obj):
        return f"{obj.month_stem}{obj.month_branch}"
    month_pillar.short_description = '월주'

    def day_pillar(self, obj):
        return f"{obj.day_stem}{obj.day_branch}"
    day_pillar.short_description = '일주'

    def hour_pillar(self, obj):
        return f"{obj.hour_stem}{obj.hour_branch}"
    hour_pillar.short_description = '시주'


@admin.register(InterpretationRule)
class InterpretationRuleAdmin(admin.ModelAdmin):
    list_display = ['rule_id', 'trigger_type', 'element_1', 'element_2', 'severity_score']
    list_filter = ['trigger_type', 'severity_score']
    search_fields = ['element_1', 'element_2', 'base_interpretation']


@admin.register(FortuneResult)
class FortuneResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'mode', 'target_date', 'created_at']
    list_filter = ['mode', 'created_at']
    search_fields = ['user__username']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ZooResult)
class ZooResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'mbti_type', 'animal_name', 'created_at']
    list_filter = ['mbti_type', 'created_at']
    search_fields = ['user__username', 'animal_name']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


class FavoriteDateInline(admin.TabularInline):
    model = FavoriteDate
    extra = 0
    raw_id_fields = ['user']


@admin.register(UserSajuProfile)
class UserSajuProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'profile_name', 'person_name', 'gender', 'is_default', 'created_at']
    list_filter = ['gender', 'is_default', 'calendar_type']
    search_fields = ['user__username', 'profile_name', 'person_name']
    raw_id_fields = ['user']
    inlines = [FavoriteDateInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(FavoriteDate)
class FavoriteDateAdmin(admin.ModelAdmin):
    list_display = ['user', 'profile', 'date', 'label', 'color']
    list_filter = ['color', 'date']
    search_fields = ['user__username', 'label']
    raw_id_fields = ['user', 'profile']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'profile')


@admin.register(DailyFortuneLog)
class DailyFortuneLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'profile', 'target_date', 'viewed_at']
    list_filter = ['target_date', 'viewed_at']
    search_fields = ['user__username']
    raw_id_fields = ['user', 'profile']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'profile')
