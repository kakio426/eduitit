import os
import uuid

from django.conf import settings
from django.db import models


def _safe_filename(filename):
    base = os.path.basename(str(filename or "").strip())
    return base or "document.pdf"


def source_pdf_upload_to(instance, filename):
    safe_name = _safe_filename(filename)
    return f"textbook_ai/source/{instance.owner_id}/{instance.id}/{safe_name}"


def parsed_json_upload_to(instance, filename):
    safe_name = _safe_filename(filename).rsplit(".", 1)[0] + ".json"
    return f"textbook_ai/parsed/{instance.document.owner_id}/{instance.document_id}/{safe_name}"


def parsed_markdown_upload_to(instance, filename):
    safe_name = _safe_filename(filename).rsplit(".", 1)[0] + ".md"
    return f"textbook_ai/parsed/{instance.document.owner_id}/{instance.document_id}/{safe_name}"


class TextbookDocument(models.Model):
    class Subject(models.TextChoices):
        KOREAN = "KOREAN", "국어"
        MATH = "MATH", "수학"
        SOCIAL = "SOCIAL", "사회"
        SCIENCE = "SCIENCE", "과학"
        ENGLISH = "ENGLISH", "영어"
        OTHER = "OTHER", "기타"

    class ParseStatus(models.TextChoices):
        QUEUED = "queued", "대기 중"
        PROCESSING = "processing", "읽는 중"
        READY = "ready", "준비 완료"
        NEEDS_REVIEW = "needs_review", "검토 필요"
        FAILED = "failed", "실패"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="textbook_ai_documents",
    )
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=20, choices=Subject.choices, default=Subject.OTHER)
    grade = models.CharField(max_length=50, blank=True, default="")
    unit_title = models.CharField(max_length=200, blank=True, default="")
    source_pdf = models.FileField(upload_to=source_pdf_upload_to)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    file_sha256 = models.CharField(max_length=64)
    file_size_bytes = models.PositiveBigIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    license_confirmed = models.BooleanField(default=False)
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.QUEUED,
    )
    parser_name = models.CharField(max_length=50, blank=True, default="")
    parser_mode = models.CharField(max_length=50, blank=True, default="")
    parser_version = models.CharField(max_length=50, blank=True, default="")
    parsed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "updated_at"]),
            models.Index(fields=["owner", "parse_status"]),
            models.Index(fields=["owner", "file_sha256"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "file_sha256"],
                name="textbook_ai_unique_owner_file_sha256",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_ready(self):
        return self.parse_status in {
            self.ParseStatus.READY,
            self.ParseStatus.NEEDS_REVIEW,
        }


class TextbookParseArtifact(models.Model):
    document = models.OneToOneField(
        TextbookDocument,
        on_delete=models.CASCADE,
        related_name="artifact",
    )
    parsed_json_file = models.FileField(upload_to=parsed_json_upload_to, blank=True)
    parsed_markdown_file = models.FileField(upload_to=parsed_markdown_upload_to, blank=True)
    parser_version = models.CharField(max_length=50, blank=True, default="")
    raw_metadata = models.JSONField(default=dict, blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    page_count = models.PositiveIntegerField(default=0)
    heading_count = models.PositiveIntegerField(default=0)
    table_count = models.PositiveIntegerField(default=0)
    image_count = models.PositiveIntegerField(default=0)
    text_char_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return f"{self.document.title} 산출물"


class TextbookChunk(models.Model):
    class ChunkType(models.TextChoices):
        HEADING = "heading", "제목"
        TEXT = "text", "본문"
        TABLE = "table", "표"

    document = models.ForeignKey(
        TextbookDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_type = models.CharField(
        max_length=20,
        choices=ChunkType.choices,
        default=ChunkType.TEXT,
    )
    heading_path = models.CharField(max_length=500, blank=True, default="")
    text = models.TextField()
    search_text = models.TextField(blank=True, default="")
    page_from = models.PositiveIntegerField(default=1)
    page_to = models.PositiveIntegerField(default=1)
    bbox_json = models.JSONField(default=list, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["document", "sort_order"]),
            models.Index(fields=["document", "page_from"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "sort_order"],
                name="textbook_ai_unique_document_sort_order",
            ),
        ]

    def __str__(self):
        return f"{self.document_id}:{self.sort_order}:{self.chunk_type}"
