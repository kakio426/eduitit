from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from django.urls import reverse
from django.utils.html import strip_tags


SITE_CANONICAL_BASE_URL = "https://eduitit.site"
DEFAULT_OG_IMAGE_URL = f"{SITE_CANONICAL_BASE_URL}/static/images/eduitit_og.png"
DEFAULT_HOME_TITLE = "Eduitit - 선생님의 스마트한 하루"
DEFAULT_HOME_DESCRIPTION = "AI 프롬프트 레시피, 도구 가이드, 교육용 게임까지. 교실에서의 혁신을 지금 시작하세요."


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

    def as_context(self) -> dict[str, str]:
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
    )


def build_default_page_seo(request) -> PageSeoMeta:
    current_path = getattr(request, "path", "/") if request else "/"
    return _build_page_seo(
        title=DEFAULT_HOME_TITLE,
        description=DEFAULT_HOME_DESCRIPTION,
        canonical_url=_absolute_url(current_path or "/"),
    )


def build_home_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title=DEFAULT_HOME_TITLE,
        description=DEFAULT_HOME_DESCRIPTION,
        canonical_url=_absolute_url(reverse("home")),
    )


def build_prompt_lab_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="AI 프롬프트 레시피 - Eduitit",
        description="교실과 행정에서 바로 복사해 쓸 AI 프롬프트 레시피를 카테고리별로 모았습니다.",
        canonical_url=_absolute_url(reverse("prompt_lab")),
    )


def build_tool_guide_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="도구 가이드 - Eduitit",
        description="교사가 바로 써볼 수 있는 AI·디지털 도구를 쉬운 설명과 함께 정리했습니다.",
        canonical_url=_absolute_url(reverse("tool_guide")),
    )


def build_service_guide_list_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="서비스 가이드 - Eduitit",
        description="Eduitit 주요 서비스를 설명 없이도 바로 따라갈 수 있도록 빠른 사용 안내로 모았습니다.",
        canonical_url=_absolute_url(reverse("service_guide_list")),
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
    return _build_page_seo(
        title=f"{public_title} - 서비스 가이드 - Eduitit",
        description=description or f"{product_name} 사용 흐름을 빠르게 따라갈 수 있는 안내입니다.",
        canonical_url=_absolute_url(reverse("service_guide_detail", kwargs={"pk": manual.pk})),
    )


def build_insight_list_seo(request, *, current_category: str = "", current_tag: str = "", current_sort: str = "recent") -> PageSeoMeta:
    base_canonical = _absolute_url(reverse("insights:list"))
    filtered = bool(current_category or current_tag or (current_sort and current_sort != "recent"))
    if filtered and current_tag:
        description = f"#{current_tag} 관련 인사이트를 모아봤습니다. 상세 글은 Eduitit Insight Library에서 확인하세요."
    elif filtered and current_category:
        description = f"{current_category} 분류 인사이트를 모아봤습니다. Eduitit Insight Library에서 전체 글을 확인하세요."
    else:
        description = "수업, 교실 운영, AI 활용에 도움이 되는 인사이트를 Eduitit Insight Library에서 모아봅니다."
    return _build_page_seo(
        title="Insight Library - Eduitit",
        description=description,
        canonical_url=base_canonical,
        robots="noindex,follow" if filtered else "index,follow",
    )


def build_insight_detail_seo(request, insight) -> PageSeoMeta:
    summary = _truncate_text(getattr(insight, "content", "") or getattr(insight, "kakio_note", ""), limit=180)
    if not summary:
        summary = getattr(insight, "title", "")
    return _build_page_seo(
        title=f"{insight.title} - Insight Library",
        description=summary,
        canonical_url=_absolute_url(reverse("insights:detail", kwargs={"pk": insight.pk})),
        og_image=getattr(insight, "thumbnail_url", "") or DEFAULT_OG_IMAGE_URL,
        og_type="article",
    )


def build_product_detail_seo(request, product) -> PageSeoMeta:
    product_name = getattr(product, "public_service_name", "") or getattr(product, "title", "")
    description = (
        getattr(product, "home_card_summary", "")
        or getattr(product, "teacher_first_support_label", "")
        or getattr(product, "solve_text", "")
        or getattr(product, "description", "")
    )
    image_url = ""
    image_field = getattr(product, "image", None)
    if image_field:
        try:
            image_url = image_field.url or ""
        except ValueError:
            image_url = ""
    return _build_page_seo(
        title=f"{product_name} - Eduitit",
        description=description or f"{product_name} 소개 페이지입니다.",
        canonical_url=_absolute_url(reverse("product_detail", kwargs={"pk": product.pk})),
        og_image=image_url or DEFAULT_OG_IMAGE_URL,
    )


def build_noticegen_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="알림장 & 주간학습 멘트 생성기 - Eduitit",
        description="대상과 전달 사항만 적으면 학부모 알림장과 주간학습 멘트를 빠르게 만듭니다.",
        canonical_url=_absolute_url(reverse("noticegen:main")),
    )


def build_qrgen_page_seo(request) -> PageSeoMeta:
    return _build_page_seo(
        title="수업 QR 생성기 - Eduitit",
        description="수업 링크 하나만 넣으면 바로 보여줄 QR 코드를 빠르게 만듭니다.",
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
