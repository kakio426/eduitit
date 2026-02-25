from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from math import log
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
import html
import ipaddress
import re
import socket
import xml.etree.ElementTree as ET

import requests
from django.utils import timezone


DEFAULT_NEWS_SOURCES = [
    {
        "name": "교육부 정책브리핑",
        "source_type": "gov",
        "url": "https://www.korea.kr/rss/dept_moe.xml",
    },
    {
        "name": "KEDI 보도자료",
        "source_type": "institute",
        "url": "https://www.kedi.re.kr/khome/main/announce/rssAnnounceData.do?board_sq_no=3",
    },
    {
        "name": "한겨레 종합",
        "source_type": "media",
        "url": "https://www.hani.co.kr/rss/",
    },
    {
        "name": "경향신문 종합",
        "source_type": "media",
        "url": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
    },
    {
        "name": "동아일보 종합",
        "source_type": "media",
        "url": "https://rss.donga.com/total.xml",
    },
    {
        "name": "조선일보 종합",
        "source_type": "media",
        "url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
    },
    {
        "name": "매일경제 주요",
        "source_type": "media",
        "url": "https://www.mk.co.kr/rss/30000001/",
    },
    {
        "name": "한국경제 종합",
        "source_type": "media",
        "url": "https://www.hankyung.com/feed/all-news",
    },
    {
        "name": "SBS 뉴스",
        "source_type": "media",
        "url": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01",
    },
    {
        "name": "연합뉴스TV",
        "source_type": "media",
        "url": "https://www.yonhapnewstv.co.kr/browse/feed/",
    },
    {
        "name": "뉴시스",
        "source_type": "media",
        "url": "https://www.newsis.com/RSS/sokbo.xml",
    },
]


TAG_KEYWORDS = {
    "정책·제도": ["법안", "시행령", "개정", "공청회", "발표", "추진", "기본계획", "가이드라인", "국회", "정책", "제도"],
    "교권·민원": ["교권", "아동학대", "민원", "고소", "소송", "폭언", "보호", "분리", "생활지도", "학생지도"],
    "수업·교육과정": ["교육과정", "성취기준", "수업", "평가계획", "수행평가", "프로젝트", "자유학기"],
    "에듀테크·AI": ["ai", "인공지능", "디지털교과서", "에듀테크", "플랫폼", "데이터", "코딩", "sw", "정보교육"],
    "입시·평가": ["수능", "대입", "정시", "수시", "내신", "고교학점제", "모의평가", "평가원", "대학"],
    "돌봄·복지·안전": ["늘봄", "돌봄", "방과후", "급식", "안전", "통학", "감염병", "재난", "학생복지"],
    "교원·노동·인사": ["교사", "교원", "노조", "교총", "임용", "인사", "연수", "수당", "처우", "파견"],
    "예산·재정": ["예산", "삭감", "교부금", "재정", "지원사업", "공모", "국고"],
}


USER_AGENT = (
    "Mozilla/5.0 (compatible; EduititNewsBot/1.0; +https://eduitit.com)"
)
ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
}

_META_PATTERNS = [
    r'<meta[^>]+(?:property|name)=["\']{key}["\'][^>]+content=["\'](?P<content>[^"\']+)["\'][^>]*>',
    r'<meta[^>]+content=["\'](?P<content>[^"\']+)["\'][^>]+(?:property|name)=["\']{key}["\'][^>]*>',
]


@dataclass
class ParsedEntry:
    title: str
    link: str
    description: str
    published_at: datetime | None


class UnsafeNewsUrlError(ValueError):
    """Raised when a feed/article URL fails safety checks."""


def _safe_strip(value: str | None) -> str:
    return (value or "").strip()


def _is_blocked_host(hostname: str) -> bool:
    host = hostname.lower().strip().rstrip(".")
    if host in BLOCKED_HOSTNAMES:
        return True
    if host.endswith(".local"):
        return True
    if host.endswith(".internal"):
        return True
    return False


