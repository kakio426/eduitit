import uuid
from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def default_office_start():
    return time(hour=8, minute=0)


def default_office_end():
    return time(hour=18, minute=0)


class ParentContact(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_contacts",
    )
    student_name = models.CharField(max_length=80)
    student_grade = models.PositiveSmallIntegerField(null=True, blank=True)
    student_classroom = models.CharField(max_length=20, blank=True, default="")
    parent_name = models.CharField(max_length=80)
    relationship = models.CharField(max_length=30, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=30, blank=True, default="")
    emergency_access_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_name", "parent_name", "id"]
        indexes = [
            models.Index(fields=["teacher", "student_name"]),
            models.Index(fields=["teacher", "is_active"]),
        ]
        verbose_name = "학부모 연락처"
        verbose_name_plural = "학부모 연락처"

    def __str__(self):
        return f"{self.student_name} · {self.parent_name}"


class ParentCommunicationPolicy(models.Model):
    teacher = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_comm_policy",
    )
    max_parent_messages_per_thread = models.PositiveSmallIntegerField(default=3)
    max_open_threads_per_parent = models.PositiveSmallIntegerField(default=1)
    office_hours_start = models.TimeField(default=default_office_start)
    office_hours_end = models.TimeField(default=default_office_end)
    auto_escalate_on_critical = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "학부모 소통 정책"
        verbose_name_plural = "학부모 소통 정책"

    def clean(self):
        super().clean()
        if self.office_hours_start >= self.office_hours_end:
            raise ValidationError("업무시간 시작은 종료보다 빨라야 합니다.")

    def __str__(self):
        return f"{self.teacher.username} 소통 정책"


class ParentNotice(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_notices",
    )
    classroom_label = models.CharField(max_length=60, blank=True, default="")
    title = models.CharField(max_length=200)
    content = models.TextField()
    attachment = models.FileField(upload_to="parentcomm/notices/", null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-published_at", "-id"]
        indexes = [
            models.Index(fields=["teacher", "-published_at"]),
        ]
        verbose_name = "알림장"
        verbose_name_plural = "알림장"

    def __str__(self):
        return self.title


class ParentNoticeReceipt(models.Model):
    notice = models.ForeignKey(
        ParentNotice,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    parent_contact = models.ForeignKey(
        ParentContact,
        on_delete=models.CASCADE,
        related_name="notice_receipts",
    )
    delivered_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("notice", "parent_contact")]
        verbose_name = "알림장 수신 기록"
        verbose_name_plural = "알림장 수신 기록"

    def __str__(self):
        return f"{self.notice_id} -> {self.parent_contact_id}"

    @property
    def is_read(self):
        return self.read_at is not None


class ParentUrgentAlert(models.Model):
    class AlertType(models.TextChoices):
        LATE = "late", "지각"
        ABSENT = "absent", "결석"
        EARLY_LEAVE = "early_leave", "조퇴"
        OTHER = "other", "기타"

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_urgent_alerts",
    )
    parent_contact = models.ForeignKey(
        ParentContact,
        on_delete=models.CASCADE,
        related_name="urgent_alerts",
    )
    alert_type = models.CharField(max_length=20, choices=AlertType.choices, default=AlertType.OTHER)
    short_message = models.CharField(max_length=20)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_acknowledged", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["teacher", "is_acknowledged", "-created_at"]),
            models.Index(fields=["parent_contact", "-created_at"]),
        ]
        verbose_name = "학부모 긴급 안내"
        verbose_name_plural = "학부모 긴급 안내"

    def __str__(self):
        return f"{self.parent_contact.student_name} {self.get_alert_type_display()}"

    def clean(self):
        super().clean()
        value = (self.short_message or "").strip()
        if not value:
            raise ValidationError("긴급 안내 메시지를 입력해 주세요.")
        if len(value) > 20:
            raise ValidationError("긴급 안내 메시지는 20자 이내로 입력해 주세요.")

    def save(self, *args, **kwargs):
        self.short_message = (self.short_message or "").strip()
        super().save(*args, **kwargs)


class ConsultationMethod(models.TextChoices):
    CHAT = "chat", "채팅 상담"
    PHONE = "phone", "전화 상담"
    VISIT = "visit", "방문 상담"


class ParentThread(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "진행 중"
        WAITING_PARENT = "waiting_parent", "학부모 답변 대기"
        WAITING_TEACHER = "waiting_teacher", "교사 답변 대기"
        NEEDS_CONSULT = "needs_consult", "상담 전환 필요"
        CLOSED = "closed", "종료"

    class Severity(models.TextChoices):
        NORMAL = "normal", "일반"
        IMPORTANT = "important", "중요"
        CRITICAL = "critical", "긴급"

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_threads",
    )
    parent_contact = models.ForeignKey(
        ParentContact,
        on_delete=models.CASCADE,
        related_name="threads",
    )
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=50, default="기타")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.NORMAL)
    parent_message_limit = models.PositiveSmallIntegerField(default=3)
    parent_message_count = models.PositiveSmallIntegerField(default=0)
    teacher_message_count = models.PositiveSmallIntegerField(default=0)
    last_parent_message_at = models.DateTimeField(null=True, blank=True)
    last_teacher_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["teacher", "status"]),
            models.Index(fields=["parent_contact", "status"]),
            models.Index(fields=["teacher", "severity"]),
        ]
        verbose_name = "학부모 쪽지 대화"
        verbose_name_plural = "학부모 쪽지 대화"

    def __str__(self):
        return self.subject

    def should_force_consultation(self):
        return (
            self.severity == self.Severity.CRITICAL
            or self.parent_message_count > self.parent_message_limit
        )

    def apply_new_message(self, sender_role, *, at=None):
        timestamp = at or timezone.now()
        update_fields = ["updated_at"]

        if sender_role == ParentThreadMessage.SenderRole.PARENT:
            self.parent_message_count += 1
            self.last_parent_message_at = timestamp
            update_fields.extend(["parent_message_count", "last_parent_message_at"])
            self.status = (
                self.Status.NEEDS_CONSULT
                if self.should_force_consultation()
                else self.Status.WAITING_TEACHER
            )
            update_fields.append("status")
        elif sender_role == ParentThreadMessage.SenderRole.TEACHER:
            self.teacher_message_count += 1
            self.last_teacher_message_at = timestamp
            update_fields.extend(["teacher_message_count", "last_teacher_message_at"])
            if self.status != self.Status.CLOSED:
                self.status = self.Status.WAITING_PARENT
                update_fields.append("status")

        self.save(update_fields=update_fields)


