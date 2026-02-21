import uuid
import logging

from django.db import transaction
from django.utils import timezone

from happy_seed.services.engine import add_seeds
from seed_quiz.models import SQAttempt, SQAttemptAnswer, SQGenerationLog

logger = logging.getLogger("seed_quiz.grading")

QUIZ_REWARD_SEEDS = 2  # 만점 보상 씨앗 수


@transaction.atomic
def submit_and_reward(*, attempt_id: uuid.UUID, answers: dict) -> SQAttempt:
    """
    채점 + 보상 원자 처리.

    answers = {order_no(int or str): selected_index(int), ...}

    멱등: 이미 submitted/rewarded이면 기존 attempt 그대로 반환.
    동시 중복 방지: select_for_update로 attempt 잠금.
    """
    attempt = (
        SQAttempt.objects.select_for_update()
        .select_related("student", "quiz_set")
        .get(id=attempt_id)
    )

    # 멱등 처리
    if attempt.status in ("submitted", "rewarded"):
        return attempt

    # 동의 상태 조회
    try:
        consent = attempt.student.consent  # HSGuardianConsent related_name='consent'
        consent_status = consent.status
    except Exception:
        consent_status = "none"

    # 채점
    items = {item.order_no: item for item in attempt.quiz_set.items.all()}
    score = 0

    for order_no_raw, selected in answers.items():
        order_no = int(order_no_raw)
        item = items.get(order_no)
        if not item:
            continue
        is_correct = item.correct_index == int(selected)
        if is_correct:
            score += 1
        SQAttemptAnswer.objects.get_or_create(
            attempt=attempt,
            item=item,
            defaults={
                "selected_index": int(selected),
                "is_correct": is_correct,
            },
        )

    attempt.score = score
    attempt.max_score = len(items)
    attempt.status = "submitted"
    attempt.submitted_at = timezone.now()
    attempt.consent_snapshot = consent_status[:15]

    # 보상 지급: 만점 + 동의 승인
    reward = 0
    if score == attempt.max_score and consent_status == "approved":
        reward_request_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"sq_reward:{attempt.id}"
        )
        add_seeds(
            student=attempt.student,
            amount=QUIZ_REWARD_SEEDS,
            reason="behavior",
            detail="[씨앗 퀴즈] 만점 보상",
            request_id=reward_request_id,
        )
        attempt.status = "rewarded"
        attempt.reward_seed_amount = QUIZ_REWARD_SEEDS
        attempt.reward_applied_at = timezone.now()
        reward = QUIZ_REWARD_SEEDS

    attempt.save(
        update_fields=[
            "score",
            "max_score",
            "status",
            "submitted_at",
            "consent_snapshot",
            "reward_seed_amount",
            "reward_applied_at",
        ]
    )

    log_code = "REWARD_OK" if attempt.status == "rewarded" else "SUBMITTED"
    SQGenerationLog.objects.create(
        quiz_set=attempt.quiz_set,
        level="info",
        code=log_code,
        message=f"score={score}/{attempt.max_score}, consent={consent_status}, reward={reward}",
        payload={
            "attempt_id": str(attempt.id),
            "student_id": str(attempt.student.id),
        },
    )
    logger.info(
        "seed_quiz grading done attempt=%s score=%d/%d status=%s",
        str(attempt.id),
        score,
        attempt.max_score,
        attempt.status,
    )
    return attempt
