from __future__ import annotations

from django.conf import settings

from core.ai_usage_limits import consume_ai_usage_limit, consume_ai_usage_limits, user_usage_subject


def draft_generation_limit_exceeded(user) -> bool:
    return consume_ai_usage_limit(
        "seed_quiz:draft_generation:user",
        user_usage_subject(user),
        (
            (600, _int_setting("SEED_QUIZ_DRAFT_AI_BURST_LIMIT", 3)),
            (86400, _int_setting("SEED_QUIZ_DRAFT_AI_DAILY_LIMIT", 10)),
        ),
    )


def game_choice_limit_exceeded(player) -> bool:
    game = player.game
    return consume_ai_usage_limits(
        (
            (
                "seed_quiz:game_choice:player",
                f"player:{player.id}:{_timestamp_subject(player, 'joined_at')}",
                ((86400, _int_setting("SEED_QUIZ_GAME_CHOICE_PLAYER_DAILY_LIMIT", 3)),),
            ),
            (
                "seed_quiz:game_choice:room",
                f"room:{game.id}:{_timestamp_subject(game, 'created_at')}",
                (
                    (600, _int_setting("SEED_QUIZ_GAME_CHOICE_ROOM_BURST_LIMIT", 20)),
                    (86400, _int_setting("SEED_QUIZ_GAME_CHOICE_ROOM_DAILY_LIMIT", 60)),
                ),
            ),
            (
                "seed_quiz:game_choice:teacher",
                _game_teacher_subject(game),
                ((86400, _int_setting("SEED_QUIZ_GAME_CHOICE_TEACHER_DAILY_LIMIT", 150)),),
            ),
        )
    )


def game_evaluation_limit_exceeded(question) -> bool:
    game = question.game
    return consume_ai_usage_limits(
        (
            (
                "seed_quiz:game_evaluation:room",
                f"room:{game.id}:{_timestamp_subject(game, 'created_at')}",
                (
                    (600, _int_setting("SEED_QUIZ_GAME_EVALUATION_ROOM_BURST_LIMIT", 20)),
                    (86400, _int_setting("SEED_QUIZ_GAME_EVALUATION_ROOM_DAILY_LIMIT", 60)),
                ),
            ),
            (
                "seed_quiz:game_evaluation:teacher",
                _game_teacher_subject(game),
                ((86400, _int_setting("SEED_QUIZ_GAME_EVALUATION_TEACHER_DAILY_LIMIT", 150)),),
            ),
        )
    )


def _int_setting(name: str, default: int) -> int:
    try:
        return max(int(getattr(settings, name, default)), 0)
    except (TypeError, ValueError):
        return max(int(default), 0)


def _game_teacher_subject(game) -> str:
    created_by = getattr(game, "created_by", None)
    if created_by is not None:
        return user_usage_subject(created_by)
    created_by_id = getattr(game, "created_by_id", None)
    if created_by_id:
        return f"user:{created_by_id}"
    classroom = getattr(game, "classroom", None)
    teacher = getattr(classroom, "teacher", None)
    if teacher is not None:
        return user_usage_subject(teacher)
    teacher_id = getattr(classroom, "teacher_id", None)
    return f"user:{teacher_id or 'unknown'}"


def _timestamp_subject(instance, field_name: str) -> str:
    value = getattr(instance, field_name, None)
    return value.isoformat() if value else ""
