from __future__ import annotations

import hashlib
import logging
from time import perf_counter

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from teacher_law.models import LegalChatSession

from .law_api import (
    build_cache_expiry,
    get_cache_date_token,
    get_law_details,
    get_law_provider,
    is_configured as is_law_api_configured,
    rank_search_results,
    search_laws,
    select_relevant_citations,
)
from .llm_client import LlmClientError, generate_legal_answer, is_configured as is_llm_configured
from .query_normalizer import ANSWER_POLICY_VERSION, QUICK_QUESTIONS, build_query_profile, compact_text


logger = logging.getLogger(__name__)


class TeacherLawError(Exception):
    pass


class TeacherLawDisabledError(TeacherLawError):
    pass


class TeacherLawTimeoutError(TeacherLawError):
    pass


def get_quick_questions() -> list[str]:
    return list(QUICK_QUESTIONS)


def get_or_create_active_session(user) -> LegalChatSession:
    session = (
        LegalChatSession.objects.filter(user=user, is_active=True)
        .order_by("-last_message_at", "-updated_at", "-id")
        .first()
    )
    if session:
        return session
    return LegalChatSession.objects.create(user=user)


def build_answer_body(payload: dict) -> str:
    action_items = [item for item in (payload.get("action_items") or []) if str(item).strip()]
    citations = [item for item in (payload.get("citations") or []) if isinstance(item, dict)]
    lines = [
        "핵심 답변",
        payload.get("summary") or "추가 확인 필요",
    ]
    if action_items:
        lines.extend(["", "지금 바로 할 일"])
        lines.extend(f"- {item}" for item in action_items[:4])
    if citations:
        lines.extend(["", "근거 조문"])
        for citation in citations[:3]:
            citation_label = " / ".join(
                part
                for part in [
                    compact_text(citation.get("law_name")),
                    compact_text(citation.get("article_label")),
                ]
                if part
            )
            if citation_label:
                lines.append(f"- {citation_label}")
    if payload.get("needs_human_help"):
        lines.extend(["", "사람 상담 권장", "- 고위험 사안일 수 있어 학교 관리자나 전문 상담을 함께 권장합니다."])
    disclaimer = compact_text(payload.get("disclaimer"))
    if disclaimer:
        lines.extend(["", disclaimer])
    return "\n".join(lines).strip()


