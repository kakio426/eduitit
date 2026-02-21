from django.contrib import admin

from seed_quiz.models import (
    SQAttempt,
    SQAttemptAnswer,
    SQGenerationLog,
    SQQuizBank,
    SQQuizBankItem,
    SQQuizItem,
    SQQuizSet,
)


class SQQuizItemInline(admin.TabularInline):
    model = SQQuizItem
    extra = 0
    fields = ["order_no", "question_text", "choices", "correct_index", "difficulty"]
    readonly_fields = ["created_at"]


class SQAttemptAnswerInline(admin.TabularInline):
    model = SQAttemptAnswer
    extra = 0
    readonly_fields = ["item", "selected_index", "is_correct", "answered_at"]
    can_delete = False


class SQQuizBankItemInline(admin.TabularInline):
    model = SQQuizBankItem
    extra = 0
    fields = ["order_no", "question_text", "choices", "correct_index", "difficulty"]


@admin.register(SQQuizBank)
class SQQuizBankAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "preset_type",
        "grade",
        "source",
        "is_official",
        "is_public",
        "is_active",
        "use_count",
        "created_at",
    ]
    list_filter = ["preset_type", "grade", "source", "is_official", "is_public", "is_active"]
    search_fields = ["title"]
    raw_id_fields = ["created_by"]
    inlines = [SQQuizBankItemInline]
    readonly_fields = ["created_at", "updated_at", "use_count"]


@admin.register(SQQuizSet)
class SQQuizSetAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "classroom",
        "target_date",
        "preset_type",
        "grade",
        "status",
        "source",
        "created_at",
    ]
    list_filter = ["status", "source", "preset_type", "target_date"]
    search_fields = ["title", "classroom__name"]
    inlines = [SQQuizItemInline]
    raw_id_fields = ["classroom", "created_by", "published_by", "bank_source"]
    readonly_fields = ["created_at", "updated_at", "published_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("classroom", "created_by")


@admin.register(SQAttempt)
class SQAttemptAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "quiz_set",
        "status",
        "score",
        "max_score",
        "reward_seed_amount",
        "started_at",
    ]
    list_filter = ["status"]
    search_fields = ["student__name", "quiz_set__title"]
    inlines = [SQAttemptAnswerInline]
    raw_id_fields = ["student", "quiz_set"]
    readonly_fields = [
        "started_at",
        "submitted_at",
        "reward_applied_at",
        "updated_at",
        "request_id",
        "consent_snapshot",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "student__classroom", "quiz_set"
        )


@admin.register(SQGenerationLog)
class SQGenerationLogAdmin(admin.ModelAdmin):
    list_display = ["level", "code", "message_short", "quiz_set", "created_at"]
    list_filter = ["level", "code"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["quiz_set"]

    def message_short(self, obj):
        return obj.message[:60]
    message_short.short_description = "메시지"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("quiz_set")
