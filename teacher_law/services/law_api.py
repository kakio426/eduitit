from __future__ import annotations

import logging
import os
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .query_normalizer import (
    ACTOR_KEYWORDS,
    CONSENT_KEYWORDS,
    DISCLOSURE_GROUP_KEYWORDS,
    DISCLOSURE_PUBLIC_KEYWORDS,
    PHOTO_VIDEO_KEYWORDS,
    PHYSICAL_VIOLENCE_KEYWORDS,
    RECORDING_ACTION_KEYWORDS,
    RECORDING_DEVICE_KEYWORDS,
    RECORDING_DISCLOSURE_KEYWORDS,
    RECORDING_INTENT_KEYWORDS,
    SCENE_KEYWORDS,
    compact_text,
    normalize_for_matching,
)


logger = logging.getLogger(__name__)

OPEN_LAW_BASE_URLS = (
    "https://www.law.go.kr/DRF",
    "http://www.law.go.kr/DRF",
)
DEFAULT_BEOPMANG_BASE_URL = "https://api.beopmang.org/api/v4"
SUPPORTED_PROVIDERS = {"beopmang", "open_law"}
SUBORDINATE_LAW_MARKERS = ("시행령", "시행규칙", "고시", "훈령", "예규")
GENERIC_ARTICLE_MARKERS = ("목적", "정의", "적용 범위", "해석", "준용")
CASE_MATCH_VISIBLE_THRESHOLD = 9
CASE_MATCH_HIGH_THRESHOLD = 14
VERBAL_ABUSE_KEYWORDS = ("폭언", "욕설", "모욕", "협박", "비난")
CASE_SAFETY_KEYWORDS = ("다치", "부상", "사고", "안전사고", "추락", "골절", "응급")
CASE_SCHOOL_CONTEXT_KEYWORDS = ("학교", "교실", "수업", "학생", "교사", "선생님", "학급")
CASE_STAGE_LABELS = {
    "device_only": "행위 단계 차이",
    "intent": "행위 단계 차이",
    "executed": "행위 단계 차이",
    "disclosed": "행위 단계 차이",
    "capture": "행위 단계 차이",
    "posted": "행위 단계 차이",
    "injury": "행위 단계 차이",
    "assault": "행위 단계 차이",
    "verbal_abuse": "행위 단계 차이",
}


class LawApiError(Exception):
    pass


class LawApiConfigError(LawApiError):
    pass


class LawApiVerificationError(LawApiError):
    pass


class LawApiTimeoutError(LawApiError):
    pass


def get_law_provider() -> str:
    configured = str(
        os.environ.get("TEACHER_LAW_PROVIDER")
        or getattr(settings, "TEACHER_LAW_PROVIDER", "")
        or ""
    ).strip().lower()
    if configured in SUPPORTED_PROVIDERS:
        return configured
    return "beopmang"


def get_api_oc() -> str:
    return str(os.environ.get("LAW_API_OC") or getattr(settings, "LAW_API_OC", "") or "").strip()


def get_beopmang_base_url() -> str:
    configured = str(
        os.environ.get("BEOPMANG_API_BASE_URL")
        or getattr(settings, "BEOPMANG_API_BASE_URL", "")
        or ""
    ).strip()
    return configured.rstrip("/") or DEFAULT_BEOPMANG_BASE_URL


def _normalize_law_name_key(value: str) -> str:
    normalized = normalize_for_matching(value)
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)


def _is_subordinate_law_name(value: str) -> bool:
    law_name = compact_text(value)
    return any(marker in law_name for marker in SUBORDINATE_LAW_MARKERS)


def is_configured() -> bool:
    if get_law_provider() == "open_law":
        return bool(get_api_oc())
    return True


def _value_text(value):
    if isinstance(value, dict):
        return str(value.get("content") or value.get("Content") or "").strip()
    if isinstance(value, list):
        return "\n".join(item for item in (_value_text(entry) for entry in value) if item)
    return str(value or "").strip()


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _candidate_base_urls() -> list[str]:
    configured = str(os.environ.get("LAW_API_BASE_URL") or "").strip().rstrip("/")
    candidates = []
    if configured:
        candidates.append(configured)
    for base_url in OPEN_LAW_BASE_URLS:
        if base_url not in candidates:
            candidates.append(base_url)
    return candidates


def _request_headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "EduititTeacherLaw/1.0 (+https://eduitit.site)",
    }


