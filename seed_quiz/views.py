import logging
import random
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.models import SQAttempt, SQQuizBank, SQQuizItem, SQQuizSet
from seed_quiz.services.bank import (
    copy_bank_to_draft,
    generate_bank_from_context_ai,
    parse_csv_upload,
    save_parsed_sets_to_bank,
)
from seed_quiz.services.gate import (
    clear_session,
    find_or_create_attempt,
    get_current_item,
    get_today_published_set,
    set_session,
)
from seed_quiz.services.generation import generate_and_save_draft
from seed_quiz.services.grading import submit_and_reward
from seed_quiz.services.rag import consume_rag_quota, refund_rag_quota
from seed_quiz.topics import DEFAULT_TOPIC, TOPIC_LABELS, normalize_topic

logger = logging.getLogger("seed_quiz.views")

CSV_PREVIEW_PAYLOAD_KEY = "sq_csv_preview_payload"
CSV_PREVIEW_TOKEN_KEY = "sq_csv_preview_token"


def _parse_bank_filters(raw_preset: str, raw_grade: str):
    preset_type = normalize_topic(raw_preset) or DEFAULT_TOPIC
    raw_grade_value = (raw_grade or "").strip().lower()
    if raw_grade_value in {"all", "*", ""}:
        return preset_type, None
    try:
        grade = int(raw_grade_value)
    except (TypeError, ValueError):
        grade = 3
    if grade not in range(1, 7):
        grade = 3
    return preset_type, grade


def _build_bank_queryset(classroom, user, preset_type: str, grade: int | None, scope: str):
    banks_qs = SQQuizBank.objects.filter(
        is_active=True,
        preset_type=preset_type,
    )
    if grade is not None:
        banks_qs = banks_qs.filter(grade=grade)

    approved_filter = Q(quality_status="approved")
    today = timezone.localdate()
    available_filter = (
        (Q(available_from__isnull=True) | Q(available_from__lte=today))
        & (Q(available_to__isnull=True) | Q(available_to__gte=today))
    )
    if scope == "official":
        banks_qs = banks_qs.filter(is_official=True).filter(approved_filter).filter(available_filter)
    elif scope == "public":
        banks_qs = banks_qs.filter(is_public=True).filter(approved_filter).filter(available_filter)
    else:
        banks_qs = banks_qs.filter(
            (Q(is_official=True) & approved_filter & available_filter)
            | (Q(is_public=True) & approved_filter & available_filter)
            | Q(created_by=user)
        ).distinct()
    return banks_qs


# ---------------------------------------------------------------------------
# 랜딩
# ---------------------------------------------------------------------------

@login_required
def landing(request):
    """제품 카드 클릭 시 happy_seed 대시보드로 이동."""
    return redirect("happy_seed:dashboard")


# ---------------------------------------------------------------------------
# 교사 뷰
# ---------------------------------------------------------------------------

@login_required
def teacher_dashboard(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    initial_preset, initial_grade = _parse_bank_filters(
        request.GET.get("preset_type", DEFAULT_TOPIC),
        request.GET.get("grade", "3"),
    )
    today_sets = SQQuizSet.objects.filter(
        classroom=classroom,
        target_date=timezone.localdate(),
    ).order_by("-created_at")
    return render(
        request,
        "seed_quiz/teacher_dashboard.html",
        {
            "classroom": classroom,
            "today_sets": today_sets,
            "preset_choices": SQQuizSet.PRESET_CHOICES,
            "initial_preset": initial_preset,
            "initial_grade": initial_grade,
            "initial_grade_str": "all" if initial_grade is None else str(initial_grade),
            "rag_daily_limit": max(0, int(getattr(settings, "SEED_QUIZ_RAG_DAILY_LIMIT", 1))),
            "allow_rag": bool(getattr(settings, "SEED_QUIZ_ALLOW_RAG", False)),
        },
    )


@login_required
def htmx_bank_browse(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.GET.get("preset_type", DEFAULT_TOPIC),
        request.GET.get("grade", "3"),
    )
    scope = (request.GET.get("scope", "official") or "official").strip().lower()
    if scope not in {"official", "public", "all"}:
        scope = "official"

    banks_qs = _build_bank_queryset(
        classroom=classroom,
        user=request.user,
        preset_type=preset_type,
        grade=grade,
        scope=scope,
    )

    banks = banks_qs.order_by("-is_official", "-use_count", "-created_at")[:24]

    return render(
        request,
        "seed_quiz/partials/bank_browse.html",
        {
            "classroom": classroom,
            "banks": banks,
            "scope": scope,
            "preset_type": preset_type,
            "preset_label": TOPIC_LABELS.get(preset_type, "주제"),
            "grade": grade,
            "allow_inline_ai": bool(getattr(settings, "SEED_QUIZ_ALLOW_INLINE_AI", False)),
        },
    )


@login_required
@require_POST
def htmx_bank_random_select(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.POST.get("preset_type", DEFAULT_TOPIC),
        request.POST.get("grade", "all"),
    )
    scope = (request.POST.get("scope", "all") or "all").strip().lower()
    if scope not in {"official", "public", "all"}:
        scope = "all"

    banks_qs = _build_bank_queryset(
        classroom=classroom,
        user=request.user,
        preset_type=preset_type,
        grade=grade,
        scope=scope,
    )

    # 최근 7일 내 이미 사용한 은행 세트는 우선 제외
    recent_bank_ids = list(
        SQQuizSet.objects.filter(
            classroom=classroom,
            target_date__gte=timezone.localdate() - timedelta(days=7),
            bank_source__isnull=False,
        )
        .values_list("bank_source_id", flat=True)
        .distinct()
    )
    candidates = list(banks_qs.exclude(id__in=recent_bank_ids)[:100])
    if not candidates:
        candidates = list(banks_qs[:100])
    if not candidates:
        return HttpResponse(
            '<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            "랜덤으로 선택할 퀴즈 세트가 없습니다. 먼저 CSV 문제를 업로드해 주세요.</div>",
            status=404,
        )

    selected_bank = random.choice(candidates)
    try:
        quiz_set = copy_bank_to_draft(
            bank_id=selected_bank.id,
            classroom=classroom,
            teacher=request.user,
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">{e}</div>',
            status=400,
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
            "rag_notice": f"랜덤 선택 완료: {selected_bank.get_preset_type_display()}",
        },
    )


