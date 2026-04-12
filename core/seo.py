from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

from django.urls import reverse
from django.utils.html import strip_tags

from .discovery_policy import has_public_search_canonical_route, is_sensitive_discovery_target


SITE_CANONICAL_BASE_URL = "https://eduitit.site"
SITE_NAME = "Eduitit"
SITE_NAME_KO = "에듀잇티"
SITE_WORDMARK = "EDUITIT"
SITE_LANGUAGE = "ko-KR"
DEFAULT_OG_IMAGE_URL = f"{SITE_CANONICAL_BASE_URL}/static/images/eduitit_og.png"
DEFAULT_FAVICON_URL = f"{SITE_CANONICAL_BASE_URL}/favicon.ico"
DEFAULT_HOME_TITLE = "교사를 위한 AI·학급 운영 도구 | Eduitit"
DEFAULT_HOME_TITLE_KO = f"{SITE_NAME_KO} - 선생님의 스마트한 하루"
DEFAULT_HOME_DESCRIPTION = f"알림장, 수업 QR, 서비스 가이드, 교실 운영 도구까지. 교사가 오늘 바로 쓰는 AI·디지털 도구를 {SITE_NAME_KO}에서 한 번에 찾으세요."


@dataclass(frozen=True)
class PageSeoMeta:
    title: str
    description: str
    canonical_url: str
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_type: str = "website"
    robots: str = "index,follow"
    structured_data: tuple[dict[str, Any], ...] = ()

    def as_context(self) -> dict[str, Any]:
        return {
            "page_title": self.title,
            "meta_description": self.description,
            "canonical_url": self.canonical_url,
            "og_title": self.og_title or self.title,
            "og_description": self.og_description or self.description,
            "og_url": self.canonical_url,
            "og_image": self.og_image or DEFAULT_OG_IMAGE_URL,
            "og_type": self.og_type,
            "robots": self.robots,
            "structured_data_json_scripts": [
                _serialize_structured_data(item) for item in self.structured_data
            ],
        }

    def as_fallback_context(self) -> dict[str, Any]:
        return {
            "default_page_title": self.title,
            "default_meta_description": self.description,
            "default_canonical_url": self.canonical_url,
            "default_og_title": self.og_title or self.title,
            "default_og_description": self.og_description or self.description,
            "default_og_url": self.canonical_url,
            "default_og_image": self.og_image or DEFAULT_OG_IMAGE_URL,
            "default_og_type": self.og_type,
            "default_robots": self.robots,
            "default_structured_data_json_scripts": [
                _serialize_structured_data(item) for item in self.structured_data
            ],
        }


def _truncate_text(value: Any, *, limit: int = 160) -> str:
    text = " ".join(strip_tags(str(value or "")).split()).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _absolute_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    return urljoin(f"{SITE_CANONICAL_BASE_URL}/", raw.lstrip("/"))


def _serialize_structured_data(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _image_field_url(image_field: Any) -> str:
    if not image_field:
        return ""
    try:
        return image_field.url or ""
    except ValueError:
        return ""


def _publisher_structured_data() -> dict[str, Any]:
    return {
        "@type": "Organization",
        "name": SITE_NAME,
        "url": SITE_CANONICAL_BASE_URL,
        "logo": {
            "@type": "ImageObject",
            "url": DEFAULT_FAVICON_URL,
        },
    }


def _breadcrumb_list_structured_data(items: list[tuple[str, str]]) -> dict[str, Any]:
    normalized_items = [
        (str(name or "").strip(), _absolute_url(url))
        for name, url in items
        if str(name or "").strip() and str(url or "").strip()
    ]
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": url,
            }
            for index, (name, url) in enumerate(normalized_items, start=1)
        ],
    }


def _collection_page_structured_data(*, name: str, description: str, url: str) -> dict[str, Any]:
    normalized_url = _absolute_url(url)
    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": f"{normalized_url}#collection",
        "name": str(name or "").strip() or DEFAULT_HOME_TITLE,
        "url": normalized_url,
        "description": _truncate_text(description or DEFAULT_HOME_DESCRIPTION),
        "inLanguage": SITE_LANGUAGE,
        "isPartOf": {
            "@type": "WebSite",
            "@id": f"{SITE_CANONICAL_BASE_URL}/#website",
            "name": SITE_NAME,
            "url": SITE_CANONICAL_BASE_URL,
        },
    }