def _error_text_from_payload(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("msg", "result", "message", "detail", "error", "instruction"):
        text = compact_text(payload.get(key))
        if text:
            return text
    return ""


def _request(endpoint: str, *, params: dict, timeout_seconds: int):
    return _request_open_law(endpoint, params=params, timeout_seconds=timeout_seconds)


def _request_open_law(endpoint: str, *, params: dict, timeout_seconds: int):
    oc = get_api_oc()
    if not oc:
        raise LawApiConfigError("국가법령정보 API 인증값이 아직 연결되지 않았습니다.")

    request_params = {
        "OC": oc,
        "type": "JSON",
        **params,
    }
    last_error = None
    attempted_urls = []

    for base_url in _candidate_base_urls():
        url = f"{base_url}/{endpoint}"
        attempted_urls.append(url)
        try:
            response = requests.get(
                url,
                params=request_params,
                headers=_request_headers(),
                timeout=timeout_seconds,
            )
        except requests.Timeout as exc:
            last_error = exc
            continue
        except requests.RequestException as exc:
            last_error = exc
            continue

        try:
            payload = response.json()
        except ValueError as exc:
            last_error = exc
            continue

        error_text = _error_text_from_payload(payload)
        if error_text and "검증" in error_text:
            raise LawApiVerificationError(error_text)
        if error_text and error_text != "success":
            raise LawApiError(error_text)
        return payload

    logger.warning(
        "[TeacherLaw] law api request failed provider=open_law attempted_urls=%s",
        attempted_urls,
    )
    if isinstance(last_error, requests.Timeout):
        raise LawApiTimeoutError("국가법령정보 응답이 지연되고 있습니다.") from last_error
    if isinstance(last_error, ValueError):
        raise LawApiError("국가법령정보 응답을 해석하지 못했습니다.") from last_error
    raise LawApiError("국가법령정보에 연결하지 못했습니다.") from last_error


def _request_beopmang(path: str, *, params: dict, timeout_seconds: int) -> dict:
    url = f"{get_beopmang_base_url()}/{path.lstrip('/')}"
    try:
        response = requests.get(
            url,
            params=params,
            headers=_request_headers(),
            timeout=timeout_seconds,
        )
    except requests.Timeout as exc:
        raise LawApiTimeoutError("법령 데이터 응답이 지연되고 있습니다.") from exc
    except requests.RequestException as exc:
        raise LawApiError("법령 데이터에 연결하지 못했습니다.") from exc

    if response.status_code == 429:
        raise LawApiError("법령 데이터 요청이 많아 잠시 후 다시 시도해 주세요.")
    if response.status_code >= 500:
        raise LawApiError("법령 데이터 연결이 일시적으로 불안정합니다.")
    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LawApiError("법령 데이터 응답을 해석하지 못했습니다.") from exc
        raise LawApiError(_error_text_from_payload(payload) or "법령 데이터를 불러오지 못했습니다.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise LawApiError("법령 데이터 응답을 해석하지 못했습니다.") from exc

    if payload.get("success") is False:
        raise LawApiError(_error_text_from_payload(payload) or "법령 데이터를 불러오지 못했습니다.")
    return payload


def _normalize_beopmang_article(article: dict, *, text_keys: tuple[str, ...]) -> dict | None:
    if not isinstance(article, dict):
        return None
    article_label = compact_text(article.get("label") or article.get("article_no") or article.get("article"))
    article_text = ""
    for key in text_keys:
        article_text = compact_text(article.get(key))
        if article_text:
            break
    if not article_text:
        title = compact_text(article.get("title"))
        snippet = compact_text(article.get("snippet"))
        article_text = compact_text(" ".join(part for part in (title, snippet) if part))
    if not article_text:
        return None
    return {
        "article_label": article_label,
        "article_text": article_text,
    }


def _normalize_beopmang_case(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None

    title = compact_text(
        item.get("title")
        or item.get("case_name")
        or item.get("case_title")
        or item.get("name")
        or item.get("caseNumber")
    )
    case_number = compact_text(
        item.get("case_number")
        or item.get("case_no")
        or item.get("name")
        or item.get("caseNumber")
    )
    quote = compact_text(
        item.get("summary")
        or item.get("summary_text")
        or item.get("holding")
        or item.get("decision_summary")
        or item.get("judgment_summary")
        or item.get("snippet")
        or item.get("excerpt")
        or item.get("reasoning")
    )
    if not quote:
        return None

    if not title:
        title = case_number or "참고 판례"

    return {
        "case_id": compact_text(item.get("case_id") or item.get("id")),
        "title": title,
        "case_number": case_number,
        "reference_label": case_number or "판례 요지",
        "quote": quote,
        "source_url": compact_text(item.get("url") or item.get("link") or item.get("detail_url") or item.get("source_url")),
        "provider": "beopmang",
        "source_type": "case",
        "law_id": compact_text(item.get("law_id")),
        "article": compact_text(item.get("article") or item.get("article_no")),
        "raw": item,
    }


def _search_open_law(query: str, *, search: int = 1, display: int | None = None) -> list[dict]:
    payload = _request_open_law(
        "lawSearch.do",
        params={
            "target": "law",
            "query": query,
            "search": str(search),
            "display": str(display or getattr(settings, "TEACHER_LAW_SEARCH_RESULT_LIMIT", 5)),
            "page": "1",
            "sort": "lasc",
        },
        timeout_seconds=int(getattr(settings, "TEACHER_LAW_SEARCH_TIMEOUT_SECONDS", 4)),
    )
    root = payload.get("LawSearch") or payload.get("lawSearch") or {}
    law_items = _as_list(root.get("law"))
    results = []
    for item in law_items:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "law_name": _value_text(item.get("법령명한글") or item.get("법령명")),
                "law_id": _value_text(item.get("법령ID")),
                "mst": _value_text(item.get("법령일련번호")),
                "law_type": _value_text(item.get("법령구분명")),
                "ministry": _value_text(item.get("소관부처명")),
                "promulgation_date": _value_text(item.get("공포일자")),
                "enforcement_date": _value_text(item.get("시행일자")),
                "detail_link": _value_text(item.get("법령상세링크") or item.get("상세링크")),
                "provider": "open_law",
                "raw": item,
            }
        )
    return results


def _search_beopmang(query: str, *, display: int | None = None) -> list[dict]:
    payload = _request_beopmang(
        "law",
        params={
            "action": "search",
            "q": query,
            "mode": "keyword",
        },
        timeout_seconds=int(getattr(settings, "TEACHER_LAW_SEARCH_TIMEOUT_SECONDS", 4)),
    )
    limit = int(display or getattr(settings, "TEACHER_LAW_SEARCH_RESULT_LIMIT", 5))
    results = []
    for item in (payload.get("data") or {}).get("results") or []:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "law_name": compact_text(item.get("law_name")),
                "law_id": compact_text(item.get("law_id")),
                "mst": "",
                "law_type": compact_text(item.get("law_type")),
                "ministry": "",
                "promulgation_date": compact_text(item.get("last_amended")),
                "enforcement_date": compact_text(item.get("enforcement_date")),
                "detail_link": "",
                "provider": "beopmang",
                "raw": item,
            }
        )
    return results[:limit]


