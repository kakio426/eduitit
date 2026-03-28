from django.contrib import admin

from .models import NextEduMaterial


@admin.register(NextEduMaterial)
class NextEduMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "teacher",
        "entry_mode",
        "subject",
        "grade",
        "material_type",
        "estimated_minutes",
        "view_count",
        "updated_at",
    )
    list_filter = ("entry_mode", "subject", "material_type", "difficulty_level", "is_published")
    search_fields = ("title", "summary", "unit_title", "grade", "search_text")
    readonly_fields = ("created_at", "updated_at", "access_code", "view_count")

