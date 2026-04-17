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
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    source_file = models.FileField(upload_to=room_source_upload_to, storage=get_raw_storage)
    source_name = models.CharField(max_length=255)
    source_format = models.CharField(max_length=10, choices=SourceFormat.choices, default=SourceFormat.HWPX)
    source_sha256 = models.CharField(max_length=64)
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
    file = models.FileField(upload_to=revision_upload_to, storage=get_raw_storage)
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