def _web_site_structured_data() -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{SITE_CANONICAL_BASE_URL}/#website",
        "name": SITE_NAME,
        "url": SITE_CANONICAL_BASE_URL,
        "description": DEFAULT_HOME_DESCRIPTION,
        "inLanguage": SITE_LANGUAGE,
        "publisher": _publisher_structured_data(),
    }


def build_organization_structured_data(
    *,
    name: str,
    url: str,
    description: str = "",
    email: str = "",
    telephone: str = "",
    same_as: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{_absolute_url(url)}#organization",
        "name": str(name or "").strip() or SITE_NAME,
        "url": _absolute_url(url),
    }
    normalized_description = _truncate_text(description or "", limit=180)
    if normalized_description:
        payload["description"] = normalized_description
    normalized_email = str(email or "").strip()
    if normalized_email:
        payload["email"] = normalized_email
    normalized_phone = str(telephone or "").strip()
    if normalized_phone:
        payload["telephone"] = normalized_phone
    normalized_same_as = _absolute_url(same_as)
    if normalized_same_as:
        payload["sameAs"] = normalized_same_as
    return payload


def _normalize_keywords(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = str(value or "").split(",")
    keywords = []
    for raw_item in raw_items:
        keyword = str(raw_item or "").strip()
        if not keyword:
            continue
        if keyword.startswith("#"):
            keyword = keyword[1:].strip()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    return keywords


def _isoformat(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _article_structured_data(
    *,
    headline: str,
    description: str,
    url: str,
    image_url: str = "",
    date_published: Any = None,
    date_modified: Any = None,
    article_section: str = "",
    about_name: str = "",
    keywords: Any = None,
    same_as: str = "",
) -> dict[str, Any]:
    normalized_url = _absolute_url(url)
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "@id": f"{normalized_url}#article",
        "headline": str(headline or "").strip() or DEFAULT_HOME_TITLE,
        "description": _truncate_text(description or DEFAULT_HOME_DESCRIPTION, limit=180),
        "url": normalized_url,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": normalized_url,
        },
        "image": [_absolute_url(image_url) or DEFAULT_OG_IMAGE_URL],
        "author": _publisher_structured_data(),
        "publisher": _publisher_structured_data(),
        "inLanguage": SITE_LANGUAGE,
    }

    published = _isoformat(date_published)
    if published:
        payload["datePublished"] = published

    modified = _isoformat(date_modified)
    if modified:
        payload["dateModified"] = modified

    if article_section:
        payload["articleSection"] = str(article_section).strip()

    if about_name:
        payload["about"] = {
            "@type": "Thing",
            "name": str(about_name).strip(),
        }

    normalized_keywords = _normalize_keywords(keywords)
    if normalized_keywords:
        payload["keywords"] = normalized_keywords

    normalized_same_as = _absolute_url(same_as)
    if normalized_same_as:
        payload["sameAs"] = normalized_same_as

    return payload


def _build_page_seo(
    *,
    title: str,
    description: str,
    canonical_url: str,
    og_title: str = "",
    og_description: str = "",
    og_image: str = "",
    og_type: str = "website",
    robots: str = "index,follow",
    structured_data: tuple[dict[str, Any], ...] | None = None,
) -> PageSeoMeta:
    normalized_title = str(title or DEFAULT_HOME_TITLE).strip() or DEFAULT_HOME_TITLE
    normalized_description = _truncate_text(description or DEFAULT_HOME_DESCRIPTION)
    normalized_canonical = _absolute_url(canonical_url) or SITE_CANONICAL_BASE_URL
    return PageSeoMeta(
        title=normalized_title,
        description=normalized_description,
        canonical_url=normalized_canonical,
        og_title=(og_title or normalized_title).strip(),
        og_description=_truncate_text(og_description or normalized_description),
        og_image=_absolute_url(og_image) or DEFAULT_OG_IMAGE_URL,
        og_type=og_type,
        robots=robots,
        structured_data=tuple(structured_data or ()),
    )


def build_default_page_seo(request) -> PageSeoMeta:
    current_path = getattr(request, "path", "/") if request else "/"
    return _build_page_seo(
        title=DEFAULT_HOME_TITLE,
        description=DEFAULT_HOME_DESCRIPTION,
        canonical_url=_absolute_url(current_path or "/"),
    )


