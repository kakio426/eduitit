import random
import string
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from happy_seed.services.engine import add_seeds
from seed_quiz.models import (
    SQGameAnswer,
    SQGamePlayer,
    SQGameQuestion,
    SQGameReward,
    SQGameRoom,
)
from seed_quiz.services.game_ai import (
    calculate_base_points,
    evaluate_question_quality,
    fallback_quality_result,
)
from seed_quiz.services.game_scoring import calculate_solver_points, recalculate_game_scores
from seed_quiz.services.limits import game_evaluation_limit_exceeded
from seed_quiz.topics import TOPIC_LABELS

GAME_SESSION_KEYS = [
    "sqg_room_id",
    "sqg_player_id",
    "sqg_student_id",
]

REWARD_BY_RANK = {
    1: 5,
    2: 3,
    3: 2,
}


def generate_join_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.SystemRandom().choices(alphabet, k=length))
        if not SQGameRoom.objects.filter(join_code=code).exists():
            return code


def create_game_room(
    *,
    classroom,
    created_by,
    title: str,
    topic: str,
    grade: int,
    question_mode: str,
    questions_per_player: int,
    solve_target_count: int,
    create_time_seconds: int,
    solve_time_seconds: int,
    reward_enabled: bool,
) -> SQGameRoom:
    clean_title = str(title or "").strip() or f"{TOPIC_LABELS.get(topic, topic)} 실시간 게임"
    return SQGameRoom.objects.create(
        classroom=classroom,
        created_by=created_by,
        title=clean_title[:120],
        topic=topic,
        grade=grade,
        join_code=generate_join_code(),
        question_mode=question_mode,
        questions_per_player=max(1, int(questions_per_player or 1)),
        solve_target_count=max(1, int(solve_target_count or 1)),
        create_time_seconds=max(60, int(create_time_seconds or 300)),
        solve_time_seconds=max(60, int(solve_time_seconds or 300)),
        reward_enabled=bool(reward_enabled),
    )


def clear_game_session(request) -> None:
    for key in GAME_SESSION_KEYS:
        request.session.pop(key, None)


def set_game_session(request, room: SQGameRoom, player: SQGamePlayer) -> None:
    request.session["sqg_room_id"] = str(room.id)
    request.session["sqg_player_id"] = str(player.id)
    request.session["sqg_student_id"] = str(player.student_id)
    request.session.modified = True


@transaction.atomic
def join_game(*, room: SQGameRoom, student, nickname: str = "") -> SQGamePlayer:
    player, _ = SQGamePlayer.objects.select_for_update().get_or_create(
        game=room,
        student=student,
        defaults={
            "nickname": (nickname or student.name or "").strip()[:50] or "학생",
            "is_connected": True,
            "last_seen_at": timezone.now(),
        },
    )
    desired_nickname = (nickname or student.name or "").strip()[:50] or player.nickname
    updates = []
    if player.nickname != desired_nickname:
        player.nickname = desired_nickname
        updates.append("nickname")
    if not player.is_connected:
        player.is_connected = True
        updates.append("is_connected")
    player.last_seen_at = timezone.now()
    updates.append("last_seen_at")
    if updates:
        player.save(update_fields=updates + ["updated_at"])
    recalculate_game_scores(room)
    return player


def touch_player(player: SQGamePlayer) -> SQGamePlayer:
    player.is_connected = True
    player.last_seen_at = timezone.now()
    player.save(update_fields=["is_connected", "last_seen_at", "updated_at"])
    return player


def refresh_connection_states(room: SQGameRoom, *, stale_seconds: int = 30) -> None:
    cutoff = timezone.now() - timedelta(seconds=stale_seconds)
    room.players.filter(last_seen_at__lt=cutoff, is_connected=True).update(is_connected=False)


def phase_deadline(room: SQGameRoom):
    if not room.phase_started_at:
        return None
    if room.status == "creating":
        seconds = room.create_time_seconds
    elif room.status == "playing":
        seconds = room.solve_time_seconds
    else:
        return None
    return room.phase_started_at + timedelta(seconds=seconds)


def create_progress_count(player: SQGamePlayer) -> int:
    return player.authored_questions.exclude(status="rejected").count()


def create_slots_left(player: SQGamePlayer) -> int:
    return max(0, int(player.game.questions_per_player or 1) - create_progress_count(player))


def assigned_questions_for_player(player: SQGamePlayer) -> list[SQGameQuestion]:
    ready_questions = list(
        SQGameQuestion.objects.filter(
            game=player.game,
            status="ready",
        )
        .exclude(author=player)
        .select_related("author", "game")
        .order_by("created_at", "id")
    )
    rnd = random.Random(f"{player.game_id}:{player.id}")
    rnd.shuffle(ready_questions)
    target = int(player.game.solve_target_count or 0)
    if target <= 0:
        return ready_questions
    return ready_questions[:target]