@login_required
@require_POST
def htmx_bank_select(request, classroom_id, bank_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    try:
        quiz_set = copy_bank_to_draft(
            bank_id=bank_id,
            classroom=classroom,
            teacher=request.user,
        )
    except SQQuizBank.DoesNotExist:
        return HttpResponse(
            '<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            "선택한 퀴즈 세트를 찾을 수 없습니다.</div>",
            status=404,
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">{e}</div>',
            status=400,
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
        },
    )


@login_required
@require_POST
def htmx_csv_upload(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {"classroom": classroom, "created_count": 0, "errors": ["CSV 파일을 선택해 주세요."]},
            status=400,
        )

    parsed_sets, errors = parse_csv_upload(csv_file)
    if errors:
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "updated_count": 0,
                "review_count": 0,
                "errors": errors,
            },
            status=400,
        )

    if not parsed_sets:
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "updated_count": 0,
                "review_count": 0,
                "errors": ["저장할 수 있는 문제 세트가 없습니다."],
            },
            status=400,
        )

    token = uuid4().hex
    request.session[CSV_PREVIEW_TOKEN_KEY] = token
    request.session[CSV_PREVIEW_PAYLOAD_KEY] = parsed_sets
    request.session.modified = True

    return render(
        request,
        "seed_quiz/partials/csv_upload_preview.html",
        {
            "classroom": classroom,
            "preview_token": token,
            "parsed_sets": parsed_sets,
            "set_count": len(parsed_sets),
        },
    )


@login_required
@require_POST
def htmx_csv_confirm(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    token = (request.POST.get("preview_token") or "").strip()
    session_token = request.session.get(CSV_PREVIEW_TOKEN_KEY)
    parsed_sets = request.session.get(CSV_PREVIEW_PAYLOAD_KEY) or []

    if not token or token != session_token or not parsed_sets:
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "updated_count": 0,
                "review_count": 0,
                "errors": ["CSV 미리보기 세션이 만료되었습니다. 다시 업로드해 주세요."],
            },
            status=400,
        )

    share_opt_in = (request.POST.get("share_opt_in") or "").lower() in {"on", "1", "true", "yes"}
    created_count, updated_count, review_count = save_parsed_sets_to_bank(
        parsed_sets=parsed_sets,
        created_by=request.user,
        share_opt_in=share_opt_in,
    )

    request.session.pop(CSV_PREVIEW_TOKEN_KEY, None)
    request.session.pop(CSV_PREVIEW_PAYLOAD_KEY, None)
    request.session.modified = True

    return render(
        request,
        "seed_quiz/partials/csv_upload_result.html",
        {
            "classroom": classroom,
            "created_count": created_count,
            "updated_count": updated_count,
            "review_count": review_count,
            "errors": [],
        },
        status=200,
    )


