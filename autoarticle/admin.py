from django.contrib import admin

from core.admin_helpers import ReadOnlyModelAdmin

from .models import GeneratedArticle


admin.site.register([GeneratedArticle], ReadOnlyModelAdmin)
