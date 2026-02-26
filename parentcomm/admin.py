from django.contrib import admin

from .models import (
    ConsultationProposal,
    ConsultationRequest,
    ConsultationSlot,
    ParentCommunicationPolicy,
    ParentContact,
    ParentNotice,
    ParentNoticeReceipt,
    ParentThread,
    ParentThreadMessage,
    ParentUrgentAlert,
)


@admin.register(ParentContact)
class ParentContactAdmin(admin.ModelAdmin):
    list_display = (
        "student_name",
        "parent_name",
        "teacher",
        "contact_email",
        "is_active",
        "updated_at",
    )
    search_fields = ("student_name", "parent_name", "contact_email", "teacher__username")
    list_filter = ("is_active",)
    raw_id_fields = ("teacher",)


@admin.register(ParentCommunicationPolicy)
class ParentCommunicationPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "max_parent_messages_per_thread",
        "max_open_threads_per_parent",
        "office_hours_start",
        "office_hours_end",
    )
    raw_id_fields = ("teacher",)


@admin.register(ParentNotice)
class ParentNoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "classroom_label", "has_attachment", "is_pinned", "published_at")
    search_fields = ("title", "teacher__username", "classroom_label")
    list_filter = ("is_pinned",)
    raw_id_fields = ("teacher",)

    @admin.display(description="첨부")
    def has_attachment(self, obj):
        return bool(obj.attachment)


@admin.register(ParentNoticeReceipt)
class ParentNoticeReceiptAdmin(admin.ModelAdmin):
    list_display = ("notice", "parent_contact", "delivered_at", "read_at")
    raw_id_fields = ("notice", "parent_contact")


@admin.register(ParentThread)
class ParentThreadAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "teacher",
        "parent_contact",
        "status",
        "severity",
        "parent_message_count",
        "teacher_message_count",
        "updated_at",
    )
    search_fields = ("subject", "teacher__username", "parent_contact__student_name")
    list_filter = ("status", "severity")
    raw_id_fields = ("teacher", "parent_contact")


@admin.register(ParentThreadMessage)
class ParentThreadMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender_role", "created_at")
    list_filter = ("sender_role",)
    raw_id_fields = ("thread",)


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "teacher",
        "parent_contact",
        "status",
        "requested_by",
        "requested_at",
        "confirmed_at",
    )
    list_filter = ("status", "requested_by")
    raw_id_fields = ("teacher", "parent_contact", "thread", "selected_slot")


@admin.register(ConsultationProposal)
class ConsultationProposalAdmin(admin.ModelAdmin):
    list_display = ("id", "consultation_request", "teacher", "allowed_methods_text", "status", "proposed_at")
    list_filter = ("status",)
    raw_id_fields = ("consultation_request", "teacher")

    @admin.display(description="상담 방식")
    def allowed_methods_text(self, obj):
        return ", ".join(obj.allowed_method_labels)


@admin.register(ConsultationSlot)
class ConsultationSlotAdmin(admin.ModelAdmin):
    list_display = ("proposal", "method", "starts_at", "ends_at", "is_selected")
    list_filter = ("method", "is_selected")
    raw_id_fields = ("proposal",)


@admin.register(ParentUrgentAlert)
class ParentUrgentAlertAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "teacher",
        "parent_contact",
        "alert_type",
        "short_message",
        "is_acknowledged",
        "acknowledged_at",
    )
    search_fields = ("parent_contact__student_name", "parent_contact__parent_name", "short_message")
    list_filter = ("alert_type", "is_acknowledged")
    raw_id_fields = ("teacher", "parent_contact")
