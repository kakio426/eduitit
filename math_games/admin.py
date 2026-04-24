from django.contrib import admin

from .models import MathGameMove, MathGameSession


class MathGameMoveInline(admin.TabularInline):
    model = MathGameMove
    extra = 0
    readonly_fields = ["actor", "move_json", "state_json", "is_valid", "feedback", "created_at"]
    can_delete = False


@admin.register(MathGameSession)
class MathGameSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "game_type", "difficulty", "result", "user", "session_key", "started_at", "ended_at"]
    list_filter = ["game_type", "difficulty", "result", "started_at"]
    search_fields = ["id", "session_key", "user__username"]
    readonly_fields = ["id", "started_at", "updated_at"]
    inlines = [MathGameMoveInline]


@admin.register(MathGameMove)
class MathGameMoveAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "actor", "is_valid", "created_at"]
    list_filter = ["actor", "is_valid", "created_at"]
    search_fields = ["session__id", "feedback"]
