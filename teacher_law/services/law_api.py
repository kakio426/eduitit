from __future__ import annotations

import logging
import os
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .query_normalizer import compact_text, normalize_for_matching


logger = logging.getLogger(__name__)

OPEN_LAW_BASE_URLS = (
    "https://www.law.go.kr/DRF",
    "http://www.law.go.kr/DRF",
)
DEFAULT_BEOPMANG_BASE_URL = "https://api.beopmang.org/api/v4"
SUPPORTED_PROVIDERS = {"beopmang", "open_law"}


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
    for key in ("msg", "result", "message", "detail", "error"):
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
    }


def _map_beopmang_article_candidates(items, *, text_keys: tuple[str, ...]) -> list[dict]:
    articles = []
    for item in _as_list(items):
        normalized = _normalize_beopmang_article(item, text_keys=text_keys)
        if normalized:
            articles.append(normalized)
    return articles


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

    if not articles and hint:
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
        articles = _map_beopmang_article_candidates(overview_data.get("top_articles"), text_keys=("full_text", "snippet"))
        data = overview_data or data

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
