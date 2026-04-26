import logging
import re

from django.urls import NoReverseMatch, reverse


logger = logging.getLogger(__name__)


CALENDAR_HUB_PUBLIC_NAME = "학급 캘린더"

PUBLIC_SERVICE_TITLE_BY_ROUTE = {
    "classcalendar:main": CALENDAR_HUB_PUBLIC_NAME,
    "messagebox:main": "AI 업무 메시지 보관함",
    "schoolcomm:main": "끼리끼리 채팅방",
    "quickdrop:landing": "바로전송",
    "collect:landing": "잇티수합",
    "docsign:list": "잇티PDF사인",
    "signatures:list": "잇티하게 서명 톡",
    "doccollab:main": "잇티한글",
    "reservations:dashboard_landing": "학교 예약 시스템",
    "reservations:landing": "학교 예약 시스템",
    "qrgen:landing": "잇티QR",
    "infoboard:dashboard": "잇티보드",
}

CLASS_ACTIVITY_ROUTE_NAMES = {
    "chess:index",
    "chess:play",
    "janggi:index",
    "janggi:play",
    "fairy_games:play_dobutsu",
    "fairy_games:play_cfour",
    "fairy_games:play_isolation",
    "fairy_games:play_ataxx",
    "fairy_games:play_breakthrough",
    "fairy_games:play_reversi",
    "reflex_game:main",
    "colorbeat:main",
    "yut_game",
}

HOME_MAIN_SECTIONS = [
    {
        "key": "collect_sign",
        "title": "수합·서명",
        "subtitle": "링크로 받고 증빙까지",
        "icon": "fa-solid fa-inbox",
        "color": "blue",
    },
    {
        "key": "doc_write",
        "title": "문서·작성",
        "subtitle": "문서 생성과 정리를 빠르게",
        "icon": "fa-solid fa-file-lines",
        "color": "emerald",
    },
    {
        "key": "class_ops",
        "title": "수업·학급 운영",
        "subtitle": "교실 진행과 운영을 한 번에",
        "icon": "fa-solid fa-chalkboard-user",
        "color": "violet",
    },
    {
        "key": "class_activity",
        "title": "교실 활동",
        "subtitle": "바로 시작하는 교실 활동",
        "icon": "fa-solid fa-gamepad",
        "color": "cyan",
    },
]

HOME_AUXILIARY_SECTIONS = [
    {
        "key": "refresh",
        "title": "상담·리프레시",
        "subtitle": "성향·운세·리프레시",
        "icon": "fa-solid fa-heart",
        "color": "violet",
    },
    {
        "key": "guide",
        "title": "가이드·인사이트",
        "subtitle": "도구 안내와 인사이트",
        "icon": "fa-solid fa-lightbulb",
        "color": "cyan",
    },
    {
        "key": "external",
        "title": "외부 서비스",
        "subtitle": "연동/제휴 서비스",
        "icon": "fa-solid fa-arrow-up-right-from-square",
        "color": "emerald",
    },
]

HOME_SECTION_BY_ROUTE = {
    "collect:landing": "collect_sign",
    "consent:landing": "collect_sign",
    "docsign:list": "collect_sign",
    "signatures:landing": "collect_sign",
    "signatures:list": "collect_sign",
    "handoff:landing": "collect_sign",
    "noticegen:main": "doc_write",
    "hwpxchat:main": "doc_write",
    "version_manager:landing": "doc_write",
    "hwp_converter:landing": "doc_write",
    "classcalendar:main": "class_ops",
    "messagebox:main": "class_ops",
    "schoolcomm:main": "class_ops",
    "quickdrop:landing": "class_ops",
    "happy_seed:dashboard": "class_ops",
    "happy_seed:landing": "class_ops",
    "reservations:dashboard_landing": "class_ops",
    "reservations:landing": "class_ops",
    "textbooks:main": "class_ops",
    "edu_materials:main": "class_ops",
    "qrgen:landing": "class_ops",
    "tts_announce": "class_ops",
    "seed_quiz:landing": "class_ops",
    "ppobgi:main": "class_ops",
    "artclass:main": "class_ops",
    "schoolprograms:landing": "class_ops",
    "chess:index": "class_activity",
    "chess:play": "class_activity",
    "janggi:index": "class_activity",
    "janggi:play": "class_activity",
    "fairy_games:play_dobutsu": "class_activity",
    "fairy_games:play_cfour": "class_activity",
    "fairy_games:play_isolation": "class_activity",
    "fairy_games:play_ataxx": "class_activity",
    "fairy_games:play_breakthrough": "class_activity",
    "fairy_games:play_reversi": "class_activity",
    "reflex_game:main": "class_activity",
    "colorbeat:main": "class_activity",
    "yut_game": "class_activity",
    "studentmbti:landing": "refresh",
    "studentmbti:start": "refresh",
    "ssambti:main": "refresh",
    "teacher_law:main": "guide",
    "fortune:saju": "refresh",
    "fortune:landing": "refresh",
    "saju:landing": "refresh",
    "notebooklm_guide:main": "guide",
    "prompt_recipe:main": "guide",
    "insights:list": "guide",
}