def _is_public_ip(ip_str: str) -> bool:
    ip_obj = ipaddress.ip_address(ip_str)
    return not (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def assert_safe_public_url(url: str, allowed_host_suffixes: list[str] | None = None) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeNewsUrlError(f"허용되지 않는 URL 스킴입니다: {parsed.scheme}")
    if parsed.username or parsed.password:
        raise UnsafeNewsUrlError("인증 정보가 포함된 URL은 허용되지 않습니다.")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise UnsafeNewsUrlError("호스트가 없는 URL입니다.")
    if _is_blocked_host(hostname):
        raise UnsafeNewsUrlError(f"차단된 호스트입니다: {hostname}")

    if allowed_host_suffixes:
        normalized_suffixes = [suffix.strip().lower().lstrip(".") for suffix in allowed_host_suffixes if suffix.strip()]
        if normalized_suffixes:
            host_allowed = any(
                hostname == suffix or hostname.endswith(f".{suffix}")
                for suffix in normalized_suffixes
            )
            if not host_allowed:
                raise UnsafeNewsUrlError(f"허용 목록에 없는 호스트입니다: {hostname}")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise UnsafeNewsUrlError(f"호스트 DNS 조회 실패: {hostname}") from exc
    if not addr_infos:
        raise UnsafeNewsUrlError(f"호스트 DNS 정보가 없습니다: {hostname}")

    for addr_info in addr_infos:
        candidate_ip = addr_info[4][0]
        if not _is_public_ip(candidate_ip):
            raise UnsafeNewsUrlError(f"비공인 주소로 해석되는 호스트입니다: {hostname} ({candidate_ip})")

    return canonicalize_url(url)


def _safe_fetch(
    url: str,
    timeout: int,
    headers: dict[str, str],
    allowed_host_suffixes: list[str] | None = None,
    max_redirects: int = 4,
) -> tuple[requests.Response, str]:
    current_url = assert_safe_public_url(url, allowed_host_suffixes=allowed_host_suffixes)
    for _ in range(max_redirects + 1):
        response = requests.get(
            current_url,
            timeout=timeout,
            headers=headers,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400 and response.headers.get("Location"):
            redirected = urljoin(current_url, response.headers["Location"])
            current_url = assert_safe_public_url(redirected, allowed_host_suffixes=allowed_host_suffixes)
            continue
        return response, current_url
    raise UnsafeNewsUrlError("리다이렉트 횟수 초과")


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        return url.strip()

    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key.startswith("utm_") or lower_key in {"fbclid", "gclid", "ocid"}:
            continue
        query_items.append((key, value))

    normalized = parsed._replace(
        fragment='',
        query=urlencode(query_items, doseq=True),
    )
    return urlunparse(normalized)


def extract_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        return netloc[4:]
    return netloc


def parse_datetime(value: str | None) -> datetime | None:
    text = _safe_strip(value)
    if not text:
        return None

    parsed: datetime | None = None
    try:
        parsed = parsedate_to_datetime(text)
    except Exception:
        parsed = None

    if parsed is None:
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except Exception:
            return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=dt_timezone.utc)
    return parsed.astimezone(timezone.get_current_timezone())


def _node_local_name(node: ET.Element) -> str:
    return node.tag.rsplit('}', 1)[-1]


def _find_child_text(element: ET.Element, candidates: set[str]) -> str:
    for child in element:
        if _node_local_name(child) in candidates:
            return _safe_strip(child.text)
    return ""


def parse_rss_entries(xml_text: str) -> list[ParsedEntry]:
    root = ET.fromstring(xml_text)
    entries: list[ParsedEntry] = []

    for item in root.findall(".//item"):
        title = _find_child_text(item, {"title"})
        description = _find_child_text(item, {"description", "summary"})
        published_raw = _find_child_text(item, {"pubDate", "published", "updated"})

        link = ""
        for child in item:
            if _node_local_name(child) == "link":
                if child.attrib.get("href"):
                    link = child.attrib.get("href", "").strip()
                elif child.text:
                    link = child.text.strip()
                if link:
                    break

        if not link:
            continue
        entries.append(
            ParsedEntry(
                title=title,
                link=link,
                description=description,
                published_at=parse_datetime(published_raw),
            )
        )

    for entry in root.findall(".//{*}entry"):
        title = _find_child_text(entry, {"title"})
        description = _find_child_text(entry, {"summary", "content"})
        published_raw = _find_child_text(entry, {"published", "updated"})

        link = ""
        for child in entry:
            if _node_local_name(child) == "link":
                href = child.attrib.get("href", "").strip()
                if href:
                    link = href
                    break
                if child.text:
                    link = child.text.strip()
                    break
        if not link:
            continue
        entries.append(
            ParsedEntry(
                title=title,
                link=link,
                description=description,
                published_at=parse_datetime(published_raw),
            )
        )

    return entries


def fetch_rss_entries(
    feed_url: str,
    timeout: int = 8,
    allowed_host_suffixes: list[str] | None = None,
) -> list[ParsedEntry]:
    response, _ = _safe_fetch(
        feed_url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1"},
        allowed_host_suffixes=allowed_host_suffixes,
    )
    response.raise_for_status()
    return parse_rss_entries(response.text)


def _find_meta_content(html_text: str, key: str) -> str:
    for pattern in _META_PATTERNS:
        matched = re.search(pattern.format(key=re.escape(key)), html_text, flags=re.IGNORECASE)
        if matched:
            return html.unescape(_safe_strip(matched.group("content")))
    return ""


def _find_title(html_text: str) -> str:
    matched = re.search(r"<title[^>]*>(?P<title>.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not matched:
        return ""
    raw = re.sub(r"\s+", " ", matched.group("title"))
    return html.unescape(raw).strip()


def _find_canonical(html_text: str) -> str:
    matched = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](?P<href>[^"\']+)["\']',
        html_text,
        flags=re.IGNORECASE,
    )
    if matched:
        return _safe_strip(matched.group("href"))
    return ""


def _safe_normalize_child_url(base_url: str, child_url: str) -> str:
    normalized = canonicalize_url(urljoin(base_url, child_url))
    try:
        return assert_safe_public_url(normalized)
    except UnsafeNewsUrlError:
        return ""


def extract_og_metadata(
    url: str,
    timeout: int = 4,
    allowed_host_suffixes: list[str] | None = None,
) -> dict[str, str | datetime | None]:
    response, final_url = _safe_fetch(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        allowed_host_suffixes=allowed_host_suffixes,
    )
    response.raise_for_status()
    text = response.text[:800_000]

    og_title = _find_meta_content(text, "og:title")
    og_description = _find_meta_content(text, "og:description")
    og_image = _find_meta_content(text, "og:image")
    og_url = _find_meta_content(text, "og:url")
    published_raw = _find_meta_content(text, "article:published_time")

    title = og_title or _find_title(text)
    description = og_description or _find_meta_content(text, "description")
    canonical = og_url or _find_canonical(text) or final_url
    canonical = _safe_normalize_child_url(final_url, canonical) or canonicalize_url(final_url)
    image_url = _safe_normalize_child_url(final_url, og_image) if og_image else ""

    return {
        "title": title,
        "description": description,
        "image_url": image_url,
        "canonical_url": canonical,
        "published_at": parse_datetime(published_raw),
        "final_url": canonicalize_url(final_url),
        "publisher": extract_domain(final_url),
    }


def classify_tags(title: str, description: str, source_type: str = "", publisher: str = "") -> tuple[str, str]:
    bag = f"{title} {description} {publisher}".lower()
    score_map = {}
    for tag, keywords in TAG_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            score += bag.count(keyword.lower())
        score_map[tag] = score

    if source_type in {"gov", "institute"}:
        score_map["정책·제도"] = score_map.get("정책·제도", 0) + 1

    sorted_tags = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    primary_tag, primary_score = sorted_tags[0]
    if primary_score <= 0:
        primary_tag = "정책·제도"

    secondary_tag = ""
    if len(sorted_tags) > 1:
        secondary_name, secondary_score = sorted_tags[1]
        if secondary_score >= 3:
            secondary_tag = secondary_name

    return primary_tag, secondary_tag


def freshness_bonus(hours_ago: float) -> float:
    if hours_ago <= 12:
        return 6.0
    if hours_ago <= 24:
        return 5.0
    if hours_ago <= 48:
        return 3.0
    if hours_ago <= 72:
        return 1.0
    return 0.0


def source_bonus(source_type: str) -> float:
    if source_type in {"gov", "institute"}:
        return 1.5
    return 0.0


def compute_news_score(post, now_dt: datetime | None = None) -> float:
    now_dt = now_dt or timezone.now()
    published_at = post.published_at or post.created_at
    hours_ago = max(0.0, (now_dt - published_at).total_seconds() / 3600)
    comment_count = getattr(post, "comments_count_annotated", None)
    if comment_count is None:
        comment_count = post.comments.filter(is_hidden=False).count()
    like_count = getattr(post, "likes_count_annotated", None)
    if like_count is None:
        like_count = post.likes.count()

    return (
        freshness_bonus(hours_ago)
        + 1.2 * log(comment_count + 1)
        + 0.8 * log(like_count + 1)
        + source_bonus(post.source_type)
    )


def pick_core_news(
    posts: Iterable,
    pick_count: int = 5,
    publisher_cap: int = 2,
    tag_cap: int = 2,
) -> list:
    scored = list(posts)
    for post in scored:
        post._computed_news_score = compute_news_score(post)
    scored.sort(key=lambda item: item._computed_news_score, reverse=True)

    selected = []
    selected_ids = set()
    publisher_count: dict[str, int] = {}
    tag_count: dict[str, int] = {}

    def _can_pick(candidate, enforce_tag_cap: bool) -> bool:
        publisher = (candidate.publisher or "").strip().lower()
        tag = (candidate.primary_tag or "").strip()
        if publisher and publisher_count.get(publisher, 0) >= publisher_cap:
            return False
        if enforce_tag_cap and tag and tag_count.get(tag, 0) >= tag_cap:
            return False
        return True

    def _append(candidate):
        selected.append(candidate)
        selected_ids.add(candidate.id)
        publisher = (candidate.publisher or "").strip().lower()
        tag = (candidate.primary_tag or "").strip()
        if publisher:
            publisher_count[publisher] = publisher_count.get(publisher, 0) + 1
        if tag:
            tag_count[tag] = tag_count.get(tag, 0) + 1

    for candidate in scored:
        if len(selected) >= pick_count:
            break
        if _can_pick(candidate, enforce_tag_cap=True):
            _append(candidate)

    if len(selected) < pick_count:
        for candidate in scored:
            if len(selected) >= pick_count:
                break
            if candidate.id in selected_ids:
                continue
            if _can_pick(candidate, enforce_tag_cap=False):
                _append(candidate)

    return selected
