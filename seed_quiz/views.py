import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.models import SQAttempt, SQQuizItem, SQQuizSet
from seed_quiz.services.gate import (
    clear_session,
    find_or_create_attempt,
    get_current_item,
    get_today_published_set,
    set_session,
)
from seed_quiz.services.generation import generate_and_save_draft
from seed_quiz.services.grading import submit_and_reward

logger = logging.getLogger("seed_quiz.views")


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
        },
    )


@login_required
@require_POST
def htmx_generate(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type = request.POST.get("preset_type", "general")
    grade = int(request.POST.get("grade", 3))

    if preset_type not in dict(SQQuizSet.PRESET_CHOICES):
        preset_type = "general"
    if grade not in range(1, 7):
        grade = 3

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
