from django.conf import settings
from django.db import models


TARGET_LOW = "student_low"
TARGET_HIGH = "student_high"
TARGET_PARENT = "parent"

TARGET_CHOICES = [
    (TARGET_LOW, "저학년"),
    (TARGET_HIGH, "고학년"),
    (TARGET_PARENT, "학부모"),
]

TOPIC_ACTIVITY = "activity"
TOPIC_EVENT = "event"
TOPIC_SAFETY = "safety"
TOPIC_NOTICE = "notice"

TOPIC_CHOICES = [
    (TOPIC_ACTIVITY, "활동"),
    (TOPIC_EVENT, "행사"),
    (TOPIC_SAFETY, "안전"),
    (TOPIC_NOTICE, "알림장"),
]

TONE_FORMAL = "formal"
TONE_WARM = "warm"
TONE_CLEAR = "clear"

TONE_CHOICES = [
    (TONE_FORMAL, "정중"),
    (TONE_WARM, "다정"),
    (TONE_CLEAR, "명확"),
]


class NoticeGenerationCache(models.Model):
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    prompt_version = models.CharField(max_length=20, default="v1")
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, db_index=True)
    tone = models.CharField(max_length=20, choices=TONE_CHOICES, db_index=True)
    topic = models.CharField(max_length=20, choices=TOPIC_CHOICES, db_index=True)
    keywords_norm = models.TextField()
    context_norm = models.TextField(blank=True)
    signature = models.TextField(db_index=True)
    result_text = models.TextField()
    hit_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_used_at"]
        indexes = [
            models.Index(fields=["target", "topic", "tone"]),
            models.Index(fields=["prompt_version", "target", "topic", "tone"]),
        ]

    def __str__(self):
        return f"{self.get_target_display()} / {self.get_topic_display()}"


class NoticeGenerationAttempt(models.Model):
    STATUS_VALIDATION_FAIL = "validation_fail"
    STATUS_LIMIT_BLOCKED = "limit_blocked"
    STATUS_CACHE_HIT = "cache_hit"
    STATUS_LLM_REQUESTED = "llm_requested"
    STATUS_LLM_SUCCESS = "llm_success"
    STATUS_LLM_FAIL = "llm_fail"

    STATUS_CHOICES = [
        (STATUS_VALIDATION_FAIL, "Validation Fail"),
        (STATUS_LIMIT_BLOCKED, "Limit Blocked"),
        (STATUS_CACHE_HIT, "Cache Hit"),
        (STATUS_LLM_REQUESTED, "LLM Requested"),
        (STATUS_LLM_SUCCESS, "LLM Success"),
        (STATUS_LLM_FAIL, "LLM Fail"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="noticegen_attempts",
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, db_index=True)
    tone = models.CharField(max_length=20, choices=TONE_CHOICES, db_index=True)
    topic = models.CharField(max_length=20, choices=TOPIC_CHOICES, db_index=True)
    key_hash = models.CharField(max_length=64, blank=True, db_index=True)
    charged = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at", "charged"]),
            models.Index(fields=["session_key", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        principal = self.user.username if self.user_id else f"guest:{self.session_key}"
        return f"{principal} / {self.status}"

