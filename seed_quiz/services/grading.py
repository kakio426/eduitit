import uuid
import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from happy_seed.services.engine import add_seeds
from seed_quiz.models import SQAttempt, SQAttemptAnswer, SQGenerationLog

logger = logging.getLogger("seed_quiz.grading")

QUIZ_REWARD_SEEDS = 2  # 만점 보상 씨앗 수


def _build_reward_request_id(attempt_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"sq_reward:{attempt_id}")


def _resolve_consent_status(student) -> str:
    try:
        consent = student.consent  # HSGuardianConsent related_name='consent'
        return str(consent.status or "none")
    except Exception:
        return "none"


def _reward_attempt_if_eligible(*, attempt: SQAttempt, consent_status: str) -> tuple[int, bool]:
    """
    reward 적용 가능하면 반영하고 (지급 수량, 신규 적용 여부) 반환.

    호출 측에서 트랜잭션/잠금(select_for_update)을 보장해야 한다.
    """
    is_perfect = bool(attempt.max_score > 0 and attempt.score == attempt.max_score)
    if not is_perfect or consent_status != "approved":
        return 0, False

    if attempt.status == "rewarded" and attempt.reward_seed_amount >= QUIZ_REWARD_SEEDS:
        return 0, False

    reward_request_id = _build_reward_request_id(attempt.id)
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
    return QUIZ_REWARD_SEEDS, True


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
    consent_status = _resolve_consent_status(attempt.student)

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
    reward, _ = _reward_attempt_if_eligible(attempt=attempt, consent_status=consent_status)

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


def list_retroactive_reward_candidate_ids(
    *,
    student_id: uuid.UUID | None = None,
    classroom_id: uuid.UUID | None = None,
    limit: int | None = None,
) -> list[uuid.UUID]:
    qs = SQAttempt.objects.filter(
        status="submitted",
        score=F("max_score"),
        max_score__gt=0,
        reward_seed_amount=0,
        reward_applied_at__isnull=True,
        student__consent__status="approved",
    ).order_by("submitted_at", "updated_at")

    if student_id:
        qs = qs.filter(student_id=student_id)
    if classroom_id:
        qs = qs.filter(student__classroom_id=classroom_id)
    if limit is not None and limit > 0:
        qs = qs[:limit]
    return list(qs.values_list("id", flat=True))


@transaction.atomic
def apply_retroactive_reward_for_attempt(
    *,
    attempt_id: uuid.UUID,
    trigger: str = "manual",
) -> tuple[SQAttempt, bool]:
    """
    동의가 나중에 승인된 학생의 만점 시도에 소급 보상을 적용한다.

    Returns:
        (attempt, rewarded_now)
    """
    attempt = (
        SQAttempt.objects.select_for_update()
        .select_related("student", "quiz_set")
        .get(id=attempt_id)
    )

    if attempt.status not in ("submitted", "rewarded"):
        return attempt, False

    consent_status = _resolve_consent_status(attempt.student)
    reward, rewarded_now = _reward_attempt_if_eligible(
        attempt=attempt,
        consent_status=consent_status,
    )
    if not rewarded_now:
        return attempt, False

    attempt.save(
        update_fields=[
            "status",
            "reward_seed_amount",
            "reward_applied_at",
        ]
    )
    SQGenerationLog.objects.create(
        quiz_set=attempt.quiz_set,
        level="info",
        code="REWARD_RETROACTIVE_OK",
        message=(
            f"retro reward applied trigger={trigger}, "
            f"score={attempt.score}/{attempt.max_score}, reward={reward}"
        ),
        payload={
            "attempt_id": str(attempt.id),
            "student_id": str(attempt.student.id),
            "trigger": trigger,
        },
    )
    logger.info(
        "seed_quiz retro reward applied attempt=%s trigger=%s",
        str(attempt.id),
        trigger,
    )
    return attempt, True


def apply_retroactive_rewards_for_student(
    *,
    student_id: uuid.UUID,
    trigger: str = "consent",
    limit: int | None = None,
) -> int:
    attempt_ids = list_retroactive_reward_candidate_ids(
        student_id=student_id,
        limit=limit,
    )
    rewarded = 0
    for attempt_id in attempt_ids:
        _, rewarded_now = apply_retroactive_reward_for_attempt(
            attempt_id=attempt_id,
            trigger=trigger,
        )
        rewarded += int(rewarded_now)
    return rewarded


def apply_retroactive_rewards(
    *,
    classroom_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    trigger: str = "command",
    limit: int | None = None,
) -> dict:
    attempt_ids = list_retroactive_reward_candidate_ids(
        classroom_id=classroom_id,
        student_id=student_id,
        limit=limit,
    )
    rewarded = 0
    for attempt_id in attempt_ids:
        _, rewarded_now = apply_retroactive_reward_for_attempt(
            attempt_id=attempt_id,
            trigger=trigger,
        )
        rewarded += int(rewarded_now)
    return {
        "candidate_count": len(attempt_ids),
        "rewarded_count": rewarded,
        "skipped_count": len(attempt_ids) - rewarded,
    }
