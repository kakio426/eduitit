from __future__ import annotations

import hashlib
import logging
import re
from time import perf_counter

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from teacher_law.models import LegalChatSession

from .law_api import (
    LawApiError,
    LawApiTimeoutError,
    build_cache_expiry,
    get_cache_date_token,
    get_law_details,
    get_law_provider,
    is_configured as is_law_api_configured,
    rank_search_results,
    search_cases,
    search_laws,
    select_relevant_case_citations,
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
    law_citations = [item for item in citations if item.get("source_type") != "case"]
    case_citations = [item for item in citations if item.get("source_type") == "case"]

    lines = [
        "핵심 답변",
        payload.get("summary") or "추가 확인 필요",
    ]

    if citations:
        lines.extend(["", "이번 답변에서 먼저 본 것"])
        if law_citations:
            law_titles = ", ".join(_citation_title(item) for item in law_citations[:2] if _citation_title(item))
            if law_titles:
                lines.append(f"- 기본 법령: {law_titles}")
        if case_citations:
            case_titles = ", ".join(_citation_title(item) for item in case_citations[:2] if _citation_title(item))
            if case_titles:
                lines.append(f"- 참고 판례: {case_titles}")

    if action_items:
        lines.extend(["", "지금 바로 할 일"])
        lines.extend(f"- {item}" for item in action_items[:4])

    if law_citations:
        lines.extend(["", "기본 법령"])
        for citation in law_citations[:2]:
            citation_label = " / ".join(
                part
                for part in [
                    compact_text(citation.get("title") or citation.get("law_name")),
                    compact_text(citation.get("reference_label") or citation.get("article_label")),
                ]
                if part
            )
            if citation_label:
                lines.append(f"- {citation_label}")

    if case_citations:
        lines.extend(["", "참고 판례"])
        for citation in case_citations[:2]:
            citation_label = " / ".join(
                part
                for part in [
                    compact_text(citation.get("title") or citation.get("law_name")),
                    compact_text(citation.get("reference_label") or citation.get("article_label")),
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
    candidate_queries = list(profile.get("candidate_queries") or [])[:3]
    case_queries = list(profile.get("case_queries") or [])[:2]

    search_attempt_count = 0
    search_result_count = 0
    detail_fetch_count = 0
    selected_sources = []
    aggregated_results = []
    collected_law_citations = []
    related_case_results = []
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
        selected_sources.append(
            {
                "source_type": "law",
                "law_name": detail.get("law_name") or ranked.get("law_name") or "",
                "title": detail.get("law_name") or ranked.get("law_name") or "",
                "law_id": detail.get("law_id") or ranked.get("law_id") or "",
                "mst": detail.get("mst") or ranked.get("mst") or "",
                "detail_link": detail.get("detail_link") or ranked.get("detail_link") or "",
                "reference_label": "",
                "provider": detail.get("provider") or ranked.get("provider") or law_provider,
            }
        )
        collected_law_citations.extend(select_relevant_citations(detail, profile, limit=2))
        related_case_results.extend(detail.get("related_cases") or [])
        if len(collected_law_citations) >= 3:
            break

    law_citations = _dedupe_citations(collected_law_citations)
    first_law_id = next((item.get("law_id") for item in selected_sources if item.get("source_type") == "law" and item.get("law_id")), "")
    first_article_ref = _extract_reference_label(law_citations[0].get("reference_label")) if law_citations else ""

    collected_case_citations = []
    if law_citations:
        deduped_case_results = _dedupe_case_results(related_case_results)
        if deduped_case_results:
            collected_case_citations.extend(
                select_relevant_case_citations(
                    deduped_case_results,
                    profile,
                    limit=2,
                    law_id=first_law_id,
                )
            )
        if not collected_case_citations:
            for query in case_queries:
                _ensure_total_timeout(started, total_timeout_seconds)
                search_attempt_count += 1
                try:
                    case_results = search_cases(query, law_id=first_law_id, article=first_article_ref, display=2)
                except (LawApiError, LawApiTimeoutError) as exc:
                    logger.warning("[TeacherLaw] case search skipped: %s", exc)
                    continue
                search_result_count += len(case_results)
                if not case_results:
                    continue
                collected_case_citations.extend(
                    select_relevant_case_citations(
                        case_results,
                        profile,
                        limit=2,
                        law_id=first_law_id,
                    )
                )
                if collected_case_citations:
                    break

    case_citations = _dedupe_citations(collected_case_citations)
    for citation in case_citations[:2]:
        selected_sources.append(
            {
                "source_type": "case",
                "law_name": citation.get("title") or citation.get("law_name") or "",
                "title": citation.get("title") or citation.get("law_name") or "",
                "law_id": citation.get("law_id") or "",
                "mst": "",
                "detail_link": citation.get("source_url") or "",
                "reference_label": citation.get("reference_label") or "",
                "case_number": citation.get("case_number") or "",
                "provider": citation.get("provider") or law_provider,
            }
        )

    visible_citations = law_citations[:2] + case_citations[:2]
    if not law_citations:
        payload = _build_insufficient_payload(profile, selected_sources)
        audit = {
            "cache_hit": False,
            "search_attempt_count": search_attempt_count,
            "search_result_count": search_result_count,
            "detail_fetch_count": detail_fetch_count,
            "selected_laws_json": selected_sources,
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
        citations=visible_citations,
        timeout_seconds=int(getattr(settings, "TEACHER_LAW_LLM_TIMEOUT_SECONDS", 12)),
    )
    payload = _normalize_answer_payload(llm_answer, visible_citations, profile)
    audit = {
        "cache_hit": False,
        "search_attempt_count": search_attempt_count,
        "search_result_count": search_result_count,
        "detail_fetch_count": detail_fetch_count,
        "selected_laws_json": selected_sources,
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
    search_terms = [compact_text(item) for item in profile.get("search_terms") or [] if compact_text(item)]
    if search_terms:
        return " ".join(search_terms[:4])
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


def _dedupe_case_results(results: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for result in results:
        key = (
            result.get("case_id") or "",
            result.get("case_number") or "",
            result.get("title") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _citation_title(citation: dict) -> str:
    return compact_text(citation.get("title") or citation.get("law_name"))


def _dedupe_citations(citations: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for citation in citations:
        key = (
            citation.get("source_type") or "law",
            _citation_title(citation),
            citation.get("reference_label") or citation.get("article_label") or "",
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
        "summary": "학교 현장과 직접 연결된 법률 질문을 먼저 안내하고 있어요. 학교 밖 개인 생활 분쟁은 아직 정확하게 답하기 어렵습니다.",
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


def _build_placeholder_citation(source: dict, *, fetched_at: str) -> dict:
    title = compact_text(source.get("title") or source.get("law_name"))
    reference_label = compact_text(source.get("reference_label"))
    source_type = source.get("source_type") or "law"
    quote = (
        "기본 법령은 확인됐지만 질문과 바로 맞는 조문 연결이 약합니다."
        if source_type == "law"
        else "기본 법령은 확인됐지만 대표 판례 연결은 더 검토가 필요합니다."
    )
    return {
        "citation_id": f"source-{source_type}-{source.get('law_id') or reference_label or title}",
        "source_type": source_type,
        "title": title,
        "law_name": title,
        "law_id": source.get("law_id") or "",
        "mst": source.get("mst") or "",
        "reference_label": reference_label or ("관련 조문 추가 확인 필요" if source_type == "law" else "대표 판례 추가 확인 필요"),
        "article_label": reference_label or ("관련 조문 추가 확인 필요" if source_type == "law" else "대표 판례 추가 확인 필요"),
        "case_number": source.get("case_number") or "",
        "quote": quote,
        "source_url": source.get("detail_link") or "",
        "provider": source.get("provider") or get_law_provider(),
        "fetched_at": fetched_at,
    }


def _build_insufficient_payload(profile: dict, selected_sources: list[dict]) -> dict:
    fetched_at = timezone.now().isoformat()
    citations = [_build_placeholder_citation(source, fetched_at=fetched_at) for source in selected_sources[:2]]
    has_law_source = any(source.get("source_type") == "law" for source in selected_sources)
    has_case_source = any(source.get("source_type") == "case" for source in selected_sources)

    if has_law_source and has_case_source:
        summary = "관련 법령은 찾았지만 질문과 바로 맞는 조문 연결이 약하고, 대표 판례 연결도 더 확인이 필요합니다."
    elif has_law_source:
        summary = "관련 법령은 찾았지만 질문과 바로 맞는 조문 연결이 약합니다."
    else:
        summary = "질문과 바로 연결되는 근거를 충분히 찾지 못해 추가 확인이 필요합니다."

    return {
        "summary": summary,
        "action_items": [
            "누가 다쳤는지, 언제였는지, 어떤 대응을 했는지처럼 사실관계를 한두 문장 더 적어 주세요.",
            "학교 규정이나 교육청 지침이 있다면 함께 확인해 주세요.",
        ],
        "citations": citations,
        "risk_level": "medium",
        "needs_human_help": bool(profile.get("risk_flags")),
        "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
        "scope_supported": True,
    }


def _preferred_visible_citations(citations: list[dict]) -> list[dict]:
    law_citations = [citation for citation in citations if citation.get("source_type") != "case"][:2]
    case_citations = [citation for citation in citations if citation.get("source_type") == "case"][:2]
    return law_citations + case_citations


def _normalize_answer_payload(answer: dict, citations: list[dict], profile: dict) -> dict:
    selected_ids = [item for item in (answer.get("citations") or []) if str(item).strip()]
    visible_citations = [citation for citation in citations if citation.get("citation_id") in selected_ids]
    if not visible_citations:
        visible_citations = _preferred_visible_citations(citations)

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
                "source_type": citation.get("source_type") or "law",
                "title": citation.get("title") or citation.get("law_name") or "",
                "law_name": citation.get("law_name") or citation.get("title") or "",
                "law_id": citation.get("law_id") or "",
                "mst": citation.get("mst") or "",
                "reference_label": citation.get("reference_label") or citation.get("article_label") or "",
                "article_label": citation.get("article_label") or citation.get("reference_label") or "",
                "case_number": citation.get("case_number") or "",
                "quote": citation.get("quote") or "",
                "source_url": citation.get("source_url") or "",
                "provider": citation.get("provider") or get_law_provider(),
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
                "source_type": citation.get("source_type") or "law",
                "law_name": citation.get("title") or citation.get("law_name") or "",
                "title": citation.get("title") or citation.get("law_name") or "",
                "law_id": citation.get("law_id") or "",
                "mst": citation.get("mst") or "",
                "detail_link": citation.get("source_url") or "",
                "reference_label": citation.get("reference_label") or citation.get("article_label") or "",
                "case_number": citation.get("case_number") or "",
                "provider": citation.get("provider") or provider,
            }
        )
    return selected


def _extract_reference_label(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return digits
