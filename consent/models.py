import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone


def _generate_access_token():
    return secrets.token_urlsafe(24)


def _generate_shared_lookup_token():
    return secrets.token_urlsafe(24)


def get_raw_storage():
    """Raw 파일은 Cloudinary 사용 시 Raw 스토리지를, 아니면 기본 스토리지를 사용."""
    if getattr(settings, "USE_CLOUDINARY", False):
        try:
            from cloudinary_storage.storage import RawMediaCloudinaryStorage

            return RawMediaCloudinaryStorage()
        except (ImportError, Exception):
            return default_storage
    return default_storage


def get_document_storage():
    """안내문 원본은 기본 스토리지를 사용."""
    return default_storage


class SignatureDocument(models.Model):
    FILE_TYPE_PDF = "pdf"
    FILE_TYPE_IMAGE = "image"
    FILE_TYPE_CHOICES = [
        (FILE_TYPE_PDF, "PDF"),
        (FILE_TYPE_IMAGE, "Image"),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent_documents",
    )
    title = models.CharField(max_length=200)
    original_file = models.FileField(
        upload_to="signatures/consent/originals/%Y/%m/%d",
        storage=get_document_storage,
        max_length=500,
    )
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "signatures_signaturedocument"

    def __str__(self):
        return f"{self.title} ({self.file_type})"


class SignatureRequest(models.Model):
    AUDIENCE_GUARDIAN = "guardian"
    AUDIENCE_GENERAL = "general"
    AUDIENCE_CHOICES = [
        (AUDIENCE_GUARDIAN, "학부모 확인형"),
        (AUDIENCE_GENERAL, "일반 서명형"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "작성중"),
        (STATUS_SENT, "발송됨"),
        (STATUS_COMPLETED, "완료"),
    ]
    LINK_EXPIRE_7 = 7
    LINK_EXPIRE_14 = 14
    LINK_EXPIRE_30 = 30
    LINK_EXPIRE_CHOICES = [
        (LINK_EXPIRE_7, "7일"),
        (LINK_EXPIRE_14, "14일"),
        (LINK_EXPIRE_30, "30일"),
    ]

    request_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent_requests",
    )
    document = models.ForeignKey(
        SignatureDocument,
        on_delete=models.CASCADE,
        related_name="requests",
    )
    title = models.CharField(max_length=200)
    document_name_snapshot = models.CharField(max_length=255, blank=True, default="")
    document_size_snapshot = models.PositiveBigIntegerField(blank=True, null=True)
    document_sha256_snapshot = models.CharField(max_length=64, blank=True, default="")
    message = models.TextField(blank=True)
    legal_notice = models.TextField(blank=True)
    consent_text_version = models.CharField(max_length=32, default="v1")
    audience_type = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default=AUDIENCE_GUARDIAN,
    )
    link_expire_days = models.PositiveSmallIntegerField(choices=LINK_EXPIRE_CHOICES, default=LINK_EXPIRE_14)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    shared_lookup_token = models.CharField(max_length=64, unique=True, default=_generate_shared_lookup_token)
    merged_pdf = models.FileField(
        upload_to="signatures/consent/merged/%Y/%m/%d",
        storage=get_raw_storage,
        max_length=500,
        blank=True,
        null=True,
    )
    shared_roster_group = models.ForeignKey(
        "handoff.HandoffRosterGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consent_requests",
        help_text="배부 체크 공유 명단과 연동 (선택)",
    )
    roster = models.ForeignKey(
        "ConsentRoster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    preview_checked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "signatures_signaturerequest"

    def __str__(self):
        return f"{self.title} ({self.request_id})"

    @property
    def link_expires_at(self):
        if not self.sent_at:
            return None
        return self.sent_at + timedelta(days=self.link_expire_days)

    @property
    def is_link_expired(self):
        expires_at = self.link_expires_at
        if not expires_at:
            return False
        return timezone.now() > expires_at

    @property
    def is_guardian_audience(self):
        return self.audience_type == self.AUDIENCE_GUARDIAN

    @property
    def audience_type_label(self):
        return dict(self.AUDIENCE_CHOICES).get(self.audience_type, self.audience_type)

    @property
    def allows_shared_lookup(self):
        return self.is_guardian_audience


class ConsentRoster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent_rosters",
    )
    audience_type = models.CharField(
        max_length=20,
        choices=SignatureRequest.AUDIENCE_CHOICES,
        default=SignatureRequest.AUDIENCE_GUARDIAN,
    )
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=200, blank=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_favorite", "name", "created_at"]
        db_table = "signatures_consentroster"
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "audience_type", "name"],
                name="consent_roster_owner_audience_name_unique",
            )
        ]

    def __str__(self):
        return f"{self.owner} - {self.name}"

    @property
    def is_guardian_audience(self):
        return self.audience_type == SignatureRequest.AUDIENCE_GUARDIAN


