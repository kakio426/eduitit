from django.contrib import admin
from django.db.models import Count, Q

from .models import HandoffReceipt, HandoffRosterGroup, HandoffRosterMember, HandoffSession


@admin.register(HandoffRosterGroup)
class HandoffRosterGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_favorite", "active_member_count", "created_at")
    list_filter = ("is_favorite", "created_at")
    search_fields = ("name", "owner__username")
    raw_id_fields = ("owner",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("owner")
            .annotate(_active_member_count=Count("members", filter=Q(members__is_active=True)))
        )

    @admin.display(description="활성 멤버")
    def active_member_count(self, obj):
        return obj._active_member_count


@admin.register(HandoffRosterMember)
class HandoffRosterMemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "group", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("display_name", "group__name", "group__owner__username")
    raw_id_fields = ("group",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "group__owner")


@admin.register(HandoffSession)
class HandoffSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "roster_group_name", "status", "received_count", "pending_count", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "owner__username", "roster_group_name")
    raw_id_fields = ("owner", "roster_group")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("owner", "roster_group")
            .annotate(
                _received_count=Count("receipts", filter=Q(receipts__state="received")),
                _pending_count=Count("receipts", filter=Q(receipts__state="pending")),
            )
        )

    @admin.display(description="수령완료")
    def received_count(self, obj):
        return obj._received_count

    @admin.display(description="미수령")
    def pending_count(self, obj):
        return obj._pending_count


@admin.register(HandoffReceipt)
class HandoffReceiptAdmin(admin.ModelAdmin):
    list_display = ("session", "member_name_snapshot", "state", "handoff_type", "received_by", "updated_at")
    list_filter = ("state", "handoff_type")
    search_fields = ("session__title", "member_name_snapshot", "session__owner__username")
    raw_id_fields = ("session", "member", "received_by")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("session", "member", "received_by", "session__owner")