def build_route_page_seo(
    request,
    *,
    title: str,
    description: str,
    route_name: str = "",
    route_kwargs: dict[str, Any] | None = None,
    current_path: str = "",
    og_image: str = "",
    og_type: str = "website",
    robots: str = "index,follow",
    structured_data: tuple[dict[str, Any], ...] | None = None,
) -> PageSeoMeta:
    if route_name:
        canonical_url = _absolute_url(reverse(route_name, kwargs=route_kwargs or {}))
    else:
        resolved_path = current_path or getattr(request, "path", "/")
        canonical_url = _absolute_url(resolved_path or "/")
    return _build_page_seo(
        title=title,
        description=description,
        canonical_url=canonical_url,
        og_image=og_image,
        og_type=og_type,
        robots=robots,
        structured_data=structured_data,
    )


def build_product_route_page_seo(
    request,
    *,
    product=None,
    title: str,
    description: str = "",
    route_name: str = "",
    route_kwargs: dict[str, Any] | None = None,
    current_path: str = "",
    og_image: str = "",
    og_type: str = "website",
    robots: str = "index,follow",
    structured_data: tuple[dict[str, Any], ...] | None = None,
) -> PageSeoMeta:
    product_description = (
        getattr(product, "lead_text", "")
        or getattr(product, "solve_text", "")
        or getattr(product, "description", "")
    )
    product_image_url = _image_field_url(getattr(product, "image", None))
    return build_route_page_seo(
        request,
        title=title,
        description=description or product_description or DEFAULT_HOME_DESCRIPTION,
        route_name=route_name,
        route_kwargs=route_kwargs,
        current_path=current_path,
        og_image=og_image or product_image_url,
        og_type=og_type,
        robots=robots,
        structured_data=structured_data,
    )


def build_public_service_landing_seo(
    request,
    *,
    title: str,
    description: str,
    route_name: str,
    landing_name: str,
    product=None,
    route_kwargs: dict[str, Any] | None = None,
    current_path: str = "",
    og_image: str = "",
    og_type: str = "website",
    robots: str = "index,follow",
    additional_structured_data: tuple[dict[str, Any], ...] | None = None,
) -> PageSeoMeta:
    if route_name:
        canonical_url = _absolute_url(reverse(route_name, kwargs=route_kwargs or {}))
    else:
        canonical_url = _absolute_url(current_path or getattr(request, "path", "/"))

    structured_data = (
        _collection_page_structured_data(
            name=landing_name,
            description=description,
            url=canonical_url,
        ),
        _breadcrumb_list_structured_data(
            [
                ("홈", reverse("home")),
                (landing_name, canonical_url),
            ]
        ),
    )
    if additional_structured_data:
        structured_data = (*structured_data, *additional_structured_data)

    return build_product_route_page_seo(
        request,
        product=product,
        title=title,
        description=description,
        route_name=route_name,
        route_kwargs=route_kwargs,
        current_path=current_path,
        og_image=og_image,
        og_type=og_type,
        robots=robots,
        structured_data=structured_data,
    )


def build_public_collection_page_seo(
    request,
    *,
    title: str,
    description: str,
    route_name: str,
    collection_name: str,
    breadcrumb_items: tuple[tuple[str, str], ...],
    product=None,
    route_kwargs: dict[str, Any] | None = None,
    current_path: str = "",
    og_image: str = "",
    og_type: str = "website",
    robots: str = "index,follow",
    additional_structured_data: tuple[dict[str, Any], ...] | None = None,
) -> PageSeoMeta:
    if route_name:
        canonical_url = _absolute_url(reverse(route_name, kwargs=route_kwargs or {}))
    else:
        canonical_url = _absolute_url(current_path or getattr(request, "path", "/"))

    structured_data = (
        _collection_page_structured_data(
            name=collection_name,
            description=description,
            url=canonical_url,
        ),
        _breadcrumb_list_structured_data(list(breadcrumb_items)),
    )
    if additional_structured_data:
        structured_data = (*structured_data, *additional_structured_data)

    return build_product_route_page_seo(
        request,
        product=product,
        title=title,
        description=description,
        route_name=route_name,
        route_kwargs=route_kwargs,
        current_path=current_path,
        og_image=og_image,
        og_type=og_type,
        robots=robots,
        structured_data=structured_data,
    )


