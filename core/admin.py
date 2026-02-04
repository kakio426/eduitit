from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Post

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_nickname', 'is_staff')
    
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

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['author', 'content_summary', 'created_at', 'like_count']
    list_filter = ['created_at', 'author']
    search_fields = ['content', 'author__username']
    readonly_fields = ['created_at']

    def content_summary(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_summary.short_description = '내용 요약'

    def like_count(self, obj):
        return obj.likes.count()
    like_count.short_description = '좋아요 수'