HOME_SECTION_KEYWORDS = [
    ("동의서", "collect_sign"),
    ("수합", "collect_sign"),
    ("서명", "collect_sign"),
    ("배부", "collect_sign"),
    ("소식지", "doc_write"),
    ("멘트", "doc_write"),
    ("문서", "doc_write"),
    ("pdf", "doc_write"),
    ("최종", "doc_write"),
    ("캘린더", "class_ops"),
    ("예약", "class_ops"),
    ("알림판", "class_ops"),
    ("TTS", "class_ops"),
    ("음성", "class_ops"),
    ("퀴즈", "class_ops"),
    ("qr", "class_ops"),
    ("행복의 씨앗", "class_ops"),
    ("추첨기", "class_ops"),
    ("미술 수업", "class_ops"),
    ("체험학습", "class_ops"),
    ("학교 프로그램", "class_ops"),
    ("교사연수", "class_ops"),
    ("학교행사", "class_ops"),
    ("윷놀이", "class_activity"),
    ("체스", "class_activity"),
    ("장기", "class_activity"),
    ("리버시", "class_activity"),
    ("커넥트 포", "class_activity"),
    ("이솔레이션", "class_activity"),
    ("아택스", "class_activity"),
    ("브레이크스루", "class_activity"),
    ("순발력", "class_activity"),
    ("bti", "refresh"),
    ("운세", "refresh"),
    ("사주", "refresh"),
    ("가이드", "guide"),
    ("레시피", "guide"),
    ("백과사전", "guide"),
    ("insight", "guide"),
    ("스쿨잇", "external"),
    ("탈알고리즘", "external"),
]

HOME_SECTION_FALLBACK_BY_TYPE = {
    "collect_sign": "collect_sign",
    "classroom": "class_ops",
    "work": "doc_write",
    "game": "class_activity",
    "counsel": "refresh",
    "edutech": "guide",
    "etc": "external",
}

HOME_SECTION_META_BY_KEY = {
    section["key"]: section
    for section in [*HOME_MAIN_SECTIONS, *HOME_AUXILIARY_SECTIONS]
}

HOME_ACCENT_TOKEN_BY_SECTION_KEY = {
    "collect_sign": "collect_sign",
    "doc_write": "doc_write",
    "class_ops": "class_ops",
    "class_activity": "class_activity",
    "games": "games",
    "refresh": "refresh",
    "guide": "guide",
    "external": "external",
}

HOME_ACCENT_TOKEN_BY_ROUTE = {
    "schoolprograms:landing": "schoolprograms",
}

HOME_ICON_CLASS_BY_SERVICE_TYPE = {
    "collect_sign": "fa-solid fa-inbox",
    "work": "fa-solid fa-file-lines",
    "classroom": "fa-solid fa-chalkboard-user",
    "game": "fa-solid fa-gamepad",
    "counsel": "fa-solid fa-heart",
    "edutech": "fa-solid fa-lightbulb",
    "etc": "fa-solid fa-arrow-up-right-from-square",
}

HOME_ICON_CLASS_ALIASES = {
    "fa-solid fa-sparkles": "fa-solid fa-star",
    "fa-solid fa-up-right-from-square": "fa-solid fa-arrow-up-right-from-square",
}

