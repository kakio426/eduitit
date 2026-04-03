import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def blob_upload_to(instance, filename):
    extension = os.path.splitext(str(filename or ""))[1].lower()
    return f"schoolcomm/blobs/{instance.checksum_sha256[:2]}/{instance.checksum_sha256}{extension}"


class SchoolWorkspace(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "운영 중"
        ARCHIVED = "archived", "보관"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    academic_year = models.CharField(max_length=16, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_school_workspaces",
    )
    archived_from_workspace = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_workspaces",
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "-created_at"]
        verbose_name = "학교 워크스페이스"
        verbose_name_plural = "학교 워크스페이스"

    def __str__(self):
        return self.name


class SchoolMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "소유자"
        ADMIN = "admin", "관리자"
        MEMBER = "member", "멤버"

    class Status(models.TextChoices):
        PENDING = "pending", "승인 대기"
        ACTIVE = "active", "활성"
        INACTIVE = "inactive", "비활성"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        SchoolWorkspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_school_membership_invites",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_school_memberships",
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace__name", "user__username"]
        unique_together = [("workspace", "user")]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["workspace", "status"]),
        ]
        verbose_name = "학교 멤버십"
        verbose_name_plural = "학교 멤버십"

    def __str__(self):
        return f"{self.workspace.name} - {self.user.username}"


class WorkspaceInvite(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        ACCEPTED = "accepted", "수락"
        EXPIRED = "expired", "만료"
        REVOKED = "revoked", "취소"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        SchoolWorkspace,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.EmailField(blank=True, default="")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="school_workspace_invites",
    )
    role = models.CharField(max_length=20, choices=SchoolMembership.Role.choices, default=SchoolMembership.Role.MEMBER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_school_workspace_invites",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "워크스페이스 초대"
        verbose_name_plural = "워크스페이스 초대"

    def __str__(self):
        return f"{self.workspace.name} 초대"


class CommunityRoom(models.Model):
    class RoomKind(models.TextChoices):
        NOTICE = "notice", "공지"
        SHARED = "shared", "자료공유"
        DM = "dm", "1:1 대화"
        GROUP_DM = "group_dm", "그룹 대화"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        SchoolWorkspace,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    name = models.CharField(max_length=120)
    room_kind = models.CharField(max_length=20, choices=RoomKind.choices)
    is_system_room = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_school_rooms",
    )
    participants_signature = models.CharField(max_length=255, blank=True, default="", db_index=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "name", "-created_at"]
        indexes = [
            models.Index(fields=["workspace", "room_kind"]),
            models.Index(fields=["workspace", "last_message_at"]),
        ]
        verbose_name = "커뮤니티 방"
        verbose_name_plural = "커뮤니티 방"

    def __str__(self):
        return f"{self.workspace.name} - {self.name}"

    def clean(self):
        super().clean()
        if self.room_kind == self.RoomKind.NOTICE and not self.is_system_room:
            raise ValidationError("공지방은 시스템 기본 방이어야 합니다.")


class RoomParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        CommunityRoom,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    membership = models.ForeignKey(
        SchoolMembership,
        on_delete=models.CASCADE,
        related_name="room_participations",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at", "membership__user__username"]
        unique_together = [("room", "membership")]
        verbose_name = "방 참여자"
        verbose_name_plural = "방 참여자"

    def __str__(self):
        return f"{self.room.name} - {self.membership.user.username}"


class RoomMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        CommunityRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="school_messages",
    )
    sender_membership = models.ForeignKey(
        SchoolMembership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_school_messages",
    )
    sender_name_snapshot = models.CharField(max_length=120, blank=True, default="")
    sender_membership_snapshot = models.CharField(max_length=40, blank=True, default="")
    parent_message = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField(blank=True, default="")
    reply_count = models.PositiveIntegerField(default=0)
    last_replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
            models.Index(fields=["parent_message", "created_at"]),
        ]
        verbose_name = "방 메시지"
        verbose_name_plural = "방 메시지"

    def __str__(self):
        return f"{self.room.name} - {self.sender_name_snapshot or '메시지'}"

    def clean(self):
        super().clean()
        if self.parent_message_id:
            if self.parent_message.room_id != self.room_id:
                raise ValidationError("답글은 같은 방 안에서만 작성할 수 있습니다.")
            if self.parent_message.parent_message_id:
                raise ValidationError("스레드는 한 단계까지만 허용됩니다.")


class UserRoomState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        CommunityRoom,
        on_delete=models.CASCADE,
        related_name="user_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_room_states",
    )
    last_read_message = models.ForeignKey(
        RoomMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    unread_count_cache = models.PositiveIntegerField(default=0)
    mute_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("room", "user")]
        indexes = [
            models.Index(fields=["user", "unread_count_cache"]),
        ]
        verbose_name = "방 읽음 상태"
        verbose_name_plural = "방 읽음 상태"

    def __str__(self):
        return f"{self.user.username} - {self.room.name}"