def answer_legal_question(*, question: str) -> dict:
    started = perf_counter()
    profile = build_query_profile(question)
    law_provider = get_law_provider()
    if not getattr(settings, "TEACHER_LAW_ENABLED", False):
        raise TeacherLawDisabledError("교사용 AI 법률 가이드가 아직 활성화되지 않았습니다.")

    if not profile.get("scope_supported"):
        payload = _build_out_of_scope_payload(profile)
        return {
            "profile": profile,
            "payload": payload,
            "audit": {
                "cache_hit": False,
                "search_attempt_count": 0,
                "search_result_count": 0,
                "detail_fetch_count": 0,
                "selected_laws_json": [],
                "failure_reason": "out_of_scope",
                "error_message": "",
                "elapsed_ms": _elapsed_ms(started),
            },
        }

    cache_key = ""
    cached_payload = None
    if profile.get("quick_question_key"):
        cache_key = _build_cache_key(profile)
        cached_payload = _restore_cache_payload(cache.get(cache_key))
    if cached_payload:
        logger.info(
            "[TeacherLaw] Action: QUICK_CACHE_HIT, Status: SUCCESS, Topic: %s, Provider: %s",
            profile.get("topic") or "unknown",
            law_provider,
        )
        return {
            "profile": profile,
            "payload": cached_payload,
            "audit": {
                "cache_hit": True,
                "search_attempt_count": 0,
                "search_result_count": 0,
                "detail_fetch_count": 0,
                "selected_laws_json": _serialize_selected_laws(cached_payload.get("citations") or []),
                "failure_reason": "",
                "error_message": "",
                "elapsed_ms": _elapsed_ms(started),
            },
        }

    if not is_llm_configured():
        raise LlmClientError("DeepSeek API key가 아직 연결되지 않았습니다.")
    if not is_law_api_configured():
        from .law_api import LawApiConfigError

        raise LawApiConfigError("국가법령정보 API 인증값이 아직 연결되지 않았습니다.")

    total_timeout_seconds = int(getattr(settings, "TEACHER_LAW_TOTAL_TIMEOUT_SECONDS", 20))
    detail_limit = int(getattr(settings, "TEACHER_LAW_DETAIL_FETCH_LIMIT", 3))
    candidate_queries = list(profile.get("candidate_queries") or [])[:2]

    search_attempt_count = 0
    search_result_count = 0
    detail_fetch_count = 0
    selected_laws = []
    aggregated_results = []
    collected_citations = []
    law_query_hint = _build_law_query_hint(profile)

    for query in candidate_queries:
        _ensure_total_timeout(started, total_timeout_seconds)
        search_attempt_count += 1
        search_results = search_laws(query, search=1)
        search_result_count += len(search_results)
        aggregated_results.extend(search_results)
        if search_results:
            break

    ranked_results = _dedupe_search_results(rank_search_results(aggregated_results, profile))
    for ranked in ranked_results[:detail_limit]:
        _ensure_total_timeout(started, total_timeout_seconds)
        detail_fetch_count += 1
        detail = get_law_details(
            law_id=ranked.get("law_id") or "",
            mst=ranked.get("mst") or "",
            detail_link=ranked.get("detail_link") or "",
            query_hint=law_query_hint,
            law_name=ranked.get("law_name") or "",
        )
        selected_laws.append(
            {
                "law_name": detail.get("law_name") or ranked.get("law_name") or "",
                "law_id": detail.get("law_id") or ranked.get("law_id") or "",
                "mst": detail.get("mst") or ranked.get("mst") or "",
                "detail_link": detail.get("detail_link") or ranked.get("detail_link") or "",
                "provider": detail.get("provider") or ranked.get("provider") or law_provider,
            }
        )
        collected_citations.extend(select_relevant_citations(detail, profile, limit=2))
        if len(collected_citations) >= 3:
            break

    citations = _dedupe_citations(collected_citations)[:3]
    if not citations:
        payload = _build_insufficient_payload(profile, selected_laws)
        audit = {
            "cache_hit": False,
            "search_attempt_count": search_attempt_count,
            "search_result_count": search_result_count,
            "detail_fetch_count": detail_fetch_count,
            "selected_laws_json": selected_laws,
            "failure_reason": "insufficient_citations",
            "error_message": "",
            "elapsed_ms": _elapsed_ms(started),
        }
        logger.info(
            "[TeacherLaw] Action: GENERATE_ANSWER, Status: SUCCESS, Topic: %s, Outcome: insufficient, Provider: %s",
            profile.get("topic") or "unknown",
            law_provider,
        )
        return {"profile": profile, "payload": payload, "audit": audit}

    _ensure_total_timeout(started, total_timeout_seconds)
    llm_answer = generate_legal_answer(
        question=profile.get("original_question") or question,
        profile=profile,
        citations=citations,
        timeout_seconds=int(getattr(settings, "TEACHER_LAW_LLM_TIMEOUT_SECONDS", 12)),
    )
    payload = _normalize_answer_payload(llm_answer, citations, profile)
    audit = {
        "cache_hit": False,
        "search_attempt_count": search_attempt_count,
        "search_result_count": search_result_count,
        "detail_fetch_count": detail_fetch_count,
        "selected_laws_json": selected_laws,
        "failure_reason": "",
        "error_message": "",
        "elapsed_ms": _elapsed_ms(started),
    }
    if cache_key:
        cache.set(cache_key, _serialize_cache_payload(payload), timeout=build_cache_expiry())
    logger.info(
        "[TeacherLaw] Action: GENERATE_ANSWER, Status: SUCCESS, Topic: %s, Cache: %s, Provider: %s",
        profile.get("topic") or "unknown",
        "hit" if audit["cache_hit"] else "miss",
        law_provider,
    )
    return {"profile": profile, "payload": payload, "audit": audit}


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _ensure_total_timeout(started: float, limit_seconds: int) -> None:
    if perf_counter() - started > limit_seconds:
        raise TeacherLawTimeoutError("법령 확인 시간이 길어져 잠시 후 다시 시도해 주세요.")


def _build_law_query_hint(profile: dict) -> str:
    hint_queries = [compact_text(item) for item in profile.get("hint_queries") or [] if compact_text(item)]
    if hint_queries:
        return hint_queries[0]
    core_terms = [compact_text(item) for item in profile.get("core_terms") or [] if compact_text(item)]
    if core_terms:
        return " ".join(core_terms[:4])
    return compact_text(profile.get("original_question") or profile.get("normalized_question"))