def build_public_article_page_seo(
    request,
    *,
    title: str,
    description: str,
    route_name: str,
    article_name: str,
    breadcrumb_items: tuple[tuple[str, str], ...],
    product=None,
    route_kwargs: dict[str, Any] | None = None,
    current_path: str = "",
    og_image: str = "",
    robots: str = "index,follow",
    date_published: Any = None,
    date_modified: Any = None,
    article_section: str = "",
    about_name: str = "",
    keywords: Any = None,
    same_as: str = "",
    additional_structured_data: tuple[dict[str, Any], ...] | None = None,
) -> PageSeoMeta:
    if route_name:
        canonical_url = _absolute_url(reverse(route_name, kwargs=route_kwargs or {}))
    else:
        canonical_url = _absolute_url(current_path or getattr(request, "path", "/"))

    structured_data = (
        _article_structured_data(
            headline=article_name,
            description=description,
            url=canonical_url,
            image_url=og_image,
            date_published=date_published,
            date_modified=date_modified,
            article_section=article_section,
            about_name=about_name,
            keywords=keywords,
            same_as=same_as,
        ),
        _breadcrumb_list_structured_data(list(breadcrumb_items)),
    )
    if additional_structured_data:
        structured_data = (*structured_data, *additional_structured_data)

    return build_product_route_page_seo(
        request,
        product=product,
        title=title,
        description=description,
        route_name=route_name,
        route_kwargs=route_kwargs,
        current_path=current_path,
        og_image=og_image,
        og_type="article",
        robots=robots,
        structured_data=structured_data,
    )


def build_home_page_seo(request) -> PageSeoMeta:
    canonical_url = _absolute_url(reverse("home"))
    return _build_page_seo(
        title=DEFAULT_HOME_TITLE_KO,
        description=DEFAULT_HOME_DESCRIPTION,
        canonical_url=canonical_url,
        structured_data=(
            _web_site_structured_data(),
            _collection_page_structured_data(
                name=DEFAULT_HOME_TITLE_KO,
                description=DEFAULT_HOME_DESCRIPTION,
                url=canonical_url,
            ),
        ),
    )


def build_prompt_lab_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="AI 프롬프트 레시피 | Eduitit",
        description="교실과 행정에서 바로 복사해 쓰는 프롬프트 예시를 목적별로 모았습니다.",
        canonical_url=_absolute_url(reverse("prompt_lab")),
    )


def build_tool_guide_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="교사용 AI·디지털 도구 가이드 | Eduitit",
        description="교사가 바로 써볼 수 있는 AI·디지털 도구를 쉬운 설명과 활용 맥락으로 정리했습니다.",
        canonical_url=_absolute_url(reverse("tool_guide")),
    )


def build_service_guide_list_seo(request) -> PageSeoMeta:
    canonical_url = _absolute_url(reverse("service_guide_list"))
    description = f"{SITE_NAME_KO} 주요 서비스를 설명 없이도 따라갈 수 있도록 첫 사용 흐름만 빠르게 정리한 안내 모음입니다."
    return _build_page_seo(
        title="서비스 시작 가이드 | Eduitit",
        description=description,
        canonical_url=canonical_url,
        structured_data=(
            _collection_page_structured_data(
                name="서비스 시작 가이드",
                description=description,
                url=canonical_url,
            ),
            _breadcrumb_list_structured_data(
                [
                    ("홈", reverse("home")),
                    ("서비스 시작 가이드", canonical_url),
                ]
            ),
        ),
    )


def build_product_list_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="교사용 서비스 카탈로그 | Eduitit",
        description=f"수업 준비, 학급 운영, 문서 작성, 활동 도구를 상황별로 정리한 {SITE_NAME_KO} 서비스 카탈로그입니다.",
        canonical_url=_absolute_url(reverse("product_list")),
    )


def build_portfolio_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="AI 연수·협업 포트폴리오 | Eduitit",
        description="AI 활용 연수, 에듀테크 설계, 교실 적용 사례와 협업 제안을 한 곳에서 확인하는 포트폴리오입니다.",
        canonical_url=_absolute_url(reverse("portfolio:list")),
    )