def search_laws(query: str, *, search: int = 1, display: int | None = None) -> list[dict]:
    provider = get_law_provider()
    logger.info("[TeacherLaw] law search provider=%s query=%s", provider, query)
    if provider == "open_law":
        return _search_open_law(query, search=search, display=display)
    return _search_beopmang(query, display=display)


def _rank_exact_law_matches(results: list[dict], *, target_name: str) -> list[dict]:
    target_compact = compact_text(target_name)
    target_key = _normalize_law_name_key(target_name)
    scored = []
    for result in results:
        law_name = compact_text(result.get("law_name"))
        law_key = _normalize_law_name_key(law_name)
        if not law_name or not law_key:
            continue
        score = 0
        if law_name == target_compact:
            score += 220
        if law_key == target_key:
            score += 200
        if target_key and law_key.startswith(target_key):
            score += 90
        if target_key and target_key in law_key:
            score += 50
        if compact_text(result.get("law_type")) == "법률":
            score += 8
        elif result.get("law_type"):
            score += 2
        if any(keyword in law_name for keyword in ("시행규칙", "시행령", "고시")):
            score -= 30
        if score > 0:
            scored.append((score, result))
    scored.sort(key=lambda item: (-item[0], len(compact_text(item[1].get("law_name"))), item[1].get("law_name") or ""))
    return [result for _, result in scored]


