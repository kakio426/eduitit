import json
import logging
import os
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_GET, require_POST

from products.models import Product

from .models import HwpxDocument, HwpxDocumentQuestion, HwpxWorkItem
from .services import (
    ABSOLUTE_TEXT_CHAR_LIMIT,
    ASK_LIMIT_MESSAGE,
    ASK_LIMITS,
    DEFAULT_PROVIDER,
    FULL_TEXT_CHAR_LIMIT,
    LIMIT_MESSAGE,
    MAX_HWPX_FILE_BYTES,
    MAX_WORK_ITEMS,
    PIPELINE_VERSION,
    STRUCTURE_LIMITS,
    TOO_LARGE_MESSAGE,
    build_fallback_work_item,
    compute_sha256,
    find_relevant_chunks,
    log_hwpx_metric,
    normalize_question,
    rate_limit_exceeded,
    summarize_text_for_structure,
)
from .utils.hwpx_parser import HwpxParseError, parse_hwpx_document
from .utils.llm_client import LlmClientError, answer_document_question, generate_structured_workitems

logger = logging.getLogger(__name__)

SERVICE_TITLE = "한글문서 AI야 읽어줘"
LEGACY_SERVICE_TITLES = (
    "한글 문서 톡톡",
    "HWPX 문서 AI 대화",
)
HWPX_SESSION_DOCUMENT_KEY = "hwpxchat_last_document_id"


def _get_service():
    product = Product.objects.filter(title=SERVICE_TITLE).first()
    if product:
        return product

    for legacy_title in LEGACY_SERVICE_TITLES:
        product = Product.objects.filter(title=legacy_title).first()
        if product:
            return product

    return Product.objects.filter(launch_route_name="hwpxchat:main").first()


@login_required
@require_GET
def main(request):
    document = _get_last_document(request)
    return render(request, "hwpxchat/main.html", _build_page_context(request, document=document))


@login_required
@require_GET
def document_detail(request, document_id):
    document = _get_owner_document_or_404(request.user, document_id)
    _remember_document(request, document)
    return render(request, "hwpxchat/main.html", _build_page_context(request, document=document))


