import uuid
import re

from django.conf import settings
from django.db import models
from django.utils import timezone


class BambooStoryQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_public=True, is_hidden_by_report=False)


class BambooStory(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bamboo_stories",
    )
    anon_handle = models.CharField(max_length=20)
    title = models.CharField(max_length=100, default="이름 없는 숲의 우화")
    input_masked = models.TextField()
    fable_output = models.TextField()
    is_public = models.BooleanField(default=True)
    is_hidden_by_report = models.BooleanField(default=False)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BambooStoryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["-like_count", "-created_at"]),
            models.Index(fields=["-comment_count", "-created_at"]),
            models.Index(fields=["is_public", "is_hidden_by_report", "-created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.anon_handle} - {self.title}"

    @property
    def display_title(self):
        title = (self.title or "이름 없는 숲의 우화").strip()
        return f"〈{title.strip('〈〉<> ')}〉"

    @property
    def fable_body(self):
        return _strip_fable_title(self.fable_output)


class BambooLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bamboo_likes",
    )
    story = models.ForeignKey(BambooStory, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "story"], name="unique_bamboo_like"),
        ]
        indexes = [models.Index(fields=["story", "user"])]

    def __str__(self):
        return f"{self.user_id} likes {self.story_id}"


class BambooReport(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bamboo_reports",
    )
    story = models.ForeignKey(BambooStory, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_bamboo_reports",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "story"], name="unique_bamboo_report"),
        ]
        indexes = [models.Index(fields=["story", "-created_at"])]

    def __str__(self):
        return f"{self.user_id} reported {self.story_id}"


class BambooCommentQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_hidden_by_report=False)


class BambooComment(models.Model):
    story = models.ForeignKey(BambooStory, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bamboo_comments",
    )
    anon_handle = models.CharField(max_length=20)
    body_masked = models.TextField()
    is_hidden_by_report = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BambooCommentQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["story", "is_hidden_by_report", "created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.anon_handle} on {self.story_id}"


class BambooCommentReport(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bamboo_comment_reports",
    )
    comment = models.ForeignKey(BambooComment, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_bamboo_comment_reports",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "comment"], name="unique_bamboo_comment_report"),
        ]
        indexes = [models.Index(fields=["comment", "-created_at"])]

    def __str__(self):
        return f"{self.user_id} reported comment {self.comment_id}"


class BambooConsent(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bamboo_consent",
    )
    accepted_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user_id} accepted bamboo terms"


def _strip_fable_title(text: str) -> str:
    body = re.sub(r"^\s*##\s*제목\s*:\s*[^\n]+\n*", "", str(text or ""), count=1)
    return body.strip()