class MessageReaction(models.Model):
    class ReactionType(models.TextChoices):
        ACK = "ack", "확인"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        RoomMessage,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_message_reactions",
    )
    reaction_type = models.CharField(max_length=20, choices=ReactionType.choices, default=ReactionType.ACK)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("message", "user", "reaction_type")]
        verbose_name = "메시지 반응"
        verbose_name_plural = "메시지 반응"

    def __str__(self):
        return f"{self.message_id} - {self.user.username} - {self.reaction_type}"


class StoredAssetBlob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checksum_sha256 = models.CharField(max_length=64, unique=True)
    storage_key = models.CharField(max_length=255, unique=True)
    mime_type = models.CharField(max_length=120, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    file = models.FileField(upload_to=blob_upload_to, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "저장 파일 원본"
        verbose_name_plural = "저장 파일 원본"

    def __str__(self):
        return self.storage_key


class SharedAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blob = models.ForeignKey(
        StoredAssetBlob,
        on_delete=models.CASCADE,
        related_name="shared_assets",
    )
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_school_assets",
    )
    uploader_name_snapshot = models.CharField(max_length=120, blank=True, default="")
    original_name = models.CharField(max_length=255)
    file_extension = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["original_name"]),
            models.Index(fields=["file_extension"]),
        ]
        verbose_name = "공유 자료"
        verbose_name_plural = "공유 자료"

    def __str__(self):
        return self.original_name


class MessageAssetLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        RoomMessage,
        on_delete=models.CASCADE,
        related_name="asset_links",
    )
    asset = models.ForeignKey(
        SharedAsset,
        on_delete=models.CASCADE,
        related_name="message_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("message", "asset")]
        verbose_name = "메시지 자료 연결"
        verbose_name_plural = "메시지 자료 연결"

    def __str__(self):
        return f"{self.message_id} -> {self.asset_id}"


class UserAssetCategory(models.Model):
    class Category(models.TextChoices):
        UNCLASSIFIED = "unclassified", "미분류"
        LESSON = "lesson", "수업자료"
        ASSESSMENT = "assessment", "평가자료"
        WORK = "work", "업무"
        OTHER = "other", "기타"

    class Source(models.TextChoices):
        AUTO = "auto", "자동"
        MANUAL = "manual", "수동"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_asset_categories",
    )
    asset = models.ForeignKey(
        SharedAsset,
        on_delete=models.CASCADE,
        related_name="user_categories",
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.UNCLASSIFIED)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.AUTO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "asset")]
        indexes = [
            models.Index(fields=["user", "category"]),
        ]
        verbose_name = "사용자별 자료 분류"
        verbose_name_plural = "사용자별 자료 분류"

    def __str__(self):
        return f"{self.user.username} - {self.asset.original_name} - {self.category}"


class CalendarSuggestion(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "검토 대기"
        APPLIED = "applied", "적용 완료"
        DISMISSED = "dismissed", "숨김"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_calendar_suggestions",
    )
    source_message = models.ForeignKey(
        RoomMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_suggestions",
    )
    source_asset = models.ForeignKey(
        SharedAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_suggestions",
    )
    suggested_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
        ]
        verbose_name = "캘린더 추천"
        verbose_name_plural = "캘린더 추천"

    def __str__(self):
        title = str((self.suggested_payload or {}).get("title") or "추천 일정")
        return f"{self.user.username} - {title}"


class SharedCalendarEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        SchoolWorkspace,
        on_delete=models.CASCADE,
        related_name="shared_calendar_events",
    )
    title = models.CharField(max_length=200)
    note = models.TextField(blank=True, default="")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_all_day = models.BooleanField(default=False)
    color = models.CharField(max_length=20, blank=True, default="emerald")
    created_by_membership = models.ForeignKey(
        SchoolMembership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_shared_calendar_events",
    )
    updated_by_membership = models.ForeignKey(
        SchoolMembership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_shared_calendar_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time", "created_at", "id"]
        indexes = [
            models.Index(fields=["workspace", "start_time"]),
            models.Index(fields=["workspace", "end_time"]),
        ]
        verbose_name = "끼리끼리 공유 일정"
        verbose_name_plural = "끼리끼리 공유 일정"

    def __str__(self):
        return f"{self.workspace.name} - {self.title}"

    def clean(self):
        super().clean()
        if self.end_time < self.start_time:
            raise ValidationError("종료 시간이 시작 시간보다 빠를 수 없습니다.")


class SharedCalendarEventCopy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shared_event = models.ForeignKey(
        SharedCalendarEvent,
        on_delete=models.CASCADE,
        related_name="copies",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_shared_calendar_copies",
    )
    personal_event = models.ForeignKey(
        "classcalendar.CalendarEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schoolcomm_source_copies",
    )
    copied_at = models.DateTimeField(auto_now_add=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("shared_event", "user")]
        indexes = [
            models.Index(fields=["user", "copied_at"]),
        ]
        verbose_name = "끼리끼리 일정 개인 복사"
        verbose_name_plural = "끼리끼리 일정 개인 복사"

    def __str__(self):
        return f"{self.user.username} - {self.shared_event.title}"
