from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from .models import UserProfile, Post, SiteConfig, Feedback, ProductUsageLog, ProductFavorite

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
    list_display = ['author', 'content_summary', 'created_at', 'like_count_display']
    list_filter = ['created_at', 'author']
    search_fields = ['content', 'author__username']
    readonly_fields = ['created_at']

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