class ParentThreadMessage(models.Model):
    class SenderRole(models.TextChoices):
        PARENT = "parent", "학부모"
        TEACHER = "teacher", "교사"
        SYSTEM = "system", "시스템"

    thread = models.ForeignKey(
        ParentThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender_role = models.CharField(max_length=20, choices=SenderRole.choices)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "학부모 쪽지 메시지"
        verbose_name_plural = "학부모 쪽지 메시지"

    def __str__(self):
        return f"{self.thread_id}:{self.sender_role}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self.thread.apply_new_message(self.sender_role, at=self.created_at)


class ConsultationRequest(models.Model):
    class RequestedBy(models.TextChoices):
        PARENT = "parent", "학부모 요청"
        TEACHER = "teacher", "교사 요청"
        SYSTEM = "system", "시스템 전환"

    class Status(models.TextChoices):
        REQUESTED = "requested", "요청됨"
        REVIEWING = "reviewing", "검토 중"
        PROPOSED = "proposed", "교사 제안 완료"
        AWAITING_PARENT = "awaiting_parent", "학부모 선택 대기"
        CONFIRMED = "confirmed", "일정 확정"
        DECLINED = "declined", "거절됨"
        COMPLETED = "completed", "완료"
        CANCELED = "canceled", "취소"

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consultation_requests",
    )
    parent_contact = models.ForeignKey(
        ParentContact,
        on_delete=models.CASCADE,
        related_name="consultation_requests",
    )
    thread = models.OneToOneField(
        ParentThread,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultation_request",
    )
    selected_slot = models.ForeignKey(
        "ConsultationSlot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="selected_requests",
    )
    requested_by = models.CharField(max_length=20, choices=RequestedBy.choices, default=RequestedBy.PARENT)
    reason = models.TextField()
    escalation_reason = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["teacher", "status"]),
            models.Index(fields=["parent_contact", "status"]),
        ]
        verbose_name = "상담 요청"
        verbose_name_plural = "상담 요청"

    def __str__(self):
        return f"{self.parent_contact.student_name} 상담 요청"

    def clean(self):
        super().clean()
        if self.selected_slot:
            proposal = self.selected_slot.proposal
            if proposal.consultation_request_id != self.id:
                raise ValidationError("선택한 상담 시간은 현재 상담 요청에 속하지 않습니다.")


class ConsultationProposal(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "제안됨"
        ACCEPTED = "accepted", "수락됨"
        DECLINED = "declined", "거절됨"
        CANCELED = "canceled", "취소됨"
        EXPIRED = "expired", "만료됨"

    consultation_request = models.ForeignKey(
        ConsultationRequest,
        on_delete=models.CASCADE,
        related_name="proposals",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consultation_proposals",
    )
    note = models.TextField(blank=True, default="")
    allowed_methods = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    proposed_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-proposed_at", "-id"]
        indexes = [
            models.Index(fields=["consultation_request", "status"]),
        ]
        verbose_name = "상담 제안"
        verbose_name_plural = "상담 제안"

    def __str__(self):
        return f"제안 #{self.id}"

    def clean(self):
        super().clean()
        methods = self.allowed_methods or []
        valid_methods = {choice for choice, _ in ConsultationMethod.choices}

        if not methods:
            raise ValidationError("상담 방식은 최소 1개 이상 선택해야 합니다.")
        if not all(method in valid_methods for method in methods):
            raise ValidationError("유효하지 않은 상담 방식이 포함되어 있습니다.")

    @property
    def allowed_method_labels(self):
        label_map = dict(ConsultationMethod.choices)
        return [label_map.get(method, method) for method in self.allowed_methods or []]


class ConsultationSlot(models.Model):
    proposal = models.ForeignKey(
        ConsultationProposal,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    method = models.CharField(max_length=20, choices=ConsultationMethod.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location_note = models.CharField(max_length=200, blank=True, default="")
    channel_hint = models.CharField(max_length=120, blank=True, default="")
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="parentcomm_slot_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["proposal", "starts_at"]),
            models.Index(fields=["method", "starts_at"]),
        ]
        verbose_name = "상담 제안 시간"
        verbose_name_plural = "상담 제안 시간"

    def __str__(self):
        return f"{self.get_method_display()} {self.starts_at:%Y-%m-%d %H:%M}"

    def clean(self):
        super().clean()
        allowed_methods = self.proposal.allowed_methods or []
        if self.method not in allowed_methods:
            raise ValidationError("선택한 시간의 상담 방식이 제안 가능한 방식 목록에 없습니다.")
