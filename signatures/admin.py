from django.contrib import admin
from .models import TrainingSession, Signature


class SignatureInline(admin.TabularInline):
    model = Signature
    extra = 0
    readonly_fields = ['participant_name', 'created_at']
    can_delete = True


@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'datetime', 'location', 'created_by', 'signature_count', 'is_active']
    list_filter = ['is_active', 'datetime', 'created_by']
    search_fields = ['title', 'instructor', 'location']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    inlines = [SignatureInline]

    def signature_count(self, obj):
        return obj.signatures.count()
    signature_count.short_description = '서명 수'


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ['participant_name', 'training_session', 'created_at']
    list_filter = ['training_session', 'created_at']
    search_fields = ['participant_name']
    readonly_fields = ['created_at']
