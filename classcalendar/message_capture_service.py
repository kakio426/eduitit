from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from django.http import JsonResponse

from .forms import MessageCaptureParseForm
from .models import (
    CalendarMessageCapture,
    CalendarMessageCaptureAttachment,
    CalendarMessageCaptureCandidate,
)


MESSAGE_CAPTURE_RULE_VERSION = "mvp-v3"


@dataclass(frozen=True)
class MessageCaptureUploadConfig:
    max_files: int
    max_file_bytes: int
    allowed_extensions: frozenset[str]
    allowed_mime_types: frozenset[str]
    allowed_mime_prefixes: tuple[str, ...]


MESSAGE_CAPTURE_UPLOAD_CONFIG = MessageCaptureUploadConfig(
    max_files=3,
    max_file_bytes=8 * 1024 * 1024,
    allowed_extensions=frozenset(
        {
            "pdf",
            "xls",
            "xlsx",
            "doc",
            "docx",
            "hwp",
            "hwpx",
        }
    ),
    allowed_mime_types=frozenset(
        {
            "application/pdf",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/x-hwp",
            "application/haansofthwp",
            "application/octet-stream",
        }
    ),
    allowed_mime_prefixes=(),
)


@dataclass(frozen=True)
class MessageCaptureSubmission:
    raw_text: str
    source_hint: str
    idempotency_key: str
    manual_date: date | None
    manual_note: str
    uploaded_files: list[Any]


def extract_upload_extension(uploaded_file: Any) -> str:
    file_name = (
        getattr(uploaded_file, "name", "")
        or getattr(uploaded_file, "original_name", "")
        or getattr(getattr(uploaded_file, "file", None), "name", "")
    )
    _, extension = os.path.splitext(file_name or "")
    return extension.lower().lstrip(".")


def guess_upload_mime_type(uploaded_file: Any) -> str:
    hinted_type = (getattr(uploaded_file, "content_type", "") or "").strip().lower()
    if hinted_type:
        return hinted_type
    guessed, _ = mimetypes.guess_type(getattr(uploaded_file, "name", "") or "")
    return (guessed or "application/octet-stream").lower()


def calculate_upload_sha256(uploaded_file: Any) -> str:
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return digest.hexdigest()


def build_message_capture_error_response(*, message: str, code: str = "validation_error", status: int = 400, errors=None):
    payload = {
        "status": "error",
        "code": code,
        "message": message,
    }
    if errors is not None:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)


def _is_allowed_message_capture_file(
    uploaded_file: Any,
    *,
    upload_config: MessageCaptureUploadConfig = MESSAGE_CAPTURE_UPLOAD_CONFIG,
) -> bool:
    extension = extract_upload_extension(uploaded_file)
    mime_type = guess_upload_mime_type(uploaded_file)

    extension_allowed = extension in upload_config.allowed_extensions
    mime_allowed = mime_type in upload_config.allowed_mime_types or any(
        mime_type.startswith(prefix) for prefix in upload_config.allowed_mime_prefixes
    )
    return extension_allowed and mime_allowed


def validate_message_capture_uploads(
    *,
    uploaded_files,
    user_id,
    operation_label: str,
    logger: logging.Logger,
    upload_config: MessageCaptureUploadConfig = MESSAGE_CAPTURE_UPLOAD_CONFIG,
):
    attachment_checksums = []
    for uploaded_file in uploaded_files:
        file_size = int(getattr(uploaded_file, "size", 0) or 0)
        if file_size > upload_config.max_file_bytes:
            logger.warning(
                "[ClassCalendar][MessageCapture] %s_failed user_id=%s reason=file_too_large file=%s size=%s",
                operation_label,
                user_id,
                uploaded_file.name,
                file_size,
            )
            return None, build_message_capture_error_response(
                code="file_too_large",
                message=(
                    f"{uploaded_file.name} 파일이 용량 제한"
                    f"({upload_config.max_file_bytes // (1024 * 1024)}MB)을 초과했습니다."
                ),
                status=413,
            )
        if not _is_allowed_message_capture_file(uploaded_file, upload_config=upload_config):
            logger.warning(
                "[ClassCalendar][MessageCapture] %s_failed user_id=%s reason=invalid_file_type file=%s",
                operation_label,
                user_id,
                uploaded_file.name,
            )
            return None, build_message_capture_error_response(
                message=f"{uploaded_file.name} 파일 형식은 지원하지 않습니다.",
            )
        attachment_checksums.append(calculate_upload_sha256(uploaded_file))
    return attachment_checksums, None


