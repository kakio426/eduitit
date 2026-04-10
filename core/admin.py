from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from core.admin_helpers import ReadOnlyModelAdmin
from .models import (
    UserProfile,
    UserMarketingEmailConsent,
    UserPolicyConsent,
    Post,
    Comment,
    CommentReport,
    NewsSource,
    SiteConfig,
    Feedback,
    ProductUsageLog,
    ProductFavorite,
    ProductWorkbenchBundle,
    TeacherBuddyDailyProgress,
    TeacherBuddyGiftCoupon,
    TeacherBuddySkinUnlock,
    TeacherBuddySocialRewardLog,
    TeacherBuddyState,
    TeacherBuddyUnlock,
    PageViewLog,
    UserModeration,
    VisitorLog,
)


admin.site.site_header = "에듀잇잇 관리자"
admin.site.site_title = "에듀잇잇 운영실"
admin.site.index_title = "찾기 쉬운 운영 메뉴"


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_nickname', 'get_marketing_email_status', 'is_staff')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('userprofile', 'marketing_email_consent')

    def get_nickname(self, instance):
        return instance.userprofile.nickname
    get_nickname.short_description = '별명'

    @admin.display(boolean=True, description='이메일 안내 동의')
    def get_marketing_email_status(self, instance):
        consent = getattr(instance, 'marketing_email_consent', None)
        return bool(consent and consent.is_active)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nickname', 'role']
    search_fields = ['user__username', 'nickname']
    list_filter = ['role']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(UserMarketingEmailConsent)
class UserMarketingEmailConsentAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'consent_source',
        'consent_version',
        'consented_at',
        'revoked_at',
        'is_active_display',
    ]
    list_filter = ['consent_source', 'consent_version', 'revoked_at', 'consented_at']
    search_fields = ['user__username', 'user__email', 'ip_address', 'user_agent']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    @admin.display(boolean=True, description='수신 가능')
    def is_active_display(self, obj):
        return obj.is_active


@admin.register(UserPolicyConsent)
class UserPolicyConsentAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'provider',
        'terms_version',
        'privacy_version',
        'agreement_source',
        'agreed_at',
    ]
    list_filter = ['provider', 'agreement_source', 'terms_version', 'privacy_version', 'agreed_at']
    search_fields = ['user__username', 'user__email', 'ip_address', 'user_agent']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        'author',
        'post_type',
        'is_notice_pinned',
        'allow_notice_dismiss',
        'approval_status',
        'publisher',
        'content_summary',
        'created_at',
        'like_count_display',
    ]
    list_filter = ['post_type', 'is_notice_pinned', 'allow_notice_dismiss', 'approval_status', 'created_at', 'author']
    search_fields = ['content', 'og_title', 'source_url', 'author__username']
    readonly_fields = ['created_at']
    actions = ['mark_news_approved', 'mark_news_rejected']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author').annotate(
            _like_count=Count('likes', distinct=True)
        )

    def content_summary(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_summary.short_description = '내용 요약'

    def like_count_display(self, obj):
        return obj._like_count
    like_count_display.short_description = '좋아요 수'
    like_count_display.admin_order_field = '_like_count'

    @admin.action(description='선택한 뉴스를 승인 처리')
    def mark_news_approved(self, request, queryset):
        updated = queryset.filter(post_type='news_link').update(
            approval_status='approved',
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f'{updated}개 뉴스를 승인 처리했습니다.')

    @admin.action(description='선택한 뉴스를 반려 처리')
    def mark_news_rejected(self, request, queryset):
        updated = queryset.filter(post_type='news_link').update(
            approval_status='rejected',
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f'{updated}개 뉴스를 반려 처리했습니다.')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'author', 'is_hidden', 'report_count', 'created_at']
    list_filter = ['is_hidden', 'hidden_reason', 'created_at']
    search_fields = ['content', 'author__username', 'post__content', 'post__og_title']
    readonly_fields = ['created_at', 'updated_at', 'report_count']
    actions = ['hide_comments', 'restore_comments']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author', 'post')

    @admin.action(description='선택한 댓글 숨김 처리')
    def hide_comments(self, request, queryset):
        updated = queryset.update(is_hidden=True, hidden_reason='admin')
        self.message_user(request, f'{updated}개 댓글을 숨김 처리했습니다.')

    @admin.action(description='선택한 댓글 복구 처리')
    def restore_comments(self, request, queryset):
        updated = queryset.update(is_hidden=False, hidden_reason='')
        self.message_user(request, f'{updated}개 댓글을 복구했습니다.')


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'comment', 'reporter', 'reason', 'created_at']
    list_filter = ['reason', 'created_at']
    search_fields = ['comment__content', 'reporter__username']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('comment', 'reporter')


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'is_active', 'url', 'updated_at']
    list_filter = ['source_type', 'is_active']
    search_fields = ['name', 'url']


