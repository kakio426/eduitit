from django.db import transaction

from seed_quiz.models import SQGameAnswer, SQGamePlayer, SQGameRoom

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
