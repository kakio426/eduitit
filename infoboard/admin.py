from django.contrib import admin

from .models import Board, Card, Collection, SharedLink, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'color', 'created_at')
    list_filter = ('owner',)
    search_fields = ('name',)


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'icon', 'color_theme', 'layout', 'is_public', 'card_count', 'created_at')
    list_filter = ('color_theme', 'is_public', 'allow_student_submit')
    search_fields = ('title', 'description')
    readonly_fields = ('id', 'access_code', 'created_at', 'updated_at')

    def card_count(self, obj):
        return obj.cards.count()
    card_count.short_description = '카드 수'


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('title', 'card_type', 'board', 'display_author', 'is_pinned', 'created_at')
    list_filter = ('card_type', 'is_pinned')
    search_fields = ('title', 'content')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'created_at')
    search_fields = ('title',)
    readonly_fields = ('id',)


@admin.register(SharedLink)
class SharedLinkAdmin(admin.ModelAdmin):
    list_display = ('board', 'access_level', 'is_active', 'access_count', 'expires_at', 'created_at')
    list_filter = ('access_level', 'is_active')
    readonly_fields = ('id', 'access_count', 'created_at')