@admin.register(UserModeration)
class UserModerationAdmin(admin.ModelAdmin):
    list_display = ['user', 'scope', 'until', 'created_by', 'created_at']
    list_filter = ['scope', 'created_at']
    search_fields = ['user__username', 'reason']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'created_by')


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'maintenance_mode', 'banner_active', 'banner_text']
    fieldsets = (
        ('점검 설정', {
            'fields': ('maintenance_mode',),
        }),
        ('배너 설정', {
            'fields': ('banner_active', 'banner_text', 'banner_color', 'banner_link'),
        }),
        ('이용방법 추천 설정', {
            'fields': ('featured_manuals',),
        }),
    )
    filter_horizontal = ('featured_manuals',)

    def has_add_permission(self, request):
        # 싱글톤: 이미 존재하면 추가 불가
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'message_summary', 'is_resolved', 'created_at']
    list_filter = ['category', 'is_resolved', 'created_at']
    search_fields = ['name', 'email', 'message']
    list_editable = ['is_resolved']
    readonly_fields = ['created_at']

    def message_summary(self, obj):
        return obj.message[:60] + "..." if len(obj.message) > 60 else obj.message
    message_summary.short_description = '내용 요약'


@admin.register(ProductUsageLog)
class ProductUsageLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'action', 'source', 'created_at']
    list_filter = ['action', 'source', 'created_at']
    search_fields = ['user__username', 'product__title']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'product']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')


@admin.register(PageViewLog)
class PageViewLogAdmin(admin.ModelAdmin):
    list_display = ['path', 'route_name', 'identity_type', 'user', 'is_bot', 'view_date', 'created_at']
    list_filter = ['identity_type', 'is_bot', 'view_date', 'route_name']
    search_fields = ['path', 'route_name', 'user__username', 'visitor_key']
    readonly_fields = ['created_at']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ProductFavorite)
class ProductFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'pin_order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__title']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'product']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')


@admin.register(TeacherBuddyState)
class TeacherBuddyStateAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'active_buddy_key',
        'profile_buddy_key',
        'active_skin_key',
        'profile_skin_key',
        'draw_token_count',
        'sticker_dust',
        'qualifying_day_count',
        'total_points_earned',
        'collection_completed_at',
        'last_home_seen_at',
    ]
    search_fields = ['user__username', 'active_buddy_key']
    readonly_fields = [
        'created_at',
        'updated_at',
        'starter_granted_at',
        'collection_completed_at',
        'last_home_seen_at',
        'public_share_token',
        'last_sns_bonus_week_key',
    ]
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(TeacherBuddyUnlock)
class TeacherBuddyUnlockAdmin(admin.ModelAdmin):
    list_display = ['user', 'buddy_key', 'rarity', 'obtained_via', 'obtained_at']
    list_filter = ['rarity', 'obtained_via', 'obtained_at']
    search_fields = ['user__username', 'buddy_key']
    readonly_fields = ['obtained_at']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(TeacherBuddySkinUnlock)
class TeacherBuddySkinUnlockAdmin(admin.ModelAdmin):
    list_display = ['user', 'buddy_key', 'skin_key', 'obtained_via', 'obtained_at']
    list_filter = ['obtained_via', 'obtained_at']
    search_fields = ['user__username', 'buddy_key', 'skin_key']
    readonly_fields = ['obtained_at']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(TeacherBuddyDailyProgress)
class TeacherBuddyDailyProgressAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'activity_date',
        'point_total',
        'first_launch_awarded',
        'draw_awarded',
        'home_ticket_awarded',
        'qualified_for_legendary_day',
        'sns_reward_awarded',
    ]
    list_filter = ['activity_date', 'first_launch_awarded', 'draw_awarded', 'home_ticket_awarded', 'sns_reward_awarded']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(TeacherBuddySocialRewardLog)
class TeacherBuddySocialRewardLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity_date', 'post_id', 'reward_granted', 'rejection_reason', 'created_at']
    list_filter = ['activity_date', 'reward_granted', 'rejection_reason']
    search_fields = ['user__username', 'content_hash', 'normalized_text']
    readonly_fields = ['created_at']
    raw_id_fields = ['user']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(TeacherBuddyGiftCoupon)
class TeacherBuddyGiftCouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'token_amount', 'is_active', 'expires_at', 'redeemed_by', 'redeemed_at', 'created_at']
    list_filter = ['is_active', 'token_amount', 'redeemed_at', 'created_at']
    search_fields = ['code', 'normalized_code', 'note', 'redeemed_by__username', 'created_by__username']
    readonly_fields = ['normalized_code', 'redeemed_by', 'redeemed_at', 'created_at', 'updated_at']
    raw_id_fields = ['created_by', 'redeemed_by']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'redeemed_by')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register([ProductWorkbenchBundle, VisitorLog], ReadOnlyModelAdmin)