@login_required
@require_POST
def chat_process(request):
    uploaded_file = request.FILES.get("hwpx_file")
    provider = DEFAULT_PROVIDER

    validation_error = _validate_upload(uploaded_file)
    if validation_error:
        return _render_result(request, error_message=validation_error, status=400)

    raw_bytes = _read_upload_bytes(uploaded_file)
    file_sha256 = compute_sha256(raw_bytes)

    existing_document = HwpxDocument.objects.filter(
        owner=request.user,
        file_sha256=file_sha256,
        pipeline_version=PIPELINE_VERSION,
    ).prefetch_related("work_items", "questions").first()
    if existing_document:
        _remember_document(request, existing_document)
        log_hwpx_metric(
            "hwpx_structure_cache_hit",
            user_id=request.user.id,
            document_id=str(existing_document.id),
        )
        return _render_result(
            request,
            document=existing_document,
            info_message="이미 정리한 문서예요. 저장된 결과를 다시 불러왔어요.",
        )

    try:
        parsed = parse_hwpx_document(raw_bytes=raw_bytes, file_name=uploaded_file.name)
    except HwpxParseError as exc:
        logger.error("[hwpxchat] parse failed: %s", exc)
        return _render_result(
            request,
            error_message="HWPX 파싱에 실패했습니다. 파일 형식을 확인한 뒤 다시 시도해 주세요.",
            status=400,
        )
    except Exception:
        logger.exception("[hwpxchat] unexpected parse failure")
        return _render_result(
            request,
            error_message="문서 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            status=500,
        )

    document = _create_document_from_upload(
        user=request.user,
        uploaded_file=uploaded_file,
        raw_bytes=raw_bytes,
        file_sha256=file_sha256,
        parsed=parsed,
        provider=provider,
    )
    _remember_document(request, document)

    info_message = "문서에서 해야 할 일을 정리했어요. 틀린 곳만 확인한 뒤 복사해 바로 쓰세요."
    limit_message = ""

    structure_text, input_mode, too_large = summarize_text_for_structure(document.raw_markdown, document.parse_payload)
    document.parse_payload = {
        **(document.parse_payload or {}),
        "structure_input_mode": input_mode,
        "pipeline_version": PIPELINE_VERSION,
        "char_limit_full": FULL_TEXT_CHAR_LIMIT,
        "char_limit_absolute": ABSOLUTE_TEXT_CHAR_LIMIT,
    }

    if too_large:
        document.structure_status = HwpxDocument.StructureStatus.TOO_LARGE
        document.summary_text = TOO_LARGE_MESSAGE
        document.save(update_fields=["parse_payload", "structure_status", "summary_text", "updated_at"])
        limit_message = TOO_LARGE_MESSAGE
        return _render_result(request, document=document, limit_message=limit_message)

    if rate_limit_exceeded("structure", request.user.id, STRUCTURE_LIMITS):
        log_hwpx_metric("hwpx_limit_blocked", user_id=request.user.id, action="structure")
        _replace_work_items(document, [build_fallback_work_item(document.raw_markdown, document.parse_payload, reason="limit_blocked")])
        document.structure_status = HwpxDocument.StructureStatus.LIMIT_BLOCKED
        document.summary_text = "문서를 저장했고, 해야 할 일은 직접 확인해 주세요."
        document.save(update_fields=["parse_payload", "structure_status", "summary_text", "updated_at"])
        return _render_result(request, document=document, limit_message=LIMIT_MESSAGE)

    log_hwpx_metric(
        "hwpx_structure_requested",
        user_id=request.user.id,
        document_id=str(document.id),
        char_count=len(document.raw_markdown or ""),
        input_mode=input_mode,
    )
    try:
        structured = generate_structured_workitems(source_text=structure_text, max_items=MAX_WORK_ITEMS)
        normalized_items = [_normalize_work_item_payload(item) for item in (structured.get("work_items") or [])]
        normalized_items = [item for item in normalized_items if item["title"] or item["action_text"]]
        if not normalized_items:
            raise LlmClientError("No work items returned.")
        _replace_work_items(document, normalized_items)
        document.summary_text = (structured.get("summary_text") or document.document_title or "").strip()[:120]
        document.structure_status = HwpxDocument.StructureStatus.READY
        document.save(update_fields=["parse_payload", "summary_text", "structure_status", "updated_at"])
        log_hwpx_metric("hwpx_structure_success", user_id=request.user.id, document_id=str(document.id))
    except Exception as exc:
        logger.exception("[hwpxchat] structure failed document_id=%s", document.id)
        _replace_work_items(document, [build_fallback_work_item(document.raw_markdown, document.parse_payload, reason="failed")])
        document.summary_text = "문서를 저장했고, 해야 할 일은 직접 확인해 주세요."
        document.structure_status = HwpxDocument.StructureStatus.FALLBACK
        document.save(update_fields=["parse_payload", "summary_text", "structure_status", "updated_at"])
        info_message = "문서를 저장했지만 자동 정리가 충분하지 않아 직접 확인이 필요해요."
        log_hwpx_metric(
            "hwpx_structure_fail",
            user_id=request.user.id,
            document_id=str(document.id),
            error=str(exc),
        )

    document.refresh_from_db()
    return _render_result(
        request,
        document=document,
        info_message=info_message,
        limit_message=limit_message,
    )

