import uuid

from django.conf import settings
from django.db import models


class MathGameSession(models.Model):
    GAME_NIM = "nim"
    GAME_TWENTY_FOUR = "24"
    GAME_2048 = "2048"
    GAME_CHOICES = [
        (GAME_NIM, "님"),
        (GAME_TWENTY_FOUR, "24 게임"),
        (GAME_2048, "2048"),
    ]

    DIFFICULTY_RANDOM = "random"
    DIFFICULTY_MCTS = "mcts"
    DIFFICULTY_MINIMAX = "minimax"
    DIFFICULTY_CHOICES = [
        (DIFFICULTY_RANDOM, "랜덤"),
        (DIFFICULTY_MCTS, "MCTS"),
        (DIFFICULTY_MINIMAX, "Minimax"),
    ]

    RESULT_ACTIVE = "active"
    RESULT_WIN = "win"
    RESULT_LOSE = "lose"
    RESULT_SOLVED = "solved"
    RESULT_GIVE_UP = "give_up"
    RESULT_CHOICES = [
        (RESULT_ACTIVE, "진행 중"),
        (RESULT_WIN, "승리"),
        (RESULT_LOSE, "패배"),
        (RESULT_SOLVED, "해결"),
        (RESULT_GIVE_UP, "포기"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="math_game_sessions",
    )
    session_key = models.CharField(max_length=80, blank=True, db_index=True)
    game_type = models.CharField(max_length=20, choices=GAME_CHOICES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, blank=True)
    state_json = models.JSONField(default=dict, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default=RESULT_ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["game_type", "result"]),
            models.Index(fields=["session_key", "game_type"]),
        ]

    def __str__(self):
        return f"{self.get_game_type_display()} {self.id}"


class MathGameMove(models.Model):
    ACTOR_STUDENT = "student"
    ACTOR_AI = "ai"
    ACTOR_SYSTEM = "system"
    ACTOR_CHOICES = [
        (ACTOR_STUDENT, "학생"),
        (ACTOR_AI, "AI"),
        (ACTOR_SYSTEM, "시스템"),
    ]

    session = models.ForeignKey(MathGameSession, on_delete=models.CASCADE, related_name="moves")
    actor = models.CharField(max_length=20, choices=ACTOR_CHOICES)
    move_json = models.JSONField(default=dict, blank=True)
    state_json = models.JSONField(default=dict, blank=True)
    is_valid = models.BooleanField(default=True)
    feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["session", "actor"]),
        ]

    def __str__(self):
        return f"{self.session_id} {self.actor}"
