from __future__ import annotations

import os

from django.core.files.base import ContentFile
from django.utils import timezone

from core.document_signing import basename, build_signed_pdf_bytes, get_pdf_bytes_from_file_field


def sanitize_filename_base(value: str, *, fallback: str = "signed-document") -> str:
    normalized = os.path.splitext(basename(value or ""))[0].strip()
    return normalized[:120] or fallback


def build_signed_download_name(job) -> str:
    base = sanitize_filename_base(job.source_file_name_snapshot or job.title)
    return f"{base}-signed.pdf"


def generate_signed_pdf(job, signature_data: str):
    if not job.is_position_configured:
        raise ValueError("서명 위치가 아직 없습니다.")

    source_pdf_bytes = get_pdf_bytes_from_file_field(
        job.source_file,
        file_type=job.file_type,
        filename_hint=job.source_file_name_snapshot,
    )
    signed_pdf_bytes = build_signed_pdf_bytes(
        source_pdf_bytes,
        page_number=job.signature_page,
        x=job.x,
        y=job.y,
        width=job.width,
        height=job.height,
        signature_data=signature_data,
        pdf_title=job.title,
    )

    if job.signed_pdf:
        job.signed_pdf.delete(save=False)

    filename = build_signed_download_name(job)
    job.signed_pdf.save(filename, ContentFile(signed_pdf_bytes, name=filename), save=False)
    job.signed_at = timezone.now()
    job.save(update_fields=["signed_pdf", "signed_at", "updated_at"])
    return job
