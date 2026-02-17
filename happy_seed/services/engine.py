import hashlib
import random
import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from happy_seed.models import (
    HSBloomDraw,
    HSClassroomConfig,
    HSPrize,
    HSSeedLedger,
    HSStudent,
    HSTicketLedger,
)


class ConsentRequiredError(Exception):
    pass


class InsufficientTicketsError(Exception):
    pass


class NoPrizeAvailableError(Exception):
    pass


def execute_bloom_draw(student, classroom, created_by, request_id=None):
    """
    추첨 실행 (멱등성 + select_for_update + 트랜잭션)
    """
    if request_id is None:
        request_id = uuid.uuid4()

    existing = HSBloomDraw.objects.filter(request_id=request_id).first()
    if existing:
        return existing

    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)

    with transaction.atomic():
        student = HSStudent.objects.select_for_update().get(pk=student.pk)

        consent = getattr(student, "consent", None)
        if not consent or consent.status != "approved":
            raise ConsentRequiredError("보호자 동의가 필요합니다.")

        if student.ticket_count < 1:
            raise InsufficientTicketsError("티켓이 부족합니다.")
        student.ticket_count -= 1

        is_forced = student.pending_forced_win
        if is_forced:
            student.pending_forced_win = False

        base_rate = Decimal(config.base_win_rate)
        balance_adj = Decimal("0")
        if config.balance_mode_enabled and not is_forced:
            balance_adj = _calculate_balance_adjustment(student, config)

        effective_rate = base_rate + balance_adj
        effective_rate = max(Decimal("0"), min(Decimal("100"), effective_rate))

        if is_forced:
            is_win = True
        else:
            roll = random.randint(1, 100)
            is_win = roll <= int(effective_rate)

        prize = None
        if is_win:
            prize = _select_prize(classroom)
        else:
            _add_seeds_internal(student, 1, "no_win", "미당첨 보정", config)

        if is_win:
            student.total_wins += 1

        student.save()

        HSTicketLedger.objects.create(
            student=student,
            source="participation",
            amount=-1,
            detail="꽃피움 추첨 사용",
            balance_after=student.ticket_count,
            request_id=uuid.uuid4(),
        )

        draw = HSBloomDraw.objects.create(
            student=student,
            is_win=is_win,
            prize=prize,
            input_probability=base_rate,
            balance_adjustment=balance_adj,
            effective_probability=effective_rate,
            is_forced=is_forced,
            force_reason="교사 예약 개입" if is_forced else "",
            request_id=request_id,
            created_by=created_by,
        )
        return draw


def add_seeds(student, amount, reason, detail="", request_id=None):
    """
    씨앗 부여 (멱등성 + 자동 블룸 전환)
    """
    if request_id is None:
        request_id = uuid.uuid4()

    existing = HSSeedLedger.objects.filter(student=student, request_id=request_id).first()
    if existing:
        return existing

    config, _ = HSClassroomConfig.objects.get_or_create(classroom=student.classroom)

    with transaction.atomic():
        student = HSStudent.objects.select_for_update().get(pk=student.pk)
        return _add_seeds_internal(student, amount, reason, detail, config, request_id)


def _add_seeds_internal(student, amount, reason, detail, config, request_id=None):
    if request_id is None:
        request_id = uuid.uuid4()

    student.seed_count += amount

    ledger = HSSeedLedger.objects.create(
        student=student,
        amount=amount,
        reason=reason,
        detail=detail,
        balance_after=student.seed_count,
        request_id=request_id,
    )

    seeds_per_bloom = config.seeds_per_bloom
    while student.seed_count >= seeds_per_bloom:
        student.seed_count -= seeds_per_bloom
        student.ticket_count += 1

        HSSeedLedger.objects.create(
            student=student,
            amount=-seeds_per_bloom,
            reason="bloom_convert",
            detail=f"씨앗 {seeds_per_bloom}개를 티켓으로 전환",
            balance_after=student.seed_count,
        )

        HSTicketLedger.objects.create(
            student=student,
            source="seed_accumulation",
            amount=1,
            detail=f"씨앗 {seeds_per_bloom}개 누적 자동 전환",
            balance_after=student.ticket_count,
        )

    student.save()
    return ledger


