from django.contrib import admin
from django.utils import timezone

from .models import (
    InquiryMessage,
    InquiryProposal,
    InquiryReview,
    InquiryThread,
    ListingAttachment,
    ListingImage,
    ListingViewLog,
    ProgramListing,
    ProviderProfile,
    SavedListing,
)


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


class ListingAttachmentInline(admin.TabularInline):
    model = ListingAttachment
    extra = 0
    readonly_fields = ("original_name", "content_type", "file_size", "created_at")


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ("provider_name", "user", "contact_email", "service_area_summary", "updated_at")
    search_fields = ("provider_name", "user__username", "summary")
    prepopulated_fields = {}


@admin.register(ProgramListing)
class ProgramListingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "provider",
        "category",
        "province",
        "city",
        "approval_status",
        "submitted_at",
        "published_at",
        "is_featured",
        "view_count",
    )
    list_filter = ("approval_status", "category", "province", "delivery_mode", "is_featured")
    search_fields = ("title", "provider__provider_name", "summary", "theme_tags_text", "city", "coverage_note")
    readonly_fields = ("submitted_at", "published_at", "created_at", "updated_at", "view_count")
    list_select_related = ("provider",)
    actions = ("mark_listings_approved", "mark_listings_rejected", "mark_listings_featured", "mark_listings_unfeatured")
    inlines = [ListingImageInline, ListingAttachmentInline]

    @admin.action(description="선택한 프로그램을 승인 처리")
    def mark_listings_approved(self, request, queryset):
        updated = 0
        now = timezone.now()
        for listing in queryset.select_related("provider"):
            listing.approval_status = ProgramListing.ApprovalStatus.APPROVED
            if listing.submitted_at is None:
                listing.submitted_at = now
            if listing.published_at is None:
                listing.published_at = now
            listing.save()
            updated += 1
        self.message_user(request, f"{updated}개 프로그램을 승인 처리했습니다.")

    @admin.action(description="선택한 프로그램을 반려 처리")
    def mark_listings_rejected(self, request, queryset):
        updated = 0
        for listing in queryset.select_related("provider"):
            listing.mark_rejected()
            listing.save()
            updated += 1
        self.message_user(request, f"{updated}개 프로그램을 반려 처리했습니다.")

    @admin.action(description="선택한 프로그램을 추천 노출로 설정")
    def mark_listings_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"{updated}개 프로그램을 추천 노출로 설정했습니다.")

    @admin.action(description="선택한 프로그램의 추천 노출을 해제")
    def mark_listings_unfeatured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f"{updated}개 프로그램의 추천 노출을 해제했습니다.")


@admin.register(InquiryThread)
class InquiryThreadAdmin(admin.ModelAdmin):
    list_display = ("listing", "provider", "teacher", "status", "last_message_at")
    list_filter = ("status", "category")
    search_fields = ("listing__title", "provider__provider_name", "teacher__username", "school_region")


@admin.register(InquiryMessage)
class InquiryMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender", "sender_role", "created_at")
    list_filter = ("sender_role",)
    search_fields = ("thread__listing__title", "sender__username", "body")


@admin.register(InquiryProposal)
class InquiryProposalAdmin(admin.ModelAdmin):
    list_display = ("thread", "sent_by", "price_text", "updated_at")
    search_fields = ("thread__listing__title", "sent_by__username", "price_text")


@admin.register(InquiryReview)
class InquiryReviewAdmin(admin.ModelAdmin):
    list_display = ("listing", "provider", "teacher", "status", "published_at", "updated_at")
    list_filter = ("status", "provider")
    search_fields = ("listing__title", "provider__provider_name", "teacher__username", "headline", "body")
    readonly_fields = ("created_at", "updated_at", "published_at")
    actions = ("mark_reviews_published", "mark_reviews_hidden")

    @admin.action(description="선택한 이용후기를 공개")
    def mark_reviews_published(self, request, queryset):
        updated = 0
        now = timezone.now()
        for review in queryset.select_related("provider", "listing"):
            review.status = InquiryReview.Status.PUBLISHED
            if review.published_at is None:
                review.published_at = now
            review.save()
            updated += 1
        self.message_user(request, f"{updated}개 이용후기를 공개했습니다.")

    @admin.action(description="선택한 이용후기를 비공개")
    def mark_reviews_hidden(self, request, queryset):
        updated = 0
        for review in queryset.select_related("provider", "listing"):
            review.status = InquiryReview.Status.HIDDEN
            review.save()
            updated += 1
        self.message_user(request, f"{updated}개 이용후기를 비공개로 전환했습니다.")


@admin.register(ListingViewLog)
class ListingViewLogAdmin(admin.ModelAdmin):
    list_display = ("listing", "viewer_key", "viewed_at")
    search_fields = ("listing__title", "viewer_key")


@admin.register(SavedListing)
class SavedListingAdmin(admin.ModelAdmin):
    list_display = ("listing", "user", "created_at")
    search_fields = ("listing__title", "user__username")
