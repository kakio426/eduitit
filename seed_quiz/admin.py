import json

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from seed_quiz.models import (
    SQAttempt,
    SQAttemptAnswer,
    SQBatchJob,
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
        "item_count_display",
        "is_official",
        "delete_button",
    ]
    list_filter = [
        "preset_type",
        "grade",
        "source",
        "quality_status",
        "share_opt_in",
        "is_official",
        "is_public",
        "is_active",
    ]
    search_fields = ["title"]
    raw_id_fields = ["created_by", "reviewed_by"]

    def item_count_display(self, obj):
        return f"{obj.items.count()}문항"
    item_count_display.short_description = "문항 수"

    def delete_button(self, obj):
        delete_url = reverse('admin:seed_quiz_sqquizbank_delete', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background-color: #ba2121; color: white; padding: 3px 10px; border-radius: 4px; text-decoration: none;">삭제</a>',
            delete_url
        )
    delete_button.short_description = "관리"
    inlines = [SQQuizBankItemInline]
    readonly_fields = ["created_at", "updated_at", "use_count", "reviewed_at", "source_hash"]
    actions = ["approve_public_share", "reject_public_share"]

    @admin.action(description="공유 신청 승인 (공개 전환)")
    def approve_public_share(self, request, queryset):
        count = queryset.update(
            quality_status="approved",
            is_public=True,
            reviewed_by_id=request.user.id,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{count}개 세트를 승인했습니다.")

    @admin.action(description="공유 신청 반려")
    def reject_public_share(self, request, queryset):
        count = queryset.update(
            quality_status="rejected",
            is_public=False,
            reviewed_by_id=request.user.id,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{count}개 세트를 반려했습니다.")

    # ── JSON 일괄 등록 커스텀 뷰 ──────────────────────────────
    def get_urls(self):
        custom_urls = [
            path(
                "json-import/",
                self.admin_site.admin_view(self.json_import_view),
                name="seed_quiz_sqquizbank_json_import",
            ),
            path(
                "cleanup-bad-data/",
                self.admin_site.admin_view(self.cleanup_bad_data_view),
                name="seed_quiz_sqquizbank_cleanup",
            ),
        ]
        return custom_urls + super().get_urls()

    def cleanup_bad_data_view(self, request):
        from django.shortcuts import redirect
        from django.contrib import messages

        bad_banks = SQQuizBank.objects.filter(items__lt=5)
        count = bad_banks.count()
        bad_banks.delete()

        broken_vocabs = SQQuizBank.objects.filter(preset_type='vocabulary', items__lt=10)
        v_count = broken_vocabs.count()
        broken_vocabs.delete()
        
        messages.success(request, f"🧹 정리 완료: 5문항 미만 세트 {count}개, 부실 어휘 세트 {v_count}개를 삭제했습니다.")
        return redirect(reverse('admin:seed_quiz_sqquizbank_changelist'))

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["json_import_url"] = reverse(
            "admin:seed_quiz_sqquizbank_json_import"
        )
        extra_context["cleanup_url"] = reverse(
            "admin:seed_quiz_sqquizbank_cleanup"
        )
        return super().changelist_view(request, extra_context=extra_context)

    def json_import_view(self, request):
        results = []
        error = None
        json_data = ""
        action = request.POST.get("action")

        if request.method == "POST":
            if action == "cleanup":
                # ── 데이터 정리 로직 (5문항 미만 삭제) ──
                bad_banks = SQQuizBank.objects.filter(items__lt=5)
                deleted_count = bad_banks.count()
                bad_banks.delete()
                results.append(f"🧹 필터링 완료: 5문항 미만인 세트 {deleted_count}개를 삭제했습니다.")
                
                # 'vocabulary' 카테고리 중 깨진 데이터 강제 정리 (요청 사항 반영)
                broken_vocabs = SQQuizBank.objects.filter(preset_type='vocabulary', items__lt=10)
                if broken_vocabs.exists():
                    deleted_v = broken_vocabs.count()
                    broken_vocabs.delete()
                    results.append(f"🧹 쓰레기 데이터 정리: 어휘(vocabulary) 카테고리 중 10문항 미만인 {deleted_v}개 세트를 정리했습니다.")
            else:
                # ── 기존 JSON 등록 로직 ──
                json_data = request.POST.get("json_data", "").strip()
                if not json_data:
                    error = "JSON 데이터가 비어 있습니다."
                else:
                    try:
                        data = json.loads(json_data)
                        if not isinstance(data, list):
                            raise ValueError("최상위 구조는 JSON 배열([])이어야 합니다.")

                        for s_data in data:
                            title = s_data.get("title", "").strip()
                            if not title:
                                results.append("⚠️ title이 비어있는 항목을 건너뛰었습니다.")
                                continue

                            items = s_data.get("items", [])
                            if not items:
                                results.append(f"⚠️ [{title}] 문항(items)이 비어있어 건너뛰었습니다.")
                                continue

                            bank, created = SQQuizBank.objects.update_or_create(
                                title=title,
                                defaults={
                                    "grade": s_data.get("grade", 0),
                                    "preset_type": s_data.get("preset_type", "vocabulary"),
                                    "is_official": True,
                                    "is_public": True,
                                    "quality_status": "approved",
                                    "created_by": request.user,
                                    "source": "manual",
                                },
                            )
                            bank.items.all().delete()

                            for i, item in enumerate(items):
                                choices = item.get("c", [])
                                if len(choices) != 4:
                                    results.append(
                                        f"⚠️ [{title}] {i+1}번 문항: 보기가 4개가 아닙니다 ({len(choices)}개). 건너뜀."
                                    )
                                    continue
                                SQQuizBankItem.objects.create(
                                    bank=bank,
                                    order_no=i + 1,
                                    question_text=item.get("q", ""),
                                    choices=choices,
                                    correct_index=item.get("a", 0),
                                    explanation=item.get("e", ""),
                                )

                            status = "생성" if created else "업데이트"
                            results.append(
                                f"✅ [{title}] {status} 완료 ({len(items)}문항)"
                            )

                    except json.JSONDecodeError as e:
                        error = f"JSON 파싱 오류: {e}"
                    except Exception as e:
                        error = f"처리 중 오류: {e}"

        context = {
            **self.admin_site.each_context(request),
            "title": "JSON 퀴즈 일괄 등록",
            "results": results,
            "error": error,
            "json_data": json_data if error else "",
        }
        return TemplateResponse(
            request, "admin/seed_quiz/json_import.html", context
        )


@admin.register(SQBatchJob)
class SQBatchJobAdmin(admin.ModelAdmin):
    list_display = [
        "provider",
        "target_month",
        "status",
        "requested_count",
        "success_count",
        "failed_count",
        "started_at",
        "completed_at",
    ]
    list_filter = ["provider", "status", "target_month"]
    search_fields = ["batch_id", "input_file_id", "output_file_id"]
    raw_id_fields = ["created_by"]
    readonly_fields = [
        "provider",
        "target_month",
        "batch_id",
        "status",
        "input_file_id",
        "output_file_id",
        "error_file_id",
        "requested_count",
        "success_count",
        "failed_count",
        "meta_json",
        "created_by",
        "started_at",
        "completed_at",
        "updated_at",
    ]


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