@login_required
@require_POST
def htmx_rag_generate(request, classroom_id):
    if not bool(getattr(settings, "SEED_QUIZ_ALLOW_RAG", False)):
        return HttpResponse(
            '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
            "현재 맞춤 생성 기능이 비활성화되어 있습니다.</div>",
            status=403,
        )

    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.POST.get("preset_type", DEFAULT_TOPIC),
        request.POST.get("grade", "3"),
    )
    source_text = (request.POST.get("source_text") or "").strip()
    if not source_text:
        return HttpResponse(
            '<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            "지문 텍스트를 입력해 주세요.</div>",
            status=400,
        )

    daily_limit = max(0, int(getattr(settings, "SEED_QUIZ_RAG_DAILY_LIMIT", 1)))
    if daily_limit == 0:
        return HttpResponse(
            '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
            "현재 맞춤 생성 기능이 비활성화되어 있습니다.</div>",
            status=403,
        )

    allowed, remaining = consume_rag_quota(classroom=classroom, teacher=request.user, daily_limit=daily_limit)
    if not allowed:
        return HttpResponse(
            '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
            "오늘의 맞춤 생성 횟수를 모두 사용했습니다. 내일 다시 시도해 주세요.</div>",
            status=429,
        )

    try:
        result = generate_bank_from_context_ai(
            preset_type=preset_type,
            grade=grade,
            source_text=source_text,
            created_by=request.user,
        )
        if isinstance(result, tuple):
            bank, from_cache = result
        else:
            bank = result
            from_cache = False
        quiz_set = copy_bank_to_draft(bank_id=bank.id, classroom=classroom, teacher=request.user)
    except Exception as e:
        refund_rag_quota(classroom=classroom, teacher=request.user)
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            f"맞춤 생성 오류: {e}</div>",
            status=400,
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
            "rag_notice": (
                f"지문 기반 맞춤 생성 완료 (오늘 남은 횟수: {remaining})"
                if not from_cache
                else f"지문 기반 캐시 세트 재사용 (오늘 남은 횟수: {remaining})"
            ),
        },
    )


@login_required
@require_POST
def htmx_generate(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.POST.get("preset_type", DEFAULT_TOPIC),
        request.POST.get("grade", "3"),
    )

    try:
        quiz_set = generate_and_save_draft(classroom, preset_type, grade, request.user)
    except RuntimeError as e:
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            f"퀴즈 생성 오류: {e}</div>"
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
        },
    )


@login_required
@require_POST
def htmx_publish(request, classroom_id, set_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    quiz_set = get_object_or_404(
        SQQuizSet, id=set_id, classroom=classroom, status="draft"
    )

    with transaction.atomic():
        # 기존 published → closed
        SQQuizSet.objects.filter(
            classroom=classroom,
            target_date=quiz_set.target_date,
            preset_type=quiz_set.preset_type,
            status="published",
        ).update(status="closed")

        quiz_set.status = "published"
        quiz_set.published_at = timezone.now()
        quiz_set.published_by = request.user
        quiz_set.save(update_fields=["status", "published_at", "published_by"])

    student_url = request.build_absolute_uri(
        reverse(
            "seed_quiz:student_gate",
            kwargs={"class_slug": classroom.slug},
        )
    )
    return render(
        request,
        "seed_quiz/partials/teacher_published.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "student_url": student_url,
        },
    )


@login_required
def htmx_progress(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    quiz_set = (
        SQQuizSet.objects.filter(
            classroom=classroom,
            target_date=timezone.localdate(),
            status="published",
        )
        .prefetch_related("attempts")
        .first()
    )

    stats = {}
    if quiz_set:
        total = classroom.students.filter(is_active=True).count()
        attempts = quiz_set.attempts.all()
        stats = {
            "total": total,
            "started": attempts.count(),
            "submitted": attempts.filter(status__in=["submitted", "rewarded"]).count(),
            "perfect": attempts.filter(score=3).count(),
        }
    return render(
        request,
        "seed_quiz/partials/teacher_progress.html",
        {
            "quiz_set": quiz_set,
            "stats": stats,
        },
    )


# ---------------------------------------------------------------------------
# 학생 뷰
# ---------------------------------------------------------------------------

def student_gate(request, class_slug):
    classroom = get_object_or_404(HSClassroom, slug=class_slug, is_active=True)
    quiz_set = get_today_published_set(classroom)
    error = request.session.pop("sq_gate_error", None)
    return render(
        request,
        "seed_quiz/student_gate.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "error": error,
        },
    )


@require_POST
def student_start(request, class_slug):
    classroom = get_object_or_404(HSClassroom, slug=class_slug, is_active=True)
    quiz_set = get_today_published_set(classroom)
    if not quiz_set:
        return redirect("seed_quiz:student_gate", class_slug=class_slug)

    number_raw = request.POST.get("number", "").strip()
    name = request.POST.get("name", "").strip()

    if not number_raw.isdigit() or not name:
        request.session["sq_gate_error"] = "번호와 이름을 모두 입력해 주세요."
        return redirect("seed_quiz:student_gate", class_slug=class_slug)

    student = HSStudent.objects.filter(
        classroom=classroom,
        number=int(number_raw),
        name=name,
        is_active=True,
    ).first()

    if not student:
        request.session["sq_gate_error"] = "번호와 이름을 다시 확인해 주세요."
        return redirect("seed_quiz:student_gate", class_slug=class_slug)

    attempt = find_or_create_attempt(quiz_set, student)
    set_session(request, classroom, student, attempt)

    if attempt.status in ("submitted", "rewarded"):
        return redirect("seed_quiz:htmx_play_result")

    return redirect("seed_quiz:student_play")


