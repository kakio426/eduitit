from django.contrib import admin
from django.db.models import Count
from core.admin_helpers import ReadOnlyModelAdmin
from .models import (
    AffiliationCorrectionLog,
    ExpectedParticipant,
    SavedSignature,
    Signature,
    SignatureAuditLog,
    SignatureStyle,
    TrainingSession,
)


class SignatureInline(admin.TabularInline):
    model = Signature
    extra = 0
    readonly_fields = ['participant_name', 'created_at']
    can_delete = True


@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'datetime', 'location', 'created_by', 'signature_count_display', 'is_active']
    list_filter = ['is_active', 'datetime', 'created_by']
    search_fields = ['title', 'instructor', 'location']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    inlines = [SignatureInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by').annotate(
            _signature_count=Count('signatures', distinct=True)
        )

    def signature_count_display(self, obj):
        return obj._signature_count
    signature_count_display.short_description = '서명 수'
    signature_count_display.admin_order_field = '_signature_count'


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ['participant_name', 'training_session', 'submission_mode', 'participant_affiliation', 'corrected_affiliation', 'ip_address', 'created_at']
    list_filter = ['training_session', 'submission_mode', 'created_at']
    search_fields = ['participant_name', 'ip_address']
    readonly_fields = ['submission_mode', 'ip_address', 'user_agent', 'created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('training_session')


@admin.register(AffiliationCorrectionLog)
class AffiliationCorrectionLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'training_session',
        'target_type',
        'mode',
        'before_affiliation',
        'after_affiliation',
        'corrected_by',
    ]
    list_filter = ['target_type', 'mode', 'created_at']
    search_fields = ['before_affiliation', 'after_affiliation', 'reason', 'training_session__title']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'training_session',
            'corrected_by',
            'signature',
            'expected_participant',
        )


@admin.register(SignatureAuditLog)
class SignatureAuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'training_session', 'signature', 'event_type', 'ip_address']
    list_filter = ['event_type', 'created_at']
    search_fields = ['training_session__title', 'signature__participant_name', 'ip_address']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('training_session', 'signature', 'expected_participant')


admin.site.register(
    [ExpectedParticipant, SavedSignature, SignatureStyle],
    ReadOnlyModelAdmin,
)