@login_required
@require_POST
def ask_document(request, document_id):
    document = _get_owner_document_or_404(request.user, document_id)
    payload = _get_request_payload(request)
    question = str(payload.get("question") or "").strip()
    if not question:
        return JsonResponse(
            {
                "answer": "",
                "citations": [],
                "has_insufficient_evidence": True,
                "reused": False,
                "message": "질문을 입력해 주세요.",
            },
            status=400,
        )

    normalized = normalize_question(question)
    cached = document.questions.filter(normalized_question=normalized, provider=DEFAULT_PROVIDER).first()
    if cached:
        log_hwpx_metric("hwpx_ask_cache_hit", user_id=request.user.id, document_id=str(document.id))
        return JsonResponse(
            {
                "answer": cached.answer,
                "citations": cached.citations_json or [],
                "has_insufficient_evidence": cached.has_insufficient_evidence,
                "reused": True,
            }
        )

    if rate_limit_exceeded("ask", request.user.id, ASK_LIMITS):
        log_hwpx_metric("hwpx_limit_blocked", user_id=request.user.id, action="ask")
        return JsonResponse(
            {
                "answer": "",
                "citations": [],
                "has_insufficient_evidence": True,
                "reused": False,
                "message": ASK_LIMIT_MESSAGE,
            },
            status=429,
        )

    log_hwpx_metric("hwpx_ask_requested", user_id=request.user.id, document_id=str(document.id))
    chunks = find_relevant_chunks(document.parse_payload, question)
    if not chunks:
        question_obj = HwpxDocumentQuestion.objects.create(
            document=document,
            question=question,
            normalized_question=normalized,
            answer="문서 근거를 찾지 못했습니다.",
            citations_json=[],
            has_insufficient_evidence=True,
            provider=DEFAULT_PROVIDER,
        )
        log_hwpx_metric("hwpx_ask_no_evidence", user_id=request.user.id, document_id=str(document.id))
        return JsonResponse(
            {
                "answer": question_obj.answer,
                "citations": [],
                "has_insufficient_evidence": True,
                "reused": False,
            }
        )

    try:
        response_payload = answer_document_question(question=question, chunks=chunks)
        HwpxDocumentQuestion.objects.create(
            document=document,
            question=question,
            normalized_question=normalized,
            answer=response_payload["answer"],
            citations_json=response_payload["citations"],
            has_insufficient_evidence=response_payload["has_insufficient_evidence"],
            provider=DEFAULT_PROVIDER,
        )
        log_hwpx_metric("hwpx_ask_success", user_id=request.user.id, document_id=str(document.id))
        return JsonResponse({**response_payload, "reused": False})
    except Exception:
        logger.exception("[hwpxchat] ask failed document_id=%s", document.id)
        return JsonResponse(
            {
                "answer": "답변을 준비하지 못했어요. 잠시 후 다시 시도해 주세요.",
                "citations": [],
                "has_insufficient_evidence": True,
                "reused": False,
            },
            status=502,
        )


@login_required
@require_POST
def chat_reset(request):
    request.session.pop(HWPX_SESSION_DOCUMENT_KEY, None)
    request.session.modified = True
    return _render_result(request, info_message="최근 문서 표시를 초기화했습니다.")