def grant_tickets(student, source, amount, detail="", request_id=None):
    """
    티켓 부여 (동의 확인 + 멱등성)
    """
    if request_id is None:
        request_id = uuid.uuid4()

    existing = HSTicketLedger.objects.filter(student=student, request_id=request_id).first()
    if existing:
        return existing

    consent = getattr(student, "consent", None)
    if not consent or consent.status != "approved":
        raise ConsentRequiredError("보호자 동의가 필요합니다.")

    with transaction.atomic():
        student = HSStudent.objects.select_for_update().get(pk=student.pk)
        student.ticket_count += amount
        student.save()

        ledger = HSTicketLedger.objects.create(
            student=student,
            source=source,
            amount=amount,
            detail=detail,
            balance_after=student.ticket_count,
            request_id=request_id,
        )
        return ledger


def get_garden_data(classroom):
    """
    공개 꽃밭 데이터 생성
    """
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)
    seeds_per_bloom = config.seeds_per_bloom

    students = classroom.students.filter(is_active=True).select_related("consent")
    flowers = []

    for student in students:
        consent = getattr(student, "consent", None)
        if not consent or consent.status != "approved":
            continue

        ratio = student.seed_count / seeds_per_bloom if seeds_per_bloom > 0 else 0
        ratio = min(ratio, 1.0)

        if ratio >= 1.0:
            stage, icon, color = "bloom", "🌸", "pink"
        elif ratio >= 0.7:
            stage, icon, color = "bud", "🌿", "darkgreen"
        elif ratio >= 0.3:
            stage, icon, color = "sprout", "🌱", "lightgreen"
        else:
            stage, icon, color = "seed", "🌰", "gray"

        hash_val = int(hashlib.md5(str(student.id).encode()).hexdigest()[:8], 16)
        offset_x = (hash_val % 21) - 10
        offset_y = ((hash_val >> 8) % 21) - 10

        flowers.append(
            {
                "student_id": str(student.id),
                "name": student.name,
                "stage": stage,
                "icon": icon,
                "color": color,
                "ratio": ratio,
                "seed_count": student.seed_count,
                "offset_x": offset_x,
                "offset_y": offset_y,
            }
        )

    return flowers


def get_effective_win_rate(student, config):
    base = Decimal(config.base_win_rate)
    if not config.balance_mode_enabled:
        return base, Decimal("0")

    adj = _calculate_balance_adjustment(student, config)
    effective = max(Decimal("0"), min(Decimal("100"), base + adj))
    return effective, adj


def _calculate_balance_adjustment(student, config):
    lookback = timezone.now() - timezone.timedelta(days=config.balance_lookback_days)
    classroom = student.classroom

    students = classroom.students.filter(is_active=True)
    total_draws = HSBloomDraw.objects.filter(
        student__in=students,
        is_win=True,
        drawn_at__gte=lookback,
    )
    avg_wins = total_draws.count() / max(students.count(), 1)

    student_wins = HSBloomDraw.objects.filter(
        student=student,
        is_win=True,
        drawn_at__gte=lookback,
    ).count()

    epsilon = Decimal(str(config.balance_epsilon))
    base = Decimal(config.base_win_rate)

    if student_wins < avg_wins:
        return base * epsilon
    if student_wins > avg_wins:
        return -(base * epsilon)
    return Decimal("0")


def _select_prize(classroom):
    """
    사용 가능한 보상 중 가중치(%) 기반 랜덤 선택 후 재고 차감
    """
    available_prizes = list(
        HSPrize.objects.filter(
            classroom=classroom,
            is_active=True,
        ).exclude(
            remaining_quantity=0,
        )
    )
    available_prizes = [p for p in available_prizes if p.is_available]

    if not available_prizes:
        return None

    weighted_pool = [p for p in available_prizes if p.win_rate_percent and p.win_rate_percent > 0]
    if not weighted_pool:
        return None

    while weighted_pool:
        weights = [float(p.win_rate_percent) for p in weighted_pool]
        prize = random.choices(weighted_pool, weights=weights, k=1)[0]

        if prize.total_quantity is None:
            return prize

        updated = HSPrize.objects.filter(
            id=prize.id,
            remaining_quantity__gt=0,
        ).update(remaining_quantity=F("remaining_quantity") - 1)

        if updated == 1:
            return prize

        # 동시성 충돌/재고 소진 시 해당 보상을 풀에서 제외 후 재시도
        weighted_pool = [p for p in weighted_pool if p.id != prize.id and p.is_available]

    return None
