from __future__ import annotations

import os
from datetime import datetime

from django.conf import settings
from django.db import models

from core.document_signing import (
    IMAGE_FILE_TYPE,
    PDF_FILE_TYPE,
    get_document_storage,
    get_raw_storage,
)


def _timestamp_path(prefix: str, filename: str) -> str:
    now = datetime.now()
    return f"{prefix}/{now:%Y/%m/%d}/{filename}"


def docsign_source_upload_to(instance, filename: str) -> str:
    return _timestamp_path("docsign/source", os.path.basename(filename or "document.pdf"))


def docsign_signed_upload_to(instance, filename: str) -> str:
    return _timestamp_path("docsign/signed", os.path.basename(filename or "document-signed.pdf"))


class DocumentSignJob(models.Model):
    MARK_TYPE_SIGNATURE = "signature"
    MARK_TYPE_CHECKMARK = "checkmark"
    FILE_TYPE_CHOICES = [
        (PDF_FILE_TYPE, "PDF"),
        (IMAGE_FILE_TYPE, "Image"),
    ]
    MARK_TYPE_CHOICES = [
        (MARK_TYPE_SIGNATURE, "사인"),
        (MARK_TYPE_CHECKMARK, "체크"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_sign_jobs",
    )
    title = models.CharField(max_length=200)
    source_file = models.FileField(
        upload_to=docsign_source_upload_to,
        storage=get_document_storage,
        max_length=500,
    )
    source_file_name_snapshot = models.CharField(max_length=255, blank=True, default="")
    source_file_size_snapshot = models.PositiveBigIntegerField(blank=True, null=True)
    source_file_sha256_snapshot = models.CharField(max_length=64, blank=True, default="")
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default=PDF_FILE_TYPE)
    mark_type = models.CharField(max_length=20, choices=MARK_TYPE_CHOICES, default=MARK_TYPE_SIGNATURE)
    signature_page = models.PositiveIntegerField(blank=True, null=True)
    x = models.FloatField(blank=True, null=True)
    y = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)
    signed_pdf = models.FileField(
        upload_to=docsign_signed_upload_to,
        storage=get_raw_storage,
        max_length=500,
        blank=True,
        null=True,
    )
    signed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title

    @property
    def is_position_configured(self) -> bool:
        return all(
            value is not None
            for value in (self.signature_page, self.x, self.y, self.width, self.height)
        )

    @property
    def is_signed(self) -> bool:
        return bool(self.signed_pdf and self.signed_at)

    @property
    def stage_key(self) -> str:
        if self.is_signed:
            return "done"
        if self.is_position_configured:
            return "sign"
        return "position"

    @property
    def mark_type_label(self) -> str:
        return dict(self.MARK_TYPE_CHOICES).get(self.mark_type, "사인")
