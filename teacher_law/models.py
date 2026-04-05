from django.conf import settings
from django.db import models
from django.db.models import Q


class LegalChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_chat_sessions",
    )
    title = models.CharField(max_length=200, blank=True, default="새 법률 상담")
    is_active = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_message_at", "-updated_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_active=True),
                name="teacher_law_unique_active_session_per_user",
            ),
        ]

    def __str__(self):
        return f"teacher-law:{self.user_id}:{self.id}"


class LegalChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "사용자"
        ASSISTANT = "assistant", "AI"

    session = models.ForeignKey(
        LegalChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    body = models.TextField()
    payload_json = models.JSONField(default=dict, blank=True)
    normalized_question = models.CharField(max_length=500, blank=True, default="")
    is_quick_question = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"{self.session_id}:{self.role}:{self.id}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if not is_new:
            return

        update_fields = {"last_message_at": self.created_at}
        if self.role == self.Role.USER and self.body and (
            not self.session.title or self.session.title == "새 법률 상담"
        ):
            update_fields["title"] = self.body.strip()[:80]
        LegalChatSession.objects.filter(id=self.session_id).update(**update_fields)


class LegalCitation(models.Model):
    message = models.ForeignKey(
        LegalChatMessage,
        on_delete=models.CASCADE,
        related_name="citations",
    )
    law_name = models.CharField(max_length=255)
    law_id = models.CharField(max_length=32, blank=True, default="")
    mst = models.CharField(max_length=32, blank=True, default="")
    article_label = models.CharField(max_length=120, blank=True, default="")
    quote = models.TextField()
    source_url = models.URLField(blank=True, default="")
    fetched_at = models.DateTimeField()
    display_order = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        return f"{self.law_name} {self.article_label}".strip()


class LegalQueryAudit(models.Model):
    session = models.ForeignKey(
        LegalChatSession,
        on_delete=models.CASCADE,
        related_name="query_audits",
    )
    user_message = models.ForeignKey(
        LegalChatMessage,
        on_delete=models.SET_NULL,
        related_name="query_audits",
        null=True,
        blank=True,
    )
    assistant_message = models.ForeignKey(
        LegalChatMessage,
        on_delete=models.SET_NULL,
        related_name="response_audits",
        null=True,
        blank=True,
    )
    original_question = models.TextField()
    normalized_question = models.CharField(max_length=500, blank=True, default="")
    topic = models.CharField(max_length=60, blank=True, default="")
    scope_supported = models.BooleanField(default=True)
    risk_flags_json = models.JSONField(default=list, blank=True)
    candidate_queries_json = models.JSONField(default=list, blank=True)
    selected_laws_json = models.JSONField(default=list, blank=True)
    search_attempt_count = models.PositiveSmallIntegerField(default=0)
    search_result_count = models.PositiveSmallIntegerField(default=0)
    detail_fetch_count = models.PositiveSmallIntegerField(default=0)
    cache_hit = models.BooleanField(default=False)
    elapsed_ms = models.PositiveIntegerField(default=0)
    failure_reason = models.CharField(max_length=120, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.topic or 'unknown'}:{self.created_at:%Y-%m-%d %H:%M:%S}"
