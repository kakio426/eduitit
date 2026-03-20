from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import TextbookDocumentUploadForm
from .models import TextbookDocument
from .services import (
    ParserExecutionError,
    ParserUnavailableError,
    get_service,
    get_parser_readiness,
    inspect_pdf_upload,
    mark_parse_failure,
    parse_document,
    search_document_chunks,
)


def _build_main_context(request, *, form=None):
    documents = list(
        TextbookDocument.objects.filter(owner=request.user)
        .select_related("artifact")
        .order_by("-updated_at")[:8]
    )
    queryset = TextbookDocument.objects.filter(owner=request.user)
    return {
        "service": get_service(),
        "parser_readiness": get_parser_readiness(),
        "upload_form": form or TextbookDocumentUploadForm(),
        "documents": documents,
        "document_count": queryset.count(),
        "ready_count": queryset.filter(parse_status=TextbookDocument.ParseStatus.READY).count(),
        "needs_review_count": queryset.filter(parse_status=TextbookDocument.ParseStatus.NEEDS_REVIEW).count(),
        "processing_count": queryset.filter(parse_status=TextbookDocument.ParseStatus.PROCESSING).count(),
    }


def _render_detail(request, document, *, active_tab="structure", search_query="", search_results=None):
    artifact = getattr(document, "artifact", None)
    summary_json = dict(getattr(artifact, "summary_json", {}) or {})
    preview_chunks = list(document.chunks.order_by("sort_order")[:12])
    context = {
        "service": get_service(),
        "parser_readiness": get_parser_readiness(),
        "document": document,
        "artifact": artifact,
        "active_tab": active_tab,
        "search_query": search_query,
        "search_results": search_results or [],
        "preview_chunks": preview_chunks,
        "heading_outline": list(summary_json.get("heading_outline") or []),
        "table_previews": list(summary_json.get("table_previews") or []),
        "content_preview_blocks": list(summary_json.get("content_preview_blocks") or []),
        "ai_generation_enabled": bool(getattr(settings, "TEXTBOOK_AI_EXTERNAL_GENERATION_ENABLED", False)),
        "scan_review_reason": str(summary_json.get("scan_review_reason") or ""),
    }
    return render(request, "textbook_ai/detail.html", context)


@login_required
@require_GET
def main_view(request):
    return render(request, "textbook_ai/main.html", _build_main_context(request))


@login_required
@require_POST
def upload_document_view(request):
    form = TextbookDocumentUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "textbook_ai/main.html", _build_main_context(request, form=form), status=400)

    uploaded_pdf = form.cleaned_data["source_pdf"]
    try:
        pdf_meta = inspect_pdf_upload(uploaded_pdf)
    except Exception as exc:
        form.add_error("source_pdf", " ".join(getattr(exc, "messages", [str(exc)])))
        return render(request, "textbook_ai/main.html", _build_main_context(request, form=form), status=400)

    duplicate = TextbookDocument.objects.filter(owner=request.user, file_sha256=pdf_meta["sha256"]).first()
    if duplicate is not None:
        messages.info(request, "이미 올린 PDF입니다. 기존 분석 결과를 열어 드릴게요.")
        return redirect("textbook_ai:detail", document_id=duplicate.id)

    document = form.save(commit=False)
    document.owner = request.user
    document.original_filename = pdf_meta["original_filename"]
    document.file_sha256 = pdf_meta["sha256"]
    document.file_size_bytes = pdf_meta["file_size_bytes"]
    document.page_count = pdf_meta["page_count"]
    document.parse_status = TextbookDocument.ParseStatus.QUEUED
    document.save()

    try:
        parse_document(document)
    except (ParserUnavailableError, ParserExecutionError) as exc:
        mark_parse_failure(document, exc)
        messages.error(request, "PDF는 저장했지만 읽기 도중 문제가 생겼습니다. 상세 화면에서 다시 시도해 주세요.")
    else:
        if document.parse_status == TextbookDocument.ParseStatus.NEEDS_REVIEW:
            messages.warning(request, "PDF를 읽었지만 텍스트 추출량이 낮습니다. 스캔본일 수 있어 결과를 꼭 확인해 주세요.")
        else:
            messages.success(request, "PDF를 읽기 좋은 구조로 정리했습니다.")
    return redirect("textbook_ai:detail", document_id=document.id)


@login_required
@require_GET
def document_detail_view(request, document_id):
    document = get_object_or_404(
        TextbookDocument.objects.filter(owner=request.user).select_related("artifact"),
        id=document_id,
    )
    active_tab = "future" if request.GET.get("tab") == "future" else "structure"
    return _render_detail(request, document, active_tab=active_tab)


@login_required
@require_POST
def reparse_document_view(request, document_id):
    document = get_object_or_404(TextbookDocument, id=document_id, owner=request.user)
    try:
        parse_document(document, force=True)
    except (ParserUnavailableError, ParserExecutionError) as exc:
        mark_parse_failure(document, exc)
        messages.error(request, "다시 읽기 중 문제가 생겼습니다. Java 또는 OpenDataLoader 설치 상태를 확인해 주세요.")
    else:
        if document.parse_status == TextbookDocument.ParseStatus.NEEDS_REVIEW:
            messages.warning(request, "다시 읽기를 마쳤지만 텍스트 추출량이 낮습니다. 결과를 직접 확인해 주세요.")
        else:
            messages.success(request, "PDF를 다시 읽었습니다.")
    return redirect("textbook_ai:detail", document_id=document.id)


@login_required
@require_GET
def document_search_view(request, document_id):
    document = get_object_or_404(
        TextbookDocument.objects.filter(owner=request.user).select_related("artifact"),
        id=document_id,
    )
    query = str(request.GET.get("q") or "").strip()
    results = search_document_chunks(document, query) if query else []
    return _render_detail(
        request,
        document,
        active_tab="search",
        search_query=query,
        search_results=results,
    )


@login_required
@require_GET
def document_pdf_view(request, document_id):
    document = get_object_or_404(TextbookDocument, id=document_id, owner=request.user)
    if not document.source_pdf:
        raise Http404()
    response = FileResponse(document.source_pdf.open("rb"), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{document.original_filename or document.title}.pdf"'
    return response
