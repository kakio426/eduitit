from django.contrib import admin

from .models import SignatureDocument, SignatureRecipient, SignatureRequest


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
    list_display = ["student_name", "parent_name", "status", "signed_at"]
    list_filter = ["status", "signed_at"]
    search_fields = ["student_name", "parent_name", "phone_number"]


@admin.register(SignatureDocument)
class SignatureDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "file_type", "created_by", "created_at"]
    list_filter = ["file_type", "created_at"]
    search_fields = ["title"]
    raw_id_fields = ["created_by"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("created_by")
