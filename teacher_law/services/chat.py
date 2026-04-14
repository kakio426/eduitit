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
    resolve_law_by_name,
    search_cases,
    select_relevant_case_citations,
    select_relevant_citations,
)
from .llm_client import LlmClientError, generate_legal_answer, is_configured as is_llm_configured
from .query_normalizer import (
    ANSWER_POLICY_VERSION,
    build_query_profile,
    compact_text,
    get_quick_question_presets,
)


logger = logging.getLogger(__name__)


class TeacherLawError(Exception):
    pass


class TeacherLawDisabledError(TeacherLawError):
    pass


class TeacherLawTimeoutError(TeacherLawError):
    pass


def get_quick_questions() -> list[dict]:
    return get_quick_question_presets()


def get_or_create_active_session(user) -> LegalChatSession:
    session = (
        LegalChatSession.objects.filter(user=user, is_active=True)
        .order_by("-last_message_at", "-updated_at", "-id")
        .first()
    )
    if session:
        return session
    return LegalChatSession.objects.create(user=user)


def _law_name_key(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", compact_text(value).lower())


def _is_allowed_law_detail(detail: dict, profile: dict) -> bool:
    allowed_laws = profile.get("law_allowlist") or []
    if not allowed_laws:
        return True
    detail_key = _law_name_key(detail.get("law_name") or "")
    if not detail_key:
        return False
    return detail_key in {_law_name_key(item) for item in allowed_laws if compact_text(item)}


def _truncate_body_text(value: str, *, limit: int = 200) -> str:
    text = compact_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _build_fallback_reasoning_summary(citations: list[dict]) -> str:
    law_titles = ", ".join(_citation_title(item) for item in citations if item.get("source_type") != "case")
    representative_case = next((item for item in citations if item.get("source_type") == "case"), None)
    parts = []
    if law_titles:
        parts.append(f"{law_titles} 조문을 먼저 기준으로 판단했습니다.")
    if representative_case:
        parts.append(f"{_citation_title(representative_case)} 판례는 사실관계 비교용 보조 근거로 참고했습니다.")
    else:
        parts.append("관련 판례는 추가 확인이 필요합니다.")
    return compact_text(" ".join(parts))


def _build_representative_case_notice(representative_case: dict | None) -> str:
    if not representative_case:
        return ""
    return "가장 가까운 판례 1건을 참고로 보여드리지만, 실제 사건과 사실관계 차이로 연관성이 많이 부족할 수 있습니다."


def build_answer_body(payload: dict) -> str:
    action_items = [item for item in (payload.get("action_items") or []) if str(item).strip()]
    clarify_questions = [item for item in (payload.get("clarify_questions") or []) if str(item).strip()]
    citations = [item for item in (payload.get("citations") or []) if isinstance(item, dict)]
    law_citations = [item for item in citations if item.get("source_type") != "case"]
    case_citations = [item for item in citations if item.get("source_type") == "case"]
    reasoning_summary = compact_text(payload.get("reasoning_summary"))
    representative_case = payload.get("representative_case") if isinstance(payload.get("representative_case"), dict) else None
    representative_case_notice = compact_text(payload.get("representative_case_notice"))
    precedent_note = compact_text(payload.get("precedent_note"))

    lines = [
        "핵심 판단",
        payload.get("summary") or "추가 확인 필요",
    ]

    if reasoning_summary:
        lines.extend(["", "판단 이유", reasoning_summary])

    if clarify_questions:
        lines.extend(["", "먼저 확인할 것"])
        lines.extend(f"- {item}" for item in clarify_questions[:2])

    if citations:
        lines.extend(["", "이번 답변에서 먼저 본 것"])
        if law_citations:
            law_titles = ", ".join(_citation_title(item) for item in law_citations[:2] if _citation_title(item))
            if law_titles:
                lines.append(f"- 기본 법령: {law_titles}")
        if case_citations:
            case_titles = ", ".join(_citation_title(item) for item in case_citations[:1] if _citation_title(item))
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

    representative_case = representative_case or (case_citations[0] if case_citations else None)
    if representative_case:
        citation_label = " / ".join(
            part
            for part in [
                compact_text(representative_case.get("title") or representative_case.get("law_name")),
                compact_text(representative_case.get("reference_label") or representative_case.get("article_label")),
            ]
            if part
        )
        lines.extend(["", "대표 판례"])
        if citation_label:
            lines.append(f"- {citation_label}")
        quote = _truncate_body_text(representative_case.get("quote") or "")
        if quote:
            lines.append(f"- {quote}")
        if representative_case_notice:
            lines.append(f"- {representative_case_notice}")
    elif precedent_note:
        lines.extend(["", "대표 판례", f"- {precedent_note}"])

    if payload.get("needs_human_help"):
        lines.extend(["", "사람 상담 권장", "- 고위험 사안일 수 있어 학교 관리자나 전문 상담을 함께 권장합니다."])
    disclaimer = compact_text(payload.get("disclaimer"))
    if disclaimer:
        lines.extend(["", disclaimer])
    return "\n".join(lines).strip()


def answer_legal_question(
    *,
    question: str,
    incident_type: str = "",
    legal_goal: str = "",
    scene: str = "",
    counterpart: str = "",
) -> dict:
    started = perf_counter()
    profile = build_query_profile(
        question,
        incident_type=incident_type,
        legal_goal=legal_goal,
        scene=scene,
        counterpart=counterpart,
    )
    law_provider = get_law_provider()
    if not getattr(settings, "TEACHER_LAW_ENABLED", False):
        raise TeacherLawDisabledError("교사용 AI 법률 가이드가 아직 활성화되지 않았습니다.")

    if not profile.get("scope_supported"):
        payload = _build_out_of_scope_payload(profile)
        return {
            "status": "ok",
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

    if profile.get("clarify_needed"):
        payload = _build_clarify_payload(profile, [])
        return {
            "status": "clarify",
            "profile": profile,
            "payload": payload,
            "audit": {
                "cache_hit": False,
                "search_attempt_count": 0,
                "search_result_count": 0,
                "detail_fetch_count": 0,
                "selected_laws_json": [],
                "failure_reason": "clarify_profile",
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
            "status": "ok",
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
    detail_limit = min(int(getattr(settings, "TEACHER_LAW_DETAIL_FETCH_LIMIT", 3)), max(len(profile.get("law_allowlist") or []), 1))
    case_queries = list(profile.get("case_queries") or [])[:2]

    search_attempt_count = 0
    search_result_count = 0
    detail_fetch_count = 0
    selected_sources = []
    collected_law_citations = []
    related_case_results = []
    law_query_hint = profile.get("law_query_hint") or _build_law_query_hint(profile)
    resolved_laws = []

    for law_name in profile.get("law_allowlist") or []:
        _ensure_total_timeout(started, total_timeout_seconds)
        search_attempt_count += 1
        resolved = resolve_law_by_name(law_name)
        if not resolved:
            continue
        search_result_count += 1
        resolved_laws.append(resolved)

    ranked_laws = rank_search_results(_dedupe_search_results(resolved_laws), profile)

    for ranked in ranked_laws[:detail_limit]:
        _ensure_total_timeout(started, total_timeout_seconds)
        detail_fetch_count += 1
        detail = get_law_details(
            law_id=ranked.get("law_id") or "",
            mst=ranked.get("mst") or "",
            detail_link=ranked.get("detail_link") or "",
            query_hint=law_query_hint,
            law_name=ranked.get("law_name") or "",
        )
        if not _is_allowed_law_detail(detail, profile):
            logger.warning(
                "[TeacherLaw] skipped unexpected law detail law_name=%s allowlist=%s",
                detail.get("law_name") or ranked.get("law_name") or "",
                profile.get("law_allowlist") or [],
            )
            continue
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
                    limit=1,
                    law_id=first_law_id,
                    article_ref=first_article_ref,
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
                        limit=1,
                        law_id=first_law_id,
                        article_ref=first_article_ref,
                    )
                )
                if collected_case_citations:
                    break

    case_citations = _dedupe_citations(collected_case_citations)
    for citation in case_citations[:1]:
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

    visible_citations = law_citations[:2] + case_citations[:1]
    if not law_citations:
        payload = _build_clarify_payload(profile, selected_sources)
        audit = {
            "cache_hit": False,
            "search_attempt_count": search_attempt_count,
            "search_result_count": search_result_count,
            "detail_fetch_count": detail_fetch_count,
            "selected_laws_json": selected_sources,
            "failure_reason": "clarify",
            "error_message": "",
            "elapsed_ms": _elapsed_ms(started),
        }
        logger.info(
            "[TeacherLaw] Action: GENERATE_ANSWER, Status: CLARIFY, Topic: %s, Provider: %s",
            profile.get("topic") or "unknown",
            law_provider,
        )
        return {"status": "clarify", "profile": profile, "payload": payload, "audit": audit}

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
    return {"status": "ok", "profile": profile, "payload": payload, "audit": audit}


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


def _has_hint_match(results: list[dict], profile: dict) -> bool:
    hint_queries = [compact_text(item).lower() for item in profile.get("hint_queries") or [] if compact_text(item)]
    if not hint_queries:
        return bool(results)
    for result in results:
        law_name = compact_text(result.get("law_name")).lower()
        if not law_name:
            continue
        if law_name in hint_queries:
            return True
        if any(hint and hint in law_name for hint in hint_queries):
            return True
    return False


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
        "reasoning_summary": "",
        "action_items": [
            "교사·학생·학부모·교실·수업 중 어떤 상황인지 함께 적어 주세요.",
            "학교 밖 개인 생활 분쟁이라면 전문 상담 기관이나 변호사 상담을 함께 검토해 주세요.",
        ],
        "citations": [],
        "risk_level": "medium",
        "needs_human_help": False,
        "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
        "scope_supported": False,
        "status": "ok",
        "answer_held": False,
        "clarify_reason": "",
        "clarify_needed": False,
        "clarify_questions": [],
        "missing_facts": [],
        "representative_case": None,
        "representative_case_notice": "",
        "precedent_note": "",
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


def _build_clarify_payload(profile: dict, selected_sources: list[dict]) -> dict:
    fetched_at = timezone.now().isoformat()
    citations = [_build_placeholder_citation(source, fetched_at=fetched_at) for source in selected_sources[:2]]
    legal_goal = profile.get("legal_goal") or ""
    legal_issues = set(profile.get("legal_issues") or [])
    profile_clarify_questions = [item for item in (profile.get("clarify_questions") or []) if compact_text(item)]
    missing_facts = [item for item in (profile.get("missing_facts") or []) if compact_text(item)]
    reasoning_summary = ""

    if profile_clarify_questions:
        summary = compact_text(profile.get("clarify_summary")) or "정확한 답변과 대표 판례를 붙이려면 먼저 두 가지만 확인할게요."
        action_items = []
        reasoning_summary = "핵심 사실이 더 확인되면 관련 법령과 대표 판례를 더 정확하게 고를 수 있습니다."
    elif profile.get("incident_type") == "education_activity" and "폭행" in legal_issues:
        summary = "형법상 폭행·상해와 교육활동 침해 여부를 함께 봐야 하지만, 지금 근거만으로는 바로 맞는 조문 연결이 약합니다."
        action_items = [
            "학교 관리자와 교육청에 교육활동 침해 사실을 바로 알리고 기록해 두세요.",
            "진단서, CCTV, 목격자 진술, 상담 기록처럼 폭행 사실을 보여줄 자료를 확보해 두세요.",
            "즉시 위험이 있거나 실제 폭행이 있었다면 경찰 신고도 함께 검토하세요.",
        ]
    elif profile.get("requires_scene") and not profile.get("scene_value"):
        summary = "관련 법령은 정해졌지만, 책임 판단에 필요한 장면 정보가 부족합니다."
        action_items = [
            "수업 중인지, 쉬는시간인지, 체험학습인지 장면을 먼저 골라 주세요.",
            "학생이 언제 어떻게 다쳤는지 한두 문장 더 적어 주세요.",
        ]
    elif profile.get("requires_counterpart") and not profile.get("counterpart"):
        summary = "관련 법령은 정해졌지만, 상대가 누구인지 불분명해 추가 확인이 필요합니다."
        action_items = [
            "학생, 학부모, 보호자, 외부인 중 상대를 먼저 골라 주세요.",
            "무슨 방식으로 문제가 생겼는지 한두 문장 더 적어 주세요.",
        ]
    elif legal_goal == "teacher_liability":
        summary = "관련 법령은 정해졌지만, 책임 판단에 필요한 사고 경위와 교사의 대응 상황을 더 확인해야 합니다."
        action_items = [
            "사고가 난 장면과 당시 교사의 위치·대응을 한두 문장 더 적어 주세요.",
            "학생 상태와 즉시 조치 내용을 함께 적어 주세요.",
        ]
    elif legal_goal == "posting_allowed":
        summary = "관련 법령은 정해졌지만, 공개 범위와 동의 여부를 더 확인해야 합니다."
        action_items = [
            "어디에 올릴지와 누가 볼 수 있는지 먼저 적어 주세요.",
            "학생 또는 보호자 동의 여부를 함께 확인해 주세요.",
        ]
    elif legal_goal == "reporting_duty":
        summary = "관련 법령은 정해졌지만, 신고 시점과 보고 대상 판단을 위해 사실관계를 더 확인해야 합니다."
        action_items = [
            "언제 어떤 의심 정황을 알게 되었는지 적어 주세요.",
            "학교 내부 보고와 외부 신고가 필요한 상황인지 함께 확인해 주세요.",
        ]
    else:
        summary = "관련 법령은 정해졌지만, 질문과 바로 맞는 조문 연결이 약해 추가 확인이 필요합니다."
        action_items = [
            "누가, 언제, 어디서, 무엇을 했는지 한두 문장 더 적어 주세요.",
            "학교 규정이나 교육청 지침이 있다면 함께 확인해 주세요.",
        ]

    return {
        "summary": summary,
        "reasoning_summary": reasoning_summary,
        "action_items": action_items,
        "citations": citations,
        "risk_level": "medium",
        "needs_human_help": bool(profile.get("risk_flags")),
        "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
        "scope_supported": True,
        "status": "clarify",
        "answer_held": True,
        "clarify_reason": summary,
        "clarify_needed": True,
        "clarify_questions": profile_clarify_questions,
        "missing_facts": missing_facts,
        "representative_case": None,
        "representative_case_notice": "",
        "precedent_note": "",
    }


def _preferred_visible_citations(citations: list[dict]) -> list[dict]:
    law_citations = [citation for citation in citations if citation.get("source_type") != "case"][:2]
    case_citations = [citation for citation in citations if citation.get("source_type") == "case"][:1]
    return law_citations + case_citations


def _normalize_answer_payload(answer: dict, citations: list[dict], profile: dict) -> dict:
    selected_ids = [item for item in (answer.get("citations") or []) if str(item).strip()]
    visible_citations = [citation for citation in citations if citation.get("citation_id") in selected_ids]
    if not visible_citations or not any(item.get("source_type") != "case" for item in visible_citations):
        visible_citations = _preferred_visible_citations(citations)
    elif any(item.get("source_type") == "case" for item in citations) and not any(
        item.get("source_type") == "case" for item in visible_citations
    ):
        visible_citations = _preferred_visible_citations(citations)

    risk_level = str(answer.get("risk_level") or "medium").strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "medium"

    needs_human_help = bool(answer.get("needs_human_help")) or bool(profile.get("risk_flags"))
    if needs_human_help:
        risk_level = "high" if risk_level != "high" else risk_level

    action_items = [compact_text(item) for item in (answer.get("action_items") or []) if compact_text(item)]
    summary = compact_text(answer.get("summary"))
    reasoning_summary = compact_text(answer.get("reasoning_summary"))
    if not summary:
        summary = "추가 확인 필요"
        needs_human_help = True
    if not reasoning_summary:
        reasoning_summary = _build_fallback_reasoning_summary(visible_citations)

    representative_case = next((citation for citation in visible_citations if citation.get("source_type") == "case"), None)
    representative_case_notice = _build_representative_case_notice(representative_case)
    precedent_note = "" if representative_case else "관련 판례는 더 확인 필요합니다."

    return {
        "summary": summary,
        "reasoning_summary": reasoning_summary,
        "action_items": action_items[:4],
        "citations": visible_citations,
        "risk_level": risk_level,
        "needs_human_help": needs_human_help,
        "disclaimer": compact_text(
            answer.get("disclaimer") or "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다."
        ),
        "scope_supported": bool(answer.get("scope_supported", True)),
        "status": "ok",
        "answer_held": False,
        "clarify_reason": "",
        "clarify_needed": False,
        "clarify_questions": [],
        "missing_facts": [],
        "representative_case": representative_case,
        "representative_case_notice": representative_case_notice,
        "precedent_note": precedent_note,
    }


def _serialize_cache_payload(payload: dict) -> dict:
    serialized = {
        "summary": payload.get("summary") or "",
        "reasoning_summary": payload.get("reasoning_summary") or "",
        "action_items": list(payload.get("action_items") or []),
        "citations": [],
        "risk_level": payload.get("risk_level") or "medium",
        "needs_human_help": bool(payload.get("needs_human_help")),
        "disclaimer": payload.get("disclaimer") or "",
        "scope_supported": bool(payload.get("scope_supported", True)),
        "status": payload.get("status") or "ok",
        "answer_held": bool(payload.get("answer_held")),
        "clarify_reason": payload.get("clarify_reason") or "",
        "clarify_needed": bool(payload.get("clarify_needed")),
        "clarify_questions": list(payload.get("clarify_questions") or []),
        "missing_facts": list(payload.get("missing_facts") or []),
        "representative_case": payload.get("representative_case") if isinstance(payload.get("representative_case"), dict) else None,
        "representative_case_notice": payload.get("representative_case_notice") or "",
        "precedent_note": payload.get("precedent_note") or "",
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
        "reasoning_summary": compact_text(raw_payload.get("reasoning_summary")),
        "action_items": [compact_text(item) for item in raw_payload.get("action_items") or [] if compact_text(item)],
        "citations": citations,
        "risk_level": compact_text(raw_payload.get("risk_level") or "medium") or "medium",
        "needs_human_help": bool(raw_payload.get("needs_human_help")),
        "disclaimer": compact_text(
            raw_payload.get("disclaimer") or "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다."
        ),
        "scope_supported": bool(raw_payload.get("scope_supported", True)),
        "status": compact_text(raw_payload.get("status") or "ok") or "ok",
        "answer_held": bool(raw_payload.get("answer_held")),
        "clarify_reason": compact_text(raw_payload.get("clarify_reason")),
        "clarify_needed": bool(raw_payload.get("clarify_needed")),
        "clarify_questions": [compact_text(item) for item in raw_payload.get("clarify_questions") or [] if compact_text(item)],
        "missing_facts": [compact_text(item) for item in raw_payload.get("missing_facts") or [] if compact_text(item)],
        "representative_case": raw_payload.get("representative_case") if isinstance(raw_payload.get("representative_case"), dict) else None,
        "representative_case_notice": compact_text(raw_payload.get("representative_case_notice")),
        "precedent_note": compact_text(raw_payload.get("precedent_note")),
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
