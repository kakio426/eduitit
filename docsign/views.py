from __future__ import annotations

import json
import os
from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, ProgrammingError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.document_signing import (
    basename,
    get_file_field_bytes,
    get_pdf_bytes_from_file_field,
    get_pdf_page_sizes,
    guess_file_type,
    normalize_pdf_bytes,
    snapshot_file_metadata,
)

from .forms import DocumentSignPositionForm, DocumentSignSignatureForm, DocumentSignUploadForm
from .models import DocumentSignJob
from .services import build_signed_download_name, generate_signed_pdf


def _is_docsign_schema_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "docsign_documentsignjob" in message
        or "no such table" in message
        or "does not exist" in message
    )


def _render_docsign_unavailable(request):
    return render(request, "docsign/unavailable.html", status=503)


def _docsign_runtime_guard(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except (OperationalError, ProgrammingError) as exc:
            if _is_docsign_schema_error(exc):
                return _render_docsign_unavailable(request)
            raise

    return wrapped


def _owned_job_or_404(user, job_id: int) -> DocumentSignJob:
    return get_object_or_404(DocumentSignJob, pk=job_id, owner=user)


def _apply_sensitive_cache_headers(response):
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def _build_stage_meta(job: DocumentSignJob) -> tuple[str, str]:
    mapping = {
        "position": ("위치", "다음: 위치"),
        "sign": ("사인", "다음: 사인"),
        "done": ("완료", "다운로드"),
    }
    return mapping.get(job.stage_key, ("진행 중", "이어하기"))


def _source_pdf_bytes(job: DocumentSignJob) -> bytes:
    return normalize_pdf_bytes(
        get_pdf_bytes_from_file_field(
            job.source_file,
            file_type=job.file_type,
            filename_hint=job.source_file_name_snapshot,
        )
    )


def _inline_pdf_response(pdf_bytes: bytes, *, filename: str):
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
    return _apply_sensitive_cache_headers(response)


def _page_sizes(job: DocumentSignJob):
    return get_pdf_page_sizes(_source_pdf_bytes(job))


def _mark_payload_from_job(job: DocumentSignJob, page_sizes: list[tuple[float, float]]) -> list[dict]:
    payload = []
    for mark in job.configured_marks:
        page_number = mark["page"]
        if page_number < 1 or page_number > len(page_sizes):
            continue
        page_width, page_height = page_sizes[page_number - 1]
        payload.append(
            {
                "page": page_number,
                "x_ratio": round(mark["x"] / page_width, 6),
                "y_ratio": round(mark["y"] / page_height, 6),
                "w_ratio": round(mark["width"] / page_width, 6),
                "h_ratio": round(mark["height"] / page_height, 6),
                "mark_type": mark["mark_type"],
            }
        )
    return payload


@login_required
@_docsign_runtime_guard
def job_list(request):
    jobs = list(DocumentSignJob.objects.filter(owner=request.user).order_by("-updated_at", "-id"))
    for job in jobs:
        stage_label, action_label = _build_stage_meta(job)
        job.stage_label = stage_label
        job.primary_action_label = action_label
    context = {
        "jobs": jobs,
        "draft_count": sum(1 for job in jobs if not job.is_signed),
        "done_count": sum(1 for job in jobs if job.is_signed),
    }
    return render(request, "docsign/list.html", context)


@login_required
@_docsign_runtime_guard
def job_create(request):
    if request.method == "POST":
        form = DocumentSignUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["source_file"]
            source_name, source_size, source_sha256 = snapshot_file_metadata(upload)
            title = (form.cleaned_data.get("title") or "").strip() or os.path.splitext(source_name)[0] or "문서 사인"
            job = DocumentSignJob.objects.create(
                owner=request.user,
                title=title[:200],
                source_file=upload,
                source_file_name_snapshot=source_name,
                source_file_size_snapshot=source_size,
                source_file_sha256_snapshot=source_sha256,
                file_type=guess_file_type(upload.name),
            )
            return redirect("docsign:position", job_id=job.id)
    else:
        form = DocumentSignUploadForm()

    return render(request, "docsign/create.html", {"form": form})


@login_required
@_docsign_runtime_guard
def job_detail(request, job_id: int):
    job = _owned_job_or_404(request.user, job_id)
    stage_label, action_label = _build_stage_meta(job)
    if job.is_signed:
        next_href = reverse("docsign:download", kwargs={"job_id": job.id})
    elif job.is_position_configured:
        next_href = reverse("docsign:sign", kwargs={"job_id": job.id})
    else:
        next_href = reverse("docsign:position", kwargs={"job_id": job.id})

    context = {
        "job": job,
        "stage_label": stage_label,
        "primary_action_label": action_label,
        "next_href": next_href,
        "auto_download": request.GET.get("download") == "1" and job.is_signed,
        "preview_document_url": (
            reverse("docsign:signed_document", kwargs={"job_id": job.id})
            if job.is_signed
            else reverse("docsign:source_document", kwargs={"job_id": job.id})
        ),
        "preview_document_name": (
            build_signed_download_name(job)
            if job.is_signed
            else job.source_file_name_snapshot or basename(job.source_file.name)
        ),
    }
    return render(request, "docsign/detail.html", context)


@login_required
@_docsign_runtime_guard
def job_source_document(request, job_id: int):
    job = _owned_job_or_404(request.user, job_id)
    if not job.source_file:
        raise Http404("문서를 찾지 못했습니다.")

    filename = basename(job.source_file_name_snapshot or job.source_file.name)
    return _inline_pdf_response(_source_pdf_bytes(job), filename=filename)


@login_required
@_docsign_runtime_guard
def job_signed_document(request, job_id: int):
    job = _owned_job_or_404(request.user, job_id)
    if not job.is_signed or not job.signed_pdf:
        raise Http404("사인된 PDF가 아직 없습니다.")
    return _inline_pdf_response(
        get_file_field_bytes(
            job.signed_pdf,
            file_type="pdf",
            filename_hint=build_signed_download_name(job),
        ),
        filename=build_signed_download_name(job),
    )


@login_required
@_docsign_runtime_guard
def job_position(request, job_id: int):
    job = _owned_job_or_404(request.user, job_id)
    page_sizes = _page_sizes(job)

    if request.method == "POST":
        form = DocumentSignPositionForm(request.POST)
        if form.is_valid():
            payload = form.cleaned_data["marks_json"]
            invalid_page = next(
                (item["page"] for item in payload if item["page"] > len(page_sizes)),
                None,
            )
            if invalid_page is not None:
                form.add_error(None, "문서 페이지 수를 다시 확인해 주세요.")
            else:
                resolved_marks = []
                for item in payload:
                    page_number = item["page"]
                    page_width, page_height = page_sizes[page_number - 1]
                    resolved_marks.append(
                        {
                            "page": page_number,
                            "x": page_width * item["x_ratio"],
                            "y": page_height * item["y_ratio"],
                            "width": page_width * item["w_ratio"],
                            "height": page_height * item["h_ratio"],
                            "mark_type": item["mark_type"],
                        }
                    )
                primary_mark = resolved_marks[0]
                job.marks = resolved_marks
                job.mark_type = primary_mark["mark_type"]
                job.signature_page = primary_mark["page"]
                job.x = primary_mark["x"]
                job.y = primary_mark["y"]
                job.width = primary_mark["width"]
                job.height = primary_mark["height"]
                if job.signed_pdf:
                    job.signed_pdf.delete(save=False)
                    job.signed_pdf = None
                job.signed_at = None
                job.save(
                    update_fields=[
                        "signature_page",
                        "x",
                        "y",
                        "width",
                        "height",
                        "marks",
                        "signed_pdf",
                        "signed_at",
                        "updated_at",
                        "mark_type",
                    ]
                )
                return redirect("docsign:sign", job_id=job.id)
    else:
        form = DocumentSignPositionForm()

    context = {
        "job": job,
        "form": form,
        "document_preview_url": reverse("docsign:source_document", kwargs={"job_id": job.id}),
        "document_file_name": job.source_file_name_snapshot or basename(job.source_file.name),
        "page_count": len(page_sizes),
        "initial_marks_json": json.dumps(
            _mark_payload_from_job(job, page_sizes),
            ensure_ascii=False,
        ),
    }
    return render(request, "docsign/position.html", context)


@login_required
@_docsign_runtime_guard
def job_sign(request, job_id: int):
    job = _owned_job_or_404(request.user, job_id)
    if not job.is_position_configured:
        messages.error(request, "표시 위치부터 잡아 주세요.")
        return redirect("docsign:position", job_id=job.id)

    if request.method == "POST":
        form = DocumentSignSignatureForm(
            request.POST,
            requires_signature=job.requires_signature_input,
        )
        if form.is_valid():
            generate_signed_pdf(job, form.cleaned_data["signature_data"])
            messages.success(request, "표시된 PDF를 만들었습니다.")
            return redirect(f'{reverse("docsign:detail", kwargs={"job_id": job.id})}?download=1')
    else:
        form = DocumentSignSignatureForm(requires_signature=job.requires_signature_input)

    context = {
        "job": job,
        "form": form,
        "document_preview_url": reverse("docsign:source_document", kwargs={"job_id": job.id}),
        "document_file_name": job.source_file_name_snapshot or basename(job.source_file.name),
    }
    return render(request, "docsign/sign.html", context)


@login_required
@_docsign_runtime_guard
def job_download_signed(request, job_id: int):
    job = _owned_job_or_404(request.user, job_id)
    if not job.is_signed or not job.signed_pdf:
        raise Http404("사인된 PDF가 아직 없습니다.")

    filename = build_signed_download_name(job)
    response = HttpResponse(
        get_file_field_bytes(
            job.signed_pdf,
            file_type="pdf",
            filename_hint=filename,
        ),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return _apply_sensitive_cache_headers(response)
