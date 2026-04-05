from __future__ import annotations

import os
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .query_normalizer import compact_text, normalize_for_matching


API_BASE_URL = "https://www.law.go.kr/DRF"


class LawApiError(Exception):
    pass


class LawApiConfigError(LawApiError):
    pass


class LawApiVerificationError(LawApiError):
    pass


class LawApiTimeoutError(LawApiError):
    pass


def get_api_oc() -> str:
    return str(os.environ.get("LAW_API_OC") or getattr(settings, "LAW_API_OC", "") or "").strip()


def is_configured() -> bool:
    return bool(get_api_oc())


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


def _request(endpoint: str, *, params: dict, timeout_seconds: int):
    oc = get_api_oc()
    if not oc:
        raise LawApiConfigError("국가법령정보 API 인증값이 아직 연결되지 않았습니다.")

    request_params = {
        "OC": oc,
        "type": "JSON",
        **params,
    }
    url = f"{API_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, params=request_params, timeout=timeout_seconds)
    except requests.Timeout as exc:
        raise LawApiTimeoutError("국가법령정보 응답이 지연되고 있습니다.") from exc
    except requests.RequestException as exc:
        raise LawApiError("국가법령정보에 연결하지 못했습니다.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise LawApiError("국가법령정보 응답을 해석하지 못했습니다.") from exc

    error_text = compact_text(payload.get("msg") or payload.get("result") or "")
    if error_text and "검증" in error_text:
        raise LawApiVerificationError(error_text)
    if error_text and error_text != "success":
        raise LawApiError(error_text)
    return payload


def search_laws(query: str, *, search: int = 1, display: int | None = None) -> list[dict]:
    payload = _request(
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
                "raw": item,
            }
        )
    return results


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


def get_law_details(*, law_id: str = "", mst: str = "", detail_link: str = "") -> dict:
    params = {"target": "law"}
    if law_id:
        params["ID"] = law_id
    elif mst:
        params["MST"] = mst
    else:
        raise LawApiError("상세 조회용 법령 식별자가 없습니다.")

    payload = _request(
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
        "law_name": _value_text(basic_info.get("법령명_한글") or basic_info.get("법령명한글")),
        "law_id": _value_text(basic_info.get("법령ID") or law_id),
        "mst": _value_text(law.get("법령키") or mst),
        "law_type": _value_text(basic_info.get("법종구분")),
        "ministry": _value_text(basic_info.get("소관부처")),
        "promulgation_date": _value_text(basic_info.get("공포일자")),
        "enforcement_date": _value_text(basic_info.get("시행일자")),
        "detail_link": detail_link,
        "articles": articles,
    }


def rank_search_results(results: list[dict], profile: dict) -> list[dict]:
    normalized_question = normalize_for_matching(profile.get("normalized_question"))
    hint_queries = [normalize_for_matching(item) for item in profile.get("hint_queries") or []]
    core_terms = [normalize_for_matching(item) for item in profile.get("core_terms") or []]
    scored = []
    for result in results:
        law_name = normalize_for_matching(result.get("law_name"))
        score = 0
        if law_name and law_name in normalized_question:
            score += 8
        score += sum(2 for term in core_terms[:4] if term and term in law_name)
        score += sum(6 for hint in hint_queries if hint and hint in law_name)
        if result.get("law_type"):
            score += 1
        scored.append((score, result))
    scored.sort(key=lambda item: (-item[0], item[1].get("law_name") or ""))
    return [result for _, result in scored]


def select_relevant_citations(details: dict, profile: dict, *, limit: int = 2) -> list[dict]:
    match_terms = [
        normalize_for_matching(term)
        for term in [
            *(profile.get("core_terms") or []),
            *(profile.get("hint_queries") or []),
        ]
        if term
    ]
    scored = []
    for article in details.get("articles") or []:
        haystack = normalize_for_matching(
            f"{article.get('article_label')} {article.get('article_text')}"
        )
        score = sum(1 for term in match_terms if term and term in haystack)
        if score <= 0:
            continue
        scored.append((score, article))

    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], item[1].get("article_label") or ""))
    fetched_at = timezone.now()
    citations = []
    for index, (_, article) in enumerate(scored[:limit], start=1):
        citations.append(
            {
                "citation_id": f"{details.get('law_id') or details.get('mst') or 'LAW'}-{index}",
                "law_name": details.get("law_name") or "법령",
                "law_id": details.get("law_id") or "",
                "mst": details.get("mst") or "",
                "article_label": article.get("article_label") or "",
                "quote": compact_text(article.get("article_text"))[:320],
                "source_url": details.get("detail_link") or "",
                "fetched_at": fetched_at.isoformat(),
            }
        )
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
