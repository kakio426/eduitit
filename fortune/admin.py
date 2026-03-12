from django.contrib import admin
from .models import (
    Stem, Branch, SixtyJiazi,
    InterpretationRule, FortuneResult, FortunePseudonymousCache,
    ZooResult, FavoriteDate, DailyFortuneLog,
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


@admin.register(FavoriteDate)
class FavoriteDateAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'label', 'color']
    list_filter = ['color', 'date']
    search_fields = ['user__username', 'label']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(DailyFortuneLog)
class DailyFortuneLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'target_date', 'viewed_at']
    list_filter = ['target_date', 'viewed_at']
    search_fields = ['user__username']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(FortunePseudonymousCache)
class FortunePseudonymousCacheAdmin(admin.ModelAdmin):
    list_display = ['user', 'purpose', 'created_at', 'expires_at']
    list_filter = ['purpose', 'created_at', 'expires_at']
    search_fields = ['user__username', 'fingerprint']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
