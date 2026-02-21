from django.db import transaction
from django.utils import timezone

from seed_quiz.models import SQRagDailyUsage


def consume_rag_quota(classroom, teacher, daily_limit: int) -> tuple[bool, int]:
    """
    일일 quota를 1회 차감한다.
    반환: (allowed, remaining_after)
    """
    today = timezone.localdate()
    with transaction.atomic():
        usage, _ = SQRagDailyUsage.objects.select_for_update().get_or_create(
            usage_date=today,
            classroom=classroom,
            teacher=teacher,
            defaults={"count": 0},
        )
        if usage.count >= daily_limit:
            return False, 0
        usage.count += 1
        usage.save(update_fields=["count", "updated_at"])
        return True, max(0, daily_limit - usage.count)


def refund_rag_quota(classroom, teacher) -> None:
    """
    생성 실패 등으로 사용량 차감이 취소되어야 할 때 1회 복구한다.
    """
    today = timezone.localdate()
    with transaction.atomic():
        usage = (
            SQRagDailyUsage.objects.select_for_update()
            .filter(usage_date=today, classroom=classroom, teacher=teacher)
            .first()
        )
        if not usage or usage.count <= 0:
            return
        usage.count -= 1
        usage.save(update_fields=["count", "updated_at"])
