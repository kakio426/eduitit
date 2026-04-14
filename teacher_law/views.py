from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from products.models import Product

from .models import LegalCitation, LegalChatMessage, LegalQueryAudit
from .services.chat import (
    TeacherLawDisabledError,
    TeacherLawTimeoutError,
    answer_legal_question,
    build_answer_body,
    get_or_create_active_session,
    get_quick_questions,
)
from .services.query_normalizer import get_input_options, validate_structured_input
from .services.law_api import (
    LawApiConfigError,
    LawApiError,
    LawApiTimeoutError,
    LawApiVerificationError,
    build_retry_after_timeout_message,
    get_law_provider,
    is_configured as is_law_api_configured,
)
from .services.llm_client import LlmClientError, is_configured as is_llm_configured


logger = logging.getLogger(__name__)

SERVICE_ROUTE = "teacher_law:main"
SERVICE_TITLE = "교사용 AI 법률 가이드"
CLARIFY_DRAFT_SESSION_KEY = "teacher_law:clarify_draft"


def _get_service():
    return Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


def _is_json_request(request) -> bool:
    return "application/json" in (request.headers.get("Content-Type") or "")


def _serialize_message(message: LegalChatMessage) -> dict:
    payload = message.payload_json or {}
    payload_citations = list(payload.get("citations") or [])
    citations = []
    for index, citation in enumerate(message.citations.all()):
        payload_citation = payload_citations[index] if index < len(payload_citations) and isinstance(payload_citations[index], dict) else {}
        title = citation.law_name
        reference_label = citation.article_label or citation.case_number
        citations.append(
            {
                "citation_id": payload_citation.get("citation_id") or "",
                "source_type": citation.source_type,
                "title": title,
                "law_name": citation.law_name,
                "law_id": citation.law_id,
                "mst": citation.mst,
                "reference_label": reference_label,
                "article_label": citation.article_label,
                "case_number": citation.case_number,
                "quote": citation.quote,
                "source_url": citation.source_url,
                "provider": payload_citation.get("provider") or "",
                "fetched_at": citation.fetched_at.isoformat() if citation.fetched_at else "",
                "match_score": payload_citation.get("match_score"),
                "match_confidence": payload_citation.get("match_confidence") or "",
                "match_mismatch_reasons": list(payload_citation.get("match_mismatch_reasons") or []),
            }
        )
    law_citations = [citation for citation in citations if citation.get("source_type") != "case"]
    case_citations = [citation for citation in citations if citation.get("source_type") == "case"]
    representative_case = payload.get("representative_case") if isinstance(payload.get("representative_case"), dict) else None
    if not representative_case and case_citations:
        representative_case = case_citations[0]
    return {
        "id": message.id,
        "role": message.role,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "created_at_display": message.created_at.strftime("%m.%d %H:%M"),
        "summary": payload.get("summary") or "",
        "reasoning_summary": payload.get("reasoning_summary") or "",
        "action_items": list(payload.get("action_items") or []),
        "citations": citations,
        "law_citations": law_citations,
        "case_citations": case_citations,
        "risk_level": payload.get("risk_level") or "",
        "needs_human_help": bool(payload.get("needs_human_help")),
        "disclaimer": payload.get("disclaimer") or "",
        "scope_supported": payload.get("scope_supported", True),
        "status": payload.get("status") or "ok",
        "answer_held": bool(payload.get("answer_held")),
        "clarify_reason": payload.get("clarify_reason") or "",
        "clarify_needed": bool(payload.get("clarify_needed")),
        "clarify_questions": list(payload.get("clarify_questions") or []),
        "missing_facts": list(payload.get("missing_facts") or []),
        "representative_case": representative_case,
        "representative_case_confidence": payload.get("representative_case_confidence") or "",
        "representative_case_score": payload.get("representative_case_score"),
        "representative_case_mismatch_reasons": list(payload.get("representative_case_mismatch_reasons") or []),
        "representative_case_notice": payload.get("representative_case_notice") or "",
        "precedent_note": payload.get("precedent_note") or "",
        "precedent_screened_out": bool(payload.get("precedent_screened_out")),
    }


