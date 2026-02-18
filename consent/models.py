import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def _generate_access_token():
    return secrets.token_urlsafe(24)


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
    original_file = models.FileField(upload_to="signatures/consent/originals/%Y/%m/%d")
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "signatures_signaturedocument"

    def __str__(self):
        return f"{self.title} ({self.file_type})"


class SignatureRequest(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_COMPLETED, "Completed"),
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
    message = models.TextField(blank=True)
    legal_notice = models.TextField(blank=True)
    consent_text_version = models.CharField(max_length=32, default="v1")
    link_expire_days = models.PositiveSmallIntegerField(choices=LINK_EXPIRE_CHOICES, default=LINK_EXPIRE_14)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    merged_pdf = models.FileField(
        upload_to="signatures/consent/merged/%Y/%m/%d",
        blank=True,
        null=True,
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
    STATUS_PENDING = "pending"
    STATUS_VERIFIED = "verified"
    STATUS_SIGNED = "signed"
    STATUS_DECLINED = "declined"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_SIGNED, "Signed"),
        (STATUS_DECLINED, "Declined"),
    ]

    DECISION_AGREE = "agree"
    DECISION_DISAGREE = "disagree"
    DECISION_CHOICES = [
        (DECISION_AGREE, "Agree"),
        (DECISION_DISAGREE, "Disagree"),
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
        blank=True,
        null=True,
    )
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


class ConsentAuditLog(models.Model):
    EVENT_VERIFY_SUCCESS = "verify_success"
    EVENT_VERIFY_FAIL = "verify_fail"
    EVENT_SIGN_SUBMITTED = "sign_submitted"
    EVENT_LINK_CREATED = "link_created"
    EVENT_REQUEST_SENT = "request_sent"
    EVENT_CHOICES = [
        (EVENT_VERIFY_SUCCESS, "Verify Success"),
        (EVENT_VERIFY_FAIL, "Verify Fail"),
        (EVENT_SIGN_SUBMITTED, "Sign Submitted"),
        (EVENT_LINK_CREATED, "Link Created"),
        (EVENT_REQUEST_SENT, "Request Sent"),
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