def resolve_law_by_name(law_name: str) -> dict | None:
    compact_name = compact_text(law_name)
    if not compact_name:
        return None

    cache_key = f"teacher_law:resolve_law:{get_law_provider()}:{_normalize_law_name_key(compact_name)}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("law_name"):
        return cached

    ranked = _rank_exact_law_matches(search_laws(compact_name, display=10), target_name=compact_name)
    if not ranked:
        return None

    if not _is_subordinate_law_name(compact_name):
        ranked = [result for result in ranked if not _is_subordinate_law_name(result.get("law_name"))]
        if not ranked:
            return None

    resolved = {
        "law_name": compact_text(ranked[0].get("law_name")),
        "law_id": compact_text(ranked[0].get("law_id")),
        "mst": compact_text(ranked[0].get("mst")),
        "law_type": compact_text(ranked[0].get("law_type")),
        "detail_link": compact_text(ranked[0].get("detail_link")),
        "provider": compact_text(ranked[0].get("provider")) or get_law_provider(),
    }
    cache.set(cache_key, resolved, timeout=86400)
    return resolved


def _build_article_text(article: dict) -> str:
    parts = []
    main_text = compact_text(_value_text(article.get("조문내용")))
    if main_text:
        parts.append(main_text)
    note_text = compact_text(_value_text(article.get("조문참고자료")))
    if note_text:
        parts.append(note_text)
    for paragraph in _as_list(article.get("항")):
        para_text = compact_text(_value_text(paragraph.get("항내용") if isinstance(paragraph, dict) else paragraph))
        if para_text:
            parts.append(para_text)
        if isinstance(paragraph, dict):
            for subparagraph in _as_list(paragraph.get("호")):
                ho_text = compact_text(_value_text(subparagraph.get("호내용") if isinstance(subparagraph, dict) else subparagraph))
                if ho_text:
                    parts.append(ho_text)
    return "\n".join(parts).strip()


def _get_open_law_details(*, law_id: str = "", mst: str = "", detail_link: str = "", law_name: str = "") -> dict:
    params = {"target": "law"}
    if law_id:
        params["ID"] = law_id
    elif mst:
        params["MST"] = mst
    else:
        raise LawApiError("상세 조회용 법령 식별자가 없습니다.")

    payload = _request_open_law(
        "lawService.do",
        params=params,
        timeout_seconds=int(getattr(settings, "TEACHER_LAW_DETAIL_TIMEOUT_SECONDS", 4)),
    )
    law = payload.get("법령")
    if not isinstance(law, dict):
        raise LawApiError("법령 상세 정보를 찾지 못했습니다.")

    basic_info = law.get("기본정보") or {}
    articles = []
    for article in _as_list((law.get("조문") or {}).get("조문단위")):
        if not isinstance(article, dict):
            continue
        if _value_text(article.get("조문여부")) == "전문":
            continue
        article_label = compact_text(
            _value_text(article.get("조문번호"))
            or _value_text(article.get("조문제목"))
            or _value_text(article.get("조번호"))
        )
        article_text = _build_article_text(article)
        if not article_text:
            continue
        articles.append(
            {
                "article_label": article_label,
                "article_text": article_text,
            }
        )

    return {
        "law_name": _value_text(basic_info.get("법령명_한글") or basic_info.get("법령명한글") or law_name),
        "law_id": _value_text(basic_info.get("법령ID") or law_id),
        "mst": _value_text(law.get("법령키") or mst),
        "law_type": _value_text(basic_info.get("법종구분")),
        "ministry": _value_text(basic_info.get("소관부처")),
        "promulgation_date": _value_text(basic_info.get("공포일자")),
        "enforcement_date": _value_text(basic_info.get("시행일자")),
        "detail_link": detail_link,
        "provider": "open_law",
        "articles": articles,
        "related_cases": [],
    }


def _map_beopmang_article_candidates(items, *, text_keys: tuple[str, ...]) -> list[dict]:
    articles = []
    for item in _as_list(items):
        normalized = _normalize_beopmang_article(item, text_keys=text_keys)
        if normalized:
            articles.append(normalized)
    return articles


def _map_beopmang_case_candidates(items) -> list[dict]:
    cases = []
    for item in _as_list(items):
        normalized = _normalize_beopmang_case(item)
        if normalized:
            cases.append(normalized)
    return cases


