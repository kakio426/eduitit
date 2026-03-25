from django.conf import settings
from django.db import models


DEVELOPER_CHAT_SENDER_ROLE_CHOICES = (
    ("user", "사용자"),
    ("admin", "관리자"),
)


def _build_message_preview(text, *, limit=200):
    normalized = " ".join(str(text or "").strip().split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}…"


class DeveloperChatThread(models.Model):
    participant = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="developer_chat_thread",
    )
    assigned_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_developer_chat_threads",
        null=True,
        blank=True,
    )
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_message_preview = models.CharField(max_length=200, blank=True)
    last_message_sender_role = models.CharField(
        max_length=16,
        choices=DEVELOPER_CHAT_SENDER_ROLE_CHOICES,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_message_at", "-updated_at", "-id")

    def __str__(self):
        return f"developer-chat:{self.participant_id}"


class DeveloperChatMessage(models.Model):
    class SenderRole(models.TextChoices):
        USER = "user", "사용자"
        ADMIN = "admin", "관리자"

    thread = models.ForeignKey(
        DeveloperChatThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="developer_chat_messages",
    )
    sender_role = models.CharField(max_length=16, choices=SenderRole.choices)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"{self.thread_id}:{self.sender_role}:{self.sender_id}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if not is_new:
            return

        update_kwargs = {
            "last_message_at": self.created_at,
            "last_message_preview": _build_message_preview(self.body),
            "last_message_sender_role": self.sender_role,
        }
        if self.sender_role == self.SenderRole.ADMIN:
            update_kwargs["assigned_admin"] = self.sender
        DeveloperChatThread.objects.filter(id=self.thread_id).update(**update_kwargs)


class DeveloperChatReadState(models.Model):
    thread = models.ForeignKey(
        DeveloperChatThread,
        on_delete=models.CASCADE,
        related_name="read_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="developer_chat_read_states",
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("thread", "user")
        ordering = ("thread_id", "user_id")

    def __str__(self):
        return f"{self.thread_id}:{self.user_id}"