def extract_message_capture_submission(
    request,
    *,
    operation_label: str,
    logger: logging.Logger,
    upload_config: MessageCaptureUploadConfig = MESSAGE_CAPTURE_UPLOAD_CONFIG,
):
    form = MessageCaptureParseForm(request.POST)
    if not form.is_valid():
        logger.warning(
            "[ClassCalendar][MessageCapture] %s_failed user_id=%s reason=form_invalid",
            operation_label,
            request.user.id,
        )
        return None, build_message_capture_error_response(
            message="입력값을 확인해 주세요.",
            errors=form.errors.get_json_data(),
        )

    raw_text = form.cleaned_data.get("raw_text") or ""
    uploaded_files = list(request.FILES.getlist("files"))
    if not raw_text.strip() and not uploaded_files:
        logger.warning(
            "[ClassCalendar][MessageCapture] %s_failed user_id=%s reason=empty_input",
            operation_label,
            request.user.id,
        )
        return None, build_message_capture_error_response(
            message="메시지 텍스트 또는 첨부파일 중 하나는 반드시 입력해 주세요.",
        )

    if len(uploaded_files) > upload_config.max_files:
        logger.warning(
            "[ClassCalendar][MessageCapture] %s_failed user_id=%s reason=too_many_files files=%s",
            operation_label,
            request.user.id,
            len(uploaded_files),
        )
        return None, build_message_capture_error_response(
            message=f"첨부파일은 최대 {upload_config.max_files}개까지 업로드할 수 있습니다.",
        )

    return (
        MessageCaptureSubmission(
            raw_text=raw_text,
            source_hint=(form.cleaned_data.get("source_hint") or "unknown").strip()[:30] or "unknown",
            idempotency_key=(form.cleaned_data.get("idempotency_key") or uuid.uuid4().hex).strip()[:64] or uuid.uuid4().hex,
            manual_date=form.cleaned_data.get("manual_date"),
            manual_note=form.cleaned_data.get("manual_note") or "",
            uploaded_files=uploaded_files,
        ),
        None,
    )


def find_existing_message_capture(*, user, idempotency_key: str):
    return (
        CalendarMessageCapture.objects.filter(author=user, idempotency_key=idempotency_key)
        .prefetch_related("attachments", "candidates")
        .first()
    )


def create_message_capture_attachments(capture, uploaded_files, attachment_checksums, *, uploaded_by):
    for uploaded_file, checksum in zip(uploaded_files, attachment_checksums):
        CalendarMessageCaptureAttachment.objects.create(
            capture=capture,
            uploaded_by=uploaded_by,
            file=uploaded_file,
            original_name=(os.path.basename(uploaded_file.name or "") or "attachment")[:255],
            mime_type=guess_upload_mime_type(uploaded_file)[:120],
            size_bytes=int(getattr(uploaded_file, "size", 0) or 0),
            checksum_sha256=checksum,
            is_selected=True,
        )


def create_message_capture_candidates(
    capture,
    parsed_candidates,
    *,
    allowed_candidate_kinds: Iterable[str],
):
    allowed_kinds = set(allowed_candidate_kinds)
    for index, candidate in enumerate(parsed_candidates or []):
        candidate_kind = str(
            candidate.get("kind") or CalendarMessageCaptureCandidate.CandidateKind.EVENT
        ).strip().lower()
        if candidate_kind not in allowed_kinds:
            candidate_kind = CalendarMessageCaptureCandidate.CandidateKind.EVENT
        CalendarMessageCaptureCandidate.objects.create(
            capture=capture,
            sort_order=index,
            candidate_kind=candidate_kind,
            title=(candidate.get("title") or "")[:200],
            summary=candidate.get("summary") or "",
            start_time=candidate.get("start_time"),
            end_time=candidate.get("end_time"),
            is_all_day=bool(candidate.get("is_all_day")),
            confidence_score=candidate.get("confidence_score") or 0,
            is_recommended=bool(candidate.get("is_recommended", True)),
            needs_check=bool(candidate.get("needs_check")),
            evidence_text=(candidate.get("evidence_text") or "")[:1000],
            evidence_payload=candidate.get("evidence_payload") or {},
            commit_status=CalendarMessageCaptureCandidate.CommitStatus.PENDING,
        )
