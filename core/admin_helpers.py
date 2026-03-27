from django.contrib import admin
from django.db import models


class ReadOnlyModelAdmin(admin.ModelAdmin):
    """Expose internal models in admin for inspection without enabling edits."""

    actions = None
    list_per_page = 100
    list_select_related = True

    def _concrete_field_names(self):
        return [field.name for field in self.model._meta.concrete_fields]

    def get_list_display(self, request):
        field_names = self._concrete_field_names()
        selected = []

        if "id" in field_names:
            selected.append("id")
        selected.append("__str__")

        for preferred in ("title", "name", "label", "status", "created_at", "updated_at"):
            if preferred in field_names and preferred not in selected:
                selected.append(preferred)

        for field in self.model._meta.concrete_fields:
            if len(selected) >= 6:
                break
            if field.name in selected:
                continue
            if isinstance(field, (models.TextField, models.JSONField, models.BinaryField)):
                continue
            selected.append(field.name)

        return tuple(selected[:6])

    def get_list_filter(self, request):
        filters = []
        for field in self.model._meta.concrete_fields:
            if len(filters) >= 4:
                break
            if getattr(field, "choices", None) or isinstance(
                field,
                (models.BooleanField, models.DateField, models.DateTimeField, models.TimeField),
            ):
                filters.append(field.name)
        return tuple(filters)

    def get_search_fields(self, request):
        search_fields = []
        for field in self.model._meta.concrete_fields:
            if len(search_fields) >= 4:
                break
            if getattr(field, "choices", None):
                continue
            if isinstance(
                field,
                (
                    models.CharField,
                    models.TextField,
                    models.EmailField,
                    models.SlugField,
                    models.URLField,
                    models.GenericIPAddressField,
                ),
            ):
                search_fields.append(field.name)
        return tuple(search_fields)

    def get_fields(self, request, obj=None):
        concrete_fields = [field.name for field in self.model._meta.concrete_fields]
        many_to_many_fields = [field.name for field in self.model._meta.many_to_many]
        return concrete_fields + many_to_many_fields

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
