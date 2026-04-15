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
    marks = models.JSONField(blank=True, default=list)
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
    def configured_marks(self) -> list[dict]:
        marks = []
        raw_marks = self.marks if isinstance(self.marks, list) else []
        for index, item in enumerate(raw_marks):
            if not isinstance(item, dict):
                continue
            try:
                page = int(item.get("page", 0))
                x = float(item.get("x"))
                y = float(item.get("y"))
                width = float(item.get("width"))
                height = float(item.get("height"))
            except (TypeError, ValueError):
                continue
            mark_type = str(item.get("mark_type") or self.MARK_TYPE_SIGNATURE).strip().lower()
            if page < 1 or width <= 0 or height <= 0:
                continue
            if mark_type not in {self.MARK_TYPE_SIGNATURE, self.MARK_TYPE_CHECKMARK}:
                mark_type = self.MARK_TYPE_SIGNATURE
            marks.append(
                {
                    "page": page,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "mark_type": mark_type,
                    "index": index,
                }
            )
        if marks:
            return marks
        if all(
            value is not None
            for value in (self.signature_page, self.x, self.y, self.width, self.height)
        ):
            return [
                {
                    "page": int(self.signature_page),
                    "x": float(self.x),
                    "y": float(self.y),
                    "width": float(self.width),
                    "height": float(self.height),
                    "mark_type": self.mark_type or self.MARK_TYPE_SIGNATURE,
                    "index": 0,
                }
            ]
        return []

    @property
    def is_position_configured(self) -> bool:
        return bool(self.configured_marks)

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
    def mark_count(self) -> int:
        return len(self.configured_marks)

    @property
    def signature_mark_count(self) -> int:
        return sum(1 for mark in self.configured_marks if mark["mark_type"] == self.MARK_TYPE_SIGNATURE)

    @property
    def checkmark_mark_count(self) -> int:
        return sum(1 for mark in self.configured_marks if mark["mark_type"] == self.MARK_TYPE_CHECKMARK)

    @property
    def requires_signature_input(self) -> bool:
        return self.signature_mark_count > 0

    @property
    def page_summary(self) -> str:
        pages = sorted({mark["page"] for mark in self.configured_marks})
        if not pages:
            return "위치 없음"
        if len(pages) == 1:
            return f"{pages[0]}쪽"
        return ", ".join(str(page) for page in pages) + "쪽"

    @property
    def mark_summary(self) -> str:
        if not self.configured_marks:
            return "표시 없음"
        parts = []
        if self.signature_mark_count:
            parts.append(
                "사인"
                if self.signature_mark_count == 1
                else f"사인 {self.signature_mark_count}개"
            )
        if self.checkmark_mark_count:
            parts.append(
                "체크"
                if self.checkmark_mark_count == 1
                else f"체크 {self.checkmark_mark_count}개"
            )
        return " · ".join(parts)

    @property
    def mark_type_label(self) -> str:
        return self.mark_summary
