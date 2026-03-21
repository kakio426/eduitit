import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class QuickdropChannel(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quickdrop_channel",
    )
    slug = models.CharField(max_length=32, unique=True, db_index=True)
    title = models.CharField(max_length=80, default="바로전송")
    active_pair_nonce = models.CharField(max_length=64, blank=True)
    active_pair_issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.title} ({self.owner_id})"


class QuickdropDevice(models.Model):
    channel = models.ForeignKey(
        QuickdropChannel,
        on_delete=models.CASCADE,
        related_name="devices",
    )
    device_id = models.CharField(max_length=64)
    label = models.CharField(max_length=80)
    paired_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    user_agent_summary = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["paired_at"]
        unique_together = ("channel", "device_id")

    def __str__(self):
        return self.label or self.device_id

    @property
    def is_active(self):
        return self.revoked_at is None


class QuickdropSession(models.Model):
    STATUS_LIVE = "live"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_LIVE, "진행 중"),
        (STATUS_ENDED, "종료"),
    ]

    KIND_EMPTY = "empty"
    KIND_TEXT = "text"
    KIND_IMAGE = "image"
    KIND_CHOICES = [
        (KIND_EMPTY, "비어 있음"),
        (KIND_TEXT, "텍스트"),
        (KIND_IMAGE, "이미지"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        QuickdropChannel,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_LIVE)
    current_kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_EMPTY)
    current_text = models.TextField(blank=True)
    current_image = models.ImageField(upload_to="quickdrop/%Y/%m/", blank=True, null=True)
    current_mime_type = models.CharField(max_length=100, blank=True)
    current_filename = models.CharField(max_length=255, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel.slug}:{self.status}"

    @property
    def is_live(self):
        return self.status == self.STATUS_LIVE