def build_about_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title=f"{SITE_NAME_KO} 소개 | 교사의 스마트한 하루",
        description=f"교사의 시간을 아껴 주는 도구를 왜, 어떻게 만들고 있는지 {SITE_NAME_KO}의 방향과 철학을 소개합니다.",
        canonical_url=_absolute_url(reverse("about")),
    )


def build_service_guide_detail_seo(request, manual) -> PageSeoMeta:
    public_title = (
        getattr(manual, "public_title", "")
        or getattr(manual, "title", "")
        or getattr(getattr(manual, "product", None), "public_service_name", "")
        or getattr(getattr(manual, "product", None), "title", "")
    )
    product_name = (
        getattr(manual, "public_service_name", "")
        or getattr(getattr(manual, "product", None), "public_service_name", "")
        or getattr(getattr(manual, "product", None), "title", "")
    )
    description = (
        getattr(manual, "public_description", "")
        or getattr(manual, "description", "")
        or getattr(getattr(manual, "product", None), "description", "")
    )
    canonical_url = _absolute_url(reverse("service_guide_detail", kwargs={"pk": manual.pk}))
    article_title = f"{public_title} - 서비스 가이드 - Eduitit"
    article_description = description or f"{product_name} 사용 흐름을 빠르게 따라갈 수 있는 안내입니다."
    image_url = _image_field_url(getattr(getattr(manual, "product", None), "image", None))
    return _build_page_seo(
        title=article_title,
        description=article_description,
        canonical_url=canonical_url,
        robots="noindex,nofollow" if is_sensitive_discovery_target(manual) else "index,follow",
        structured_data=(
            _article_structured_data(
                headline=public_title,
                description=article_description,
                url=canonical_url,
                image_url=image_url,
                date_published=getattr(manual, "created_at", None),
                date_modified=getattr(manual, "updated_at", None),
                article_section="서비스 가이드",
                about_name=product_name or public_title,
            ),
            _breadcrumb_list_structured_data(
                [
                    ("홈", reverse("home")),
                    ("서비스 시작 가이드", reverse("service_guide_list")),
                    (public_title or product_name or "서비스 가이드", canonical_url),
                ]
            ),
        ),
    )


def build_insight_list_seo(request, *, current_category: str = "", current_tag: str = "", current_sort: str = "recent") -> PageSeoMeta:
    base_canonical = _absolute_url(reverse("insights:list"))
    filtered = bool(current_category or current_tag or (current_sort and current_sort != "recent"))
    if filtered and current_tag:
        description = f"#{current_tag} 관련 교실 AI 인사이트를 모아봤습니다. 상세 글은 {SITE_NAME_KO}에서 이어서 확인하세요."
    elif filtered and current_category:
        description = f"{current_category} 주제의 교실 AI 인사이트를 모아봤습니다. {SITE_NAME_KO}에서 전체 글을 확인하세요."
    else:
        description = "수업, 학급 운영, AI 활용에 도움이 되는 실전 인사이트를 교사 관점으로 정리했습니다."
    return _build_page_seo(
        title="교실 AI 인사이트 | Eduitit",
        description=description,
        canonical_url=base_canonical,
        robots="noindex,follow" if filtered else "index,follow",
        structured_data=(
            _collection_page_structured_data(
                name="교실 AI 인사이트",
                description=description,
                url=base_canonical,
            ),
            _breadcrumb_list_structured_data(
                [
                    ("홈", reverse("home")),
                    ("교실 AI 인사이트", base_canonical),
                ]
            ),
        ),
    )