def _get_beopmang_details(*, law_id: str = "", query_hint: str = "", law_name: str = "") -> dict:
    if not law_id:
        raise LawApiError("상세 조회용 법령 식별자가 없습니다.")

    hint = compact_text(query_hint)
    request_params = {
        "action": "get",
        "law_id": law_id,
    }
    if hint:
        request_params["grep"] = hint

    payload = _request_beopmang(
        "law",
        params=request_params,
        timeout_seconds=int(getattr(settings, "TEACHER_LAW_DETAIL_TIMEOUT_SECONDS", 4)),
    )
    data = payload.get("data") or {}
    articles = _map_beopmang_article_candidates(data.get("articles"), text_keys=("full_text", "content"))
    related_cases = []

    if hint and not articles:
        overview_payload = _request_beopmang(
            "tools",
            params={
                "action": "overview",
                "law_id": law_id,
                "q": hint,
            },
            timeout_seconds=int(getattr(settings, "TEACHER_LAW_DETAIL_TIMEOUT_SECONDS", 4)),
        )
        overview_data = overview_payload.get("data") or {}
        if not articles:
            articles = _map_beopmang_article_candidates(
                overview_data.get("top_articles"),
                text_keys=("full_text", "snippet"),
            )
        related_cases = _map_beopmang_case_candidates(overview_data.get("top_cases"))
        if overview_data:
            data = {**data, **overview_data}

    return {
        "law_name": compact_text(data.get("law_name") or law_name),
        "law_id": compact_text(data.get("law_id") or law_id),
        "mst": "",
        "law_type": compact_text(data.get("law_type")),
        "ministry": "",
        "promulgation_date": compact_text(data.get("last_amended")),
        "enforcement_date": compact_text(data.get("enforcement_date")),
        "detail_link": "",
        "provider": "beopmang",
        "articles": articles,
        "related_cases": related_cases,
    }


def get_law_details(
    *,
    law_id: str = "",
    mst: str = "",
    detail_link: str = "",
    query_hint: str = "",
    law_name: str = "",
) -> dict:
    provider = get_law_provider()
    logger.info(
        "[TeacherLaw] law detail provider=%s law_id=%s mst=%s",
        provider,
        law_id or "",
        mst or "",
    )
    if provider == "open_law":
        return _get_open_law_details(law_id=law_id, mst=mst, detail_link=detail_link, law_name=law_name)
    return _get_beopmang_details(law_id=law_id, query_hint=query_hint, law_name=law_name)


def _extract_article_reference(reference_label: str) -> str:
    digits = "".join(char for char in str(reference_label or "") if char.isdigit())
    return digits


def _search_beopmang_cases(query: str, *, law_id: str = "", article: str = "", display: int | None = None) -> list[dict]:
    params = {
        "action": "search",
        "q": query,
        "mode": "keyword",
    }
    if law_id:
        params["law_id"] = law_id
    if article:
        params["article"] = article

    payload = _request_beopmang(
        "case",
        params=params,
        timeout_seconds=int(getattr(settings, "TEACHER_LAW_DETAIL_TIMEOUT_SECONDS", 4)),
    )
    limit = int(display or 2)
    results = _map_beopmang_case_candidates((payload.get("data") or {}).get("results"))
    if results:
        return results[:limit]

    if law_id:
        overview_payload = _request_beopmang(
            "tools",
            params={
                "action": "overview",
                "law_id": law_id,
                "q": query,
            },
            timeout_seconds=int(getattr(settings, "TEACHER_LAW_DETAIL_TIMEOUT_SECONDS", 4)),
        )
        overview_results = _map_beopmang_case_candidates((overview_payload.get("data") or {}).get("top_cases"))
        if overview_results:
            return overview_results[:limit]

    return []


def search_cases(query: str, *, law_id: str = "", article: str = "", display: int | None = None) -> list[dict]:
    provider = get_law_provider()
    logger.info("[TeacherLaw] case search provider=%s query=%s", provider, query)
    if provider == "open_law":
        return []
    return _search_beopmang_cases(query, law_id=law_id, article=article, display=display)