class ConsentRosterEntry(models.Model):
    roster = models.ForeignKey(
        ConsentRoster,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    student_name = models.CharField(max_length=100)
    parent_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        db_table = "signatures_consentrosterentry"
        constraints = [
            models.UniqueConstraint(
                fields=["roster", "student_name", "parent_name", "phone_number"],
                name="consent_roster_entry_unique",
            )
        ]

    def __str__(self):
        return f"{self.roster.name} - {self.student_name}"

    @property
    def phone_last4(self):
        digits = "".join(ch for ch in self.phone_number if ch.isdigit())
        return digits[-4:]

    def to_recipient_payload(self):
        return {
            "student_name": self.student_name,
            "parent_name": self.parent_name,
            "phone_number": self.phone_number,
        }


class SignaturePosition(models.Model):
    request = models.ForeignKey(
        SignatureRequest,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    page = models.PositiveIntegerField(default=1)
    x = models.FloatField(help_text="Points from left")
    y = models.FloatField(help_text="Points from bottom")
    width = models.FloatField(default=180)
    height = models.FloatField(default=70)
    x_ratio = models.FloatField(blank=True, null=True)
    y_ratio = models.FloatField(blank=True, null=True)
    w_ratio = models.FloatField(blank=True, null=True)
    h_ratio = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ["page", "id"]
        db_table = "signatures_signatureposition"


class SignatureRecipient(models.Model):
    IDENTITY_TOKEN_ONLY = "token_only"
    IDENTITY_PHONE_LAST4 = "phone_last4"
    IDENTITY_ASSURANCE_CHOICES = [
        (IDENTITY_TOKEN_ONLY, "링크 기반 제출"),
        (IDENTITY_PHONE_LAST4, "전화번호 끝 4자리 확인"),
    ]

    STATUS_PENDING = "pending"
    STATUS_VERIFIED = "verified"
    STATUS_SIGNED = "signed"
    STATUS_DECLINED = "declined"
    STATUS_CHOICES = [
        (STATUS_PENDING, "대기"),
        (STATUS_VERIFIED, "본인확인 완료"),
        (STATUS_SIGNED, "동의 제출"),
        (STATUS_DECLINED, "비동의 제출"),
    ]

    DECISION_AGREE = "agree"
    DECISION_DISAGREE = "disagree"
    DECISION_CHOICES = [
        (DECISION_AGREE, "동의"),
        (DECISION_DISAGREE, "비동의"),
    ]

    request = models.ForeignKey(
        SignatureRequest,
        on_delete=models.CASCADE,
        related_name="recipients",
    )
    student_name = models.CharField(max_length=100)
    parent_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    access_token = models.CharField(max_length=64, unique=True, default=_generate_access_token)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, blank=True)
    decline_reason = models.TextField(blank=True)
    signature_data = models.TextField(blank=True)
    signed_pdf = models.FileField(
        upload_to="signatures/consent/signed/%Y/%m/%d",
        storage=get_raw_storage,
        max_length=500,
        blank=True,
        null=True,
    )
    identity_assurance = models.CharField(
        max_length=20,
        choices=IDENTITY_ASSURANCE_CHOICES,
        default=IDENTITY_TOKEN_ONLY,
    )
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_ip_address = models.GenericIPAddressField(blank=True, null=True)
    verified_user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    signed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["student_name", "id"]
        unique_together = [("request", "student_name", "parent_name", "phone_number")]
        db_table = "signatures_signaturerecipient"

    def __str__(self):
        return f"{self.student_name} / {self.parent_name}"

    @property
    def phone_last4(self):
        digits = "".join(ch for ch in self.phone_number if ch.isdigit())
        return digits[-4:]

    @property
    def is_guardian_recipient(self):
        return self.request.is_guardian_audience

    @property
    def display_name(self):
        return self.student_name

    @property
    def secondary_name(self):
        return self.parent_name if self.is_guardian_recipient else ""


class ConsentAuditLog(models.Model):
    EVENT_LOOKUP_SUCCESS = "lookup_success"
    EVENT_LOOKUP_FAIL = "lookup_fail"
    EVENT_VERIFY_SUCCESS = "verify_success"
    EVENT_VERIFY_FAIL = "verify_fail"
    EVENT_SIGN_SUBMITTED = "sign_submitted"
    EVENT_LINK_CREATED = "link_created"
    EVENT_REQUEST_SENT = "request_sent"
    EVENT_DOCUMENT_VIEWED = "document_viewed"
    EVENT_CHOICES = [
        (EVENT_LOOKUP_SUCCESS, "Lookup Success"),
        (EVENT_LOOKUP_FAIL, "Lookup Fail"),
        (EVENT_VERIFY_SUCCESS, "Verify Success"),
        (EVENT_VERIFY_FAIL, "Verify Fail"),
        (EVENT_SIGN_SUBMITTED, "Sign Submitted"),
        (EVENT_LINK_CREATED, "Link Created"),
        (EVENT_REQUEST_SENT, "Request Sent"),
        (EVENT_DOCUMENT_VIEWED, "Document Viewed"),
    ]

    request = models.ForeignKey(
        SignatureRequest,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    recipient = models.ForeignKey(
        SignatureRecipient,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    event_meta = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "signatures_consentauditlog"
