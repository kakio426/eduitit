from django.urls import NoReverseMatch, reverse

from products.models import Product
from core.product_visibility import filter_discoverable_products


# 완료 화면에서 다음으로 자연스럽게 이어갈 서비스 매핑
SUGGESTIONS = {
    "noticegen": ["classcalendar", "qrgen", "consent"],
    "classcalendar": ["reservations"],
    "collect": ["collect"],
    "studentmbti": ["ssambti"],
    "ssambti": ["fortune"],
    "happy_seed": ["seed_quiz"],
    "seed_quiz": ["happy_seed"],
    "reservations": ["artclass"],
    "artclass": ["ppobgi"],
}


# 서비스 키별 조회 힌트 (route 우선, title 키워드 보조)
SERVICE_META = {
    "noticegen": {
        "route_names": ["noticegen:main"],
        "title_keywords": ["알림장", "주간학습"],
        "default_icon": "📝",
        "fallback_summary": "알림장과 주간학습 멘트를 빠르게 만들어보세요.",
    },
    "classcalendar": {
        "route_names": ["classcalendar:main"],
        "title_keywords": ["캘린더", "일정"],
        "default_icon": "📅",
        "fallback_summary": "학급 일정을 한 번에 관리하세요.",
    },
    "qrgen": {
        "route_names": ["qrgen:landing"],
        "title_keywords": ["QR"],
        "default_icon": "📱",
        "fallback_summary": "가정통신문과 활동 안내에 바로 쓸 QR을 만드세요.",
    },
    "consent": {
        "route_names": ["consent:dashboard"],
        "title_keywords": ["동의"],
        "default_icon": "✍️",
        "fallback_summary": "동의서 서명과 제출 현황을 한 번에 관리하세요.",
    },
    "collect": {
        "route_names": ["collect:landing"],
        "title_keywords": ["수합"],
        "default_icon": "📥",
        "fallback_summary": "다음 수합 요청을 바로 만들어 이어서 진행하세요.",
    },
    "studentmbti": {
        "route_names": ["studentmbti:landing"],
        "title_keywords": ["우리반BTI"],
        "default_icon": "🐾",
        "fallback_summary": "학급 성향을 더 쉽게 파악하는 진단을 이어가세요.",
    },
    "ssambti": {
        "route_names": ["ssambti:main"],
        "title_keywords": ["쌤BTI"],
        "default_icon": "🦁",
        "fallback_summary": "교사 성향 결과를 확인하고 수업 스타일에 연결해보세요.",
    },
    "fortune": {
        "route_names": ["fortune:saju"],
        "title_keywords": ["운세", "사주"],
        "default_icon": "🔮",
        "fallback_summary": "상담 전에 참고할 대화 소재를 가볍게 살펴보세요.",
    },
    "happy_seed": {
        "route_names": ["happy_seed:landing"],
        "title_keywords": ["행복의 씨앗"],
        "default_icon": "🌱",
        "fallback_summary": "학급 참여 루틴을 이어서 운영해보세요.",
    },
    "seed_quiz": {
        "route_names": ["seed_quiz:landing"],
        "title_keywords": ["씨앗 퀴즈"],
        "default_icon": "🧩",
        "fallback_summary": "학생 맞춤 퀴즈를 만들고 즉시 배포해보세요.",
    },
    "reservations": {
        "route_names": ["reservations:dashboard_landing"],
        "title_keywords": ["예약"],
        "default_icon": "🗓️",
        "fallback_summary": "특별실과 고정 시간표를 한 화면에서 관리하세요.",
    },
    "artclass": {
        "route_names": ["artclass:setup"],
        "title_keywords": ["미술"],
        "default_icon": "🎨",
        "fallback_summary": "미술 수업 진행 자료를 간편하게 구성해보세요.",
    },
    "ppobgi": {
        "route_names": ["ppobgi:main"],
        "title_keywords": ["추첨기"],
        "default_icon": "🎲",
        "fallback_summary": "수업 마무리 활동으로 학생 참여를 높여보세요.",
    },
}


def _shorten_text(text, limit=70):
    value = (text or "").strip()
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}…"


def _candidate_products(meta):
    qs = filter_discoverable_products(
        Product.objects.filter(is_active=True).order_by("display_order", "title")
    )
    for route_name in meta.get("route_names", []):
        product = qs.filter(launch_route_name=route_name).first()
        if product:
            return product

    for keyword in meta.get("title_keywords", []):
        product = qs.filter(title__icontains=keyword).first()
        if product:
            return product
    return None


def _resolve_url(product, meta):
    if product and (product.external_url or "").strip():
        return product.external_url, True

    route_names = []
    if product and (product.launch_route_name or "").strip():
        route_names.append(product.launch_route_name.strip())
    route_names.extend(meta.get("route_names", []))

    tried = set()
    for route_name in route_names:
        if not route_name or route_name in tried:
            continue
        tried.add(route_name)
        try:
            return reverse(route_name), False
        except NoReverseMatch:
            continue

    if product:
        try:
            return reverse("product_detail", kwargs={"pk": product.pk}), False
        except NoReverseMatch:
            pass

    return "", False


def get_service_suggestions(service_key):
    target_keys = SUGGESTIONS.get(service_key, [])
    cards = []
    seen = set()

    for key in target_keys:
        if key in seen:
            continue
        seen.add(key)

        meta = SERVICE_META.get(key, {})
        product = _candidate_products(meta)
        url, is_external = _resolve_url(product, meta)
        if not url:
            continue

        title = product.title if product else key
        icon = (product.icon if product and product.icon else meta.get("default_icon")) or "✨"
        summary = ""
        if product:
            summary = (
                _shorten_text(product.solve_text)
                or _shorten_text(product.lead_text)
                or _shorten_text(product.description)
            )
        if not summary:
            summary = meta.get("fallback_summary", "")

        cards.append(
            {
                "key": key,
                "title": title,
                "icon": icon,
                "summary": summary,
                "url": url,
                "is_external": is_external,
            }
        )

    return cards