def rank_search_results(results: list[dict], profile: dict) -> list[dict]:
    normalized_question = normalize_for_matching(profile.get("normalized_question"))
    hint_queries = [normalize_for_matching(item) for item in profile.get("hint_queries") or []]
    core_terms = [normalize_for_matching(item) for item in profile.get("core_terms") or []]
    search_terms = [normalize_for_matching(item) for item in profile.get("search_terms") or []]
    scored = []
    for result in results:
        law_name = normalize_for_matching(result.get("law_name"))
        score = 0
        if law_name in hint_queries:
            score += 30
        score += sum(12 for hint in hint_queries if hint and hint in law_name and law_name != hint)
        if law_name and law_name in normalized_question:
            score += 8
        score += sum(2 for term in core_terms[:4] if term and term in law_name)
        score += sum(3 for term in search_terms[:6] if term and term in law_name)
        if compact_text(result.get("law_type")) == "법률":
            score += 3
        elif result.get("law_type"):
            score += 1
        if _is_subordinate_law_name(result.get("law_name")):
            score -= 20
        scored.append((score, result))
    scored.sort(key=lambda item: (-item[0], item[1].get("law_name") or ""))
    return [result for _, result in scored]


def _build_strong_match_terms(profile: dict) -> list[str]:
    terms = []
    for value in [
        *(profile.get("legal_issues") or []),
        profile.get("legal_goal_label") or "",
        profile.get("counterpart_label") or "",
        *(profile.get("scene") or []),
        *(profile.get("core_terms") or []),
    ]:
        normalized = normalize_for_matching(value)
        if normalized and normalized not in terms:
            terms.append(normalized)
    return terms


def _build_weak_match_terms(profile: dict) -> list[str]:
    terms = []
    for value in [
        *(profile.get("search_terms") or []),
        *(profile.get("hint_queries") or []),
    ]:
        normalized = normalize_for_matching(value)
        if normalized and normalized not in terms:
            terms.append(normalized)
    return terms


def _looks_like_generic_article(article: dict) -> bool:
    label = compact_text(article.get("article_label"))
    text = compact_text(article.get("article_text"))
    return any(marker in label or marker in text[:120] for marker in GENERIC_ARTICLE_MARKERS)


def _build_law_citation(details: dict, article: dict, *, index: int, fetched_at) -> dict:
    reference_label = article.get("article_label") or ""
    title = details.get("law_name") or "법령"
    return {
        "citation_id": f"law-{details.get('law_id') or details.get('mst') or 'LAW'}-{index}",
        "source_type": "law",
        "title": title,
        "law_name": title,
        "law_id": details.get("law_id") or "",
        "mst": details.get("mst") or "",
        "reference_label": reference_label,
        "article_label": reference_label,
        "case_number": "",
        "quote": compact_text(article.get("article_text")),
        "source_url": details.get("detail_link") or "",
        "provider": details.get("provider") or get_law_provider(),
        "fetched_at": fetched_at.isoformat(),
    }


def select_relevant_citations(details: dict, profile: dict, *, limit: int = 2) -> list[dict]:
    strong_terms = _build_strong_match_terms(profile)
    weak_terms = _build_weak_match_terms(profile)
    scored = []
    for article in details.get("articles") or []:
        haystack = normalize_for_matching(f"{article.get('article_label')} {article.get('article_text')}")
        strong_score = sum(4 for term in strong_terms if term and term in haystack)
        weak_score = sum(1 for term in weak_terms if term and term in haystack)
        if strong_score <= 0:
            continue
        score = strong_score + weak_score
        if _looks_like_generic_article(article):
            score -= 3
        scored.append((score, article))

    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], item[1].get("article_label") or ""))
    selected_articles = [article for score, article in scored if score > 0][:limit]
    if not selected_articles:
        return []

    fetched_at = timezone.now()
    return [
        _build_law_citation(details, article, index=index, fetched_at=fetched_at)
        for index, article in enumerate(selected_articles, start=1)
    ]


def _build_case_citation(case_result: dict, *, index: int, law_id: str = "") -> dict:
    title = compact_text(case_result.get("title") or case_result.get("law_name") or "참고 판례")
    reference_label = compact_text(case_result.get("reference_label") or case_result.get("case_number") or "판례 요지")
    quote = compact_text(case_result.get("quote"))
    fetched_at = timezone.now().isoformat()
    return {
        "citation_id": f"case-{case_result.get('case_id') or reference_label or index}-{index}",
        "source_type": "case",
        "title": title,
        "law_name": title,
        "law_id": law_id or case_result.get("law_id") or "",
        "mst": "",
        "reference_label": reference_label,
        "article_label": reference_label,
        "case_number": compact_text(case_result.get("case_number") or reference_label),
        "quote": quote,
        "source_url": compact_text(case_result.get("source_url")),
        "provider": case_result.get("provider") or get_law_provider(),
        "fetched_at": fetched_at,
    }


