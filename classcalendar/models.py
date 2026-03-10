from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
import uuid


def _default_idempotency_key():
    return uuid.uuid4().hex


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
        "happy_seed.HSClassroom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="calendar_events",
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


class CalendarIntegrationSetting(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_integration_setting",
    )
    collect_deadline_enabled = models.BooleanField(default=True)
    consent_expiry_enabled = models.BooleanField(default=True)
    reservation_enabled = models.BooleanField(default=True)
    signatures_training_enabled = models.BooleanField(default=True)
    share_enabled = models.BooleanField(default=False)
    share_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    retention_notice_event_seeded_at = models.DateTimeField(null=True, blank=True)
    retention_notice_banner_dismissed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "캘린더 연동 설정"
        verbose_name_plural = "캘린더 연동 설정"

    def __str__(self):
        return f"{self.user.username} 캘린더 연동 설정"


class CalendarCollaborator(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_collaborators",
    )
    collaborator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_calendars",
    )
    can_edit = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "캘린더 협업자"
        verbose_name_plural = "캘린더 협업자"
        unique_together = [("owner", "collaborator")]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(owner=models.F("collaborator")),
                name="calendar_collaborator_owner_not_self",
            )
        ]

    def clean(self):
        super().clean()
        if self.owner_id and self.owner_id == self.collaborator_id:
            raise ValidationError("본인을 협업자로 등록할 수 없습니다.")

    def __str__(self):
        permission = "편집" if self.can_edit else "읽기"
        return f"{self.owner.username} -> {self.collaborator.username} ({permission})"


class EventPageBlock(models.Model):
    event = models.ForeignKey(CalendarEvent, on_delete=models.CASCADE, related_name="blocks")
    block_type = models.CharField(max_length=20)
    content = models.JSONField(default=dict)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.event.title} - {self.block_type} block"


class CalendarTask(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    note = models.TextField(blank=True, default="")
    classroom = models.ForeignKey(
        "happy_seed.HSClassroom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="calendar_tasks",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_tasks",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    has_time = models.BooleanField(default=False)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    integration_source = models.CharField(max_length=40, blank=True, default="")
    integration_key = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_at", "created_at", "id"]
        indexes = [
            models.Index(fields=["author", "due_at"]),
            models.Index(fields=["author", "status", "due_at"]),
            models.Index(fields=["classroom", "due_at"]),
            models.Index(fields=["author", "integration_source"]),
            models.Index(fields=["author", "integration_source", "integration_key"]),
        ]

    def __str__(self):
        if self.due_at:
            return f"{self.title} ({self.due_at.date()})"
        return self.title


class CalendarMessageCapture(models.Model):
    class ParseStatus(models.TextChoices):
        PARSED = "parsed", "Parsed"
        NEEDS_REVIEW = "needs_review", "Needs Review"
        FAILED = "failed", "Failed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    class ItemType(models.TextChoices):
        EVENT = "event", "Event"
        TASK = "task", "Task"
        IGNORE = "ignore", "Ignore"
        UNKNOWN = "unknown", "Unknown"

    class ConfirmedItemType(models.TextChoices):
        EVENT = "event", "Event"
        TASK = "task", "Task"
        MANUAL_SKIP = "manual_skip", "Manual Skip"

    class DecisionSource(models.TextChoices):
        RULE = "rule", "Rule"
        RULE_ML = "rule_ml", "Rule + ML"
        MANUAL = "manual", "Manual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_message_captures",
    )
    raw_text = models.TextField(blank=True, default="")
    normalized_text = models.TextField(blank=True, default="")
    source_hint = models.CharField(max_length=30, blank=True, default="unknown")
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.NEEDS_REVIEW,
    )
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    predicted_item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.UNKNOWN,
    )
    confirmed_item_type = models.CharField(
        max_length=20,
        choices=ConfirmedItemType.choices,
        blank=True,
        default="",
    )
    decision_source = models.CharField(
        max_length=20,
        choices=DecisionSource.choices,
        default=DecisionSource.RULE,
    )
    extracted_title = models.CharField(max_length=200, blank=True, default="")
    extracted_start_time = models.DateTimeField(null=True, blank=True)
    extracted_end_time = models.DateTimeField(null=True, blank=True)
    extracted_is_all_day = models.BooleanField(default=False)
    extracted_priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        blank=True,
        default="",
    )
    extracted_todo_summary = models.TextField(blank=True, default="")
    parse_payload = models.JSONField(default=dict, blank=True)
    initial_extract_payload = models.JSONField(default=dict, blank=True)
    final_commit_payload = models.JSONField(default=dict, blank=True)
    edit_diff_payload = models.JSONField(default=dict, blank=True)
    rule_version = models.CharField(max_length=30, blank=True, default="")
    ml_scores = models.JSONField(default=dict, blank=True)
    llm_used = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=64, default=_default_idempotency_key)
    content_cache_key = models.CharField(max_length=64, blank=True, default="")
    committed_event = models.ForeignKey(
        CalendarEvent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="message_captures",
    )
    committed_task = models.ForeignKey(
        CalendarTask,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="message_captures",
    )
    committed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["author", "created_at"]),
            models.Index(fields=["author", "parse_status", "created_at"]),
            models.Index(fields=["author", "predicted_item_type", "created_at"]),
            models.Index(fields=["author", "content_cache_key"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["author", "idempotency_key"],
                name="calendar_message_capture_unique_idempotency_per_author",
            ),
        ]

    def __str__(self):
        return f"{self.author_id}:{self.parse_status}:{self.created_at}"


class CalendarMessageCaptureAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capture = models.ForeignKey(
        CalendarMessageCapture,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_message_capture_attachments",
    )
    file = models.FileField(upload_to="classcalendar/message_capture_attachments/%Y/%m/%d")
    original_name = models.CharField(max_length=255, blank=True, default="")
    mime_type = models.CharField(max_length=120, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    is_selected = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["capture", "created_at"]),
        ]

    def __str__(self):
        return f"{self.capture_id}:{self.original_name or self.id}"


class CalendarMessageCaptureCandidate(models.Model):
    class CandidateKind(models.TextChoices):
        EVENT = "event", "Event"
        DEADLINE = "deadline", "Deadline"
        PREP = "prep", "Prep"

    class CommitStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SAVED = "saved", "Saved"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capture = models.ForeignKey(
        CalendarMessageCapture,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    sort_order = models.PositiveIntegerField(default=0)
    candidate_kind = models.CharField(
        max_length=20,
        choices=CandidateKind.choices,
        default=CandidateKind.EVENT,
    )
    title = models.CharField(max_length=200, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_recommended = models.BooleanField(default=True)
    needs_check = models.BooleanField(default=False)
    evidence_text = models.TextField(blank=True, default="")
    evidence_payload = models.JSONField(default=dict, blank=True)
    committed_event = models.ForeignKey(
        CalendarEvent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="message_capture_candidates",
    )
    commit_status = models.CharField(
        max_length=20,
        choices=CommitStatus.choices,
        default=CommitStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["capture", "sort_order"]),
            models.Index(fields=["capture", "commit_status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["capture", "sort_order"],
                name="calendar_message_capture_candidate_unique_sort_order",
            ),
        ]

    def __str__(self):
        return f"{self.capture_id}:{self.sort_order}:{self.title or self.id}"


class CalendarEventAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        CalendarEvent,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_event_attachments",
    )
    source_capture_attachment = models.ForeignKey(
        CalendarMessageCaptureAttachment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_attachments",
    )
    file = models.FileField(upload_to="classcalendar/event_attachments/%Y/%m/%d")
    original_name = models.CharField(max_length=255, blank=True, default="")
    mime_type = models.CharField(max_length=120, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["event", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.event_id}:{self.original_name or self.id}"


class CalendarEventSyncTask(models.Model):
    class TargetType(models.TextChoices):
        SHEETBOOK_SCHEDULE = "sheetbook_schedule", "Sheetbook Schedule"

    class SyncStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        CalendarEvent,
        on_delete=models.CASCADE,
        related_name="sync_tasks",
    )
    target_type = models.CharField(
        max_length=30,
        choices=TargetType.choices,
        default=TargetType.SHEETBOOK_SCHEDULE,
    )
    status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    retry_count = models.PositiveIntegerField(default=0)
    target_ref = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["status", "updated_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "target_type"],
                name="calendar_event_sync_task_unique_event_target",
            ),
        ]

    def __str__(self):
        return f"{self.event_id}:{self.target_type}:{self.status}"
