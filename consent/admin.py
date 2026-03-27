from django.contrib import admin

from core.admin_helpers import ReadOnlyModelAdmin

from .models import (
    ConsentAuditLog,
    ConsentRoster,
    ConsentRosterEntry,
    SignatureDocument,
    SignaturePosition,
    SignatureRecipient,
    SignatureRequest,
)


@admin.register(SignatureRequest)
class SignatureRequestAdmin(admin.ModelAdmin):
    list_display = ["title", "created_by", "status", "created_at", "sent_at", "preview_checked_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "request_id"]
    readonly_fields = ["request_id", "created_at", "sent_at", "preview_checked_at"]
    raw_id_fields = ["created_by"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("created_by")


@admin.register(SignatureRecipient)
class SignatureRecipientAdmin(admin.ModelAdmin):
    list_display = ["student_name", "parent_name", "status", "identity_assurance", "verified_at", "signed_at"]
    list_filter = ["status", "identity_assurance", "signed_at"]
    search_fields = ["student_name", "parent_name", "phone_number"]
    readonly_fields = [
        "verified_at",
        "verified_ip_address",
        "verified_user_agent",
        "ip_address",
        "user_agent",
        "signed_at",
    ]


@admin.register(SignatureDocument)
class SignatureDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "file_type", "created_by", "created_at"]
    list_filter = ["file_type", "created_at"]
    search_fields = ["title"]
    raw_id_fields = ["created_by"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("created_by")


@admin.register(ConsentAuditLog)
class ConsentAuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "request", "recipient", "event_type", "ip_address"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["request__title", "request__request_id", "recipient__student_name", "recipient__parent_name"]
    readonly_fields = ["created_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("request", "recipient")


admin.site.register(
    [ConsentRoster, ConsentRosterEntry, SignaturePosition],
    ReadOnlyModelAdmin,
)