def _has_case_keyword(haystack: str, keywords: tuple[str, ...] | list[str]) -> bool:
    return any(keyword.lower() in haystack for keyword in keywords)


def _detect_case_stage(haystack: str) -> str:
    if _has_case_keyword(haystack, RECORDING_DISCLOSURE_KEYWORDS) and (
        _has_case_keyword(haystack, RECORDING_ACTION_KEYWORDS) or "녹음" in haystack or "녹취" in haystack
    ):
        return "disclosed"
    if _has_case_keyword(haystack, PHOTO_VIDEO_KEYWORDS) and _has_case_keyword(haystack, RECORDING_DISCLOSURE_KEYWORDS):
        return "posted"
    if _has_case_keyword(haystack, RECORDING_ACTION_KEYWORDS) or "녹음" in haystack or "녹취" in haystack:
        return "executed"
    if _has_case_keyword(haystack, PHOTO_VIDEO_KEYWORDS):
        return "capture"
    if _has_case_keyword(haystack, RECORDING_INTENT_KEYWORDS):
        return "intent"
    if _has_case_keyword(haystack, RECORDING_DEVICE_KEYWORDS):
        return "device_only"
    if _has_case_keyword(haystack, CASE_SAFETY_KEYWORDS):
        return "injury"
    if _has_case_keyword(haystack, PHYSICAL_VIOLENCE_KEYWORDS):
        return "assault"
    if _has_case_keyword(haystack, VERBAL_ABUSE_KEYWORDS):
        return "verbal_abuse"
    return ""


def _detect_case_disclosure_scope(haystack: str) -> str:
    if _has_case_keyword(haystack, DISCLOSURE_GROUP_KEYWORDS):
        return "group"
    if _has_case_keyword(haystack, DISCLOSURE_PUBLIC_KEYWORDS):
        return "public"
    return ""


def _detect_case_actors(haystack: str) -> list[str]:
    actors = []
    for label, keywords in ACTOR_KEYWORDS.items():
        if _has_case_keyword(haystack, keywords):
            actors.append(label)
    return actors


def _detect_case_scenes(haystack: str) -> list[str]:
    scenes = []
    for label, keywords in SCENE_KEYWORDS.items():
        if _has_case_keyword(haystack, keywords):
            scenes.append(label)
    return scenes


def _extract_case_match_features(case_result: dict) -> dict:
    haystack = normalize_for_matching(
        f"{case_result.get('title')} {case_result.get('case_number')} {case_result.get('quote')}"
    )
    return {
        "haystack": haystack,
        "stage": _detect_case_stage(haystack),
        "disclosure_scope": _detect_case_disclosure_scope(haystack),
        "actors": _detect_case_actors(haystack),
        "scenes": _detect_case_scenes(haystack),
        "mentions_consent": _has_case_keyword(haystack, CONSENT_KEYWORDS),
        "school_context": _has_case_keyword(haystack, CASE_SCHOOL_CONTEXT_KEYWORDS),
    }


def _case_match_confidence(score: int) -> str:
    if score >= CASE_MATCH_HIGH_THRESHOLD:
        return "high"
    if score >= CASE_MATCH_VISIBLE_THRESHOLD:
        return "medium"
    if score > 0:
        return "low"
    return ""


def _append_unique_reason(reasons: list[str], reason: str) -> None:
    compact_reason = compact_text(reason)
    if compact_reason and compact_reason not in reasons:
        reasons.append(compact_reason)


