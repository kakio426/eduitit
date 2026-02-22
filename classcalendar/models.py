from django.db import models
from django.conf import settings
import uuid


class CalendarEvent(models.Model):
    SOURCE_LOCAL = "local"
    SOURCE_CHOICES = [
        (SOURCE_LOCAL, "로컬"),
    ]

    VISIBILITY_CLASS = "class_readonly"
    VISIBILITY_TEACHER = "teacher_only"
    VISIBILITY_CHOICES = [
        (VISIBILITY_CLASS, "학급 공유"),
        (VISIBILITY_TEACHER, "교사 전용"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    classroom = models.ForeignKey(
        'happy_seed.HSClassroom',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='calendar_events'
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_all_day = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_TEACHER,
    )

    # Reserved for source classification (currently local-only).
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_LOCAL)
    color = models.CharField(max_length=20, blank=True, null=True)
    integration_source = models.CharField(max_length=40, blank=True, default="")
    integration_key = models.CharField(max_length=255, blank=True, default="")
    is_locked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time", "id"]
        indexes = [
            models.Index(fields=["author", "start_time"]),
            models.Index(fields=["classroom", "start_time"]),
            models.Index(fields=["author", "integration_source"]),
            models.Index(fields=["author", "integration_source", "integration_key"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_time.date()})"


class EventPageBlock(models.Model):
    event = models.ForeignKey(CalendarEvent, on_delete=models.CASCADE, related_name='blocks')
    block_type = models.CharField(max_length=20)  # 'text', 'checklist', 'link', 'file'
    content = models.JSONField(default=dict)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.event.title} - {self.block_type} block"
