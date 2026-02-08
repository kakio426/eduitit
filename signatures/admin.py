from django.contrib import admin
from django.db.models import Count
from .models import TrainingSession, Signature


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
    list_display = ['participant_name', 'training_session', 'created_at']
    list_filter = ['training_session', 'created_at']
    search_fields = ['participant_name']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('training_session')
