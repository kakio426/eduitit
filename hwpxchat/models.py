import uuid

from django.conf import settings
from django.db import models


class HwpxDocument(models.Model):
    class StructureStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FALLBACK = "fallback", "Fallback"
        TOO_LARGE = "too_large", "Too Large"
        LIMIT_BLOCKED = "limit_blocked", "Limit Blocked"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hwpx_documents",
    )
    source_file = models.FileField(upload_to="hwpxchat/%Y/%m/%d")
    original_name = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64)
    document_title = models.CharField(max_length=200, blank=True, default="")
    raw_markdown = models.TextField(blank=True, default="")
    summary_text = models.CharField(max_length=255, blank=True, default="")
    parse_payload = models.JSONField(default=dict, blank=True)
    provider = models.CharField(max_length=30, blank=True, default="deepseek")
    structure_status = models.CharField(
        max_length=20,
        choices=StructureStatus.choices,
        default=StructureStatus.PENDING,
    )
    pipeline_version = models.CharField(max_length=30, default="workitem-v1")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["owner", "file_sha256", "pipeline_version"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "file_sha256", "pipeline_version"],
                name="hwpx_document_unique_owner_hash_pipeline",
            ),
        ]

    def __str__(self):
        return f"{self.document_title or self.original_name} ({self.owner_id})"


class HwpxWorkItem(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        SKIPPED = "skipped", "Skipped"
        SAVED = "saved", "Saved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        HwpxDocument,
        on_delete=models.CASCADE,
        related_name="work_items",
    )
    sort_order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    action_text = models.TextField(blank=True, default="")
    due_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    assignee_text = models.CharField(max_length=120, blank=True, default="")
    target_text = models.CharField(max_length=200, blank=True, default="")
    materials_text = models.TextField(blank=True, default="")
    delivery_required = models.BooleanField(default=False)
    evidence_text = models.TextField(blank=True, default="")
    evidence_refs_json = models.JSONField(default=list, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "created_at", "id"]
        indexes = [
            models.Index(fields=["document", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.document_id}:{self.title}"


class HwpxDocumentQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        HwpxDocument,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question = models.TextField()
    normalized_question = models.CharField(max_length=300)
    answer = models.TextField(blank=True, default="")
    citations_json = models.JSONField(default=list, blank=True)
    has_insufficient_evidence = models.BooleanField(default=False)
    provider = models.CharField(max_length=30, blank=True, default="deepseek")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["document", "normalized_question", "provider"]),
        ]

    def __str__(self):
        return f"{self.document_id}:{self.normalized_question[:40]}"
