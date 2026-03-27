from django.contrib import admin

from core.admin_helpers import ReadOnlyModelAdmin

from .models import EduMaterial


admin.site.register([EduMaterial], ReadOnlyModelAdmin)
