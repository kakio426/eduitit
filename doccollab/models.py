import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from version_manager.models import get_raw_storage


def _dated_upload_path(prefix, filename):
    today = timezone.localdate()
    extension = os.path.splitext(str(filename or ""))[1].lower() or ".bin"
    stem = os.path.splitext(os.path.basename(str(filename or "document")))[0][:80] or "document"
    return f"doccollab/{prefix}/{today:%Y/%m/%d}/{stem}{extension}"


def room_source_upload_to(instance, filename):
    return _dated_upload_path("rooms", filename)


def revision_upload_to(instance, filename):
    return _dated_upload_path("revisions", filename)


class DocWorkspace(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "운영 중"
        ARCHIVED = "archived", "보관"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_doc_workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "-updated_at"]
        indexes = [
            models.Index(fields=["created_by", "status"]),
        ]

    def __str__(self):
        return self.name


class DocMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "소유자"
        EDITOR = "editor", "편집"
        VIEWER = "viewer", "보기"

    class Status(models.TextChoices):
        ACTIVE = "active", "활성"
        DISABLED = "disabled", "비활성"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        DocWorkspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doc_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_doc_memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace__name", "user__username"]
        unique_together = [("workspace", "user")]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return f"{self.workspace.name} - {self.user.username}"


class DocRoom(models.Model):
    class OriginKind(models.TextChoices):
        UPLOAD = "upload", "업로드"
        GENERATED_WORKSHEET = "generated_worksheet", "학습지 생성"
        AI_DRAFT = "ai_draft", "AI 초안"

    class SourceFormat(models.TextChoices):
        HWP = "hwp", "HWP"
        HWPX = "hwpx", "HWPX"

    class Status(models.TextChoices):
        ACTIVE = "active", "편집 중"
        ARCHIVED = "archived", "보관"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        DocWorkspace,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    title = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_doc_rooms",
    )
    mirrored_document = models.OneToOneField(
        "version_manager.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doccollab_room",
    )
    origin_kind = models.CharField(max_length=30, choices=OriginKind.choices, default=OriginKind.UPLOAD)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    source_file = models.FileField(
        upload_to=room_source_upload_to,
        storage=get_raw_storage,
        max_length=500,
        null=True,
        blank=True,
    )
    source_name = models.CharField(max_length=255, blank=True, default="")
    source_format = models.CharField(max_length=10, choices=SourceFormat.choices, default=SourceFormat.HWPX)
    source_sha256 = models.CharField(max_length=64, blank=True, default="")
    last_activity_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at", "-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["created_by", "status"]),
        ]

    def __str__(self):
        return self.title


