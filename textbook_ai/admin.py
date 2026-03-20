from django.contrib import admin

from .models import TextbookChunk, TextbookDocument, TextbookParseArtifact


class TextbookChunkInline(admin.TabularInline):
    model = TextbookChunk
    extra = 0
    fields = ("sort_order", "chunk_type", "heading_path", "page_from", "page_to")
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(TextbookDocument)
class TextbookDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "subject",
        "parse_status",
        "page_count",
        "updated_at",
    )
    list_filter = ("parse_status", "subject", "license_confirmed")
    search_fields = ("title", "unit_title", "grade", "original_filename", "owner__username")
    list_select_related = ("owner",)
    raw_id_fields = ("owner",)
    readonly_fields = (
        "id",
        "file_sha256",
        "file_size_bytes",
        "page_count",
        "parsed_at",
        "created_at",
        "updated_at",
    )
    inlines = [TextbookChunkInline]


@admin.register(TextbookParseArtifact)
class TextbookParseArtifactAdmin(admin.ModelAdmin):
    list_display = ("document", "page_count", "heading_count", "table_count", "updated_at")
    search_fields = ("document__title", "document__owner__username")
    raw_id_fields = ("document",)


@admin.register(TextbookChunk)
class TextbookChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "sort_order", "chunk_type", "page_from", "page_to")
    list_filter = ("chunk_type",)
    search_fields = ("document__title", "heading_path", "text")
    raw_id_fields = ("document",)

# Register your models here.