@login_required
@require_GET
def download_markdown(request):
    document_id = (request.GET.get("document_id") or "").strip() or request.session.get(HWPX_SESSION_DOCUMENT_KEY, "")
    if not document_id:
        return HttpResponse(
            "변환된 Markdown이 없습니다. HWPX 파일을 먼저 업로드해 주세요.",
            status=400,
            content_type="text/plain; charset=utf-8",
        )

    document = HwpxDocument.objects.filter(owner=request.user, id=document_id).first()
    if not document or not document.raw_markdown:
        return HttpResponse(
            "변환된 Markdown이 없습니다. HWPX 파일을 먼저 업로드해 주세요.",
            status=400,
            content_type="text/plain; charset=utf-8",
        )

    response = HttpResponse(document.raw_markdown, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="hwpx_markdown.md"'
    return response


def _validate_upload(uploaded_file):
    if uploaded_file and uploaded_file.name.lower().endswith(".hwp"):
        return "HWP 파일은 지원하지 않습니다. HWPX로 변환해서 업로드해 주세요."
    if not uploaded_file:
        return "HWPX 파일을 업로드해 주세요."
    if not uploaded_file.name.lower().endswith(".hwpx"):
        return "HWPX 파일만 업로드할 수 있습니다."
    if getattr(uploaded_file, "size", 0) > MAX_HWPX_FILE_BYTES:
        return "파일이 너무 커요. 15MB 이하 HWPX만 올릴 수 있습니다."
    return ""


def _read_upload_bytes(uploaded_file):
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    raw_bytes = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return raw_bytes


def _create_document_from_upload(*, user, uploaded_file, raw_bytes, file_sha256, parsed, provider):
    parse_payload = {
        "char_count": parsed.get("char_count") or len(parsed.get("markdown_text") or ""),
        "first_text_block": parsed.get("first_text_block") or "",
        "document_title": parsed.get("document_title") or "",
        "blocks": parsed.get("blocks") or [],
        "chunks": parsed.get("chunks") or [],
    }
    document = HwpxDocument(
        owner=user,
        original_name=(uploaded_file.name or "문서.hwpx")[:255],
        file_sha256=file_sha256,
        document_title=(parsed.get("document_title") or uploaded_file.name or "문서")[:200],
        raw_markdown=parsed.get("markdown_text") or "",
        summary_text="",
        parse_payload=parse_payload,
        provider=provider,
        structure_status=HwpxDocument.StructureStatus.PENDING,
        pipeline_version=PIPELINE_VERSION,
    )
    document.source_file.save(os.path.basename(uploaded_file.name or "document.hwpx"), ContentFile(raw_bytes), save=False)
    try:
        document.save()
    except IntegrityError:
        existing = HwpxDocument.objects.filter(
            owner=user,
            file_sha256=file_sha256,
            pipeline_version=PIPELINE_VERSION,
        ).first()
        if existing:
            return existing
        raise
    return document


def _normalize_work_item_payload(raw_item):
    raw_item = raw_item or {}
    return {
        "title": str(raw_item.get("title") or "").strip()[:200],
        "action_text": str(raw_item.get("action_text") or "").strip(),
        "due_date": parse_date(str(raw_item.get("due_date") or "").strip()) if raw_item.get("due_date") else None,
        "start_time": parse_time(str(raw_item.get("start_time") or "").strip()) if raw_item.get("start_time") else None,
        "end_time": parse_time(str(raw_item.get("end_time") or "").strip()) if raw_item.get("end_time") else None,
        "is_all_day": _as_bool(raw_item.get("is_all_day")),
        "assignee_text": str(raw_item.get("assignee_text") or "").strip()[:120],
        "target_text": str(raw_item.get("target_text") or "").strip()[:200],
        "materials_text": str(raw_item.get("materials_text") or "").strip(),
        "delivery_required": _as_bool(raw_item.get("delivery_required")),
        "evidence_text": str(raw_item.get("evidence_text") or "").strip(),
        "evidence_refs_json": list(raw_item.get("evidence_refs_json") or []),
        "confidence_score": _coerce_decimal(raw_item.get("confidence_score")),
    }


def _replace_work_items(document, items):
    document.work_items.all().delete()
    objects = []
    for index, item in enumerate(items, start=1):
        normalized = _normalize_work_item_payload(item)
        objects.append(
            HwpxWorkItem(
                document=document,
                sort_order=index,
                title=normalized["title"] or f"업무 {index}",
                action_text=normalized["action_text"],
                due_date=normalized["due_date"],
                start_time=normalized["start_time"],
                end_time=normalized["end_time"],
                is_all_day=normalized["is_all_day"],
                assignee_text=normalized["assignee_text"],
                target_text=normalized["target_text"],
                materials_text=normalized["materials_text"],
                delivery_required=normalized["delivery_required"],
                evidence_text=normalized["evidence_text"],
                evidence_refs_json=normalized["evidence_refs_json"],
                confidence_score=normalized["confidence_score"],
                status=HwpxWorkItem.Status.DRAFT,
            )
        )
    if objects:
        HwpxWorkItem.objects.bulk_create(objects)


def _build_page_context(request, *, document=None, error_message="", info_message="", limit_message=""):
    work_items = list(document.work_items.order_by("sort_order", "id")) if document else []
    question_history = list(document.questions.order_by("-created_at", "-id")[:6]) if document else []
    return {
        "service": _get_service(),
        "current_document": document,
        "work_items": work_items,
        "question_history": question_history,
        "error_message": error_message,
        "info_message": info_message,
        "limit_message": limit_message,
        "has_document": bool(document),
        "download_markdown_url": _build_download_url(document),
        "document_detail_url": reverse("hwpxchat:document_detail", kwargs={"document_id": document.id}) if document else "",
    }


def _render_result(request, *, document=None, error_message="", info_message="", limit_message="", status=200):
    context = _build_page_context(
        request,
        document=document,
        error_message=error_message,
        info_message=info_message,
        limit_message=limit_message,
    )
    return render(request, "hwpxchat/partials/chat_result.html", context, status=status)


def _get_owner_document_or_404(user, document_id):
    return get_object_or_404(
        HwpxDocument.objects.prefetch_related("work_items", "questions").filter(owner=user),
        id=document_id,
    )


def _remember_document(request, document):
    request.session[HWPX_SESSION_DOCUMENT_KEY] = str(document.id)
    request.session.modified = True


def _get_last_document(request):
    document_id = request.session.get(HWPX_SESSION_DOCUMENT_KEY)
    if not document_id:
        return None
    return HwpxDocument.objects.filter(owner=request.user, id=document_id).prefetch_related("work_items", "questions").first()


def _build_download_url(document):
    if not document:
        return ""
    base_url = reverse("hwpxchat:download_markdown")
    return f"{base_url}?document_id={document.id}"


def _get_request_payload(request):
    if _is_json_request(request):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            return payload if isinstance(payload, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST


def _is_json_request(request):
    content_type = (request.content_type or "").split(";")[0].strip().lower()
    return content_type == "application/json"


def _as_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def _coerce_decimal(value):
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