def _score_case_match(case_result: dict, profile: dict, *, law_id: str = "", article_ref: str = "") -> dict | None:
    strong_terms = _build_strong_match_terms(profile)
    weak_terms = _build_weak_match_terms(profile)
    case_features = _extract_case_match_features(case_result)
    haystack = case_features["haystack"]
    strong_score = sum(4 for term in strong_terms if term and term in haystack)
    weak_score = sum(1 for term in weak_terms if term and term in haystack)
    if strong_score <= 0:
        return None

    score = strong_score + weak_score
    mismatch_reasons = []
    fact_profile = profile.get("case_fact_profile") or {}
    conduct_stage = compact_text(fact_profile.get("conduct_stage"))
    disclosure_scope = compact_text(fact_profile.get("disclosure_scope"))
    target_actor = compact_text(fact_profile.get("target_actor"))
    scene_label = compact_text(fact_profile.get("scene_label"))
    quote = compact_text(case_result.get("quote"))

    if law_id and compact_text(case_result.get("law_id")) == compact_text(law_id):
        score += 6
    case_article_ref = _extract_article_reference(
        case_result.get("article") or case_result.get("article_no") or case_result.get("reference_label") or ""
    )
    if article_ref and case_article_ref and case_article_ref == compact_text(article_ref):
        score += 4

    if conduct_stage and case_features["stage"]:
        if conduct_stage == case_features["stage"]:
            score += 4
        else:
            score -= 6
            _append_unique_reason(mismatch_reasons, CASE_STAGE_LABELS.get(conduct_stage, "행위 단계 차이"))

    if disclosure_scope:
        if disclosure_scope == case_features["disclosure_scope"]:
            score += 3
        elif case_features["disclosure_scope"]:
            score -= 5
            _append_unique_reason(mismatch_reasons, "공개 범위 차이")
        elif conduct_stage in {"disclosed", "posted"}:
            score -= 2
            _append_unique_reason(mismatch_reasons, "공개 범위 확인 어려움")

    if target_actor:
        if target_actor in case_features["actors"]:
            score += 3
        elif case_features["actors"]:
            score -= 4
            _append_unique_reason(mismatch_reasons, "대상 차이")

    if scene_label:
        if scene_label in case_features["scenes"]:
            score += 2
        elif case_features["scenes"]:
            score -= 3
            _append_unique_reason(mismatch_reasons, "장면 차이")

    if fact_profile.get("requires_consent") and fact_profile.get("consent_mentioned"):
        if case_features["mentions_consent"]:
            score += 2
        else:
            score -= 3
            _append_unique_reason(mismatch_reasons, "동의 쟁점 차이")

    if fact_profile.get("school_context") and not case_features["school_context"]:
        score -= 2
        _append_unique_reason(mismatch_reasons, "학교 맥락 차이")

    if len(quote) < 20:
        score -= 2
        _append_unique_reason(mismatch_reasons, "판례 요지 정보가 짧음")

    return {
        "score": score,
        "confidence": _case_match_confidence(score),
        "mismatch_reasons": mismatch_reasons[:3],
        "case_result": case_result,
    }


def rank_case_matches(
    case_results: list[dict],
    profile: dict,
    *,
    law_id: str = "",
    article_ref: str = "",
) -> list[dict]:
    ranked = []
    for case_result in case_results:
        match = _score_case_match(case_result, profile, law_id=law_id, article_ref=article_ref)
        if not match:
            continue
        ranked.append(match)

    ranked.sort(
        key=lambda item: (
            -item["score"],
            item["case_result"].get("case_number") or item["case_result"].get("title") or "",
        )
    )
    return ranked


def select_relevant_case_citations(
    case_results: list[dict],
    profile: dict,
    *,
    limit: int = 2,
    law_id: str = "",
    article_ref: str = "",
) -> list[dict]:
    ranked_matches = rank_case_matches(case_results, profile, law_id=law_id, article_ref=article_ref)
    if not ranked_matches:
        return []

    citations = []
    for index, match in enumerate(ranked_matches, start=1):
        if match["score"] < CASE_MATCH_VISIBLE_THRESHOLD:
            continue
        citation = _build_case_citation(match["case_result"], index=index, law_id=law_id)
        citation["match_score"] = match["score"]
        citation["match_confidence"] = match["confidence"]
        citation["match_mismatch_reasons"] = list(match["mismatch_reasons"])
        citations.append(citation)
        if len(citations) >= limit:
            break
    return citations


def build_retry_after_timeout_message() -> str:
    seconds = int(getattr(settings, "TEACHER_LAW_TOTAL_TIMEOUT_SECONDS", 20))
    return f"법령 확인이 {seconds}초 안에 끝나지 않아 응답을 멈췄습니다. 잠시 후 다시 시도해 주세요."


def get_cache_date_token() -> str:
    return timezone.localdate().isoformat()


def build_cache_expiry() -> int:
    return int(getattr(settings, "TEACHER_LAW_FAQ_CACHE_TTL_SECONDS", 43200))


def cache_expired_fetched_at(iso_string: str):
    try:
        return timezone.datetime.fromisoformat(str(iso_string))
    except ValueError:
        return timezone.now() - timedelta(minutes=1)