def get_next_question_for_player(player: SQGamePlayer) -> SQGameQuestion | None:
    answered_ids = set(player.answers.values_list("question_id", flat=True))
    for question in assigned_questions_for_player(player):
        if question.id not in answered_ids:
            return question
    return None


def player_is_done_solving(player: SQGamePlayer) -> bool:
    return get_next_question_for_player(player) is None


def all_connected_players_done(room: SQGameRoom) -> bool:
    refresh_connection_states(room)
    players = list(room.players.select_related("student").all())
    if not players:
        return False
    candidates = [player for player in players if player.is_connected] or players
    return all(player_is_done_solving(player) for player in candidates)


@transaction.atomic
def advance_phase(room: SQGameRoom, *, to_status: str | None = None) -> SQGameRoom:
    room = SQGameRoom.objects.select_for_update().get(id=room.id)
    transitions = {
        "waiting": "creating",
        "creating": "playing",
        "playing": "finished",
        "finished": "finished",
    }
    next_status = to_status or transitions.get(room.status, "finished")

    if next_status == "playing":
        question_counts = room.questions.aggregate(
            ready=Count("id", filter=Q(status="ready")),
            pending=Count("id", filter=Q(status="pending_ai")),
            needs_review=Count("id", filter=Q(status="needs_review")),
        )
        if question_counts["pending"] > 0:
            raise ValueError("pending_ai_remaining")
        if question_counts["needs_review"] > 0:
            raise ValueError("needs_review_remaining")
        if question_counts["ready"] <= 0:
            raise ValueError("ready_questions_required")

    room.status = next_status
    room.phase_started_at = timezone.now()
    if next_status == "finished":
        room.finished_at = timezone.now()
    room.save(update_fields=["status", "phase_started_at", "finished_at", "updated_at"])

    recalculate_game_scores(room)
    if next_status == "finished":
        apply_rewards(room)
    return room


def _finalize_question(question: SQGameQuestion, quality_result: dict) -> SQGameQuestion:
    overall = int(quality_result.get("overall", 0) or 0)
    approved = bool(quality_result.get("approved", overall >= 40)) and overall >= 40
    needs_review = bool(quality_result.get("fallback_used")) or not approved
    base_points = 0 if needs_review else calculate_base_points(overall)
    feedback = str(quality_result.get("feedback") or "").strip()
    if needs_review and not feedback:
        feedback = "선생님 확인 후 사용할 수 있어요."
    question.ai_quality_score = overall
    question.ai_quality_json = quality_result
    question.ai_feedback = feedback[:255]
    question.base_points = base_points if approved else 0
    question.status = "needs_review" if needs_review else "ready"
    question.evaluated_at = timezone.now()
    question.save(
        update_fields=[
            "ai_quality_score",
            "ai_quality_json",
            "ai_feedback",
            "base_points",
            "status",
            "evaluated_at",
            "updated_at",
        ]
    )
    recalculate_game_scores(question.game)
    return question


def evaluate_pending_question(question: SQGameQuestion, *, retry_after_seconds: int = 20) -> SQGameQuestion:
    now = timezone.now()
    with transaction.atomic():
        question = SQGameQuestion.objects.select_for_update().select_related(
            "game__classroom__teacher",
            "game__created_by",
        ).get(id=question.id)
        if question.status != "pending_ai":
            return question
        if question.ai_started_at and question.ai_started_at > now - timedelta(seconds=retry_after_seconds):
            return question
        question.ai_started_at = now
        question.save(update_fields=["ai_started_at", "updated_at"])

    if game_evaluation_limit_exceeded(question):
        result = fallback_quality_result("AI 확인 한도를 넘어 선생님 확인으로 넘겼습니다.")
    else:
        try:
            result = evaluate_question_quality(
                question_text=question.question_text,
                answer_text=question.answer_text,
                question_type=question.question_type,
                topic=question.game.topic,
                grade=question.game.grade,
            )
        except Exception:
            result = fallback_quality_result()

    with transaction.atomic():
        question = SQGameQuestion.objects.select_for_update().select_related("game").get(id=question.id)
        if question.status != "pending_ai":
            return question
        return _finalize_question(question, result)