def student_play_shell(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return redirect("/")
    return render(request, "seed_quiz/student_play.html")


def htmx_play_current(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return HttpResponse(status=403)

    attempt = get_object_or_404(SQAttempt, id=attempt_id)

    if attempt.status in ("submitted", "rewarded"):
        return _render_result(request, attempt)

    item = get_current_item(attempt)
    if not item:
        # 모든 문항 답변됨 → 채점
        return _do_finish(request, attempt)

    answered_count = attempt.answers.count()
    return render(
        request,
        "seed_quiz/partials/play_item.html",
        {
            "item": item,
            "item_no": answered_count + 1,
            "total": 3,
        },
    )


@require_POST
def htmx_play_answer(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return HttpResponse(status=403)

    attempt = get_object_or_404(SQAttempt, id=attempt_id)

    if attempt.status in ("submitted", "rewarded"):
        return _render_result(request, attempt)

    item_id = request.POST.get("item_id")
    selected_raw = request.POST.get("selected_index", "")

    if not selected_raw.lstrip("-").isdigit():
        return HttpResponse(status=400)
    selected_index = int(selected_raw)
    if selected_index not in [0, 1, 2, 3]:
        return HttpResponse(status=400)

    # 해당 item이 현재 퀴즈 세트 소속이고, 현재 순서여야 함
    item = get_object_or_404(SQQuizItem, id=item_id, quiz_set=attempt.quiz_set)

    # 순서 검증: 현재 풀어야 할 문항만 허용
    expected_item = get_current_item(attempt)
    if expected_item is None or str(expected_item.id) != str(item.id):
        # 이미 완료되었거나 순서가 다름 → 현재 상태 기준으로 다음 화면 반환
        next_item = get_current_item(attempt)
        if next_item is None:
            return _do_finish(request, attempt)
        answered_count = attempt.answers.count()
        return render(
            request,
            "seed_quiz/partials/play_item.html",
            {"item": next_item, "item_no": answered_count + 1, "total": 3},
        )

    # 답변 저장 (이미 답변한 경우 get_or_create로 무시)
    SQAttempt.objects.select_for_update().filter(id=attempt.id)  # 잠금
    with transaction.atomic():
        attempt_locked = SQAttempt.objects.select_for_update().get(id=attempt.id)
        if attempt_locked.status in ("submitted", "rewarded"):
            return _render_result(request, attempt_locked)

        from seed_quiz.models import SQAttemptAnswer
        SQAttemptAnswer.objects.get_or_create(
            attempt=attempt_locked,
            item=item,
            defaults={
                "selected_index": selected_index,
                "is_correct": item.correct_index == selected_index,
            },
        )

    # 다음 문항 확인
    attempt.refresh_from_db()
    next_item = get_current_item(attempt)
    if next_item is None:
        return _do_finish(request, attempt)

    answered_count = attempt.answers.count()
    return render(
        request,
        "seed_quiz/partials/play_item.html",
        {"item": next_item, "item_no": answered_count + 1, "total": 3},
    )


def htmx_play_result(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return HttpResponse(status=403)
    attempt = get_object_or_404(SQAttempt, id=attempt_id)
    return _render_result(request, attempt)


def _do_finish(request, attempt: SQAttempt) -> HttpResponse:
    """채점 + 보상 처리 후 결과 partial 반환."""
    answers = {
        a.item.order_no: a.selected_index
        for a in attempt.answers.select_related("item").all()
    }
    attempt = submit_and_reward(attempt_id=attempt.id, answers=answers)
    return _render_result(request, attempt)


def _render_result(request, attempt: SQAttempt) -> HttpResponse:
    answers_by_order = {
        a.item.order_no: a
        for a in attempt.answers.select_related("item")
    }
    items_with_answers = []
    for item in attempt.quiz_set.items.order_by("order_no"):
        ans = answers_by_order.get(item.order_no)
        choices = item.choices or []
        selected_choice = choices[ans.selected_index] if ans and 0 <= ans.selected_index < len(choices) else ""
        items_with_answers.append({
            "item": item,
            "answer": ans,
            "correct_choice": choices[item.correct_index] if 0 <= item.correct_index < len(choices) else "",
            "selected_choice": selected_choice,
        })
    return render(
        request,
        "seed_quiz/partials/play_result.html",
        {
            "attempt": attempt,
            "items_with_answers": items_with_answers,
        },
    )
