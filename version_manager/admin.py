from django.contrib import admin

from .models import Document, DocumentGroup, DocumentProtectedPhrase, DocumentShareLink, DocumentVersion


@admin.register(DocumentGroup)
class DocumentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('base_name', 'group', 'published_version', 'updated_at')
    search_fields = ('base_name', 'group__name')
    list_filter = ('group',)


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('document', 'version', 'status', 'uploaded_by_name', 'created_at')
    search_fields = ('document__base_name', 'original_filename')
    list_filter = ('status', 'document__group')


@admin.register(DocumentProtectedPhrase)
class DocumentProtectedPhraseAdmin(admin.ModelAdmin):
    list_display = ('document', 'phrase', 'is_active', 'created_at')
    search_fields = ('document__base_name', 'phrase')
    list_filter = ('is_active',)


@admin.register(DocumentShareLink)
class DocumentShareLinkAdmin(admin.ModelAdmin):
    list_display = ('document', 'token', 'is_active', 'expires_at', 'created_at')
    search_fields = ('document__base_name', 'token')
    list_filter = ('is_active',)