def _serialize_pair(user_message: LegalChatMessage, assistant_message: LegalChatMessage) -> dict:
    return {
        "pair_id": assistant_message.id,
        "user_message": _serialize_message(user_message),
        "assistant_message": _serialize_message(assistant_message),
    }


def _build_message_pairs(session) -> list[dict]:
    audits = (
        LegalQueryAudit.objects.filter(
            session=session,
            user_message__isnull=False,
            assistant_message__isnull=False,
        )
        .select_related("user_message", "assistant_message")
        .prefetch_related("assistant_message__citations")
        .order_by("assistant_message__created_at", "assistant_message__id")
    )
    pairs = []
    for audit in audits:
        if not audit.user_message or not audit.assistant_message:
            continue
        pairs.append(_serialize_pair(audit.user_message, audit.assistant_message))
    return pairs


def _build_page_context(request):
    service = _get_service()
    session = get_or_create_active_session(request.user)
    law_provider = get_law_provider()
    clarify_draft = _get_clarify_draft(request)
    input_options = get_input_options()
    warning_messages = []
    if not getattr(request.user, "is_authenticated", False):
        warning_messages.append("로그인 후 사용할 수 있습니다.")
    if not getattr(settings, "TEACHER_LAW_ENABLED", False):
        warning_messages.append("관리자가 아직 서비스를 켜지 않았습니다.")
    if not is_law_api_configured():
        warning_messages.append("관리자가 아직 법령 연결을 마치지 않았습니다.")
    if not is_llm_configured():
        warning_messages.append("관리자가 아직 답변 연결을 마치지 않았습니다.")
    if getattr(request.user, "is_authenticated", False) and _daily_limit_reached(request.user.id):
        warning_messages.append(_daily_limit_message())
    all_pairs = _build_message_pairs(session)
    latest_pair = all_pairs[-1] if all_pairs else None
    history_pairs = list(reversed(all_pairs[:-1]))[:6] if len(all_pairs) > 1 else []
    ui_blocked = bool(warning_messages)
    clarify_draft_requirement = ""
    incident_options = input_options["incident_options"]
    for option in incident_options:
        if option.get("value") == clarify_draft.get("incident_type"):
            clarify_draft_requirement = option.get("requires") or ""
            break

    return {
        "service": service,
        "title": service.title if service else SERVICE_TITLE,
        "page_title": service.title if service else SERVICE_TITLE,
        "service_enabled": getattr(settings, "TEACHER_LAW_ENABLED", False),
        "law_api_configured": is_law_api_configured(),
        "llm_configured": is_llm_configured(),
        "ui_blocked": ui_blocked,
        "ui_block_reason": " ".join(warning_messages).strip(),
        "law_data_notice": (
            "법령 데이터는 법망(API.beopmang.org)을 통해 조회되며, 답변은 참고용입니다."
            if law_provider == "beopmang"
            else ""
        ),
        "warning_messages": warning_messages,
        "quick_questions": get_quick_questions(),
        "incident_options": incident_options,
        **{key: value for key, value in input_options.items() if key != "incident_options"},
        "daily_limit_per_user": _daily_limit_per_user(),
        "session": session,
        "latest_pair": latest_pair,
        "history_pairs": history_pairs,
        "ask_url": reverse("teacher_law:ask"),
        "clarify_draft_question": clarify_draft.get("question") or "",
        "clarify_draft_incident_type": clarify_draft.get("incident_type") or "",
        "clarify_draft_legal_goal": clarify_draft.get("legal_goal") or "",
        "clarify_draft_scene": clarify_draft.get("scene") or "",
        "clarify_draft_counterpart": clarify_draft.get("counterpart") or "",
        "clarify_draft_requirement": clarify_draft_requirement,
    }


def _daily_limit_per_user() -> int:
    return max(int(getattr(settings, "TEACHER_LAW_DAILY_LIMIT_PER_USER", 15)), 0)