@transaction.atomic
def submit_question(
    *,
    player: SQGamePlayer,
    request_id,
    question_type: str,
    question_text: str,
    answer_text: str,
    choices: list[str],
    correct_index: int,
) -> tuple[SQGameQuestion, bool]:
    player = SQGamePlayer.objects.select_for_update().select_related("game").get(id=player.id)
    room = player.game
    try:
        request_uuid = request_id if isinstance(request_id, uuid.UUID) else uuid.UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("invalid_request_id") from exc

    existing = SQGameQuestion.objects.select_for_update().filter(request_id=request_uuid).first()
    if existing:
        if existing.author_id != player.id or existing.game_id != room.id:
            raise ValueError("request_conflict")
        return existing, False

    if room.status != "creating":
        raise ValueError("invalid_phase")
    if create_slots_left(player) <= 0:
        raise ValueError("no_slots_left")
    if correct_index < 0 or correct_index >= len(choices or []):
        raise ValueError("invalid_correct_index")

    question = SQGameQuestion.objects.create(
        game=room,
        author=player,
        request_id=request_uuid,
        question_type=question_type,
        question_text=question_text,
        answer_text=answer_text,
        choices=choices,
        correct_index=correct_index,
        status="pending_ai",
        submitted_at=timezone.now(),
    )
    return question, True


@transaction.atomic
def submit_answer(
    *,
    player: SQGamePlayer,
    question: SQGameQuestion,
    selected_index: int,
    time_taken_ms: int,
) -> SQGameAnswer:
    player = SQGamePlayer.objects.select_for_update().select_related("game").get(id=player.id)
    question = SQGameQuestion.objects.select_related("author", "game").get(id=question.id)
    existing = SQGameAnswer.objects.select_for_update().filter(question=question, player=player).first()
    if existing:
        return existing
    if question.author_id == player.id:
        raise ValueError("cannot_answer_own_question")
    if question.game_id != player.game_id or question.status != "ready":
        raise ValueError("invalid_question")
    if selected_index < 0 or selected_index >= len(question.choices or []):
        raise ValueError("invalid_choice")
    next_question = get_next_question_for_player(player)
    if not next_question or next_question.id != question.id:
        raise ValueError("not_assigned_question")
    points = calculate_solver_points(
        is_correct=question.correct_index == selected_index,
        time_taken_ms=time_taken_ms,
        time_limit_seconds=player.game.solve_time_seconds,
    )
    answer = SQGameAnswer.objects.create(
        question=question,
        player=player,
        selected_index=selected_index,
        is_correct=question.correct_index == selected_index,
        time_taken_ms=max(0, int(time_taken_ms or 0)),
        points_earned=points,
    )
    recalculate_game_scores(player.game)
    return answer


@transaction.atomic
def review_question(*, question: SQGameQuestion, action: str) -> SQGameQuestion:
    question = SQGameQuestion.objects.select_for_update().select_related("game").get(id=question.id)
    if question.status != "needs_review":
        return question

    clean_action = str(action or "").strip()
    if clean_action == "approve":
        question.status = "ready"
        question.base_points = 20
        if not question.ai_feedback:
            question.ai_feedback = "선생님이 확인하고 사용 가능으로 바꿨어요."
    elif clean_action == "reject":
        question.status = "rejected"
        question.base_points = 0
        if not question.ai_feedback:
            question.ai_feedback = "선생님이 게임에서 제외했어요."
    else:
        raise ValueError("invalid_review_action")

    question.evaluated_at = timezone.now()
    question.save(
        update_fields=[
            "status",
            "base_points",
            "ai_feedback",
            "evaluated_at",
            "updated_at",
        ]
    )
    recalculate_game_scores(question.game)
    return question


def calculate_rankings(room: SQGameRoom) -> list[SQGamePlayer]:
    return recalculate_game_scores(room)


def maybe_auto_advance_room(room: SQGameRoom) -> SQGameRoom:
    room.refresh_from_db()
    deadline = phase_deadline(room)
    if room.status == "playing":
        if (deadline and timezone.now() >= deadline) or all_connected_players_done(room):
            return advance_phase(room, to_status="finished")
    return room


@transaction.atomic
def apply_rewards(room: SQGameRoom) -> list[SQGameReward]:
    if not room.reward_enabled:
        return []

    rewards = []
    players = list(
        SQGamePlayer.objects.select_related("student")
        .filter(game=room)
        .order_by("rank", "joined_at")
    )
    for player in players:
        seed_amount = REWARD_BY_RANK.get(player.rank, 0)
        if seed_amount <= 0:
            continue
        reward, created = SQGameReward.objects.get_or_create(
            game=room,
            player=player,
            defaults={
                "rank": player.rank,
                "seed_amount": seed_amount,
                "request_id": uuid.uuid4(),
            },
        )
        if created:
            add_seeds(
                student=player.student,
                amount=seed_amount,
                reason="behavior",
                detail=f"[씨앗 퀴즈 게임] {player.rank}위 보상",
                request_id=reward.request_id,
            )
        elif reward.rank != player.rank or reward.seed_amount != seed_amount:
            reward.rank = player.rank
            reward.seed_amount = seed_amount
            reward.save(update_fields=["rank", "seed_amount"])
        rewards.append(reward)
    return rewards
