import uuid

from django.utils import timezone

from seed_quiz.models import SQAttempt, SQQuizSet

SESSION_KEYS = ["sq_classroom_id", "sq_student_id", "sq_attempt_id", "sq_request_id"]


def get_today_published_set(classroom) -> SQQuizSet | None:
    """오늘 날짜의 배포 중인 퀴즈 세트 반환."""
    return SQQuizSet.objects.filter(
        classroom=classroom,
        target_date=timezone.localdate(),
        status="published",
    ).first()


def find_or_create_attempt(quiz_set: SQQuizSet, student) -> SQAttempt:
    """학생의 attempt를 찾거나 새로 생성."""
    attempt, _ = SQAttempt.objects.get_or_create(
        quiz_set=quiz_set,
        student=student,
        defaults={"request_id": uuid.uuid4()},
    )
    return attempt


def get_current_item(attempt: SQAttempt):
    """현재 풀어야 할 문항 반환. 모두 풀었으면 None."""
    answered_order_nos = set(
        attempt.answers.values_list("item__order_no", flat=True)
    )
    items = attempt.quiz_set.items.order_by("order_no")
    for item in items:
        if item.order_no not in answered_order_nos:
            return item
    return None


def clear_session(request) -> None:
    for key in SESSION_KEYS:
        request.session.pop(key, None)


def set_session(request, classroom, student, attempt) -> None:
    request.session["sq_classroom_id"] = str(classroom.id)
    request.session["sq_student_id"] = str(student.id)
    request.session["sq_attempt_id"] = str(attempt.id)
    request.session["sq_request_id"] = str(attempt.request_id)
