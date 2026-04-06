from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
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
from .services.law_api import (
    LawApiConfigError,
    LawApiError,
    LawApiTimeoutError,
    LawApiVerificationError,
    build_retry_after_timeout_message,
    is_configured as is_law_api_configured,
)
from .services.llm_client import LlmClientError, is_configured as is_llm_configured


logger = logging.getLogger(__name__)

SERVICE_ROUTE = "teacher_law:main"
SERVICE_TITLE = "교사용 AI 법률 가이드"


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
    citations = [
        {
            "law_name": citation.law_name,
            "law_id": citation.law_id,
            "mst": citation.mst,
            "article_label": citation.article_label,
            "quote": citation.quote,
            "source_url": citation.source_url,
            "fetched_at": citation.fetched_at.isoformat() if citation.fetched_at else "",
        }
        for citation in message.citations.all()
    ]
    return {
        "id": message.id,
        "role": message.role,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "created_at_display": message.created_at.strftime("%m.%d %H:%M"),
        "summary": payload.get("summary") or "",
        "action_items": list(payload.get("action_items") or []),
        "citations": citations,
        "risk_level": payload.get("risk_level") or "",
        "needs_human_help": bool(payload.get("needs_human_help")),
        "disclaimer": payload.get("disclaimer") or "",
        "scope_supported": payload.get("scope_supported", True),
    }


def _build_page_context(request):
    service = _get_service()
    session = get_or_create_active_session(request.user)
    messages_qs = session.messages.prefetch_related("citations").order_by("created_at", "id")
    warning_messages = []
    if not getattr(request.user, "is_authenticated", False):
        warning_messages.append("로그인 후 사용할 수 있습니다.")
    if not getattr(settings, "TEACHER_LAW_ENABLED", False):
        warning_messages.append("관리자가 아직 서비스를 켜지 않았습니다.")
    if not is_law_api_configured():
        warning_messages.append("관리자가 아직 법령 연결을 마치지 않았습니다.")
    if not is_llm_configured():
        warning_messages.append("관리자가 아직 답변 연결을 마치지 않았습니다.")

    return {
        "service": service,
        "title": service.title if service else SERVICE_TITLE,
        "page_title": service.title if service else SERVICE_TITLE,
        "service_enabled": getattr(settings, "TEACHER_LAW_ENABLED", False),
        "law_api_configured": is_law_api_configured(),
        "llm_configured": is_llm_configured(),
        "warning_messages": warning_messages,
        "quick_questions": get_quick_questions(),
        "session": session,
        "message_items": [_serialize_message(message) for message in messages_qs],
        "ask_url": reverse("teacher_law:ask"),
    }


def _daily_limit_exceeded(user_id: int) -> bool:
    from django.core.cache import cache
    from django.utils import timezone

    limit = int(getattr(settings, "TEACHER_LAW_DAILY_LIMIT_PER_USER", 20))
    cache_key = f"teacher_law:daily:{user_id}:{timezone.localdate().isoformat()}"
    current = cache.get(cache_key)
    if current is None:
        cache.set(cache_key, 1, timeout=86410)
        return False
    try:
        current = cache.incr(cache_key)
    except Exception:
        current = int(current) + 1
        cache.set(cache_key, current, timeout=86410)
    return int(current) > limit


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
            article_label=str(citation.get("article_label") or "").strip(),
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


@login_required
def main_view(request):
    return render(request, "teacher_law/main.html", _build_page_context(request))


@require_http_methods(["POST"])
@login_required
def ask_question_api(request):
    payload = _json_body(request) if _is_json_request(request) else None
    if _is_json_request(request) and payload is None:
        return _json_error("잘못된 요청 형식입니다.", status=400)

    question = (
        str((payload or {}).get("question") or "").strip()
        if _is_json_request(request)
        else str(request.POST.get("question") or "").strip()
    )
    if not question:
        if _is_json_request(request):
            return _json_error("질문을 입력해 주세요.", status=400)
        messages.error(request, "질문을 입력해 주세요.")
        return redirect("teacher_law:main")

    if _daily_limit_exceeded(request.user.id):
        message_text = "오늘 질문 가능 횟수를 모두 사용했어요. 내일 다시 시도해 주세요."
        if _is_json_request(request):
            return _json_error(message_text, status=429)
        messages.error(request, message_text)
        return redirect("teacher_law:main")

    session = get_or_create_active_session(request.user)
    user_message = LegalChatMessage.objects.create(
        session=session,
        role=LegalChatMessage.Role.USER,
        body=question,
    )

    try:
        result = answer_legal_question(question=question)
        profile = result.get("profile") or {}
        LegalChatMessage.objects.filter(id=user_message.id).update(
            normalized_question=profile.get("normalized_question") or "",
            is_quick_question=bool(profile.get("quick_question_key")),
        )
        user_message.refresh_from_db()
        assistant_message = _create_assistant_message(session, result.get("payload") or {})
        _persist_success_audit(session, user_message, assistant_message, result)
    except TeacherLawDisabledError:
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
                "status": "ok",
                "user_message": _serialize_message(user_message),
                "assistant_message": _serialize_message(assistant_message),
            },
            status=201,
        )
    return redirect("teacher_law:main")
