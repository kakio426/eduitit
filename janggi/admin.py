from django.contrib import admin

from .models import JanggiMatchLog


@admin.register(JanggiMatchLog)
class JanggiMatchLogAdmin(admin.ModelAdmin):
    list_display = ('mode', 'difficulty', 'result', 'created_by', 'created_at')
    list_filter = ('mode', 'result')
    search_fields = ('created_by__username',)