HOME_ICON_CLASS_BY_ROUTE = {
    "collect:landing": "fa-solid fa-inbox",
    "collect:dashboard": "fa-solid fa-inbox",
    "consent:landing": "fa-solid fa-clipboard-check",
    "consent:dashboard": "fa-solid fa-clipboard-check",
    "docsign:list": "fa-solid fa-file-signature",
    "signatures:landing": "fa-solid fa-file-signature",
    "signatures:list": "fa-solid fa-file-signature",
    "handoff:landing": "fa-solid fa-box-open",
    "classcalendar:main": "fa-solid fa-calendar-days",
    "messagebox:main": "fa-solid fa-box-archive",
    "schoolcomm:main": "fa-solid fa-comments",
    "quickdrop:landing": "fa-solid fa-paper-plane",
    "reservations:dashboard_landing": "fa-solid fa-calendar-check",
    "reservations:landing": "fa-solid fa-calendar-check",
    "textbooks:main": "fa-solid fa-book-open",
    "edu_materials:main": "fa-solid fa-layer-group",
    "qrgen:landing": "fa-solid fa-qrcode",
    "tts_announce": "fa-solid fa-bullhorn",
    "schoolprograms:landing": "fa-solid fa-school",
    "chess:index": "fa-solid fa-chess-knight",
    "chess:play": "fa-solid fa-chess-knight",
    "janggi:index": "fa-solid fa-chess-rook",
    "janggi:play": "fa-solid fa-chess-rook",
    "reflex_game:main": "fa-solid fa-bolt",
    "colorbeat:main": "fa-solid fa-music",
    "yut_game": "fa-solid fa-dice-four",
    "teacher_law:main": "fa-solid fa-scale-balanced",
    "ssambti:main": "fa-solid fa-id-badge",
    "studentmbti:landing": "fa-solid fa-users",
    "studentmbti:start": "fa-solid fa-users",
    "fortune:saju": "fa-solid fa-star",
    "fortune:landing": "fa-solid fa-star",
    "saju:landing": "fa-solid fa-star",
}

HOME_ICON_CLASS_BY_ROUTE_PREFIX = (
    ("fairy_games:", "fa-solid fa-puzzle-piece"),
)

HOME_ICON_CLASS_BY_TITLE_KEYWORD = (
    ("쌤bti", "fa-solid fa-id-badge"),
    ("우리반bti", "fa-solid fa-users"),
    ("사주", "fa-solid fa-star"),
    ("운세", "fa-solid fa-star"),
    ("법", "fa-solid fa-scale-balanced"),
)

FORCE_LOGIN_ROUTE_NAMES = {
    "infoboard:dashboard",
    "edu_materials:main",
    "textbooks:main",
    "reservations:dashboard_landing",
}

ANONYMOUS_ROUTE_OVERRIDES = {
    "happy_seed:dashboard": "happy_seed:landing",
}

NEW_WINDOW_ROUTE_NAMES = {
    "dutyticker",
}

SERVICE_LAUNCHER_GROUP_META_BY_SECTION = {
    "class_ops": {"key": "class_ops", "title": "오늘/운영", "order": 1},
    "collect_sign": {"key": "collect_sign", "title": "수합·서명", "order": 2},
    "doc_write": {"key": "doc_write", "title": "문서·작성", "order": 3},
    "class_activity": {"key": "class_activity", "title": "수업·학급 운영", "order": 4},
    "refresh": {"key": "refresh", "title": "상담·리프레시", "order": 5},
    "guide": {"key": "guide", "title": "가이드·인사이트", "order": 6},
    "external": {"key": "external", "title": "외부 서비스", "order": 7},
}

DEFAULT_SERVICE_LAUNCHER_GROUP_META = {"key": "guide", "title": "가이드·인사이트", "order": 6}

_INLINE_CONFLICT_MARKER_RE = re.compile(r"(?:<{7}|>{7})\s*[^ \t\r\n]*")