def build_insight_detail_seo(request, insight) -> PageSeoMeta:
    summary = _truncate_text(getattr(insight, "content", "") or getattr(insight, "kakio_note", ""), limit=180)
    if not summary:
        summary = getattr(insight, "title", "")
    canonical_url = _absolute_url(reverse("insights:detail", kwargs={"pk": insight.pk}))
    article_title = f"{insight.title} - Insight Library"
    return _build_page_seo(
        title=article_title,
        description=summary,
        canonical_url=canonical_url,
        og_image=getattr(insight, "thumbnail_url", "") or DEFAULT_OG_IMAGE_URL,
        og_type="article",
        structured_data=(
            _article_structured_data(
                headline=getattr(insight, "title", ""),
                description=summary,
                url=canonical_url,
                image_url=getattr(insight, "thumbnail_url", ""),
                date_published=getattr(insight, "created_at", None),
                date_modified=getattr(insight, "updated_at", None),
                article_section=getattr(insight, "get_category_display", lambda: "")(),
                about_name=getattr(insight, "title", ""),
                keywords=getattr(insight, "tags", ""),
                same_as=getattr(insight, "video_url", ""),
            ),
            _breadcrumb_list_structured_data(
                [
                    ("홈", reverse("home")),
                    ("교실 AI 인사이트", reverse("insights:list")),
                    (getattr(insight, "title", "") or "인사이트", canonical_url),
                ]
            ),
        ),
    )


def build_product_detail_seo(request, product) -> PageSeoMeta:
    product_name = getattr(product, "public_service_name", "") or getattr(product, "title", "")
    description = (
        getattr(product, "home_card_summary", "")
        or getattr(product, "teacher_first_support_label", "")
        or getattr(product, "solve_text", "")
        or getattr(product, "description", "")
    )
    image_url = _image_field_url(getattr(product, "image", None))
    canonical_url = _absolute_url(reverse("product_detail", kwargs={"pk": product.pk}))
    page_title = f"{product_name} - Eduitit"
    page_description = description or f"{product_name} 소개 페이지입니다."
    return _build_page_seo(
        title=page_title,
        description=page_description,
        canonical_url=canonical_url,
        og_image=image_url or DEFAULT_OG_IMAGE_URL,
        robots=(
            "noindex,nofollow"
            if is_sensitive_discovery_target(product) or has_public_search_canonical_route(product)
            else "index,follow"
        ),
        structured_data=(
            _article_structured_data(
                headline=product_name,
                description=page_description,
                url=canonical_url,
                image_url=image_url,
                date_published=getattr(product, "created_at", None),
                date_modified=getattr(product, "updated_at", None),
                article_section=getattr(product, "get_service_type_display", lambda: "")(),
                about_name=product_name,
            ),
            _breadcrumb_list_structured_data(
                [
                    ("홈", reverse("home")),
                    ("서비스 카탈로그", reverse("product_list")),
                    (product_name or "서비스 상세", canonical_url),
                ]
            ),
        ),
    )


def build_noticegen_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="알림장·주간학습 멘트 생성기 | Eduitit",
        description="전달할 내용만 넣으면 학부모 알림장과 주간학습 멘트를 빠르게 작성할 수 있습니다.",
        canonical_url=_absolute_url(reverse("noticegen:main")),
    )


def build_qrgen_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="수업 QR 생성기 | Eduitit",
        description="수업 자료 링크를 바로 QR 코드로 바꿔 교실에서 빠르게 공유할 수 있습니다.",
        canonical_url=_absolute_url(reverse("qrgen:landing")),
    )


def build_fortune_saju_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="사주 운세 - Eduitit",
        description="로그인 후 이용하는 비공개 사주 분석 화면입니다.",
        canonical_url=_absolute_url(reverse("fortune:saju")),
        robots="noindex,nofollow",
    )


def build_fortune_history_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="내 사주 보관함 - Eduitit",
        description="직접 저장한 사주 분석 결과를 다시 보는 비공개 보관함입니다.",
        canonical_url=_absolute_url(reverse("fortune:history")),
        robots="noindex,nofollow",
    )


def build_fortune_detail_page_seo(request, item) -> PageSeoMeta:
    if getattr(item, "target_date", None):
        description = f"{item.target_date:%Y년 %m월 %d일} 운세 보관 상세입니다."
    else:
        description = "저장한 사주 분석 결과 상세입니다."

    return _build_page_seo(
        title="사주 분석 상세보기 - Eduitit",
        description=description,
        canonical_url=_absolute_url(reverse("fortune:history_detail", kwargs={"pk": item.pk})),
        robots="noindex,nofollow",
    )


def build_fortune_chat_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="사주 선생님 채팅 - Eduitit",
        description="현재 탭의 분석 결과를 바탕으로 이어서 상담하는 비공개 채팅 화면입니다.",
        canonical_url=_absolute_url(reverse("fortune:chat_main")),
        robots="noindex,nofollow",
    )