def _daily_limit_cache_key(user_id: int) -> str:
    return f"teacher_law:daily:{user_id}:{timezone.localdate().isoformat()}"


def _daily_limit_message(limit: int | None = None) -> str:
    effective_limit = _daily_limit_per_user() if limit is None else max(int(limit), 0)
    return f"오늘 질문 {effective_limit}회를 모두 사용했어요. 내일 다시 시도해 주세요."


def _daily_limit_reached(user_id: int) -> bool:
    limit = _daily_limit_per_user()
    if limit <= 0:
        return True
    current = cache.get(_daily_limit_cache_key(user_id)) or 0
    try:
        current = int(current)
    except (TypeError, ValueError):
        current = 0
    return current >= limit


def _reserve_daily_limit(user_id: int) -> bool:
    limit = _daily_limit_per_user()
    if limit <= 0:
        return False
    if _daily_limit_reached(user_id):
        return False

    cache_key = _daily_limit_cache_key(user_id)
    current = cache.get(cache_key)
    if current is None:
        cache.set(cache_key, 1, timeout=86410)
        return True
    try:
        current = cache.incr(cache_key)
    except Exception:
        current = int(current) + 1
        cache.set(cache_key, current, timeout=86410)
    return int(current) <= limit


def _release_daily_limit(user_id: int) -> None:
    cache_key = _daily_limit_cache_key(user_id)
    current = cache.get(cache_key)
    if current is None:
        return
    try:
        current = int(current)
    except (TypeError, ValueError):
        current = 0
    if current <= 1:
        cache.delete(cache_key)
        return
    cache.set(cache_key, current - 1, timeout=86410)


def _get_clarify_draft(request) -> dict:
    raw_draft = {}
    if getattr(request, "session", None) is not None:
        raw_draft = request.session.get(CLARIFY_DRAFT_SESSION_KEY) or {}
    if not isinstance(raw_draft, dict):
        return {}
    return {
        "question": str(raw_draft.get("question") or "").strip(),
        "incident_type": str(raw_draft.get("incident_type") or "").strip(),
        "legal_goal": str(raw_draft.get("legal_goal") or "").strip(),
        "scene": str(raw_draft.get("scene") or "").strip(),
        "counterpart": str(raw_draft.get("counterpart") or "").strip(),
    }


def _store_clarify_draft(request, *, question: str, incident_type: str, legal_goal: str, scene: str, counterpart: str) -> None:
    if getattr(request, "session", None) is None:
        return
    request.session[CLARIFY_DRAFT_SESSION_KEY] = {
        "question": str(question or "").strip(),
        "incident_type": str(incident_type or "").strip(),
        "legal_goal": str(legal_goal or "").strip(),
        "scene": str(scene or "").strip(),
        "counterpart": str(counterpart or "").strip(),
    }
    if hasattr(request.session, "modified"):
        request.session.modified = True


def _clear_clarify_draft(request) -> None:
    if getattr(request, "session", None) is None:
        return
    if CLARIFY_DRAFT_SESSION_KEY in request.session:
        del request.session[CLARIFY_DRAFT_SESSION_KEY]
        if hasattr(request.session, "modified"):
            request.session.modified = True


def _create_assistant_message(session, payload: dict):
    assistant_message = LegalChatMessage.objects.create(
        session=session,
        role=LegalChatMessage.Role.ASSISTANT,
        body=build_answer_body(payload),
        payload_json=payload,
    )
    for order, citation in enumerate(payload.get("citations") or [], start=1):
        fetched_at_raw = citation.get("fetched_at") or ""
        fetched_at = parse_datetime(str(fetched_at_raw)) if fetched_at_raw else None
        LegalCitation.objects.create(
            message=assistant_message,
            law_name=str(citation.get("law_name") or "").strip(),
            law_id=str(citation.get("law_id") or "").strip(),
            mst=str(citation.get("mst") or "").strip(),
            source_type=str(citation.get("source_type") or LegalCitation.SourceType.LAW).strip(),
            article_label=str(citation.get("article_label") or "").strip(),
            case_number=str(citation.get("case_number") or "").strip(),
            quote=str(citation.get("quote") or "").strip(),
            source_url=str(citation.get("source_url") or "").strip(),
            fetched_at=fetched_at or assistant_message.created_at,
            display_order=order,
        )
    return assistant_message