def sanitize_public_display_text(value):
    text = str(value or "")
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    resolved_lines = []
    in_conflict = False
    keep_head_side = True

    for line in normalized.split("\n"):
        stripped = line.strip()
        if stripped.startswith("<<<<<<<"):
            inline_text = _INLINE_CONFLICT_MARKER_RE.sub(" ", stripped).strip()
            if inline_text:
                resolved_lines.append(inline_text)
                continue
            in_conflict = True
            keep_head_side = True
            continue
        if in_conflict and stripped == "=======":
            keep_head_side = False
            continue
        if in_conflict and stripped.startswith(">>>>>>>"):
            in_conflict = False
            keep_head_side = True
            continue
        if not in_conflict or keep_head_side:
            resolved_lines.append(line)

    collapsed = " ".join(" ".join(resolved_lines).split())
    cleaned = _INLINE_CONFLICT_MARKER_RE.sub(" ", collapsed).replace("=======", " ")
    return " ".join(cleaned.split())


def product_route_name(product):
    return str(getattr(product, "launch_route_name", "") or "").strip().lower()


def product_title_text(product):
    return sanitize_public_display_text(getattr(product, "title", ""))


def normalize_home_icon_class(icon_class):
    normalized_icon_class = " ".join(str(icon_class or "").strip().split()).lower()
    if not normalized_icon_class:
        return ""
    return HOME_ICON_CLASS_ALIASES.get(normalized_icon_class, normalized_icon_class)


def resolve_home_section_key(product):
    route_name = product_route_name(product)
    if route_name in HOME_SECTION_BY_ROUTE:
        return HOME_SECTION_BY_ROUTE[route_name]

    title = product_title_text(product).lower()
    for keyword, section_key in HOME_SECTION_KEYWORDS:
        if keyword.lower() in title:
            return section_key

    external_url = str(getattr(product, "external_url", "") or "").strip().lower()
    if external_url.startswith("http://") or external_url.startswith("https://"):
        return "external"

    return HOME_SECTION_FALLBACK_BY_TYPE.get(getattr(product, "service_type", ""), "guide")


def resolve_home_accent_token(product=None, *, section_key="", route_name="", service_type=""):
    if product is not None:
        route_name = product_route_name(product)
        service_type = str(getattr(product, "service_type", "") or "").strip().lower()

    normalized_route_name = str(route_name or "").strip().lower()
    if normalized_route_name in HOME_ACCENT_TOKEN_BY_ROUTE:
        return HOME_ACCENT_TOKEN_BY_ROUTE[normalized_route_name]

    normalized_section_key = str(section_key or "").strip().lower()
    if not normalized_section_key and normalized_route_name in HOME_SECTION_BY_ROUTE:
        normalized_section_key = HOME_SECTION_BY_ROUTE[normalized_route_name]
    if not normalized_section_key and service_type:
        normalized_section_key = HOME_SECTION_FALLBACK_BY_TYPE.get(service_type, "")

    return HOME_ACCENT_TOKEN_BY_SECTION_KEY.get(normalized_section_key, "external")


def resolve_home_icon_class(product=None, *, icon="", route_name="", service_type="", title=""):
    if product is not None:
        icon = getattr(product, "icon", "")
        route_name = product_route_name(product)
        service_type = str(getattr(product, "service_type", "") or "").strip().lower()
        title = product_title_text(product)

    normalized_icon = str(icon or "").strip()
    if "fa-" in normalized_icon:
        return normalize_home_icon_class(normalized_icon)

    normalized_route_name = str(route_name or "").strip().lower()
    if normalized_route_name in HOME_ICON_CLASS_BY_ROUTE:
        return HOME_ICON_CLASS_BY_ROUTE[normalized_route_name]
    for prefix, icon_class in HOME_ICON_CLASS_BY_ROUTE_PREFIX:
        if normalized_route_name.startswith(prefix):
            return icon_class

    normalized_title = str(title or "").strip().lower()
    for keyword, icon_class in HOME_ICON_CLASS_BY_TITLE_KEYWORD:
        if keyword in normalized_title:
            return icon_class

    normalized_service_type = str(service_type or "").strip().lower()
    if normalized_service_type in HOME_ICON_CLASS_BY_SERVICE_TYPE:
        return HOME_ICON_CLASS_BY_SERVICE_TYPE[normalized_service_type]

    return "fa-solid fa-star"


