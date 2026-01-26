from django.contrib import admin
from .models import UserProfile, Post

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