def _persist_success_audit(session, user_message, assistant_message, result: dict):
    profile = result.get("profile") or {}
    audit = result.get("audit") or {}
    return LegalQueryAudit.objects.create(
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        original_question=profile.get("original_question") or user_message.body,
        normalized_question=profile.get("normalized_question") or "",
        topic=profile.get("topic") or "",
        scope_supported=bool(profile.get("scope_supported", True)),
        risk_flags_json=list(profile.get("risk_flags") or []),
        candidate_queries_json=list(profile.get("candidate_queries") or []),
        selected_laws_json=list(audit.get("selected_laws_json") or []),
        search_attempt_count=int(audit.get("search_attempt_count") or 0),
        search_result_count=int(audit.get("search_result_count") or 0),
        detail_fetch_count=int(audit.get("detail_fetch_count") or 0),
        cache_hit=bool(audit.get("cache_hit")),
        elapsed_ms=int(audit.get("elapsed_ms") or 0),
        failure_reason=str(audit.get("failure_reason") or "").strip(),
        error_message=str(audit.get("error_message") or "").strip(),
    )


def _persist_error_audit(session, user_message, *, question: str, failure_reason: str, error_message: str):
    return LegalQueryAudit.objects.create(
        session=session,
        user_message=user_message,
        original_question=question,
        normalized_question="",
        topic="",
        scope_supported=True,
        risk_flags_json=[],
        candidate_queries_json=[],
        selected_laws_json=[],
        search_attempt_count=0,
        search_result_count=0,
        detail_fetch_count=0,
        cache_hit=False,
        elapsed_ms=0,
        failure_reason=failure_reason,
        error_message=error_message,
    )


def _json_error(message_text: str, *, status: int):
    return JsonResponse({"status": "error", "message": message_text}, status=status)


def _read_request_value(request, payload: dict | None, field_name: str) -> str:
    if _is_json_request(request):
        return str((payload or {}).get(field_name) or "").strip()
    return str(request.POST.get(field_name) or "").strip()


@login_required
def main_view(request):
    return render(request, "teacher_law/main.html", _build_page_context(request))