def resolve_product_launch_route_name(product, user=None):
    route_name = str(getattr(product, "launch_route_name", "") or "").strip()
    if not route_name:
        return ""
    if getattr(user, "is_authenticated", False):
        return route_name
    return ANONYMOUS_ROUTE_OVERRIDES.get(route_name.lower(), route_name)


def product_supports_guest_preview(product=None, *, route_name="", is_guest_allowed=False):
    if product is not None:
        route_name = getattr(product, "launch_route_name", "")
        is_guest_allowed = bool(getattr(product, "is_guest_allowed", False) or is_guest_allowed)

    normalized_route_name = str(route_name or "").strip().lower()
    if normalized_route_name in FORCE_LOGIN_ROUTE_NAMES:
        return False
    if normalized_route_name in ANONYMOUS_ROUTE_OVERRIDES:
        return True
    return bool(is_guest_allowed)


def resolve_product_launch_url(product, user=None):
    route_name = resolve_product_launch_route_name(product, user=user)
    external_url = str(getattr(product, "external_url", "") or "").strip()

    if external_url.startswith("http://") or external_url.startswith("https://"):
        return external_url, True

    if route_name:
        if (
            getattr(user, "is_authenticated", False)
            and route_name.strip().lower() == "reservations:dashboard_landing"
        ):
            return reverse("reservations:smart_entry"), False
        try:
            resolved_url = reverse(route_name)
            return resolved_url, route_name.strip().lower() in NEW_WINDOW_ROUTE_NAMES
        except NoReverseMatch:
            logger.warning("Launch route missing for product '%s' (%s).", product_title_text(product), route_name)

    if external_url:
        return external_url, False

    return reverse("product_detail", kwargs={"pk": product.pk}), False


def is_calendar_hub_product(product):
    return product_route_name(product) == "classcalendar:main"

def get_public_product_name(product):
    route_name = product_route_name(product)
    title = product_title_text(product)
    if not title:
        title = "서비스"
    return PUBLIC_SERVICE_TITLE_BY_ROUTE.get(route_name, title)


def replace_public_service_terms(text, product=None):
    cleaned = sanitize_public_display_text(text)
    if not cleaned:
        return ""
    replacement = get_public_product_name(product) if product is not None else "서비스"
    swapped = (
        cleaned.replace("교무수첩", replacement)
        .replace("교무 수첩", replacement)
        .replace("학급 기록 보드", replacement)
    )
    return sanitize_public_display_text(swapped)


def build_service_launcher_summary(product):
    public_title = get_public_product_name(product)
    for candidate in (
        getattr(product, "solve_text", ""),
        getattr(product, "lead_text", ""),
        getattr(product, "description", ""),
    ):
        summary = replace_public_service_terms(candidate, product)
        if summary and summary != public_title:
            return summary
    section_key = resolve_home_section_key(product)
    fallback = HOME_SECTION_META_BY_KEY.get(section_key, {}).get("subtitle", "")
    if fallback:
        return fallback
    return "필요한 순간 바로 열 수 있습니다."


def get_service_launcher_group_meta(product):
    section_key = resolve_home_section_key(product)
    return SERVICE_LAUNCHER_GROUP_META_BY_SECTION.get(section_key, DEFAULT_SERVICE_LAUNCHER_GROUP_META)


def build_service_launcher_items(products, user=None):
    items = []
    for index, product in enumerate(products):
        href, is_external = resolve_product_launch_url(product, user=user)
        group_meta = get_service_launcher_group_meta(product)
        title = get_public_product_name(product)
        summary = build_service_launcher_summary(product)
        items.append(
            {
                "id": product.id,
                "title": title,
                "summary": summary,
                "icon": resolve_home_icon_class(product),
                "service_type": getattr(product, "service_type", "") or "",
                "group_key": group_meta["key"],
                "group_title": group_meta["title"],
                "group_order": group_meta["order"],
                "href": href,
                "is_external": is_external,
                "searchable_text": " ".join(
                    part
                    for part in (
                        title,
                        summary,
                        group_meta["title"],
                        getattr(product, "service_type", "") or "",
                    )
                    if part
                ).lower(),
                "_sort_order": index,
            }
        )

    items.sort(key=lambda item: (item["group_order"], item["_sort_order"], item["title"]))
    for item in items:
        item.pop("_sort_order", None)
    return items
