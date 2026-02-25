from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from .models import (
    UserProfile,
    Post,
    Comment,
    CommentReport,
    NewsSource,
    SiteConfig,
    Feedback,
    ProductUsageLog,
    ProductFavorite,
    UserModeration,
)

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_nickname', 'is_staff')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('userprofile')

    def get_nickname(self, instance):
        return instance.userprofile.nickname
    get_nickname.short_description = '별명'

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

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['author', 'post_type', 'approval_status', 'publisher', 'content_summary', 'created_at', 'like_count_display']
    list_filter = ['post_type', 'approval_status', 'created_at', 'author']
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
    list_display = ['__str__', 'banner_active', 'banner_text']
    fieldsets = (
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


@admin.register(ProductFavorite)
class ProductFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'pin_order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__title']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'product']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')
