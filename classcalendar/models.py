from django.db import models
from django.conf import settings
import uuid


class CalendarEvent(models.Model):
    SOURCE_LOCAL = "local"
    SOURCE_GOOGLE = "google"
    SOURCE_CHOICES = [
        (SOURCE_LOCAL, "로컬"),
        (SOURCE_GOOGLE, "구글"),
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
        default=VISIBILITY_CLASS,
    )

    # external sync
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_LOCAL)
    color = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time", "id"]
        indexes = [
            models.Index(fields=["author", "start_time"]),
            models.Index(fields=["classroom", "start_time"]),
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


class GoogleAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_google_account',
    )
    email = models.EmailField(blank=True, null=True)
    credentials = models.JSONField(default=dict, help_text="OAuth2 credentials dict")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Google Calendar Auth"


class GoogleSyncState(models.Model):
    account = models.ForeignKey(
        GoogleAccount,
        on_delete=models.CASCADE,
        related_name='sync_states',
    )
    google_calendar_id = models.CharField(max_length=255, default='primary')
    sync_token = models.TextField(blank=True, null=True, help_text="Token for incremental sync")
    last_sync = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "google_calendar_id"],
                name="uniq_google_sync_state_per_calendar",
            )
        ]
        indexes = [
            models.Index(fields=["account", "last_sync"]),
        ]

    def __str__(self):
        return f"Sync state for {self.account.user.username} ({self.google_calendar_id})"


class EventExternalMap(models.Model):
    account = models.ForeignKey(
        GoogleAccount,
        on_delete=models.CASCADE,
        related_name='event_maps',
        null=True,
        blank=True,
    )
    event = models.ForeignKey(CalendarEvent, on_delete=models.CASCADE, related_name='external_maps')
    google_calendar_id = models.CharField(max_length=255, default='primary')
    google_event_id = models.CharField(max_length=255)
    etag = models.CharField(max_length=255, blank=True, null=True, help_text="ETag for conflict resolution")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "google_calendar_id", "google_event_id"],
                name="uniq_google_event_map",
            ),
            models.UniqueConstraint(
                fields=["event", "account", "google_calendar_id"],
                name="uniq_event_calendar_map",
            ),
        ]

    def __str__(self):
        return f"Map: {self.event.id} -> {self.google_event_id}"