def _dedupe_search_results(results: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for result in results:
        key = (result.get("law_id") or "", result.get("mst") or "", result.get("law_name") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _dedupe_citations(citations: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for citation in citations:
        key = (
            citation.get("law_name") or "",
            citation.get("article_label") or "",
            citation.get("quote") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


def _build_cache_key(profile: dict) -> str:
    normalized = compact_text(profile.get("quick_question_key") or profile.get("normalized_matching_question") or "")
    normalized_hash = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    return ":".join(
        [
            "teacher_law",
            "faq",
            normalized_hash,
            ANSWER_POLICY_VERSION,
            get_cache_date_token(),
        ]
    )


def _build_out_of_scope_payload(profile: dict) -> dict:
    return {
        "summary": "학교 현장과 직접 관련된 법률 질문을 우선 안내하고 있어요. 학교 밖 개인 생활 법률은 아직 정확하게 답하기 어려워요.",
        "action_items": [
            "교사·학생·학부모·교실·수업 중 어떤 상황인지 함께 적어 주세요.",
            "학교 밖 개인 생활 분쟁이라면 전문 상담 기관이나 변호사 상담을 함께 검토해 주세요.",
        ],
        "citations": [],
        "risk_level": "medium",
        "needs_human_help": False,
        "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
        "scope_supported": False,
    }


def _build_insufficient_payload(profile: dict, selected_laws: list[dict]) -> dict:
    citations = []
    fetched_at = timezone.now().isoformat()
    for law in selected_laws[:2]:
        law_name = compact_text(law.get("law_name"))
        if not law_name:
            continue
        citations.append(
            {
                "citation_id": f"source-{law.get('law_id') or law.get('mst') or law_name}",
                "law_name": law_name,
                "law_id": law.get("law_id") or "",
                "mst": law.get("mst") or "",
                "article_label": "관련 조문 추가 확인 필요",
                "quote": "검색된 법령은 있으나 질문과 직접 맞는 조문을 더 확인해야 합니다.",
                "source_url": law.get("detail_link") or "",
                "fetched_at": fetched_at,
            }
        )
    return {
        "summary": "질문과 바로 연결되는 조문을 충분히 찾지 못해 추가 확인이 필요합니다.",
        "action_items": [
            "상황을 더 구체적으로 적어 주세요. 예: 사진 게시, 학폭 초기 대응, 생활지도 중 신체 접촉",
            "학교 규정이나 교육청 지침이 있다면 함께 확인해 주세요.",
        ],
        "citations": citations,
        "risk_level": "medium",
        "needs_human_help": bool(profile.get("risk_flags")),
        "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
        "scope_supported": True,
    }


def _normalize_answer_payload(answer: dict, citations: list[dict], profile: dict) -> dict:
    selected_ids = [item for item in (answer.get("citations") or []) if str(item).strip()]
    visible_citations = [citation for citation in citations if citation.get("citation_id") in selected_ids]
    if not visible_citations:
        visible_citations = citations[:2]

    risk_level = str(answer.get("risk_level") or "medium").strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "medium"

    needs_human_help = bool(answer.get("needs_human_help")) or bool(profile.get("risk_flags"))
    if needs_human_help:
        risk_level = "high" if risk_level != "high" else risk_level

    action_items = [compact_text(item) for item in (answer.get("action_items") or []) if compact_text(item)]
    summary = compact_text(answer.get("summary"))
    if not summary:
        summary = "추가 확인 필요"
        needs_human_help = True

    return {
        "summary": summary,
        "action_items": action_items[:4],
        "citations": visible_citations,
        "risk_level": risk_level,
        "needs_human_help": needs_human_help,
        "disclaimer": compact_text(
            answer.get("disclaimer") or "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다."
        ),
        "scope_supported": bool(answer.get("scope_supported", True)),
    }


def _serialize_cache_payload(payload: dict) -> dict:
    serialized = {
        "summary": payload.get("summary") or "",
        "action_items": list(payload.get("action_items") or []),
        "citations": [],
        "risk_level": payload.get("risk_level") or "medium",
        "needs_human_help": bool(payload.get("needs_human_help")),
        "disclaimer": payload.get("disclaimer") or "",
        "scope_supported": bool(payload.get("scope_supported", True)),
    }
    for citation in payload.get("citations") or []:
        if not isinstance(citation, dict):
            continue
        serialized["citations"].append(
            {
                "citation_id": citation.get("citation_id") or "",
                "law_name": citation.get("law_name") or "",
                "law_id": citation.get("law_id") or "",
                "mst": citation.get("mst") or "",
                "article_label": citation.get("article_label") or "",
                "quote": citation.get("quote") or "",
                "source_url": citation.get("source_url") or "",
                "fetched_at": citation.get("fetched_at") or "",
            }
        )
    return serialized


def _restore_cache_payload(raw_payload):
    if not isinstance(raw_payload, dict):
        return None
    citations = []
    for citation in raw_payload.get("citations") or []:
        if not isinstance(citation, dict):
            continue
        citations.append(citation)
    return {
        "summary": compact_text(raw_payload.get("summary")),
        "action_items": [compact_text(item) for item in raw_payload.get("action_items") or [] if compact_text(item)],
        "citations": citations,
        "risk_level": compact_text(raw_payload.get("risk_level") or "medium") or "medium",
        "needs_human_help": bool(raw_payload.get("needs_human_help")),
        "disclaimer": compact_text(
            raw_payload.get("disclaimer") or "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다."
        ),
        "scope_supported": bool(raw_payload.get("scope_supported", True)),
    }


def _serialize_selected_laws(citations: list[dict]) -> list[dict]:
    provider = get_law_provider()
    selected = []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        selected.append(
            {
                "law_name": citation.get("law_name") or "",
                "law_id": citation.get("law_id") or "",
                "mst": citation.get("mst") or "",
                "detail_link": citation.get("source_url") or "",
                "provider": citation.get("provider") or provider,
            }
        )
    return selected
