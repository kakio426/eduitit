import json
import logging
import os
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_GET, require_POST

from classcalendar.models import CalendarEvent, EventPageBlock
from core.product_visibility import is_sheetbook_discovery_visible
from products.models import Product
from sheetbook.models import SheetCell, Sheetbook

from .models import HwpxDocument, HwpxDocumentQuestion, HwpxWorkItem, HwpxWorkItemSync
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
    localize_due_date_to_event_window,
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
SHEETBOOK_RECENT_SHEETBOOK_ID_SESSION_KEY = "sheetbook_recent_sheetbook_id"
HWPX_CALENDAR_SOURCE = "hwpxchat_workitem"


def _get_service():
    product = Product.objects.filter(title=SERVICE_TITLE).first()
    if product:
        return product

    for legacy_title in LEGACY_SERVICE_TITLES:
        product = Product.objects.filter(title=legacy_title).first()
        if product:
            return product

    return Product.objects.filter(launch_route_name="hwpxchat:main").first()


def _is_sheetbook_companion_available():
    return bool(getattr(settings, "SHEETBOOK_ENABLED", False)) and is_sheetbook_discovery_visible()


def _ensure_sheetbook_companion_available():
    if _is_sheetbook_companion_available():
        return
    raise Http404("Sheetbook companion is hidden.")


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
def commit_document(request, document_id):
    _ensure_sheetbook_companion_available()
    document = _get_owner_document_or_404(request.user, document_id)
    payload = _get_request_payload(request)
    sheetbook = _resolve_sheetbook(request.user, payload.get("sheetbook_id"))
    if sheetbook is None:
        return _render_commit_error(request, document, "학급 기록 보드를 선택해 주세요.")

    from sheetbook.views import _next_row_order, _upsert_grid_cell_value, ensure_execution_tab

    execution_tab = ensure_execution_tab(sheetbook)
    column_map = {column.key: column for column in execution_tab.columns.order_by("sort_order", "id")}
    work_items = list(document.work_items.order_by("sort_order", "id"))
    requested_items = _extract_commit_items(payload, work_items)

    if not requested_items:
        return _render_commit_error(request, document, "보낼 업무를 하나 이상 선택해 주세요.")

    saved_count = 0
    updated_count = 0
    calendar_created_count = 0
    calendar_deleted_count = 0
    now_ts = timezone.now()

    with transaction.atomic():
        for item in requested_items:
            work_item = item["work_item"]
            _update_work_item_from_payload(work_item, item)
            sync, created_sync = HwpxWorkItemSync.objects.select_for_update().get_or_create(
                work_item=work_item,
                sheetbook=sheetbook,
                defaults={
                    "tab": execution_tab,
                    "calendar_enabled": item["calendar_enabled"],
                },
            )

            row = sync.row
            if row is None or row.tab_id != execution_tab.id:
                row = execution_tab.rows.create(
                    sort_order=_next_row_order(execution_tab),
                    created_by=request.user,
                    updated_by=request.user,
                )
            else:
                row.updated_by = request.user
                row.save(update_fields=["updated_by", "updated_at"])

            sync.tab = execution_tab
            sync.row = row
            sync.calendar_enabled = item["calendar_enabled"]
            sync.last_committed_at = now_ts

            _upsert_execution_cells(
                row=row,
                column_map=column_map,
                document=document,
                work_item=work_item,
                upsert_cell=_upsert_grid_cell_value,
            )

            event, was_created, was_deleted = _sync_calendar_event(
                request=request,
                document=document,
                work_item=work_item,
                sync=sync,
                calendar_enabled=item["calendar_enabled"],
            )
            sync.calendar_event = event
            sync.save()

            work_item.status = HwpxWorkItem.Status.SAVED
            work_item.save(update_fields=["status", "updated_at"])
            if created_sync:
                saved_count += 1
            else:
                updated_count += 1
            if was_created:
                calendar_created_count += 1
            if was_deleted:
                calendar_deleted_count += 1

    request.session[SHEETBOOK_RECENT_SHEETBOOK_ID_SESSION_KEY] = int(sheetbook.id)
    request.session.modified = True
    redirect_url = f"{reverse('sheetbook:detail', kwargs={'pk': sheetbook.id})}?tab={execution_tab.id}"

    if _is_json_request(request):
        return JsonResponse(
            {
                "status": "success",
                "saved_count": saved_count,
                "updated_count": updated_count,
                "calendar_created_count": calendar_created_count,
                "calendar_deleted_count": calendar_deleted_count,
                "sheetbook_id": sheetbook.id,
                "execution_tab_id": execution_tab.id,
                "redirect_url": redirect_url,
            }
        )

    messages.success(request, "학급 기록 보드 실행업무 탭에 담았어요.")
    return redirect(redirect_url)


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
    sheetbook_companion_available = _is_sheetbook_companion_available()
    sheetbook_options, selected_sheetbook_id = _get_sheetbook_options(request)
    work_items = list(document.work_items.order_by("sort_order", "id")) if document else []
    question_history = list(document.questions.order_by("-created_at", "-id")[:6]) if document else []
    can_commit = bool(
        sheetbook_companion_available
        and document
        and work_items
        and document.structure_status != HwpxDocument.StructureStatus.TOO_LARGE
    )
    return {
        "service": _get_service(),
        "current_document": document,
        "work_items": work_items,
        "question_history": question_history,
        "error_message": error_message,
        "info_message": info_message,
        "limit_message": limit_message,
        "has_document": bool(document),
        "can_commit": can_commit,
        "sheetbook_companion_available": sheetbook_companion_available,
        "sheetbook_options": sheetbook_options,
        "selected_sheetbook_id": selected_sheetbook_id,
        "download_markdown_url": _build_download_url(document),
        "document_detail_url": reverse("hwpxchat:document_detail", kwargs={"document_id": document.id}) if document else "",
        "sheetbook_index_url": reverse("sheetbook:index") if sheetbook_companion_available else "",
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


def _get_sheetbook_options(request):
    if not _is_sheetbook_companion_available():
        return [], 0

    sheetbooks = list(
        Sheetbook.objects.filter(owner=request.user)
        .prefetch_related("tabs")
        .order_by("-updated_at", "-id")
    )
    recent_sheetbook_id = 0
    try:
        recent_sheetbook_id = int(request.session.get(SHEETBOOK_RECENT_SHEETBOOK_ID_SESSION_KEY) or 0)
    except (TypeError, ValueError):
        recent_sheetbook_id = 0

    selected_sheetbook_id = 0
    if recent_sheetbook_id and any(sheetbook.id == recent_sheetbook_id for sheetbook in sheetbooks):
        selected_sheetbook_id = recent_sheetbook_id
    else:
        preferred_sheetbook = next((sheetbook for sheetbook in sheetbooks if sheetbook.preferred_calendar_tab_id), None)
        if preferred_sheetbook is not None:
            selected_sheetbook_id = preferred_sheetbook.id
        elif sheetbooks:
            selected_sheetbook_id = sheetbooks[0].id
    return sheetbooks, selected_sheetbook_id


def _resolve_sheetbook(user, raw_sheetbook_id):
    try:
        sheetbook_id = int(raw_sheetbook_id or 0)
    except (TypeError, ValueError):
        return None
    if not sheetbook_id:
        return None
    return Sheetbook.objects.filter(owner=user, id=sheetbook_id).first()


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


def _extract_commit_items(payload, work_items):
    if isinstance(payload.get("items"), list):
        items_by_id = {str(work_item.id): work_item for work_item in work_items}
        collected = []
        for raw_item in payload.get("items") or []:
            work_item = items_by_id.get(str(raw_item.get("work_item_id") or "").strip())
            if not work_item or not _as_bool(raw_item.get("selected")):
                continue
            collected.append(
                {
                    "work_item": work_item,
                    "title": raw_item.get("title"),
                    "action_text": raw_item.get("action_text"),
                    "due_date": raw_item.get("due_date"),
                    "start_time": raw_item.get("start_time"),
                    "end_time": raw_item.get("end_time"),
                    "is_all_day": raw_item.get("is_all_day"),
                    "assignee_text": raw_item.get("assignee_text"),
                    "target_text": raw_item.get("target_text"),
                    "materials_text": raw_item.get("materials_text"),
                    "delivery_required": raw_item.get("delivery_required"),
                    "evidence_text": raw_item.get("evidence_text"),
                    "calendar_enabled": _as_bool(raw_item.get("calendar_enabled")),
                }
            )
        return collected

    collected = []
    for work_item in work_items:
        item_id = str(work_item.id)
        if not _as_bool(payload.get(f"selected_{item_id}")):
            continue
        collected.append(
            {
                "work_item": work_item,
                "title": payload.get(f"title_{item_id}"),
                "action_text": payload.get(f"action_text_{item_id}"),
                "due_date": payload.get(f"due_date_{item_id}"),
                "start_time": payload.get(f"start_time_{item_id}"),
                "end_time": payload.get(f"end_time_{item_id}"),
                "is_all_day": payload.get(f"is_all_day_{item_id}"),
                "assignee_text": payload.get(f"assignee_text_{item_id}"),
                "target_text": payload.get(f"target_text_{item_id}"),
                "materials_text": payload.get(f"materials_text_{item_id}"),
                "delivery_required": payload.get(f"delivery_required_{item_id}"),
                "evidence_text": payload.get(f"evidence_text_{item_id}"),
                "calendar_enabled": _as_bool(payload.get(f"calendar_enabled_{item_id}")),
            }
        )
    return collected


def _update_work_item_from_payload(work_item, payload):
    work_item.title = str(payload.get("title") or work_item.title or "").strip()[:200]
    work_item.action_text = str(payload.get("action_text") or work_item.action_text or "").strip()
    raw_due_date = payload.get("due_date")
    work_item.due_date = parse_date(str(raw_due_date or "").strip()) if raw_due_date else None
    raw_start_time = payload.get("start_time")
    raw_end_time = payload.get("end_time")
    work_item.start_time = parse_time(str(raw_start_time or "").strip()) if raw_start_time else None
    work_item.end_time = parse_time(str(raw_end_time or "").strip()) if raw_end_time else None
    work_item.is_all_day = _as_bool(payload.get("is_all_day"))
    work_item.assignee_text = str(payload.get("assignee_text") or "").strip()[:120]
    work_item.target_text = str(payload.get("target_text") or "").strip()[:200]
    work_item.materials_text = str(payload.get("materials_text") or "").strip()
    work_item.delivery_required = _as_bool(payload.get("delivery_required"))
    work_item.evidence_text = str(payload.get("evidence_text") or "").strip()
    work_item.status = HwpxWorkItem.Status.CONFIRMED
    work_item.save()


def _upsert_execution_cells(*, row, column_map, document, work_item, upsert_cell):
    values = {
        "title": work_item.title,
        "action_text": work_item.action_text,
        "due_date": work_item.due_date,
        "assignee": work_item.assignee_text,
        "target": work_item.target_text,
        "materials": work_item.materials_text,
        "delivery_required": work_item.delivery_required,
        "evidence": work_item.evidence_text,
        "source_document": document.document_title,
    }
    for key, raw_value in values.items():
        column = column_map.get(key)
        if column is None:
            continue
        upsert_cell(row, column, raw_value)

    status_column = column_map.get("status")
    if status_column is not None:
        existing_status = SheetCell.objects.filter(row=row, column=status_column).first()
        if not existing_status or not (existing_status.value_text or "").strip():
            upsert_cell(row, status_column, "할 일")


def _sync_calendar_event(*, request, document, work_item, sync, calendar_enabled):
    if not calendar_enabled or work_item.due_date is None:
        deleted = False
        if sync.calendar_event_id:
            sync.calendar_event.delete()
            deleted = True
        return None, False, deleted

    start_dt, end_dt, is_all_day = localize_due_date_to_event_window(
        work_item.due_date,
        start_time=work_item.start_time,
        end_time=work_item.end_time,
        is_all_day=work_item.is_all_day,
    )
    integration_key = f"{document.id}:{work_item.id}"
    event = sync.calendar_event
    created = False
    if event is None:
        event, created = CalendarEvent.objects.get_or_create(
            author=request.user,
            integration_source=HWPX_CALENDAR_SOURCE,
            integration_key=integration_key,
            defaults={
                "title": work_item.title[:200],
                "start_time": start_dt,
                "end_time": end_dt,
                "is_all_day": is_all_day,
                "visibility": CalendarEvent.VISIBILITY_TEACHER,
                "source": CalendarEvent.SOURCE_LOCAL,
                "is_locked": False,
            },
        )
    event.title = work_item.title[:200]
    event.start_time = start_dt
    event.end_time = end_dt
    event.is_all_day = is_all_day
    event.visibility = CalendarEvent.VISIBILITY_TEACHER
    event.source = CalendarEvent.SOURCE_LOCAL
    event.integration_source = HWPX_CALENDAR_SOURCE
    event.integration_key = integration_key
    event.is_locked = False
    event.save()
    _persist_event_note(event, work_item)
    return event, created, False


def _persist_event_note(event, work_item):
    note_lines = [line for line in [work_item.action_text, f"근거: {work_item.evidence_text}" if work_item.evidence_text else ""] if line]
    note_text = "\n\n".join(note_lines).strip()
    blocks = event.blocks.filter(block_type="text").order_by("order", "id")
    primary_block = blocks.first()
    if not note_text:
        blocks.delete()
        return
    if primary_block is not None:
        primary_block.content = {"text": note_text}
        primary_block.order = 0
        primary_block.save(update_fields=["content", "order"])
        blocks.exclude(id=primary_block.id).delete()
        return
    EventPageBlock.objects.create(
        event=event,
        block_type="text",
        content={"text": note_text},
        order=0,
    )


def _render_commit_error(request, document, message):
    if _is_json_request(request):
        return JsonResponse({"status": "error", "message": message}, status=400)
    context = _build_page_context(request, document=document, error_message=message)
    return render(request, "hwpxchat/main.html", context, status=400)


def _as_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def _coerce_decimal(value):
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
