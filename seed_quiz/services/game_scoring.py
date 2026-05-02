from django.db import transaction
from django.db.models import Count, Q

from seed_quiz.models import SQGameAnswer, SQGamePlayer, SQGameQuestion, SQGameRoom

CREATOR_CORRECT_BONUS = 10
SOLVER_CORRECT_BASE = 100
SOLVER_BONUS_MAX = 50


def calculate_solver_points(*, is_correct: bool, time_taken_ms: int, time_limit_seconds: int) -> int:
    if not is_correct:
        return 0
    limit_ms = max(1, int(time_limit_seconds or 1) * 1000)
    clamped = min(max(0, int(time_taken_ms or 0)), limit_ms)
    bonus = round(SOLVER_BONUS_MAX * (1 - (clamped / limit_ms)))
    return SOLVER_CORRECT_BASE + max(0, bonus)


def creator_stats(player: SQGamePlayer) -> dict:
    questions = list(
        SQGameQuestion.objects.filter(game=player.game, author=player, status="ready")
        .annotate(
            answer_count=Count("answers", distinct=True),
            correct_count=Count("answers", filter=Q(answers__is_correct=True), distinct=True),
        )
        .order_by("created_at", "id")
    )
    total_answer_count = sum(question.answer_count for question in questions)
    total_correct_count = sum(question.correct_count for question in questions)
    hardest_question = None
    for question in questions:
        if question.answer_count <= 0:
            continue
        question.correct_rate = round((question.correct_count / question.answer_count) * 100)
        if hardest_question is None or question.correct_rate < hardest_question.correct_rate:
            hardest_question = question

    correct_rate = round((total_correct_count / total_answer_count) * 100) if total_answer_count else 0
    return {
        "question_count": len(questions),
        "answer_count": total_answer_count,
        "correct_count": total_correct_count,
        "correct_rate": correct_rate,
        "bonus_score": total_correct_count * CREATOR_CORRECT_BONUS,
        "hardest_question": hardest_question,
    }


@transaction.atomic
def recalculate_game_scores(game: SQGameRoom) -> list[SQGamePlayer]:
    players = list(
        SQGamePlayer.objects.select_for_update()
        .filter(game=game)
        .select_related("student")
        .order_by("joined_at", "student__number", "nickname")
    )
    answers = list(
        SQGameAnswer.objects.filter(question__game=game)
        .select_related("player", "question__author")
        .order_by("answered_at")
    )

    created_scores = {player.id: 0 for player in players}
    solve_scores = {player.id: 0 for player in players}

    for player in players:
        question_rows = player.authored_questions.filter(status="ready")
        created_scores[player.id] = sum(
            int(question.base_points or 0) + question.answers.filter(is_correct=True).count() * CREATOR_CORRECT_BONUS
            for question in question_rows
        )

    for answer in answers:
        solve_scores[answer.player_id] = solve_scores.get(answer.player_id, 0) + int(answer.points_earned or 0)

    ordered = sorted(
        players,
        key=lambda player: (
            -(created_scores.get(player.id, 0) + solve_scores.get(player.id, 0)),
            -solve_scores.get(player.id, 0),
            -created_scores.get(player.id, 0),
            player.joined_at,
            player.nickname,
        ),
    )

    for rank, player in enumerate(ordered, start=1):
        player.create_score = created_scores.get(player.id, 0)
        player.solve_score = solve_scores.get(player.id, 0)
        player.rank = rank
        player.save(update_fields=["create_score", "solve_score", "rank", "updated_at"])

    return ordered