@require_http_methods(["POST"])
@login_required
def ask_question_api(request):
    payload = _json_body(request) if _is_json_request(request) else None
    if _is_json_request(request) and payload is None:
        return _json_error("잘못된 요청 형식입니다.", status=400)

    question = _read_request_value(request, payload, "question")
    incident_type = _read_request_value(request, payload, "incident_type")
    legal_goal = _read_request_value(request, payload, "legal_goal")
    scene = _read_request_value(request, payload, "scene")
    counterpart = _read_request_value(request, payload, "counterpart")

    if not question:
        if _is_json_request(request):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "질문을 입력해 주세요.",
                    "field_errors": {"question": "질문을 입력해 주세요."},
                },
                status=400,
            )
        messages.error(request, "질문을 입력해 주세요.")
        return redirect("teacher_law:main")

    field_errors = validate_structured_input(
        incident_type=incident_type,
        legal_goal=legal_goal,
        scene=scene,
        counterpart=counterpart,
    )
    if field_errors:
        if _is_json_request(request):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "필수 항목을 먼저 선택해 주세요.",
                    "field_errors": field_errors,
                },
                status=400,
            )
        messages.error(request, "필수 항목을 먼저 선택해 주세요.")
        return redirect("teacher_law:main")

    if not _reserve_daily_limit(request.user.id):
        message_text = _daily_limit_message()
        if _is_json_request(request):
            return _json_error(message_text, status=429)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    daily_limit_reserved = True

    session = get_or_create_active_session(request.user)
    user_message = LegalChatMessage.objects.create(
        session=session,
        role=LegalChatMessage.Role.USER,
        body=question,
    )

    try:
        result = answer_legal_question(
            question=question,
            incident_type=incident_type,
            legal_goal=legal_goal,
            scene=scene,
            counterpart=counterpart,
        )
        profile = result.get("profile") or {}
        LegalChatMessage.objects.filter(id=user_message.id).update(
            normalized_question=profile.get("normalized_question") or "",
            is_quick_question=bool(profile.get("quick_question_key")),
        )
        user_message.refresh_from_db()
        assistant_message = _create_assistant_message(session, result.get("payload") or {})
        _persist_success_audit(session, user_message, assistant_message, result)
        if (result.get("status") or "ok") == "clarify":
            _store_clarify_draft(
                request,
                question=question,
                incident_type=incident_type,
                legal_goal=legal_goal,
                scene=scene,
                counterpart=counterpart,
            )
            if daily_limit_reserved:
                _release_daily_limit(request.user.id)
                daily_limit_reserved = False
        else:
            _clear_clarify_draft(request)
    except TeacherLawDisabledError:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="disabled",
            error_message="teacher_law_disabled",
        )
        message_text = "관리자가 아직 교사용 AI 법률 가이드를 켜지 않았습니다."
        if _is_json_request(request):
            return _json_error(message_text, status=503)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    except LawApiConfigError:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="law_api_config",
            error_message="law_api_missing",
        )
        message_text = "관리자가 아직 법령 연결을 마치지 않았습니다."
        if _is_json_request(request):
            return _json_error(message_text, status=503)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    except LawApiVerificationError as exc:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        verification_message = str(exc).strip()
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="law_api_verification",
            error_message=verification_message or "law_api_domain_registration_required",
        )
        if "ip주소" in verification_message.lower() or "도메인주소" in verification_message.lower():
            message_text = "국가법령정보에서 도메인 또는 서버 IP 검증에 실패했습니다. 등록 정보를 다시 확인해 주세요."
        else:
            message_text = verification_message or "법령 연결 점검이 필요합니다. 잠시 후 다시 시도해 주세요."
        if _is_json_request(request):
            return _json_error(message_text, status=503)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    except LawApiTimeoutError:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="law_api_timeout",
            error_message="law_api_timeout",
        )
        message_text = build_retry_after_timeout_message()
        if _is_json_request(request):
            return _json_error(message_text, status=504)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    except TeacherLawTimeoutError:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="teacher_law_timeout",
            error_message="teacher_law_timeout",
        )
        message_text = build_retry_after_timeout_message()
        if _is_json_request(request):
            return _json_error(message_text, status=504)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    except LlmClientError:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="llm_error",
            error_message="deepseek_error",
        )
        message_text = "답변 연결 점검이 필요합니다. 잠시 후 다시 시도해 주세요."
        if _is_json_request(request):
            return _json_error(message_text, status=503)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    except LawApiError:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        logger.exception("[TeacherLaw] law api error")
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="law_api_error",
            error_message="law_api_error",
        )
        message_text = "법령 정보를 확인하는 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요."
        if _is_json_request(request):
            return _json_error(message_text, status=503)
        messages.error(request, message_text)
        return redirect("teacher_law:main")
    except Exception:
        if daily_limit_reserved:
            _release_daily_limit(request.user.id)
        logger.exception("[TeacherLaw] unexpected error")
        _persist_error_audit(
            session,
            user_message,
            question=question,
            failure_reason="unexpected",
            error_message="unexpected_error",
        )
        message_text = "답변을 준비하는 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요."
        if _is_json_request(request):
            return _json_error(message_text, status=500)
        messages.error(request, message_text)
        return redirect("teacher_law:main")

    if _is_json_request(request):
        return JsonResponse(
            {
                "status": result.get("status") or "ok",
                "user_message": _serialize_message(user_message),
                "assistant_message": _serialize_message(assistant_message),
            },
            status=201 if (result.get("status") or "ok") == "ok" else 200,
        )
    return redirect("teacher_law:main")