class DocWorksheet(models.Model):
    class BootstrapStatus(models.TextChoices):
        PENDING = "pending", "대기"
        BUILDING = "building", "생성 중"
        READY = "ready", "준비 완료"
        FAILED = "failed", "실패"

    room = models.OneToOneField(
        DocRoom,
        on_delete=models.CASCADE,
        related_name="worksheet",
    )
    source_worksheet = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloned_worksheets",
    )
    topic = models.CharField(max_length=120)
    summary_text = models.CharField(max_length=200, blank=True, default="")
    content_json = models.JSONField(default=dict, blank=True)
    search_text = models.TextField(blank=True, default="")
    provider = models.CharField(max_length=30, blank=True, default="deepseek")
    prompt_version = models.CharField(max_length=40, blank=True, default="")
    latest_page_count = models.PositiveIntegerField(default=0)
    bootstrap_status = models.CharField(
        max_length=20,
        choices=BootstrapStatus.choices,
        default=BootstrapStatus.PENDING,
    )
    is_library_published = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["bootstrap_status", "is_library_published"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.room.title


class DocGeneratedDraft(models.Model):
    class DocumentType(models.TextChoices):
        NOTICE = "notice", "안내문"
        HOME_LETTER = "home_letter", "가정통신문"
        PLAN = "plan", "계획안"
        MINUTES = "minutes", "회의록"
        REPORT = "report", "보고서"
        FREEFORM = "freeform", "자유 문서"

    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        BUILDING = "building", "생성 중"
        READY = "ready", "준비 완료"
        FAILED = "failed", "실패"

    room = models.OneToOneField(
        DocRoom,
        on_delete=models.CASCADE,
        related_name="generated_draft",
    )
    document_type = models.CharField(max_length=30, choices=DocumentType.choices, default=DocumentType.FREEFORM)
    request_text = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    content_json = models.JSONField(default=dict, blank=True)
    summary_text = models.CharField(max_length=200, blank=True, default="")
    error_message = models.CharField(max_length=200, blank=True, default="")
    provider = models.CharField(max_length=40, blank=True, default="deepseek")
    prompt_version = models.CharField(max_length=40, blank=True, default="")
    latest_page_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "document_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.room.title


class DocAnalysis(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "정리 중"
        READY = "ready", "정리 완료"
        FAILED = "failed", "정리 실패"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        DocRoom,
        on_delete=models.CASCADE,
        related_name="analyses",
    )
    source_revision = models.ForeignKey(
        "DocRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analyses",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    engine = models.CharField(max_length=40, blank=True, default="")
    raw_markdown = models.TextField(blank=True, default="")
    parse_payload = models.JSONField(default=dict, blank=True)
    summary_text = models.CharField(max_length=200, blank=True, default="")
    error_message = models.CharField(max_length=200, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_doc_analyses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["room", "source_revision"], name="uniq_doc_analysis_room_revision"),
        ]
        indexes = [
            models.Index(fields=["room", "status"]),
            models.Index(fields=["source_revision", "status"]),
        ]

    def __str__(self):
        return f"{self.room.title} - {self.get_status_display()}"


class DocAssistantQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(
        DocAnalysis,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_doc_assistant_questions",
    )
    question = models.CharField(max_length=300)
    normalized_question = models.CharField(max_length=300)
    answer = models.TextField(blank=True, default="")
    citations_json = models.JSONField(default=list, blank=True)
    has_insufficient_evidence = models.BooleanField(default=False)
    provider = models.CharField(max_length=40, blank=True, default="doccollab-local-v1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("analysis", "normalized_question", "provider")]
        indexes = [
            models.Index(fields=["analysis", "created_at"]),
        ]

    def __str__(self):
        return self.question


class DocRevision(models.Model):
    class ExportFormat(models.TextChoices):
        SOURCE_HWP = "source_hwp", "원본 HWP"
        SOURCE_HWPX = "source_hwpx", "원본 HWPX"
        HWP_EXPORT = "hwp_export", "협업 저장본 HWP"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        DocRoom,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    file = models.FileField(upload_to=revision_upload_to, storage=get_raw_storage, max_length=500)
    original_name = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64)
    export_format = models.CharField(max_length=20, choices=ExportFormat.choices, default=ExportFormat.HWP_EXPORT)
    note = models.CharField(max_length=200, blank=True, default="")
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_doc_revisions",
    )
    mirrored_version = models.ForeignKey(
        "version_manager.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doccollab_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision_number", "-created_at"]
        unique_together = [("room", "revision_number")]
        indexes = [
            models.Index(fields=["room", "created_at"]),
        ]

    @property
    def ui_export_format_label(self):
        if self.export_format == self.ExportFormat.SOURCE_HWP:
            return "원본 HWP"
        if self.export_format == self.ExportFormat.SOURCE_HWPX:
            return "원본 HWPX"
        return "저장본 HWP"

    def __str__(self):
        return f"{self.room.title} r{self.revision_number}"


class DocSnapshot(models.Model):
    class SnapshotKind(models.TextChoices):
        AUTO = "auto", "자동"
        MANUAL = "manual", "수동"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        DocRoom,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    revision = models.ForeignKey(
        DocRevision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
    )
    snapshot_kind = models.CharField(max_length=20, choices=SnapshotKind.choices, default=SnapshotKind.AUTO)
    command_count = models.PositiveIntegerField(default=0)
    state_json = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_doc_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
        ]


class DocEditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        DocRoom,
        on_delete=models.CASCADE,
        related_name="edit_events",
    )
    base_revision = models.ForeignKey(
        DocRevision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="edit_events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doc_edit_events",
    )
    command_id = models.CharField(max_length=80, blank=True, default="")
    command_type = models.CharField(max_length=40)
    display_name = models.CharField(max_length=80, blank=True, default="")
    summary = models.CharField(max_length=200)
    command_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
            models.Index(fields=["room", "command_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.room.title} - {self.summary}"


class DocPresence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        DocRoom,
        on_delete=models.CASCADE,
        related_name="presences",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="doc_presences",
    )
    session_key = models.CharField(max_length=80)
    display_name = models.CharField(max_length=80, blank=True, default="")
    role = models.CharField(max_length=20, choices=DocMembership.Role.choices, default=DocMembership.Role.VIEWER)
    is_connected = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "-updated_at"]
        unique_together = [("room", "session_key")]
        indexes = [
            models.Index(fields=["room", "is_connected"]),
        ]

    def __str__(self):
        return f"{self.room_id}:{self.display_name or self.session_key}"
