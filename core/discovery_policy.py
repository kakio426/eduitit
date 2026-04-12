"""Rules for limiting public indexing of sensitive product/detail pages."""

from __future__ import annotations

SENSITIVE_DISCOVERY_ROUTE_NAMES = {
    "classcalendar:main",
    "collect:landing",
    "consent:dashboard",
    "parentcomm:main",
    "reservations:dashboard_landing",
    "reservations:landing",
    "signatures:list",
    "studentmbti:landing",
    "timetable:main",
}

SENSITIVE_DISCOVERY_PRODUCT_TITLES = {
    "가뿐하게 서명 톡",
    "간편 수합",
    "동의서는 나에게 맡겨",
    "우리반BTI",
    "전담 시간표·특별실 배치 도우미",
    "학교 예약 시스템",
    "학급 캘린더",
    "학부모 소통 허브",
}

PUBLIC_SEARCH_CANONICAL_ROUTE_NAMES = frozenset(
    {
        "collect:landing",
        "handoff:landing",
        "noticegen:main",
        "prompt_lab",
        "qrgen:landing",
        "schoolprograms:landing",
        "tts_announce",
    }
)


def _normalized(value) -> str:
    return str(value or "").strip()


def is_sensitive_discovery_target(product_or_manual) -> bool:
    product = getattr(product_or_manual, "product", product_or_manual)
    route_name = _normalized(getattr(product, "launch_route_name", ""))
    title = _normalized(getattr(product, "title", ""))

    if route_name in SENSITIVE_DISCOVERY_ROUTE_NAMES:
        return True
    if title in SENSITIVE_DISCOVERY_PRODUCT_TITLES:
        return True
    return False


def has_public_search_canonical_route(product_or_manual) -> bool:
    product = getattr(product_or_manual, "product", product_or_manual)
    route_name = _normalized(getattr(product, "launch_route_name", ""))
    return route_name in PUBLIC_SEARCH_CANONICAL_ROUTE_NAMES
