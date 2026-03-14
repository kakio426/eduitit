from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.core.paginator import Paginator
from django.urls import NoReverseMatch
from django.core.cache import cache
from products.models import Product, ServiceManual
from .forms import APIKeyForm, UserProfileUpdateForm
from .models import (
    UserProfile,
    UserPolicyConsent,
    Post,
    Comment,
    CommentReport,
    Feedback,
    SiteConfig,
    ProductUsageLog,
    ProductFavorite,
    ProductWorkbenchBundle,
    UserModeration,
)
from .forms import PolicyConsentForm
from .policy_consent import (
    get_agreement_source,
    get_latest_social_provider,
    has_current_policy_consent,
    mark_current_policy_consent,
    user_requires_policy_consent,
)
from .policy_meta import (
    PRIVACY_VERSION,
    TERMS_VERSION,
    get_policy_meta,
    get_provider_label,
    get_safe_next_url,
)
from . import service_launcher as service_launcher_utils
from .product_visibility import filter_discoverable_products, is_sheetbook_discovery_visible
from .active_classroom import (
    get_active_classroom_for_request,
    set_active_classroom_session,
    clear_active_classroom_session,
    set_default_classroom_for_user,
)
from .service_launcher import (
    CALENDAR_HUB_PUBLIC_NAME,
    HOME_AUXILIARY_SECTIONS,
    HOME_MAIN_SECTIONS,
    HOME_SECTION_FALLBACK_BY_TYPE,
    HOME_SECTION_META_BY_KEY,
    SHEETBOOK_PUBLIC_NAME,
    get_public_product_name as _get_public_product_name,
    is_calendar_hub_product as _is_calendar_hub_product,
    is_sheetbook_cross_surface_hidden as _is_sheetbook_cross_surface_hidden,
    is_sheetbook_product as _is_sheetbook_product,
    replace_public_service_terms as _replace_public_service_terms,
    resolve_home_section_key as _resolve_home_section_key,
    resolve_product_launch_url as _resolve_product_launch_url,
)
from .prompt_lab_data import get_prompt_lab_catalog
from .seo import (
    build_home_page_seo,
    build_prompt_lab_page_seo,
    build_service_guide_detail_seo,
    build_service_guide_list_seo,
    build_tool_guide_page_seo,
)
from .teacher_first_cards import build_favorite_service_title, build_workbench_card_meta
from django.contrib import messages
from django.db import transaction
from django.db.models import Case, Count, DateTimeField, F, IntegerField, Max, Q, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from urllib.parse import urlencode
from PIL import Image
import logging

logger = logging.getLogger(__name__)

POST_LIST_TARGET_DEFAULT = 'post-list-container'
POST_LIST_TARGET_ALLOWED = {
    POST_LIST_TARGET_DEFAULT,
    'mobile-post-list-container',
}

POST_FEED_SCOPE_ALL = 'all'
POST_FEED_SCOPE_NOTICE = 'notice'
POST_FEED_SCOPE_ALLOWED = {
    POST_FEED_SCOPE_ALL,
    POST_FEED_SCOPE_NOTICE,
}
POST_FEED_NOTICE_TYPES = (
    'notice',
)


WORKBENCH_BUNDLE_LIMIT = 6
WORKBENCH_BUNDLE_PRODUCT_LIMIT = 8
WORKBENCH_SLOT_COUNT = 4
WORKBENCH_WEEKLY_BUNDLE_LIMIT = 2


def _get_request_client_ip(request):
    forwarded_for = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip()


def _record_sheetbook_workspace_metric(request, event_name, *, metadata=None):
    if not request.user.is_authenticated:
        return
    if not getattr(settings, "SHEETBOOK_ENABLED", False):
        return
    if not is_sheetbook_discovery_visible():
        return
    try:
        from sheetbook.models import SheetbookMetricEvent
    except Exception:
        return
    try:
        SheetbookMetricEvent.objects.create(
            event_name=str(event_name or "").strip()[:80] or "workspace_event",
            user=request.user,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception(
            "[SheetbookWorkspaceMetric] failed to save event=%s user_id=%s",
            event_name,
            getattr(request.user, "id", None),
        )


def _get_post_list_target_id(request):
    """Resolve the SNS list target id from HTMX request context."""
    raw_target = (
        request.GET.get('target')
        or request.POST.get('post_list_target_id')
        or request.headers.get('HX-Target')
    )
    if not raw_target:
        return POST_LIST_TARGET_DEFAULT

    target_id = str(raw_target).strip().lstrip('#')
    if target_id in POST_LIST_TARGET_ALLOWED:
        return target_id
    return POST_LIST_TARGET_DEFAULT


def _get_post_feed_scope(request):
    raw_scope = request.GET.get('feed_scope') or request.POST.get('feed_scope')
    if not raw_scope:
        return POST_FEED_SCOPE_ALL

    feed_scope = str(raw_scope).strip().lower()
    if feed_scope in POST_FEED_SCOPE_ALLOWED:
        return feed_scope
    return POST_FEED_SCOPE_ALL


def _get_compact_posts(request):
    raw_value = request.GET.get('compact_posts') or request.POST.get('compact_posts')
    if raw_value is None:
        return False
    return str(raw_value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _render_post_list_partial(request, page_obj, feed_scope):
    empty_title = None
    empty_subtitle = None
    if feed_scope == POST_FEED_SCOPE_NOTICE:
        empty_title = "등록된 공지사항이 없습니다."
        empty_subtitle = "새 공지가 올라오면 여기서 바로 확인할 수 있어요."

    return render(
        request,
        'core/partials/post_feed_container.html',
        {
            'posts': page_obj,
            'page_obj': page_obj,
            'post_list_target_id': _get_post_list_target_id(request),
            'feed_scope': feed_scope,
            'compact_posts': _get_compact_posts(request),
            'empty_title': empty_title,
            'empty_subtitle': empty_subtitle,
        },
    )


def _build_post_feed_queryset(feed_scope=POST_FEED_SCOPE_ALL):
    now = timezone.now()
    active_feature_window = (
        Q(featured_from__isnull=False, featured_from__lte=now)
        & (Q(featured_until__isnull=True) | Q(featured_until__gte=now))
    )

    queryset = (
        Post.objects
        .filter(approval_status='approved')
        .select_related(
            'author',
            'author__userprofile',
        )
        .prefetch_related(
            'likes',
            'comments',
            'comments__author',
            'comments__author__userprofile',
        )
        .annotate(
            likes_count_annotated=Count('likes', distinct=True),
            comments_count_annotated=Count('comments', filter=Q(comments__is_hidden=False), distinct=True),
            active_feature_order=Case(
                When(active_feature_window, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            active_feature_from=Case(
                When(active_feature_window, then=F('featured_from')),
                default=Value(None),
                output_field=DateTimeField(),
            ),
        )
    )

    if feed_scope == POST_FEED_SCOPE_NOTICE:
        queryset = queryset.filter(post_type__in=POST_FEED_NOTICE_TYPES)

    return queryset.order_by('-active_feature_order', '-active_feature_from', '-created_at')


def _get_home_layout_version():
    raw_version = str(getattr(settings, 'HOME_LAYOUT_VERSION', '') or '').strip().lower()
    if raw_version in {'v1', 'v2', 'v4'}:
        return raw_version
    return 'v2' if getattr(settings, 'HOME_V2_ENABLED', False) else 'v1'


def _resolve_post_for_action(post_id, user):
    post = get_object_or_404(Post, pk=post_id)
    if post.approval_status != 'approved' and not user.is_staff and post.author_id != user.id:
        return None
    return post


def _rate_limit_exceeded(bucket_name, user_id, limits):
    """
    limits: [(window_seconds, max_count), ...]
    Returns True if any limit is exceeded.
    """
    now_ts = int(timezone.now().timestamp())
    for window_seconds, max_count in limits:
        slot = now_ts // window_seconds
        cache_key = f"core:rate:{bucket_name}:{user_id}:{window_seconds}:{slot}"
        current = cache.get(cache_key)
        if current is None:
            cache.set(cache_key, 1, timeout=window_seconds + 2)
            current = 1
        else:
            try:
                current = cache.incr(cache_key)
            except Exception:
                current = int(current) + 1
                cache.set(cache_key, current, timeout=window_seconds + 2)
        if current > max_count:
            return True
    return False


def _has_active_comment_restriction(user):
    return UserModeration.objects.filter(
        user=user,
        scope__in=['comment', 'all'],
    ).filter(
        Q(until__isnull=True) | Q(until__gt=timezone.now())
    ).exists()

HOME_COMPANION_SECTION_MAP = {
    'collect_sign': ['doc_write', 'class_ops'],
    'doc_write': ['collect_sign', 'class_ops'],
    'class_ops': ['doc_write', 'collect_sign'],
    'class_activity': ['class_ops'],
    'refresh': ['doc_write'],
}

HOME_CARD_SUMMARY_FALLBACK_BY_SECTION = {
    "collect_sign": "회수부터 서명 확인까지 바로 이어서 처리합니다.",
    "doc_write": "문서 초안과 정리를 빠르게 시작할 수 있습니다.",
    "class_ops": "오늘 운영 흐름에 맞춰 바로 실행할 수 있습니다.",
    "class_activity": "교실 분위기를 바로 살릴 수 있는 활동입니다.",
    "refresh": "상담과 리프레시가 필요할 때 바로 엽니다.",
    "guide": "필요한 안내와 참고를 빠르게 확인합니다.",
    "external": "외부 서비스로 바로 이어집니다.",
}


def _resolve_section_preview_limit(section_key, preview_limit):
    if isinstance(preview_limit, dict):
        value = preview_limit.get(section_key)
        if value is None:
            value = preview_limit.get("default")
        return value
    return preview_limit


def _build_section_payload(section, items, preview_limit=None):
    resolved_preview_limit = _resolve_section_preview_limit(section["key"], preview_limit)
    if resolved_preview_limit and resolved_preview_limit > 0:
        preview_items = items[:resolved_preview_limit]
    else:
        preview_items = items
    overflow_items = items[len(preview_items):]
    remaining_count = max(0, len(items) - len(preview_items))
    return {
        **section,
        "products": preview_items,
        "overflow_products": overflow_items,
        "total_count": len(items),
        "remaining_count": remaining_count,
        "has_more": remaining_count > 0,
    }


def _build_home_v2_display_groups(sections, aux_sections):
    ordered_sections = [*sections, *aux_sections]
    section_by_key = {section["key"]: section for section in ordered_sections}

    primary_keys = ("collect_sign", "doc_write", "class_ops", "refresh")
    secondary_keys = ("guide", "external")

    primary_display_sections = [section_by_key[key] for key in primary_keys if key in section_by_key]
    used_keys = {section["key"] for section in primary_display_sections}

    secondary_display_sections = [section_by_key[key] for key in secondary_keys if key in section_by_key and key not in used_keys]
    used_keys.update(section["key"] for section in secondary_display_sections)

    secondary_display_sections.extend(
        section for section in ordered_sections if section["key"] not in used_keys
    )

    return primary_display_sections, secondary_display_sections


def get_purpose_sections(products_qs, preview_limit=None):
    """Product list -> 메인 섹션, 보조 섹션, 활동 배너."""
    bucket = {}
    for section in [*HOME_MAIN_SECTIONS, *HOME_AUXILIARY_SECTIONS]:
        bucket[section["key"]] = []

    for product in products_qs:
        section_key = _resolve_home_section_key(product)
        if section_key not in bucket:
            section_key = HOME_SECTION_FALLBACK_BY_TYPE.get(product.service_type, "guide")
        bucket.setdefault(section_key, []).append(product)

    main_sections = []
    for section in HOME_MAIN_SECTIONS:
        # 교실 활동은 전용 배너(game_banner)로만 노출해 중복을 방지한다.
        if section["key"] == "class_activity":
            continue
        items = bucket.get(section["key"], [])
        if items:
            main_sections.append(_build_section_payload(section, items, preview_limit=preview_limit))

    aux_sections = []
    for section in HOME_AUXILIARY_SECTIONS:
        items = bucket.get(section["key"], [])
        if items:
            aux_sections.append(_build_section_payload(section, items, preview_limit=preview_limit))

    games = list(bucket.get("class_activity", []))
    return main_sections, aux_sections, games


CALENDAR_HUB_PUBLIC_NAME = "학급 캘린더"
SHEETBOOK_PUBLIC_NAME = "학급 기록 보드"

PRODUCT_CONTEXT_CHIP_DEFAULTS = {
    "collect_sign": ["안내 뒤 회수", "휴대폰 응답", "학급 전체", "10분 안팎"],
    "classroom": ["오늘 운영", "PC·모바일", "학급 전체", "5분 안팎"],
    "work": ["문서 준비", "PC 권장", "교사 1인", "10분 안팎"],
    "game": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "counsel": ["상담 전후", "PC·모바일", "개별·소그룹", "5분 안팎"],
    "edutech": ["막힐 때 참고", "PC·모바일", "교사 1인", "10분 안팎"],
    "etc": ["필요할 때 참고", "PC·모바일", "교사 1인", "10분 안팎"],
}

PRODUCT_CONTEXT_CHIP_OVERRIDES = {
    "classcalendar:main": ["오늘 일정", "PC·모바일", "학급 전체", "5분 안팎"],
    "noticegen:main": ["안내문 준비", "PC 권장", "학급 전체", "10분 안팎"],
    "collect:landing": ["안내 뒤 회수", "휴대폰 응답", "학급 전체", "10분 안팎"],
    "consent:landing": ["안내 뒤 회수", "휴대폰 응답", "학급 전체", "10분 안팎"],
    "signatures:landing": ["서명 받아야 할 때", "휴대폰 응답", "학급 전체", "10분 안팎"],
    "handoff:landing": ["배부 뒤 확인", "휴대폰 응답", "학급 전체", "10분 안팎"],
    "reservations:dashboard_landing": ["일정 잡을 때", "PC·모바일", "개별·소그룹", "5분 안팎"],
    "reservations:landing": ["일정 잡을 때", "PC·모바일", "개별·소그룹", "5분 안팎"],
    "hwpxchat:main": ["수업 준비", "PC 권장", "교사 1인", "10분 안팎"],
}

PUBLIC_EXPERIENCE_ROUTE_NAMES = {
    "chess:play",
    "janggi:play",
    "reflex_game:main",
    "yut_game",
}

FILE_REQUIRED_ROUTE_NAMES = {
    "noticegen:main",
    "hwpxchat:main",
    "hwp_pdf:convert",
}

STUDENT_PARTICIPATION_ROUTE_NAMES = {
    "chess:play",
    "janggi:play",
    "reflex_game:main",
    "yut_game",
}

HOME_SHORTCUT_SPECS = [
    {
        "key": "calendar",
        "title": "출결/일정",
        "description": "오늘 일정과 출결 흐름을 먼저 열어 봅니다.",
        "icon": "fa-solid fa-calendar-days",
        "preferred_routes": ["classcalendar:main"],
        "fallback_route": "classcalendar:main",
    },
    {
        "key": "notice",
        "title": "안내장/알림",
        "description": "안내문과 공지를 빠르게 보내야 할 때 엽니다.",
        "icon": "fa-solid fa-bullhorn",
        "preferred_routes": ["noticegen:main"],
        "fallback_route": "noticegen:main",
    },
    {
        "key": "collect",
        "title": "수합/서명",
        "description": "응답, 동의, 서명을 한 번에 받는 흐름입니다.",
        "icon": "fa-solid fa-inbox",
        "preferred_routes": ["collect:landing", "consent:landing", "signatures:landing", "handoff:landing"],
        "fallback_route": "collect:landing",
    },
    {
        "key": "prepare",
        "title": "예약/준비",
        "description": "예약, 자료 준비, 수업 전 정리를 이어서 합니다.",
        "icon": "fa-solid fa-wand-magic-sparkles",
        "preferred_routes": ["reservations:dashboard_landing", "reservations:landing", "hwpxchat:main"],
        "fallback_route": "reservations:landing",
    },
]

HOME_TRY_NOW_CARD_SPECS = [
    {
        "key": "notice",
        "service_name": "알림장 & 주간학습 멘트 생성기",
        "title": "알림장 멘트",
        "description": "알림장과 주간학습 멘트를 바로 만듭니다.",
        "icon": "fa-solid fa-note-sticky",
        "preferred_routes": ["noticegen:main"],
        "fallback_route": "noticegen:main",
        "service_type": "work",
        "is_guest_allowed": False,
    },
    {
        "key": "collect",
        "service_name": "간편 수합",
        "title": "간편 수합",
        "description": "파일·링크·응답을 한 번에 모읍니다.",
        "icon": "fa-solid fa-inbox",
        "preferred_routes": ["collect:landing"],
        "fallback_route": "collect:landing",
        "service_type": "collect_sign",
        "is_guest_allowed": True,
    },
]

HOME_TRY_NOW_SUPPORT_CARD_SPECS = [
    {
        "key": "qrgen",
        "service_name": "수업 QR 생성기",
        "title": "수업 QR 생성기",
        "description": "수업 링크를 QR로 바로 엽니다.",
        "icon": "fa-solid fa-qrcode",
        "preferred_routes": ["qrgen:landing"],
        "fallback_route": "qrgen:landing",
        "service_type": "classroom",
        "is_guest_allowed": True,
    },
    {
        "key": "prompt",
        "service_name": "AI 프롬프트 레시피",
        "title": "AI 프롬프트 레시피",
        "description": "검증된 프롬프트를 바로 꺼내 씁니다.",
        "icon": "fa-solid fa-wand-magic-sparkles",
        "preferred_routes": ["prompt_lab", "prompt_recipe:main"],
        "fallback_route": "prompt_lab",
        "service_type": "edutech",
        "is_guest_allowed": True,
    },
]

GUEST_START_CARD_SPECS = [
    {
        "title": "오늘 일정 정리",
        "description": "하루 흐름을 먼저 잡고 필요한 도구로 이어갑니다.",
        "icon": "fa-solid fa-calendar-days",
        "preferred_routes": ["classcalendar:main"],
        "fallback_route": "classcalendar:main",
    },
    {
        "title": "안내장 보내기",
        "description": "가정 안내가 필요할 때 바로 시작합니다.",
        "icon": "fa-solid fa-bullhorn",
        "preferred_routes": ["noticegen:main"],
        "fallback_route": "noticegen:main",
    },
    {
        "title": "수합/서명 받기",
        "description": "응답과 확인을 링크로 빠르게 모읍니다.",
        "icon": "fa-solid fa-file-signature",
        "preferred_routes": ["collect:landing", "consent:landing", "signatures:landing"],
        "fallback_route": "collect:landing",
    },
    {
        "title": "수업 활동 열기",
        "description": "교실 분위기를 바로 살릴 활동형 도구입니다.",
        "icon": "fa-solid fa-gamepad",
        "preferred_routes": [],
        "fallback_route": "",
        "service_type": "game",
    },
]

CATALOG_SCENARIO_SECTIONS = [
    {
        "key": "today_ops",
        "title": "오늘 운영",
        "description": "출결과 일정, 예약처럼 오늘 바로 이어야 하는 흐름입니다.",
    },
    {
        "key": "collect",
        "title": "안내와 회수",
        "description": "안내장, 수합, 동의, 서명처럼 회신을 받아야 할 때 찾습니다.",
    },
    {
        "key": "prep",
        "title": "수업 준비",
        "description": "문서 작성, 자료 정리, 발표 준비 도구를 모았습니다.",
    },
    {
        "key": "activity",
        "title": "수업 활동",
        "description": "참여형 활동과 분위기 전환 도구를 모았습니다.",
    },
    {
        "key": "counsel",
        "title": "상담·소통",
        "description": "상담 조율과 보호자 소통처럼 사람을 연결할 때 엽니다.",
    },
    {
        "key": "reference",
        "title": "참고·읽을거리",
        "description": "가이드, 인사이트, 외부 참고 서비스를 필요할 때만 엽니다.",
    },
]

VALID_CATALOG_SECTION_KEYS = {section["key"] for section in CATALOG_SCENARIO_SECTIONS}

GUIDE_ENTRY_POINT_META = [
    {
        "key": "start",
        "title": "처음 시작",
        "description": "홈과 첫 캘린더 흐름부터 짧게 확인",
        "anchor": "#guide-start",
    },
    {
        "key": "calendar",
        "title": CALENDAR_HUB_PUBLIC_NAME,
        "description": "일정에서 다른 업무로 이어지는 허브",
        "anchor": "#guide-calendar",
    },
    {
        "key": "tasks",
        "title": "자주 하는 업무",
        "description": "안내, 수합, 수업 준비를 상황별로 찾기",
        "anchor": "#guide-tasks",
    },
]


def _product_route_name(product):
    return str(getattr(product, "launch_route_name", "") or "").strip().lower()


def _product_title_text(product):
    return service_launcher_utils.product_title_text(product)


def _is_sheetbook_product(product):
    route_name = _product_route_name(product)
    title = _product_title_text(product)
    return route_name.startswith("sheetbook:") or title in {"교무수첩", SHEETBOOK_PUBLIC_NAME}


def _is_calendar_hub_product(product):
    return _product_route_name(product) == "classcalendar:main"


def _is_sheetbook_cross_surface_hidden(product):
    return not bool(getattr(product, "is_active", False))


def _get_public_product_name(product):
    return service_launcher_utils.get_public_product_name(product)


def _replace_public_service_terms(text, product=None):
    return service_launcher_utils.replace_public_service_terms(text, product)


def _build_product_context_chips(product, *, limit=None):
    route_name = _product_route_name(product)
    chips = PRODUCT_CONTEXT_CHIP_OVERRIDES.get(route_name)
    if chips is None:
        chips = PRODUCT_CONTEXT_CHIP_DEFAULTS.get(getattr(product, "service_type", ""), PRODUCT_CONTEXT_CHIP_DEFAULTS["etc"])
    chip_list = list(chips)
    if limit is not None:
        chip_list = chip_list[:limit]
    return chip_list


def _build_product_state_labels(
    product=None,
    *,
    route_name="",
    service_type="",
    launch_is_external=False,
    is_guest_allowed=False,
    limit=None,
):
    if product is not None:
        route_name = _product_route_name(product)
        service_type = str(getattr(product, "service_type", "") or "").strip()
        launch_is_external = bool(getattr(product, "launch_is_external", False))
        is_guest_allowed = bool(getattr(product, "is_guest_allowed", False))

    access_status_label = "공개 체험" if (is_guest_allowed or service_type == "game" or route_name in PUBLIC_EXPERIENCE_ROUTE_NAMES) else "로그인 필요"

    state_badges = []
    if service_type == "game" or route_name in STUDENT_PARTICIPATION_ROUTE_NAMES:
        state_badges.append("학생 참여")
    if route_name in FILE_REQUIRED_ROUTE_NAMES:
        state_badges.append("파일 필요")
    if launch_is_external:
        state_badges.append("외부 이동")

    if limit is not None:
        state_badges = state_badges[:limit]

    return {
        "home_access_status_label": access_status_label,
        "home_state_badges": state_badges,
    }


def _build_teacher_first_product_labels(product):
    task_label = service_launcher_utils.sanitize_public_display_text(getattr(product, 'solve_text', ''))
    service_label = _product_title_text(product)
    support_label = ''

    if task_label and task_label != service_label:
        support_label = service_label
    else:
        task_label = service_label
        service_label = ''
        for candidate in (
            getattr(product, 'result_text', ''),
            getattr(product, 'lead_text', ''),
            getattr(product, 'description', ''),
        ):
            support_label = service_launcher_utils.sanitize_public_display_text(candidate)
            if support_label and support_label != task_label:
                break
        else:
            support_label = ''

    public_service_name = _get_public_product_name(product)
    task_label = _replace_public_service_terms(task_label, product)
    service_label = _replace_public_service_terms(service_label, product)
    support_label = _replace_public_service_terms(support_label, product)

    if public_service_name != _product_title_text(product):
        service_label = public_service_name
    if _is_calendar_hub_product(product) and task_label in {'', public_service_name}:
        task_label = '오늘 일정 정리'
    if _is_sheetbook_product(product) and task_label in {'', public_service_name}:
        task_label = '기록 이어쓰기'

    if not support_label:
        if _is_calendar_hub_product(product):
            support_label = '오늘 일정에서 안내장, 수합, 예약까지 바로 이어갑니다.'
        elif _is_sheetbook_product(product):
            support_label = '기록을 이어 쓰거나 정리한 뒤 필요한 업무로 연결합니다.'

    return {
        'teacher_first_task_label': task_label,
        'teacher_first_service_label': service_label,
        'teacher_first_support_label': support_label,
        'public_service_name': public_service_name,
        'home_context_chips': _build_product_context_chips(product, limit=2),
        'detail_context_chips': _build_product_context_chips(product, limit=4),
        **_build_product_state_labels(product, limit=2),
    }


def _build_home_card_summary(product):
    public_service_name = str(
        getattr(product, "public_service_name", "") or getattr(product, "title", "") or ""
    ).strip()

    for candidate in (
        getattr(product, "teacher_first_support_label", ""),
        getattr(product, "solve_text", ""),
        getattr(product, "description", ""),
    ):
        summary = str(candidate or "").strip()
        if summary and summary != public_service_name:
            return _replace_public_service_terms(summary, product)

    section_key = _resolve_home_section_key(product)
    fallback = HOME_CARD_SUMMARY_FALLBACK_BY_SECTION.get(section_key)
    if not fallback:
        fallback = HOME_SECTION_META_BY_KEY.get(section_key, {}).get("subtitle", "")
    if not fallback:
        fallback = "필요한 순간 바로 열 수 있습니다."
    return _replace_public_service_terms(fallback, product)


def _build_product_guide_url_map(products):
    product_ids = [product.id for product in products if getattr(product, "id", None)]
    if not product_ids:
        return {}

    try:
        manuals = (
            ServiceManual.objects.filter(
                is_published=True,
                product__is_active=True,
                product_id__in=product_ids,
            )
            .order_by("product__display_order", "product__title", "id")
        )
    except Exception:
        logger.exception("[ProductGuideMap] published manual lookup failed")
        return {}

    guide_url_map = {}
    for manual in manuals:
        if manual.product_id in guide_url_map:
            continue
        try:
            guide_url_map[manual.product_id] = reverse("service_guide_detail", kwargs={"pk": manual.pk})
        except NoReverseMatch:
            continue
    return guide_url_map


def _attach_product_launch_meta(products):
    """Attach launch target metadata so templates can navigate directly without modal."""
    guide_url_map = _build_product_guide_url_map(products)
    prepared = []
    for product in products:
        launch_href, launch_is_external = _resolve_product_launch_url(product)
        product.launch_href = launch_href
        product.launch_is_external = launch_is_external
        product.guide_url = guide_url_map.get(product.id, "")
        product.sample_url = ""
        for attr_name, attr_value in _build_teacher_first_product_labels(product).items():
            setattr(product, attr_name, attr_value)
        product.home_card_summary = _build_home_card_summary(product)
        prepared.append(product)
    return prepared

def _get_user_favorite_products(user, product_list, limit=None):
    """홈에서 사용할 사용자 즐겨찾기 서비스 목록 반환."""
    product_map = {p.id: p for p in product_list}
    favorites_qs = (
        ProductFavorite.objects
        .filter(user=user, product__is_active=True)
        .select_related('product')
        .order_by('pin_order', '-created_at')
    )

    favorites = []
    for favorite in favorites_qs:
        product = product_map.get(favorite.product_id)
        if not product:
            continue
        favorites.append(product)
        if limit and len(favorites) >= limit:
            break
    return favorites


def _get_user_workbench_bundles(user, product_list, *, limit=WORKBENCH_BUNDLE_LIMIT):
    product_map = {p.id: p for p in product_list}
    bundles_qs = (
        ProductWorkbenchBundle.objects
        .filter(user=user)
        .order_by('-last_used_at', '-updated_at', 'name')[:limit]
    )

    bundles = []
    for bundle in bundles_qs:
        raw_ids = bundle.product_ids if isinstance(bundle.product_ids, list) else []
        normalized_ids = []
        for raw_id in raw_ids:
            try:
                pid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if pid in normalized_ids:
                continue
            if pid not in product_map:
                continue
            normalized_ids.append(pid)
        preview_titles = [build_workbench_card_meta(product_map[pid]).title for pid in normalized_ids[:3]]
        bundles.append({
            'id': bundle.id,
            'name': bundle.name,
            'product_ids': normalized_ids,
            'product_count': len(normalized_ids),
            'preview_titles': preview_titles,
            'last_used_at': bundle.last_used_at,
        })
    return bundles



def _build_workbench_slots(favorite_items, *, slot_count=WORKBENCH_SLOT_COUNT):
    total_slots = max(slot_count, len(favorite_items))
    slots = []
    for index in range(total_slots):
        if index < len(favorite_items):
            slots.append({'kind': 'item', 'index': index + 1, 'item': favorite_items[index]})
        else:
            slots.append({'kind': 'empty', 'index': index + 1})
    return slots



def _get_weekly_workbench_bundle_highlights(user, product_list, *, limit=WORKBENCH_WEEKLY_BUNDLE_LIMIT):
    from datetime import timedelta

    product_map = {p.id: p for p in product_list}
    since = timezone.now() - timedelta(days=7)
    bundles_qs = (
        ProductWorkbenchBundle.objects
        .filter(user=user)
        .filter(Q(last_used_at__gte=since) | Q(updated_at__gte=since))
        .order_by('-last_used_at', '-updated_at', 'name')[:limit]
    )

    items = []
    for bundle in bundles_qs:
        raw_ids = bundle.product_ids if isinstance(bundle.product_ids, list) else []
        normalized_ids = []
        for raw_id in raw_ids:
            try:
                pid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if pid in normalized_ids or pid not in product_map:
                continue
            normalized_ids.append(pid)
        if len(normalized_ids) < 2:
            continue
        preview_titles = [build_workbench_card_meta(product_map[pid]).title for pid in normalized_ids[:2]]
        summary_text = ' + '.join(preview_titles)
        if len(normalized_ids) > 2:
            summary_text = f"{summary_text} 외 {len(normalized_ids) - 2}"
        items.append({
            'id': bundle.id,
            'name': bundle.name,
            'product_count': len(normalized_ids),
            'summary_text': summary_text,
            'reason_label': '이번 주 자주 쓴 흐름',
        })
    return items


def _normalize_workbench_product_ids(raw_ids, *, require_non_empty=True, limit=WORKBENCH_BUNDLE_PRODUCT_LIMIT):
    if not isinstance(raw_ids, list):
        return None
    normalized_ids = []
    seen = set()
    for raw_id in raw_ids:
        try:
            pid = int(raw_id)
        except (TypeError, ValueError):
            return None
        if pid in seen:
            continue
        normalized_ids.append(pid)
        seen.add(pid)
        if len(normalized_ids) >= limit:
            break
    if require_non_empty and not normalized_ids:
        return None
    return normalized_ids


def _build_product_link_items(products, include_section_meta=False):
    """템플릿에서 공통으로 쓰는 서비스 링크 아이템 구성."""
    items = []
    for product in products:
        href, is_external = _resolve_product_launch_url(product)
        workbench_meta = build_workbench_card_meta(product)
        favorite_full_title = (
            service_launcher_utils.sanitize_public_display_text(
                getattr(product, "public_service_name", "") or getattr(product, "title", "")
            )
            or "도구"
        )
        item = {
            'product': product,
            'href': href,
            'is_external': is_external,
            'workbench_title': workbench_meta.title,
            'workbench_summary': workbench_meta.summary,
            'favorite_title': build_favorite_service_title(favorite_full_title) or favorite_full_title,
            'favorite_full_title': favorite_full_title,
        }
        if include_section_meta:
            section_key = _resolve_home_section_key(product)
            section_meta = HOME_SECTION_META_BY_KEY.get(section_key, {})
            item['section_key'] = section_key
            item['section_title'] = section_meta.get('title', '추천 도구')
            item['section_subtitle'] = section_meta.get('subtitle', '')
        items.append(item)
    return items


def _dedupe_products(products, *, exclude_ids=None, limit=None):
    exclude_ids = set(exclude_ids or [])
    unique_products = []
    seen_ids = set(exclude_ids)
    for product in products:
        if product is None:
            continue
        product_id = getattr(product, 'id', None)
        if not product_id or product_id in seen_ids:
            continue
        unique_products.append(product)
        seen_ids.add(product_id)
        if limit and len(unique_products) >= limit:
            break
    return unique_products


def _rotate_items(items, seed):
    if not items:
        return []
    offset = seed % len(items)
    return items[offset:] + items[:offset]


def _build_home_v4_representative_slots(
    user,
    *,
    favorite_products,
    recent_products,
    quick_actions,
    discovery_products,
    sections,
    aux_sections,
    games,
    limit=4,
):
    favorite_ids = {product.id for product in favorite_products}
    fixed_products = _dedupe_products(
        [*recent_products, *[product for product in quick_actions if product.id not in favorite_ids]],
        exclude_ids=favorite_ids,
        limit=2,
    )

    used_ids = favorite_ids | {product.id for product in fixed_products}
    rotating_candidates = _dedupe_products(discovery_products, exclude_ids=used_ids)
    rotation_seed = timezone.localdate().toordinal() + int(getattr(user, 'id', 0) or 0)
    rotating_products = _rotate_items(rotating_candidates, rotation_seed)[:2]
    used_ids.update(product.id for product in rotating_products)

    fallback_products = []
    for section in [*sections, *aux_sections]:
        fallback_products.extend(section.get('products', []))
        fallback_products.extend(section.get('overflow_products', []))
    fallback_products.extend(games or [])
    fallback_products = _dedupe_products(fallback_products, exclude_ids=used_ids | favorite_ids)

    slots = (
        [{'product': product, 'slot_kind': 'fixed'} for product in fixed_products]
        + [{'product': product, 'slot_kind': 'rotating'} for product in rotating_products]
    )
    for product in fallback_products:
        if len(slots) >= limit:
            break
        slots.append({'product': product, 'slot_kind': 'fallback'})
    return slots[:limit]


def _build_home_v4_recommendations(companion_items, discovery_items, *, exclude_ids=None, limit=3):
    exclude_ids = set(exclude_ids or [])
    recommendations = []
    seen_ids = set(exclude_ids)

    for item in companion_items:
        product = item.get('product')
        product_id = getattr(product, 'id', None)
        if not product_id or product_id in seen_ids:
            continue
        recommendations.append({
            'title': getattr(product, 'public_service_name', '') or getattr(product, 'title', '') or '도구',
            'href': item.get('href', ''),
            'is_external': item.get('is_external', False),
            'reason_label': item.get('reason_label') or item.get('section_title') or '추천 도구',
        })
        seen_ids.add(product_id)
        if len(recommendations) >= limit:
            return recommendations

    for item in discovery_items:
        product = item.get('product')
        product_id = getattr(product, 'id', None)
        if not product_id or product_id in seen_ids:
            continue
        recommendations.append({
            'title': item.get('favorite_title')
            or getattr(product, 'public_service_name', '')
            or getattr(product, 'title', '')
            or '도구',
            'href': item.get('href', ''),
            'is_external': item.get('is_external', False),
            'reason_label': item.get('section_title') or '추천 도구',
        })
        seen_ids.add(product_id)
        if len(recommendations) >= limit:
            break

    return recommendations


def _get_usage_based_quick_actions(user, product_list, limit=5):
    """즐겨찾기 우선 + 사용 빈도 기반 퀵 액션 목록 생성."""
    from django.utils import timezone
    from datetime import timedelta

    product_map = {p.id: p for p in product_list}
    quick_actions = []
    seen = set()

    # 1) 즐겨찾기 우선
    favorite_products = _get_user_favorite_products(user, product_list, limit=limit)
    for product in favorite_products:
        if product.id in seen:
            continue
        quick_actions.append(product)
        seen.add(product.id)
        if len(quick_actions) >= limit:
            return quick_actions

    # 2) 최근 사용 빈도
    since = timezone.now() - timedelta(days=14)
    usage_qs = (
        ProductUsageLog.objects
        .filter(user=user, created_at__gte=since, product__is_active=True)
        .values('product_id')
        .annotate(cnt=Count('product_id'))
        .order_by('-cnt')[:limit]
    )
    usage_ids = [row['product_id'] for row in usage_qs]
    for pid in usage_ids:
        product = product_map.get(pid)
        if not product or product.id in seen:
            continue
        quick_actions.append(product)
        seen.add(product.id)
        if len(quick_actions) >= limit:
            return quick_actions

    # 3) 사용 기록이 부족하면 featured → display_order 보충
    if len(quick_actions) < limit:
        for p in product_list:
            if p.is_featured and p.id not in seen:
                quick_actions.append(p)
                seen.add(p.id)
                if len(quick_actions) >= limit:
                    break
    if len(quick_actions) < limit:
        for p in product_list:
            if p.id not in seen:
                quick_actions.append(p)
                seen.add(p.id)
                if len(quick_actions) >= limit:
                    break

    return quick_actions


def _get_recently_used_products(user, product_list, *, exclude_ids=None, limit=4):
    """홈에서 최근 이어서 볼 서비스를 고른다. 즐겨찾기와는 별도 섹션으로 유지한다."""
    exclude_ids = set(exclude_ids or [])
    product_map = {p.id: p for p in product_list}
    recent_products = []
    seen = set(exclude_ids)

    usage_ids = (
        ProductUsageLog.objects
        .filter(user=user, product__is_active=True)
        .order_by('-created_at')
        .values_list('product_id', flat=True)
    )

    for product_id in usage_ids:
        if product_id in seen:
            continue
        product = product_map.get(product_id)
        if not product:
            continue
        recent_products.append(product)
        seen.add(product_id)
        if len(recent_products) >= limit:
            break

    return recent_products


def _get_home_discovery_products(user, product_list, *, exclude_ids=None, limit=4):
    """홈에서 새로 써보기 영역에 노출할 서비스 후보를 고른다."""
    exclude_ids = set(exclude_ids or [])
    featured_by_section = {}
    fallback = []

    for product in product_list:
        if product.id in exclude_ids:
            continue
        section_key = _resolve_home_section_key(product)
        if section_key == 'external':
            continue
        if product.is_featured and section_key not in featured_by_section:
            featured_by_section[section_key] = product
            continue
        fallback.append((0 if product.is_featured else 1, product.display_order, product.id, product))

    selected = list(featured_by_section.values())
    seen_ids = {product.id for product in selected}
    for _, _, _, product in sorted(fallback, key=lambda row: (row[0], row[1], row[2])):
        if product.id in seen_ids:
            continue
        selected.append(product)
        seen_ids.add(product.id)
        if len(selected) >= limit:
            break

    return selected[:limit]



def _get_home_companion_items(seed_products, product_list, *, exclude_ids=None, limit=3):
    """현재 흐름과 자주 이어지는 도구를 홈에 짧게 추천한다."""
    exclude_ids = set(exclude_ids or [])
    seed_section_keys = []
    for product in seed_products:
        section_key = _resolve_home_section_key(product)
        if section_key == 'external' or section_key in seed_section_keys:
            continue
        seed_section_keys.append(section_key)

    if not seed_section_keys:
        return []

    products_by_section = {}
    for product in product_list:
        if product.id in exclude_ids:
            continue
        section_key = _resolve_home_section_key(product)
        if section_key == 'external':
            continue
        products_by_section.setdefault(section_key, []).append(product)

    for section_key, section_products in products_by_section.items():
        products_by_section[section_key] = sorted(
            section_products,
            key=lambda item: (0 if item.is_featured else 1, item.display_order, item.id),
        )

    items = []
    seen_ids = set(exclude_ids)
    picked_sections = set()
    for source_section in seed_section_keys:
        for target_section in HOME_COMPANION_SECTION_MAP.get(source_section, []):
            if len(items) >= limit:
                break
            if target_section in picked_sections:
                continue
            candidates = products_by_section.get(target_section, [])
            product = next((candidate for candidate in candidates if candidate.id not in seen_ids), None)
            if not product:
                continue
            source_meta = HOME_SECTION_META_BY_KEY.get(source_section, {})
            target_meta = HOME_SECTION_META_BY_KEY.get(target_section, {})
            href, is_external = _resolve_product_launch_url(product)
            items.append({
                'product': product,
                'href': href,
                'is_external': is_external,
                'section_key': target_section,
                'section_title': target_meta.get('title', '추천 도구'),
                'reason_label': f"{source_meta.get('title', '지금 하는 일')}과 같이 쓰기",
                'action_label': '작업대에 추가',
            })
            seen_ids.add(product.id)
            picked_sections.add(target_section)
        if len(items) >= limit:
            break

    return items


def _build_home_student_games_qr_context(request):
    """홈 화면에서 바로 사용할 학생 게임 QR 컨텍스트 생성."""
    if not request.user.is_authenticated:
        return {}

    from products.views import _student_games_launch_ticket_ttl_minutes

    return {
        "student_games_issue_url": reverse("dt_student_games_issue"),
        "student_games_launch_ttl_minutes": _student_games_launch_ticket_ttl_minutes(),
    }


def _build_today_context(request):
    """홈 V2용 오늘 할 일 위젯 데이터."""
    if not request.user.is_authenticated:
        return {"today_items": []}

    today = timezone.localdate()
    today_items = []

    try:
        from reservations.models import Reservation

        reservation_count = Reservation.objects.filter(
            room__school__owner=request.user,
            date=today,
        ).count()
        if reservation_count > 0:
            today_items.append(
                {
                    "title": "오늘 특별실 예약 확인",
                    "count_text": f"{reservation_count}건",
                    "description": "오늘 예약 현황을 확인하고 필요한 변경을 빠르게 처리하세요.",
                    "emoji": "🗓️",
                    "href": reverse("reservations:dashboard_landing"),
                    "cta_text": "예약 대시보드 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] reservations 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    try:
        from collect.models import CollectionRequest

        collect_due_count = CollectionRequest.objects.filter(
            creator=request.user,
            status="active",
            deadline__isnull=False,
            deadline__date=today,
        ).count()
        if collect_due_count > 0:
            today_items.append(
                {
                    "title": "오늘 마감 수합 점검",
                    "count_text": f"{collect_due_count}건",
                    "description": "마감일이 오늘인 수합 요청이 있습니다. 미제출자를 확인해 주세요.",
                    "emoji": "📥",
                    "href": reverse("collect:dashboard"),
                    "cta_text": "수합 대시보드 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] collect 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    try:
        from consent.models import SignatureRecipient, SignatureRequest

        unsigned_consent_count = SignatureRecipient.objects.filter(
            request__created_by=request.user,
            request__status=SignatureRequest.STATUS_SENT,
            status__in=[
                SignatureRecipient.STATUS_PENDING,
                SignatureRecipient.STATUS_VERIFIED,
            ],
        ).count()
        if unsigned_consent_count > 0:
            today_items.append(
                {
                    "title": "미서명 동의서 확인",
                    "count_text": f"{unsigned_consent_count}건",
                    "description": "서명이 아직 완료되지 않은 동의서가 있습니다. 진행 상태를 확인해 주세요.",
                    "emoji": "✍️",
                    "href": reverse("consent:dashboard"),
                    "cta_text": "동의서 대시보드 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] consent 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    try:
        from classcalendar.today_memos import build_today_execution_context

        active_classroom = get_active_classroom_for_request(request) if hasattr(request, "session") else None
        calendar_workspace = build_today_execution_context(
            request.user,
            active_classroom=active_classroom,
            target_date=today,
            today_url=_home_calendar_surface_url(),
            main_url=_home_calendar_surface_url(),
            create_api_url=_safe_reverse("classcalendar:api_create_event"),
        )
        if calendar_workspace["today_event_count"] > 0:
            today_items.append(
                {
                    "title": "오늘 학급 일정",
                    "count_text": f"{calendar_workspace['today_event_count']}건",
                    "description": "캘린더에서 오늘 일정과 메모를 같은 기준으로 확인하세요.",
                    "emoji": "📅",
                    "href": calendar_workspace["today_all_url"] or _home_calendar_surface_url(),
                    "cta_text": "캘린더 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] classcalendar 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    return {
        "today_items": today_items,
        "today_date_text": today.strftime("%Y-%m-%d"),
    }


def _build_sheetbook_workspace_context(request, *, require_discovery_visible=True):
    workspace = {
        "enabled": False,
        "entry_url": "",
        "create_url": "",
        "copy_url": "",
        "create_action_url": "",
        "copy_action_url": "",
        "recent_sheetbooks": [],
        "today_rows": [],
        "today_date_text": timezone.localdate().strftime("%Y-%m-%d"),
        "quick_actions": [],
    }

    if (
        not request.user.is_authenticated
        or not getattr(settings, "SHEETBOOK_ENABLED", False)
        or (require_discovery_visible and not is_sheetbook_discovery_visible())
    ):
        return {"sheetbook_workspace": workspace}

    try:
        from sheetbook.models import Sheetbook, SheetCell, SheetColumn, SheetTab
    except Exception:
        logger.exception("[SheetbookWorkspace] sheetbook import failed")
        return {"sheetbook_workspace": workspace}

    try:
        index_url = reverse("sheetbook:index")
    except NoReverseMatch:
        logger.exception("[SheetbookWorkspace] sheetbook:index route missing")
        return {"sheetbook_workspace": workspace}

    workspace["enabled"] = True
    workspace["create_url"] = f"{index_url}?source=workspace_home_create"
    workspace["copy_url"] = f"{index_url}?source=workspace_home_copy"
    try:
        workspace["create_action_url"] = reverse("sheetbook:quick_create")
    except NoReverseMatch:
        workspace["create_action_url"] = ""
    try:
        workspace["copy_action_url"] = reverse("sheetbook:quick_copy")
    except NoReverseMatch:
        workspace["copy_action_url"] = ""

    recent_qs = (
        Sheetbook.objects
        .filter(owner=request.user)
        .prefetch_related("tabs")
        .order_by("-updated_at", "-id")[:5]
    )
    recent_items = []
    for item in recent_qs:
        detail_url = reverse("sheetbook:detail", kwargs={"pk": item.pk})
        recent_items.append(
            {
                "id": item.id,
                "title": item.title,
                "updated_at": item.updated_at,
                "tab_count": item.tabs.count(),
                "href": f"{detail_url}?source=workspace_home_recent",
            }
        )
    workspace["recent_sheetbooks"] = recent_items
    workspace["entry_url"] = recent_items[0]["href"] if recent_items else f"{index_url}?source=workspace_home_entry"

    quick_action_specs = [
        ("간편 수합", "collect:dashboard", "fa-solid fa-inbox"),
        ("동의서", "consent:dashboard", "fa-solid fa-file-signature"),
        ("배부 체크", "handoff:dashboard", "fa-solid fa-list-check"),
        ("안내문", "noticegen:main", "fa-solid fa-newspaper"),
    ]
    quick_actions = []
    for title, route_name, icon in quick_action_specs:
        try:
            href = reverse(route_name)
        except NoReverseMatch:
            continue
        quick_actions.append({"title": title, "href": href, "icon": icon})
    workspace["quick_actions"] = quick_actions

    today = timezone.localdate()
    date_cells = list(
        SheetCell.objects.filter(
            row__tab__sheetbook__owner=request.user,
            row__tab__tab_type=SheetTab.TYPE_GRID,
            column__column_type=SheetColumn.TYPE_DATE,
            value_date=today,
        )
        .select_related("row__tab__sheetbook")
        .order_by("-row__tab__sheetbook__updated_at", "row__sort_order", "id")[:6]
    )

    row_ids = [cell.row_id for cell in date_cells]
    title_map = {}
    if row_ids:
        text_cells = (
            SheetCell.objects
            .filter(row_id__in=row_ids, column__column_type=SheetColumn.TYPE_TEXT)
            .select_related("column")
            .order_by("row_id", "column__sort_order", "id")
        )
        for cell in text_cells:
            cleaned = (cell.value_text or "").strip()
            if cleaned and cell.row_id not in title_map:
                title_map[cell.row_id] = cleaned

    today_rows = []
    for date_cell in date_cells:
        row = date_cell.row
        tab = row.tab
        sheetbook = tab.sheetbook
        title = title_map.get(row.id) or f"{tab.name} 일정"
        today_rows.append(
            {
                "title": title,
                "sheetbook_title": sheetbook.title,
                "href": f"{reverse('sheetbook:detail', kwargs={'pk': sheetbook.id})}?tab={tab.id}&source=workspace_home_today",
            }
        )
    workspace["today_rows"] = today_rows
    _record_sheetbook_workspace_metric(
        request,
        "workspace_home_opened",
        metadata={
            "recent_sheetbook_count": len(recent_items),
            "today_row_count": len(today_rows),
            "quick_action_count": len(quick_actions),
        },
    )

    return {"sheetbook_workspace": workspace}


def _build_home_community_summary_posts(page_obj, *, limit=2):
    object_list = list(getattr(page_obj, "object_list", []) or [])
    prioritized = sorted(
        enumerate(object_list),
        key=lambda row: (
            0 if getattr(row[1], "post_type", "") == "notice" else 1,
            0 if getattr(getattr(row[1], "author", None), "is_staff", False) else 1,
            row[0],
        ),
    )

    items = []
    for _, post in prioritized[:limit]:
        image_url = ""
        try:
            if getattr(post, "image", None):
                image_url = post.image.url
        except Exception:
            image_url = ""
        if not image_url:
            image_url = str(getattr(post, "og_image_url", "") or "").strip()

        post_type = str(getattr(post, "post_type", "") or "").strip()
        title = ""
        body = ""
        eyebrow = "최근 소통"

        if post_type == "notice":
            eyebrow = "공지"
            title = str(getattr(post, "og_title", "") or "").strip()
            body = str(getattr(post, "content", "") or "").strip()
        elif post_type == "news_link":
            eyebrow = "뉴스"
            title = str(getattr(post, "og_title", "") or "").strip()
            body = str(getattr(post, "og_description", "") or getattr(post, "content", "") or "").strip()
        else:
            body = str(getattr(post, "content", "") or "").strip()

        if title and body:
            if body == title:
                body = ""
            elif body.startswith(title):
                body = body[len(title):].strip(" -:\n")

        items.append(
            {
                "post": post,
                "eyebrow": eyebrow,
                "title": title,
                "body": body,
                "image_url": image_url,
            }
        )
    return items


def _format_home_calendar_schedule(event):
    start_dt = timezone.localtime(event.start_time)
    end_dt = timezone.localtime(event.end_time)
    if getattr(event, "is_all_day", False):
        return f"{start_dt.month}월 {start_dt.day}일 · 하루 종일"
    if start_dt.date() == end_dt.date():
        return f"{start_dt.month}월 {start_dt.day}일 · {start_dt:%H:%M} - {end_dt:%H:%M}"
    return f"{start_dt.month}월 {start_dt.day}일 {start_dt:%H:%M} ~ {end_dt.month}월 {end_dt.day}일 {end_dt:%H:%M}"


def _extract_home_calendar_event_note(event):
    try:
        text_blocks = sorted(
            (block for block in event.blocks.all() if block.block_type == "text"),
            key=lambda block: (block.order, block.id),
        )
    except Exception:
        return ""

    if not text_blocks:
        return ""

    content = text_blocks[0].content
    if isinstance(content, dict):
        note_text = content.get("text") or content.get("note") or ""
    elif isinstance(content, str):
        note_text = content
    else:
        note_text = ""
    return str(note_text).strip()


def _build_home_calendar_memo_excerpt(note_text, *, max_length=120):
    lines = [line.strip() for line in str(note_text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    normalized = "\n".join(lines)
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def _format_home_task_schedule(task):
    if not getattr(task, "due_at", None):
        return "오늘 다시 볼 할 일"
    due_dt = timezone.localtime(task.due_at)
    if getattr(task, "has_time", False):
        return f"{due_dt.month}월 {due_dt.day}일 · {due_dt:%H:%M}까지"
    return f"{due_dt.month}월 {due_dt.day}일 · 오늘 할 일"


def _build_home_calendar_summary_context(request):
    today = timezone.localdate()
    summary = {
        "enabled": False,
        "today_count": 0,
        "week_count": 0,
        "today_event_count": 0,
        "today_event_memo_count": 0,
        "today_task_count": 0,
        "today_task_memo_count": 0,
        "today_events": [],
        "today_memo_items": [],
        "today_event_memos": [],
        "today_memos": [],
        "review_memos": [],
        "review_groups": [],
        "today_tasks": [],
        "today_task_memos": [],
        "next_upcoming_events": [],
        "recent_memo_items": [],
        "has_supporting_items": False,
        "today_memo_empty_message": "오늘 확인할 일정, 메모, 할 일이 없습니다.",
        "empty_message": "오늘 확인할 일정, 메모, 할 일이 없습니다.",
        "main_url": "",
        "today_url": "",
        "today_all_url": "",
        "today_memo_url": "",
        "today_review_url": "",
        "today_memo_panel_url": "",
        "today_create_url": "",
        "main_create_url": "",
        "create_api_url": "",
        "date_key": today.isoformat(),
        "date_label": f"{today.month}월 {today.day}일",
        "has_items": False,
    }
    if not request.user.is_authenticated:
        return summary

    try:
        from classcalendar.today_memos import build_today_execution_context
    except Exception:
        logger.exception("[Home] classcalendar import failed")
        return summary

    try:
        summary["main_url"] = _safe_calendar_surface_reverse("calendar_main", "classcalendar:main")
    except NoReverseMatch:
        summary["main_url"] = ""
    try:
        summary["today_url"] = _safe_calendar_surface_reverse("calendar_today", "classcalendar:today")
    except NoReverseMatch:
        summary["today_url"] = ""
    if summary["main_url"]:
        summary["today_memo_panel_url"] = summary["today_url"] or summary["main_url"]

    try:
        summary["create_api_url"] = reverse("classcalendar:api_create_event")
    except NoReverseMatch:
        summary["create_api_url"] = ""
    active_classroom = get_active_classroom_for_request(request)
    workspace = build_today_execution_context(
        request.user,
        active_classroom=active_classroom,
        target_date=today,
        main_url=summary["main_url"],
        today_url=summary["today_url"],
        create_api_url=summary["create_api_url"],
    )
    summary.update(workspace)
    summary["today_memo_items"] = workspace.get("today_memos", [])
    summary["today_memo_panel_url"] = workspace.get("today_memo_url") or summary["today_memo_panel_url"]
    summary["today_memo_empty_message"] = workspace.get("empty_message", summary["today_memo_empty_message"])
    summary["enabled"] = bool(summary["today_url"] and summary["main_url"] and summary["create_api_url"])
    return summary


def _safe_reverse(route_name):
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return ""


def _safe_calendar_surface_reverse(alias_route_name, fallback_route_name):
    return _safe_reverse(alias_route_name) or _safe_reverse(fallback_route_name)


def _home_calendar_surface_url():
    home_url = _safe_reverse("home")
    if home_url:
        return f"{home_url}#home-calendar"
    return _safe_calendar_surface_reverse("calendar_main", "classcalendar:main")


def _build_public_calendar_entry_context():
    main_url = _home_calendar_surface_url()
    today_url = _home_calendar_surface_url()
    login_url = _safe_reverse("account_login")
    login_with_next = login_url
    if login_url and main_url:
        login_with_next = f"{login_url}?{urlencode({'next': main_url})}"
    return {
        "title": CALENDAR_HUB_PUBLIC_NAME,
        "description": "로그인 후 내 일정과 메모를 이어서 봅니다.",
        "supporting_copy": "홈에서 숫자 달력과 날짜별 일정을 바로 보고, 같은 화면에서 이어서 확인합니다.",
        "main_url": main_url,
        "today_url": today_url,
        "login_url": login_with_next or login_url or main_url,
        "chips": [
            "오늘 일정 정리",
            "오늘 메모 확인",
            "홈에서 캘린더 보기",
        ],
    }


def _find_product_by_routes(product_list, route_names):
    route_name_set = {str(route_name or "").strip().lower() for route_name in route_names or [] if route_name}
    if not route_name_set:
        return None
    return next(
        (product for product in product_list if _product_route_name(product) in route_name_set),
        None,
    )


def _build_home_related_shortcuts(product_list):
    items = []
    for spec in HOME_SHORTCUT_SPECS:
        product = _find_product_by_routes(product_list, spec.get("preferred_routes"))
        href = getattr(product, "launch_href", "") if product else ""
        is_external = bool(getattr(product, "launch_is_external", False)) if product else False
        if not href:
            href = _safe_reverse(spec.get("fallback_route"))
        if not href:
            continue
        state_meta = _build_product_state_labels(
            product,
            route_name=spec.get("fallback_route", ""),
            launch_is_external=is_external,
            limit=2,
        )
        items.append(
            {
                "key": spec["key"],
                "title": spec["title"],
                "description": spec["description"],
                "icon": spec["icon"],
                "href": href,
                "is_external": is_external,
                "service_name": getattr(product, "public_service_name", "") if product else "",
                "meta": (getattr(product, "home_context_chips", []) or [""])[0] if product else "",
                "access_status_label": state_meta["home_access_status_label"],
                "state_badges": state_meta["home_state_badges"],
                "guide_url": getattr(product, "guide_url", "") if product else "",
                "sample_url": getattr(product, "sample_url", "") if product else "",
            }
        )
    return items


def _home_card_icon_color_class(service_type):
    color_map = {
        "collect_sign": "text-blue-500",
        "classroom": "text-violet-500",
        "work": "text-emerald-500",
        "game": "text-red-500",
        "counsel": "text-pink-500",
        "edutech": "text-cyan-500",
    }
    return color_map.get(service_type, "text-slate-500")


def _build_home_try_now_card_entries(product_list, specs):
    cards = []
    for spec in specs:
        product = _find_product_by_routes(product_list, spec.get("preferred_routes"))
        href = getattr(product, "launch_href", "") if product else ""
        is_external = bool(getattr(product, "launch_is_external", False)) if product else False
        if not href:
            href = _safe_reverse(spec.get("fallback_route"))
        if not href:
            continue

        service_type = str(getattr(product, "service_type", "") or spec.get("service_type", "") or "").strip()
        state_meta = _build_product_state_labels(
            product,
            route_name=spec.get("fallback_route", ""),
            service_type=service_type,
            launch_is_external=is_external,
            is_guest_allowed=bool(spec.get("is_guest_allowed", False)),
            limit=1,
        )
        cards.append(
            {
                "key": spec["key"],
                "product_id": getattr(product, "id", ""),
                "title": spec["title"],
                "description": spec["description"],
                "icon": getattr(product, "icon", "") if product and "fa-" in str(getattr(product, "icon", "")) else spec["icon"],
                "icon_color_class": _home_card_icon_color_class(service_type),
                "href": href,
                "is_external": is_external,
                "track_label": getattr(product, "title", "") or spec["service_name"],
                "access_status_label": state_meta["home_access_status_label"],
            }
        )
    return cards


def _build_home_try_now_cards(product_list):
    return _build_home_try_now_card_entries(product_list, HOME_TRY_NOW_CARD_SPECS)


def _build_home_try_now_support_cards(product_list):
    return _build_home_try_now_card_entries(product_list, HOME_TRY_NOW_SUPPORT_CARD_SPECS)


def _build_home_guest_start_cards(product_list):
    cards = []
    for spec in GUEST_START_CARD_SPECS:
        product = _find_product_by_routes(product_list, spec.get("preferred_routes"))
        if product is None and spec.get("service_type"):
            product = next(
                (
                    candidate for candidate in product_list
                    if getattr(candidate, "service_type", "") == spec["service_type"]
                ),
                None,
            )
        href = getattr(product, "launch_href", "") if product else ""
        is_external = bool(getattr(product, "launch_is_external", False)) if product else False
        if not href:
            href = _safe_reverse(spec.get("fallback_route"))
        if not href:
            continue
        state_meta = _build_product_state_labels(
            product,
            route_name=spec.get("fallback_route", ""),
            service_type=spec.get("service_type", ""),
            launch_is_external=is_external,
            limit=2,
        )
        cards.append(
            {
                "title": spec["title"],
                "description": spec["description"],
                "icon": spec["icon"],
                "href": href,
                "is_external": is_external,
                "service_name": getattr(product, "public_service_name", "") if product else "",
                "meta": (getattr(product, "home_context_chips", []) or [""])[0] if product else "",
                "access_status_label": state_meta["home_access_status_label"],
                "state_badges": state_meta["home_state_badges"],
                "guide_url": getattr(product, "guide_url", "") if product else "",
                "sample_url": getattr(product, "sample_url", "") if product else "",
            }
        )
    return cards[:4]


def _build_home_calendar_hub_context(request):
    calendar_summary = _build_home_calendar_summary_context(request)
    return {
        "title": CALENDAR_HUB_PUBLIC_NAME,
        "description": "전체 캘린더와 같은 원본으로 오늘 일정, 메모, 할 일을 요약해서 보여줍니다.",
        "month_label": calendar_summary.get("month_label", ""),
        "month_grid": calendar_summary.get("month_grid", []),
        "today_count": calendar_summary.get("today_count", 0),
        "week_count": calendar_summary.get("week_count", 0),
        "date_key": calendar_summary.get("date_key", ""),
        "date_label": calendar_summary.get("date_label", ""),
        "today_event_count": calendar_summary.get("today_event_count", 0),
        "today_event_memo_count": calendar_summary.get("today_event_memo_count", 0),
        "today_task_count": calendar_summary.get("today_task_count", 0),
        "today_task_memo_count": calendar_summary.get("today_task_memo_count", 0),
        "today_events": calendar_summary.get("today_events", []),
        "today_memos": calendar_summary.get("today_memos", []),
        "today_event_memos": calendar_summary.get("today_event_memos", []),
        "review_memos": calendar_summary.get("review_memos", []),
        "review_groups": calendar_summary.get("review_groups", []),
        "today_tasks": calendar_summary.get("today_tasks", []),
        "today_task_memos": calendar_summary.get("today_task_memos", []),
        "next_upcoming_events": calendar_summary.get("next_upcoming_events", []),
        "recent_memo_items": calendar_summary.get("recent_memo_items", []),
        "has_supporting_items": calendar_summary.get("has_supporting_items", False),
        "has_items": calendar_summary.get("has_items", False),
        "empty_message": calendar_summary.get("empty_message", ""),
        "main_url": calendar_summary.get("main_url") or _safe_calendar_surface_reverse("calendar_main", "classcalendar:main"),
        "today_url": calendar_summary.get("today_url") or _safe_calendar_surface_reverse("calendar_today", "classcalendar:today"),
        "today_all_url": calendar_summary.get("today_all_url") or _safe_calendar_surface_reverse("calendar_today", "classcalendar:today"),
        "today_memo_url": calendar_summary.get("today_memo_url") or _safe_calendar_surface_reverse("calendar_today", "classcalendar:today"),
        "today_review_url": calendar_summary.get("today_review_url") or _safe_calendar_surface_reverse("calendar_today", "classcalendar:today"),
        "today_memo_panel_url": calendar_summary.get("today_memo_panel_url") or _safe_calendar_surface_reverse("calendar_today", "classcalendar:today"),
        "today_create_url": calendar_summary.get("today_create_url") or "",
        "main_create_url": calendar_summary.get("main_create_url") or "",
        "create_api_url": calendar_summary.get("create_api_url", ""),
        "primary_cta_label": "전체 캘린더",
        "secondary_cta_label": "오늘 보기",
    }


def _normalize_catalog_section_key(raw_value):
    value = str(raw_value or "").strip().lower()
    if value in VALID_CATALOG_SECTION_KEYS:
        return value
    return ""


def _resolve_catalog_scenario_key(product):
    if _is_sheetbook_cross_surface_hidden(product):
        return None

    route_name = _product_route_name(product)
    service_type = str(getattr(product, "service_type", "") or "").strip()

    if route_name in {"classcalendar:main", "reservations:dashboard_landing", "reservations:landing"}:
        return "today_ops"
    if route_name in {"collect:landing", "consent:landing", "signatures:landing", "handoff:landing"} or service_type == "collect_sign":
        return "collect"
    if service_type == "game":
        return "activity"
    if service_type == "counsel":
        return "counsel"
    if service_type in {"edutech", "etc"}:
        return "reference"
    if service_type == "work":
        return "prep"
    if service_type == "classroom":
        return "today_ops"
    return "reference"


def _build_catalog_hub_context(product_list):
    guide_url = ""
    try:
        manual = (
            ServiceManual.objects.filter(
                is_published=True,
                product__is_active=True,
                product__launch_route_name="classcalendar:main",
            )
            .order_by("product__display_order", "product__title")
            .first()
        )
    except Exception:
        manual = None
    if manual is not None:
        guide_url = reverse("service_guide_detail", kwargs={"pk": manual.pk})
    if not guide_url:
        guide_url = reverse("service_guide_list")

    return {
        "title": "메인 캘린더는 홈에서 시작합니다",
        "description": "홈의 캘린더 요약에서 오늘 일정과 메모를 먼저 보고, 필요할 때만 월간 확장 보기로 이동하세요.",
        "href": reverse("home"),
        "is_external": False,
        "guide_url": guide_url,
        "primary_label": "홈에서 시작하기",
    }


def _build_catalog_scenario_sections(product_list, selected_section_key=""):
    selected_section_key = _normalize_catalog_section_key(selected_section_key)
    bucket = {section["key"]: [] for section in CATALOG_SCENARIO_SECTIONS}
    for product in product_list:
        section_key = _resolve_catalog_scenario_key(product)
        if not section_key:
            continue
        bucket.setdefault(section_key, []).append(product)

    sections = []
    for section in CATALOG_SCENARIO_SECTIONS:
        if selected_section_key and section["key"] != selected_section_key:
            continue
        items = bucket.get(section["key"], [])
        if not items:
            continue
        sections.append(
            {
                **section,
                "products": items,
            }
        )
    return sections


def _prepare_manual_display(manual):
    product = manual.product
    manual.public_title = _replace_public_service_terms(manual.title or f"{_get_public_product_name(product)} 안내", product)
    manual.public_description = _replace_public_service_terms(
        manual.description or getattr(product, "teacher_first_support_label", "") or product.description or "",
        product,
    )
    manual.public_service_name = getattr(product, "public_service_name", _get_public_product_name(product))
    manual.public_launch_label = f"{manual.public_service_name} 열기"
    manual.public_chips = list(getattr(product, "detail_context_chips", []) or [])
    return manual


def _build_guide_entry_points():
    return [
        {
            "key": item["key"],
            "title": item["title"],
            "description": item["description"],
            "href": item["anchor"],
        }
        for item in GUIDE_ENTRY_POINT_META
    ]


def _build_guide_groups(manuals, products_without_manual):
    prepared_manuals = [_prepare_manual_display(manual) for manual in manuals]

    calendar_manuals = []
    task_manuals = []
    for manual in prepared_manuals:
        if _is_calendar_hub_product(manual.product):
            calendar_manuals.append(manual)
        elif _is_sheetbook_product(manual.product):
            continue
        else:
            task_manuals.append(manual)

    calendar_href = _safe_calendar_surface_reverse("calendar_main", "classcalendar:main")
    today_href = _safe_calendar_surface_reverse("calendar_today", "classcalendar:today")
    start_items = [
        {
            "title": "홈에서 어디를 먼저 보는지",
            "description": "홈에서 오늘 해야 하는 일과 메인 캘린더를 먼저 보는 흐름입니다.",
            "href": reverse("home"),
            "meta": "홈에서 바로 확인",
        },
        {
            "title": "오늘 보기 열기",
            "description": "오늘 일정, 오늘 메모, 오늘 할 일을 한 화면에서 바로 확인합니다.",
            "href": today_href or reverse("home"),
            "meta": "오늘 보기",
        },
        {
            "title": "월간 확장 보기 열기",
            "description": "날짜를 넓게 보거나 상세 편집이 필요할 때만 월간 화면으로 이동합니다.",
            "href": calendar_href or reverse("home"),
            "meta": "확장 보기",
        },
        {
            "title": "첫 일정 만들기",
            "description": "오늘 보기에서 일정 한 건만 먼저 추가해도 하루 흐름이 잡힙니다.",
            "href": f"{today_href}?action=create" if today_href else reverse("home"),
            "meta": "일정 추가",
        },
        {
            "title": "자주 쓰는 도구 저장하기",
            "description": "홈에서 자주 쓰는 도구에 추가해 다음부터 바로 열 수 있습니다.",
            "href": reverse("home"),
            "meta": "홈에서 설정",
        },
    ]

    pending_products = [
        product for product in products_without_manual
        if not _is_sheetbook_cross_surface_hidden(product)
    ]
    for product in pending_products:
        product.pending_public_name = _get_public_product_name(product)

    return [
        {
            "key": "start",
            "anchor": "guide-start",
            "title": "처음 시작",
            "description": "홈과 오늘 보기, 월간 확장 보기 순서만 짧게 확인합니다.",
            "items": start_items,
            "manuals": [],
            "pending_products": [],
        },
        {
            "key": "calendar",
            "anchor": "guide-calendar",
            "title": "메인 캘린더 흐름",
            "description": "홈의 캘린더 요약과 월간 확장 보기로 이어지는 핵심 캘린더 흐름만 전면에서 안내합니다.",
            "items": [],
            "manuals": calendar_manuals,
            "pending_products": [],
        },
        {
            "key": "tasks",
            "anchor": "guide-tasks",
            "title": "자주 하는 업무",
            "description": "안내장, 수합, 수업 준비, 활동, 상담 흐름을 상황별로 찾습니다.",
            "items": [],
            "manuals": task_manuals,
            "pending_products": pending_products,
        },
    ]


def _home_v2(request, products, posts, page_obj, feed_scope):
    """Feature flag on 시 호출되는 V2 홈."""
    product_list = _attach_product_launch_meta(list(products))
    section_product_list = [
        product
        for product in product_list
        if str(getattr(product, "launch_route_name", "") or "").strip().lower() != "messagebox:main"
    ]
    today_try_cards = _build_home_try_now_cards(product_list)
    today_try_support_cards = _build_home_try_now_support_cards(product_list)
    sections, aux_sections, games = get_purpose_sections(
        section_product_list,
        preview_limit=2,
    )
    primary_display_sections, secondary_display_sections = _build_home_v2_display_groups(sections, aux_sections)
    sns_summary_posts = _build_home_community_summary_posts(page_obj, limit=2)
    community_summary = {
        'title': '실시간 소통',
        'description': '공지와 최근 소통 두 가지만 먼저 보고, 전체 소통은 따로 이어서 확인합니다.',
        'posts': sns_summary_posts,
        'full_url': reverse('community_feed'),
    }

    if request.user.is_authenticated:
        UserProfile.objects.get_or_create(user=request.user)
        favorite_products = _get_user_favorite_products(request.user, product_list, limit=12)
        recent_products = _get_recently_used_products(
            request.user,
            product_list,
            exclude_ids={p.id for p in favorite_products},
            limit=4,
        )

        # 퀵 액션: 즐겨찾기 우선 + 사용 빈도 기반 (폴백: featured → display_order)
        quick_actions = _get_usage_based_quick_actions(request.user, product_list)
        workflow_seed_products = []
        seen_seed_ids = set()
        for seed_product in [*favorite_products, *recent_products, *quick_actions]:
            if seed_product.id in seen_seed_ids:
                continue
            workflow_seed_products.append(seed_product)
            seen_seed_ids.add(seed_product.id)

        companion_items = _get_home_companion_items(
            workflow_seed_products,
            product_list,
            exclude_ids={p.id for p in [*favorite_products, *recent_products]},
            limit=3,
        )
        discovery_products = _get_home_discovery_products(
            request.user,
            product_list,
            exclude_ids={
                p.id for p in [*favorite_products, *recent_products, *quick_actions]
            } | {item['product'].id for item in companion_items},
            limit=4,
        )
        if not discovery_products:
            discovery_products = _get_home_discovery_products(
                request.user,
                product_list,
                exclude_ids={
                    p.id for p in [*favorite_products, *recent_products]
                },
                limit=4,
            )

        quick_action_items = _build_product_link_items(quick_actions, include_section_meta=True)
        favorite_items = _build_product_link_items(favorite_products, include_section_meta=True)
        workbench_slots = _build_workbench_slots(favorite_items)
        recent_items = _build_product_link_items(recent_products, include_section_meta=True)
        discovery_items = _build_product_link_items(discovery_products, include_section_meta=True)
        from classcalendar.views import build_calendar_surface_context

        home_calendar_surface = build_calendar_surface_context(
            request,
            page_variant='main',
            embedded_surface='home',
        )
        workbench_bundles = _get_user_workbench_bundles(request.user, product_list)
        weekly_bundle_items = _get_weekly_workbench_bundle_highlights(request.user, product_list)
        today_context = _build_today_context(request)
        home_calendar_summary = next(iter(today_context.get('today_items', [])), None)
        home_sections = [*sections, *aux_sections]
        home_v2_frontend_config = {
            'toggleFavoriteUrl': reverse('toggle_product_favorite'),
            'trackUsageUrl': reverse('track_product_usage'),
        }

        return render(request, 'core/home_authenticated_v2.html', {
            'products': products,
            'sections': sections,
            'aux_sections': aux_sections,
            'primary_display_sections': primary_display_sections,
            'secondary_display_sections': secondary_display_sections,
            'home_sections': home_sections,
            'games': games,
            'quick_actions': quick_action_items,
            'favorite_items': favorite_items,
            'workbench_slots': workbench_slots,
            'favorite_product_ids': [p.id for p in favorite_products],
            'recent_items': recent_items,
            'companion_items': companion_items,
            'discovery_items': discovery_items,
            'workbench_bundles': workbench_bundles,
            'weekly_bundle_items': weekly_bundle_items,
            'home_calendar_surface': home_calendar_surface,
            'home_calendar_summary': home_calendar_summary,
            'today_try_cards': today_try_cards,
            'today_try_support_cards': today_try_support_cards,
            'home_v2_frontend_config': home_v2_frontend_config,
            'community_summary': community_summary,
            'posts': posts,
            'page_obj': page_obj,
            'feed_scope': feed_scope,
            **home_calendar_surface,
            **build_home_page_seo(request).as_context(),
            **today_context,
            **_build_sheetbook_workspace_context(request),
            **_build_home_student_games_qr_context(request),
        })

    featured_product = next((p for p in product_list if p.is_featured), product_list[0] if product_list else None)
    return render(request, 'core/home_v2.html', {
        'products': products,
        'featured_product': featured_product,
        'sections': sections,
        'aux_sections': aux_sections,
        'primary_display_sections': primary_display_sections,
        'secondary_display_sections': secondary_display_sections,
        'games': games,
        'community_summary': community_summary,
        'public_calendar_entry': _build_public_calendar_entry_context(),
        'posts': posts,
        'page_obj': page_obj,
        'feed_scope': feed_scope,
        **build_home_page_seo(request).as_context(),
    })


def _home_v4(request, products, posts, page_obj, feed_scope):
    """환경변수로 안전하게 롤아웃하는 인증 홈 V4."""
    product_list = _attach_product_launch_meta(list(products))
    section_product_list = [
        product
        for product in product_list
        if str(getattr(product, "launch_route_name", "") or "").strip().lower() != "messagebox:main"
    ]
    sections, aux_sections, games = get_purpose_sections(
        section_product_list,
        preview_limit=2,
    )
    primary_display_sections, secondary_display_sections = _build_home_v2_display_groups(sections, aux_sections)
    sns_summary_posts = _build_home_community_summary_posts(page_obj, limit=2)
    community_summary = {
        'title': '실시간 소통',
        'posts': sns_summary_posts,
        'full_url': reverse('community_feed'),
    }

    UserProfile.objects.get_or_create(user=request.user)
    favorite_products = _get_user_favorite_products(request.user, product_list, limit=12)
    recent_products = _get_recently_used_products(
        request.user,
        product_list,
        exclude_ids={product.id for product in favorite_products},
        limit=4,
    )
    quick_actions = _get_usage_based_quick_actions(request.user, product_list)

    workflow_seed_products = []
    seen_seed_ids = set()
    for seed_product in [*favorite_products, *recent_products, *quick_actions]:
        if seed_product.id in seen_seed_ids:
            continue
        workflow_seed_products.append(seed_product)
        seen_seed_ids.add(seed_product.id)

    companion_items = _get_home_companion_items(
        workflow_seed_products,
        product_list,
        exclude_ids={product.id for product in [*favorite_products, *recent_products]},
        limit=3,
    )
    discovery_products = _get_home_discovery_products(
        request.user,
        product_list,
        exclude_ids={
            product.id for product in [*favorite_products, *recent_products, *quick_actions]
        } | {item['product'].id for item in companion_items},
        limit=4,
    )
    if not discovery_products:
        discovery_products = _get_home_discovery_products(
            request.user,
            product_list,
            exclude_ids={product.id for product in [*favorite_products, *recent_products]},
            limit=4,
        )

    favorite_items = _build_product_link_items(favorite_products, include_section_meta=True)
    discovery_items = _build_product_link_items(discovery_products, include_section_meta=True)
    representative_slots = _build_home_v4_representative_slots(
        request.user,
        favorite_products=favorite_products,
        recent_products=recent_products,
        quick_actions=quick_actions,
        discovery_products=discovery_products,
        sections=sections,
        aux_sections=aux_sections,
        games=games,
    )
    representative_recommendations = _build_home_v4_recommendations(
        companion_items,
        discovery_items,
        exclude_ids=(
            {product.id for product in favorite_products}
            | {slot['product'].id for slot in representative_slots}
        ),
        limit=3,
    )

    from classcalendar.views import build_calendar_surface_context

    home_calendar_surface = build_calendar_surface_context(
        request,
        page_variant='main',
        embedded_surface='home',
    )
    home_v2_frontend_config = {
        'toggleFavoriteUrl': reverse('toggle_product_favorite'),
        'trackUsageUrl': reverse('track_product_usage'),
    }

    return render(request, 'core/home_authenticated_v4.html', {
        'products': products,
        'sections': sections,
        'aux_sections': aux_sections,
        'primary_display_sections': primary_display_sections,
        'secondary_display_sections': secondary_display_sections,
        'games': games,
        'favorite_items': favorite_items,
        'favorite_product_ids': [product.id for product in favorite_products],
        'representative_slots': representative_slots,
        'representative_recommendations': representative_recommendations,
        'home_calendar_surface': home_calendar_surface,
        'home_v2_frontend_config': home_v2_frontend_config,
        'community_summary': community_summary,
        'posts': posts,
        'page_obj': page_obj,
        'feed_scope': feed_scope,
        **home_calendar_surface,
        **build_home_page_seo(request).as_context(),
    })

def home(request):
    # Order by display_order first, then by creation date
    products = filter_discoverable_products(
        Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
    )
    feed_scope = _get_post_feed_scope(request)

    # SNS Posts - 모든 사용자에게 제공 (최신순 정렬)
    posts = _build_post_feed_queryset(feed_scope=feed_scope)

    # 페이징 처리 (PC 우측 및 모바일 하단 SNS 위젯용)
    paginator = Paginator(posts, 5) # 한 페이지에 5개씩
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # HTMX 요청이면 post_list 영역만 반환
    if request.headers.get('HX-Request'):
        return _render_post_list_partial(request, page_obj, feed_scope)

    home_layout_version = _get_home_layout_version()

    if home_layout_version == 'v4':
        if request.user.is_authenticated:
            return _home_v4(request, products, posts, page_obj, feed_scope)
        return _home_v2(request, products, posts, page_obj, feed_scope)

    # V2 홈: Feature flag on 시 분기
    if home_layout_version == 'v2':
        return _home_v2(request, products, posts, page_obj, feed_scope)

    # If user is logged in, show the "dashboard-style" authenticated home
    if request.user.is_authenticated:
        # Ensure profile exists to prevent 500 errors for legacy users
        UserProfile.objects.get_or_create(user=request.user)

        from django.db.models import Q
        # Get IDs of products explicitly owned by the user
        owned_ids = request.user.owned_products.values_list('product_id', flat=True)
        # Filter products that are either owned or free, and exclude specific ones
        available_products = products.filter(
            Q(id__in=owned_ids) | Q(price=0)
        ).exclude(
            Q(title__icontains="인사이트") | Q(title__icontains="사주")
        ).distinct()
        available_products = _attach_product_launch_meta(list(available_products))

        return render(request, 'core/home_authenticated.html', {
            'products': available_products,
            'posts': page_obj,
            'page_obj': page_obj,
            'feed_scope': feed_scope,
            **build_home_page_seo(request).as_context(),
        })

    # Else show the public home
    products = _attach_product_launch_meta(list(products))
    featured_product = next((product for product in products if product.is_featured), None)
    # Fallback if no featured product
    if not featured_product:
        featured_product = products[0] if products else None

    return render(request, 'core/home.html', {
        'products': products,
        'featured_product': featured_product,
        'posts': page_obj,
        'page_obj': page_obj,
        'feed_scope': feed_scope,
        **build_home_page_seo(request).as_context(),
    })


def community_feed(request):
    feed_scope = _get_post_feed_scope(request)
    posts = _build_post_feed_queryset(feed_scope=feed_scope)
    paginator = Paginator(posts, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    if request.headers.get('HX-Request'):
        return _render_post_list_partial(request, page_obj, feed_scope)

    return render(
        request,
        'core/community_feed.html',
        {
            'posts': posts,
            'page_obj': page_obj,
            'feed_scope': feed_scope,
        },
    )


@login_required
def dashboard(request):
    return redirect('home')

@login_required
def post_create(request):
    if request.method == 'POST':
        content = request.POST.get('content')
        image = request.FILES.get('image')
        submit_kind = (request.POST.get('submit_kind') or 'general').strip().lower()
        post_type = 'notice' if request.user.is_staff and submit_kind == 'notice' else 'general'

        # 이미지 검증
        if image:
            MAX_SIZE = 10 * 1024 * 1024  # 10MB
            ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

            if image.size > MAX_SIZE:
                messages.error(request, '이미지 크기는 10MB 이하만 가능합니다.')
                return redirect('home')

            if image.content_type not in ALLOWED_TYPES:
                messages.error(request, '허용되지 않는 파일 형식입니다. (JPEG, PNG, GIF, WebP만 가능)')
                return redirect('home')

            # PIL로 이미지 무결성 검증 (악성 파일 방지)
            try:
                img = Image.open(image)
                img.verify()
                image.seek(0)  # 포인터 리셋
            except Exception:
                messages.error(request, '올바른 이미지 파일이 아닙니다.')
                return redirect('home')

        # 게시물 생성
        if content or image:
            Post.objects.create(
                author=request.user,
                content=content,
                image=image,
                post_type=post_type,
            )

    # HTMX 응답
    if request.headers.get('HX-Request'):
        feed_scope = _get_post_feed_scope(request)
        posts = _build_post_feed_queryset(feed_scope=feed_scope)
        
        from django.core.paginator import Paginator
        paginator = Paginator(posts, 5) # 등록 후에는 무조건 1페이지로
        page_obj = paginator.get_page(1)
        
        return _render_post_list_partial(request, page_obj, feed_scope)

    return redirect('home')

@login_required
def post_like(request, pk):
    post = _resolve_post_for_action(pk, request.user)
    if post is None:
        return HttpResponse("Not found", status=404)

    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
        
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/post_item.html', {'post': post})
        
    return redirect('home')

@login_required
def comment_create(request, pk):
    post = _resolve_post_for_action(pk, request.user)
    if post is None:
        return HttpResponse("Not found", status=404)

    if request.method == 'POST':
        content = request.POST.get('content')
        if _has_active_comment_restriction(request.user):
            if request.headers.get('HX-Request'):
                return HttpResponse("댓글 작성이 일시 제한되었습니다.", status=429)
            messages.error(request, '댓글 작성이 일시 제한된 계정입니다.')
            return redirect('home')

        if _rate_limit_exceeded(
            bucket_name='comment_create',
            user_id=request.user.id,
            limits=[(60, 1), (3600, 10), (86400, 30)],
        ):
            if request.headers.get('HX-Request'):
                return HttpResponse("댓글 작성 속도가 너무 빠릅니다. 잠시 후 다시 시도해주세요.", status=429)
            messages.error(request, '댓글 작성 속도가 너무 빠릅니다. 잠시 후 다시 시도해주세요.')
            return redirect('home')

        if content:
            Comment.objects.create(
                post=post,
                author=request.user,
                content=content
            )
            
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/post_item.html', {'post': post})
        
    return redirect('home')

@login_required
def post_delete(request, pk):
    post = _resolve_post_for_action(pk, request.user)
    if post is None:
        return HttpResponse("Not found", status=404)
    # Check if the user is the author or staff
    if post.author == request.user or request.user.is_staff:
        post.delete()
        if request.headers.get('HX-Request'):
            return HttpResponse("") # HTMX expects empty string for deletion
            
    return redirect('home')

@login_required
def post_edit(request, pk):
    post = _resolve_post_for_action(pk, request.user)
    if post is None:
        return HttpResponse("Not found", status=404)
    
    # Only author can edit
    if post.author != request.user:
        return HttpResponse("Unauthorized", status=403)
        
    if request.method == 'POST':
        content = request.POST.get('content')
        image = request.FILES.get('image')
        
        # 이미지 삭제 처리
        if request.POST.get('remove_image') == 'true':
            post.image = None
            
        # 이미지 수정 처리
        if image:
            MAX_SIZE = 10 * 1024 * 1024  # 10MB
            ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

            if image.size > MAX_SIZE:
                messages.error(request, '이미지 크기는 10MB 이하만 가능합니다.')
                return render(request, 'core/partials/post_edit_form.html', {'post': post})

            if image.content_type not in ALLOWED_TYPES:
                messages.error(request, '허용되지 않는 파일 형식입니다. (JPEG, PNG, GIF, WebP만 가능)')
                return render(request, 'core/partials/post_edit_form.html', {'post': post})

            try:
                img = Image.open(image)
                img.verify()
                image.seek(0)
                post.image = image
            except Exception:
                messages.error(request, '올바른 이미지 파일이 아닙니다.')
                return render(request, 'core/partials/post_edit_form.html', {'post': post})

        if content:
            post.content = content
            post.save()
            # Return the updated post item (expanded)
            return render(request, 'core/partials/post_item.html', {'post': post, 'is_first': True})
            
    # GET: Return the edit form
    return render(request, 'core/partials/post_edit_form.html', {'post': post})

@login_required
def post_detail_partial(request, pk):
    """Helper view to return the read-only post item (e.g. for Cancel button)"""
    post = _resolve_post_for_action(pk, request.user)
    if post is None:
        return HttpResponse("Not found", status=404)
    # Force expansion when returning from edit mode
    return render(request, 'core/partials/post_item.html', {'post': post, 'is_first': True})

@login_required
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    # Check if the user is the author or staff
    if comment.author == request.user or request.user.is_staff:
        comment.delete()
        if request.headers.get('HX-Request'):
            return HttpResponse("") # HTMX expects empty string
            
    return redirect('home')

@login_required
def comment_edit(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    
    # Only author can edit
    if comment.author != request.user:
        return HttpResponse("Unauthorized", status=403)
        
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment.content = content
            comment.save()
            return render(request, 'core/partials/comment_item.html', {'comment': comment})
            
    # GET: Return the edit form
    return render(request, 'core/partials/comment_edit_form.html', {'comment': comment})

@login_required
def comment_item_partial(request, pk):
    """Helper view to return the read-only comment item"""
    comment = get_object_or_404(Comment, pk=pk)
    return render(request, 'core/partials/comment_item.html', {'comment': comment})


@login_required
@require_POST
def comment_report(request, pk):
    comment = get_object_or_404(
        Comment.objects.select_related('post', 'author'),
        pk=pk,
    )
    post = comment.post
    if post.approval_status != 'approved' and not request.user.is_staff and post.author_id != request.user.id:
        return HttpResponse("Not found", status=404)

    if comment.author_id == request.user.id:
        return HttpResponse("본인 댓글은 신고할 수 없습니다.", status=400)

    if _rate_limit_exceeded(
        bucket_name='comment_report',
        user_id=request.user.id,
        limits=[(60, 3), (86400, 30)],
    ):
        return HttpResponse("신고 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", status=429)

    reason = request.POST.get('reason', 'other')
    if reason not in {item[0] for item in CommentReport.REASON_CHOICES}:
        reason = 'other'
    detail = (request.POST.get('detail') or '').strip()[:300]

    report, created = CommentReport.objects.get_or_create(
        comment=comment,
        reporter=request.user,
        defaults={'reason': reason, 'detail': detail},
    )
    if not created and detail and report.detail != detail:
        report.detail = detail
        report.save(update_fields=['detail'])

    report_count = CommentReport.objects.filter(comment=comment).count()
    update_fields = ['report_count']
    comment.report_count = report_count
    if report_count >= 3 and not comment.is_hidden:
        comment.is_hidden = True
        comment.hidden_reason = 'reports'
        update_fields.extend(['is_hidden', 'hidden_reason'])
    comment.save(update_fields=update_fields)

    if request.headers.get('HX-Request'):
        if comment.is_hidden and not request.user.is_staff:
            return HttpResponse("")
        return render(request, 'core/partials/comment_item.html', {'comment': comment})

    if created:
        messages.success(request, '신고가 접수되었습니다.')
    else:
        messages.info(request, '이미 신고한 댓글입니다.')
    return redirect('home')


@login_required
def news_review_queue(request):
    if not request.user.is_staff:
        messages.error(request, '관리 권한이 필요합니다.')
        return redirect('home')

    pending_posts_qs = (
        Post.objects.filter(post_type='news_link', approval_status='pending')
        .select_related('author')
        .order_by('-created_at')
    )
    pending_total = pending_posts_qs.count()
    paginator = Paginator(pending_posts_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'core/news_review_queue.html',
        {
            'pending_posts': page_obj,
            'page_obj': page_obj,
            'pending_total': pending_total,
        },
    )


@login_required
@require_POST
def news_review_action(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    post = get_object_or_404(Post, pk=pk, post_type='news_link')
    action = request.POST.get('action')
    if action == 'approve':
        post.approval_status = 'approved'
    elif action == 'reject':
        post.approval_status = 'rejected'
    else:
        return HttpResponse("Invalid action", status=400)

    post.reviewed_by = request.user
    post.reviewed_at = timezone.now()
    post.save(update_fields=['approval_status', 'reviewed_by', 'reviewed_at'])
    return redirect('news_review_queue')


def _format_datetime_local_value(dt):
    if not dt:
        return ''
    return timezone.localtime(dt).strftime('%Y-%m-%dT%H:%M')


def _parse_feature_datetime(raw_value):
    raw = (raw_value or '').strip()
    if not raw:
        return None

    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@login_required
def insight_sns_queue(request):
    if not request.user.is_staff:
        messages.error(request, '관리 권한이 필요합니다.')
        return redirect('home')

    from datetime import timedelta
    from insights.models import Insight

    insights_qs = Insight.objects.order_by('-created_at')
    insights_total = insights_qs.count()
    paginator = Paginator(insights_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    insights_page = list(page_obj.object_list)

    detail_urls = [
        reverse('insights:detail', kwargs={'pk': insight.pk})
        for insight in insights_page
    ]
    linked_posts_qs = (
        Post.objects
        .filter(
            post_type='news_link',
            publisher='Insight Library',
            source_url__in=detail_urls,
        )
        .order_by('source_url', '-created_at')
    )
    latest_post_by_source = {}
    for linked_post in linked_posts_qs:
        latest_post_by_source.setdefault(linked_post.source_url, linked_post)

    now = timezone.now()
    default_start = now
    default_end = now + timedelta(hours=24)
    insight_rows = []
    for insight in insights_page:
        detail_url = reverse('insights:detail', kwargs={'pk': insight.pk})
        linked_post = latest_post_by_source.get(detail_url)
        start_dt = linked_post.featured_from if linked_post and linked_post.featured_from else default_start
        end_dt = linked_post.featured_until if linked_post and linked_post.featured_until else default_end
        is_active = False
        if linked_post and linked_post.featured_from and linked_post.featured_from <= now:
            if not linked_post.featured_until or linked_post.featured_until >= now:
                is_active = True

        insight_rows.append({
            'insight': insight,
            'detail_url': detail_url,
            'linked_post': linked_post,
            'is_active': is_active,
            'start_value': _format_datetime_local_value(start_dt),
            'end_value': _format_datetime_local_value(end_dt),
        })

    return render(
        request,
        'core/insight_sns_queue.html',
        {
            'insight_rows': insight_rows,
            'insights_total': insights_total,
            'page_obj': page_obj,
        },
    )


@login_required
@require_POST
def insight_sns_action(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    from datetime import timedelta
    from insights.models import Insight

    insight = get_object_or_404(Insight, pk=pk)
    detail_url = reverse('insights:detail', kwargs={'pk': insight.pk})
    post = (
        Post.objects
        .filter(
            post_type='news_link',
            publisher='Insight Library',
            source_url=detail_url,
        )
        .order_by('-created_at')
        .first()
    )

    action = (request.POST.get('action') or '').strip().lower()
    now = timezone.now()

    if action == 'clear':
        if not post:
            messages.info(request, '이미 노출 해제된 상태입니다.')
            return redirect('insight_sns_queue')

        post.featured_from = None
        post.featured_until = None
        post.reviewed_by = request.user
        post.reviewed_at = now
        post.save(update_fields=['featured_from', 'featured_until', 'reviewed_by', 'reviewed_at'])
        messages.success(request, '인사이트 상단 노출을 해제했습니다.')
        return redirect('insight_sns_queue')

    if action != 'feature':
        return HttpResponse("Invalid action", status=400)

    start_at = _parse_feature_datetime(request.POST.get('featured_from')) or now
    end_at = _parse_feature_datetime(request.POST.get('featured_until')) or (start_at + timedelta(hours=24))
    if end_at <= start_at:
        messages.error(request, '노출 종료 시간은 시작 시간보다 늦어야 합니다.')
        return redirect('insight_sns_queue')

    summary = " ".join((insight.content or '').split())
    if len(summary) > 220:
        summary = f"{summary[:217]}..."
    if not summary:
        summary = insight.title

    payload = {
        'content': summary,
        'post_type': 'news_link',
        'source_type': 'institute',
        'source_url': detail_url,
        'canonical_url': detail_url,
        'og_title': insight.title,
        'og_description': summary,
        'og_image_url': insight.thumbnail_url or '',
        'publisher': 'Insight Library',
        'published_at': now,
        'primary_tag': '인사이트',
        'secondary_tag': f'insight:{insight.pk}',
        'approval_status': 'approved',
        'featured_from': start_at,
        'featured_until': end_at,
    }

    if post is None:
        post = Post(author=request.user, **payload)
    else:
        for key, value in payload.items():
            setattr(post, key, value)

    post.reviewed_by = request.user
    post.reviewed_at = now
    post.save()
    messages.success(request, '인사이트를 SNS 상단 노출 대상으로 등록했습니다.')
    return redirect('insight_sns_queue')

def prompt_lab(request):
    return render(
        request,
        'core/prompt_lab.html',
        {
            'prompt_lab_catalog': get_prompt_lab_catalog(),
            **build_prompt_lab_page_seo(request).as_context(),
        },
    )

TEACHER_FIRST_PRODUCT_CONTRACT_PATH = 'docs/plans/CONTRACT_teacher_first_product_2026-03-08.md'

TEACHER_FIRST_ENTRY_POINT_META = [
    {
        'key': 'home',
        'title': '홈',
        'description': '지금 해야 할 일부터 시작',
        'route_name': 'home',
    },
    {
        'key': 'catalog',
        'title': '전체 서비스',
        'description': '업무 기준으로 전체 보기',
        'route_name': 'product_list',
    },
    {
        'key': 'manuals',
        'title': '빠른 사용 안내',
        'description': '막히는 순간만 짧게 확인',
        'route_name': 'service_guide_list',
    },
    {
        'key': 'tools',
        'title': '외부 AI 도구 참고',
        'description': '외부 도구 비교는 여기서',
        'route_name': 'tool_guide',
    },
]

TEACHER_FIRST_SERVICE_GUIDE_SECTIONS = [
    {
        'key': 'collect_sign',
        'title': '수합·서명',
        'description': '동의, 서명, 회수처럼 학부모 응답을 빠르게 모아야 할 때 확인합니다.',
    },
    {
        'key': 'work',
        'title': '문서·작성',
        'description': '가정통신문, 문서 작성, 정리형 도구를 사용할 때 필요한 안내를 모았습니다.',
    },
    {
        'key': 'classroom',
        'title': '학급 운영',
        'description': '학급 캘린더, 학급 기록 보드, 학급 운영 도구처럼 매일 쓰는 흐름을 먼저 보여줍니다.',
    },
    {
        'key': 'counsel',
        'title': '학부모 소통·상담',
        'description': '연락, 상담 조율, 보호자 안내처럼 사람과 연결되는 흐름을 담았습니다.',
    },
    {
        'key': 'edutech',
        'title': '가이드·인사이트',
        'description': '도구 사용법이나 인사이트처럼 참고 성격이 강한 콘텐츠입니다.',
    },
    {
        'key': 'game',
        'title': '교실 활동',
        'description': '수업 몰입과 분위기 전환을 돕는 활동형 도구를 모았습니다.',
    },
    {
        'key': 'etc',
        'title': '외부 서비스',
        'description': '외부 연동 또는 별도 서비스로 이어지는 도구입니다.',
    },
]

TEACHER_FIRST_TOOL_GUIDE_SECTIONS = [
    {
        'key': 'writing',
        'title': '글쓰기·정리 도움',
        'description': '통신문 초안, 글 정리, 번역, 수업 자료 정리에 도움이 되는 외부 도구입니다.',
        'tool_ids': ['chatgpt', 'claude', 'gemini', 'deepl', 'wrtn', 'notion'],
    },
    {
        'key': 'research',
        'title': '자료 찾기·분석',
        'description': '출처 확인, 자료 조사, 문서 기반 요약이 필요할 때 참고합니다.',
        'tool_ids': ['perplexity', 'copilot'],
    },
    {
        'key': 'design',
        'title': '디자인·발표',
        'description': '수업 자료, 발표 자료, 이미지·영상·음성 제작에 쓰는 도구입니다.',
        'tool_ids': ['figma', 'canva', 'midjourney', 'runway', 'elevenlabs'],
    },
    {
        'key': 'build',
        'title': '개발·운영 참고',
        'description': '서비스 제작이나 운영 점검이 필요한 고급 참고 도구입니다.',
        'tool_ids': ['cursor', 'v0', 'supabase', 'railway', 'sentry'],
    },
]


def _build_teacher_first_entry_points(current_key):
    entry_points = []
    for item in TEACHER_FIRST_ENTRY_POINT_META:
        entry_points.append({
            'key': item['key'],
            'title': item['title'],
            'description': item['description'],
            'href': reverse(item['route_name']),
            'is_current': item['key'] == current_key,
        })
    return entry_points


def _build_service_guide_sections(manuals, products_without_manual):
    manual_buckets = {section['key']: [] for section in TEACHER_FIRST_SERVICE_GUIDE_SECTIONS}
    for manual in manuals:
        manual_buckets.setdefault(manual.product.service_type, []).append(manual)

    pending_buckets = {section['key']: [] for section in TEACHER_FIRST_SERVICE_GUIDE_SECTIONS}
    for product in products_without_manual:
        pending_buckets.setdefault(product.service_type, []).append(product)

    sections = []
    for section in TEACHER_FIRST_SERVICE_GUIDE_SECTIONS:
        section_manuals = manual_buckets.get(section['key'], [])
        pending_products = pending_buckets.get(section['key'], [])
        if not section_manuals and not pending_products:
            continue
        sections.append({
            **section,
            'manuals': section_manuals,
            'pending_products': pending_products,
            'pending_count': len(pending_products),
        })
    return sections


def _build_tool_guide_sections(tools):
    tools_by_id = {tool['id']: tool for tool in tools}
    sections = []
    for section in TEACHER_FIRST_TOOL_GUIDE_SECTIONS:
        section_tools = []
        for tool_id in section['tool_ids']:
            tool = tools_by_id.get(tool_id)
            if tool:
                section_tools.append(tool)
        if not section_tools:
            continue
        sections.append({
            **section,
            'tools': section_tools,
        })
    return sections


def tool_guide(request):
    from core.data import TOOLS_DATA
    from datetime import datetime, timedelta

    today = datetime.now().date()
    threshold = today - timedelta(days=30)

    tools = []
    for tool in TOOLS_DATA:
        tool_copy = tool.copy()
        try:
            updated_date = datetime.strptime(tool['last_updated'], '%Y-%m-%d').date()
            tool_copy['is_new'] = updated_date >= threshold
        except (KeyError, ValueError):
            tool_copy['is_new'] = False
        tools.append(tool_copy)

    return render(request, 'core/tool_guide.html', {
        'entry_points': _build_teacher_first_entry_points('tools'),
        'tool_sections': _build_tool_guide_sections(tools),
        'all_tools_count': len(tools),
        'new_tools_count': sum(1 for tool in tools if tool['is_new']),
        'teacher_first_contract_path': TEACHER_FIRST_PRODUCT_CONTRACT_PATH,
        **build_tool_guide_page_seo(request).as_context(),
    })


def about(request):
    # Stats could be dynamic later
    stats = {
        'lecture_hours': 120, # Placeholder
        'tools_built': Product.objects.count() + 5, # Approx
        'students': 500, # Placeholder
    }
    return render(request, 'core/about.html', {'stats': stats})

@login_required
def settings_view(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, '프로필 정보가 성공적으로 수정되었습니다.')
            return redirect('settings')
    else:
        form = UserProfileUpdateForm(instance=profile)
    
    return render(request, 'core/settings.html', {'form': form})

@login_required
def select_role(request):
    """역할 선택 및 별명 설정 화면"""
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    # 이미 역할과 닉네임이 설정된 경우 스킵 (단, 명시적으로 수정을 위해 접근했을 수도 있으니 처리 필요하지만, 
    # 보통 settings에서 수정하므로 여기는 초기 설정용으로 간주)
    # 하지만 사용자가 강제로 URL로 들어올 수도 있으므로, GET 요청이고 이미 설정되어있다면 home으로 보낸다.
    # 단, next가 있으면 next로 보낸다.
    if request.method == 'GET' and profile.role and profile.nickname:
        next_url = request.GET.get('next', 'home')
        return redirect(next_url)

    if request.method == 'POST':
        role = request.POST.get('role')
        nickname = request.POST.get('nickname')
        
        if role in ['school', 'instructor', 'company']:
            profile.role = role
        
        if nickname:
            profile.nickname = nickname.strip()

        profile.save()
            
        # 역할 선택 후 원래 가려던 SSO 페이지로 이동하거나 대시보드로 이동
        next_url = request.GET.get('next', 'home')
        return redirect(next_url)
    
    return render(request, 'core/select_role.html')

@login_required
def sso_to_schoolit(request):
    """스쿨잇으로 자동 로그인하여 이동하는 브릿지 뷰"""
    from .utils import generate_sso_token, get_schoolit_url
    
    profile = request.user.userprofile
    if not profile.role:
        # 역할이 없으면 선택 페이지로 먼저 보냄
        return redirect(f"{reverse('select_role')}?next={request.path}")
    
    token = generate_sso_token(request.user)
    target_url = get_schoolit_url(profile.role)
    
    # 쿼리 스트링으로 토큰 전달 (schoolit에서 이 토큰을 받아 처리해야 함)
    import urllib.parse
    redirect_url = f"{target_url}?sso_token={token}"
    return redirect(redirect_url)


@login_required
def policy_consent_view(request):
    next_url = get_safe_next_url(request)
    if not user_requires_policy_consent(request.user):
        return redirect(next_url)

    if has_current_policy_consent(request.user, request.session):
        return redirect(next_url)

    provider = get_latest_social_provider(request.user)
    form = PolicyConsentForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        UserPolicyConsent.objects.get_or_create(
            user=request.user,
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            defaults={
                'provider': provider,
                'agreed_at': timezone.now(),
                'agreement_source': get_agreement_source(request.user, provider),
                'ip_address': _get_request_client_ip(request) or None,
                'user_agent': (request.META.get('HTTP_USER_AGENT') or '').strip(),
            },
        )
        mark_current_policy_consent(request.session, request.user)
        return redirect(next_url)

    policy_meta = get_policy_meta()
    return render(
        request,
        'core/policy_consent.html',
        {
            'form': form,
            'policy_meta': policy_meta,
            'provider': provider,
            'provider_label': get_provider_label(provider),
            'next_url': next_url,
            'terms_url': f"{reverse('policy')}#terms",
            'privacy_url': f"{reverse('policy')}#privacy",
            'operations_url': f"{reverse('policy')}#operations",
            'hide_navbar': True,
        },
    )


def policy_view(request):
    """이용약관 및 개인정보처리방침 페이지"""
    return render(request, 'core/policy.html', {'policy_meta': get_policy_meta()})

@login_required
def update_email(request):
    """
    기존 사용자 이메일 및 닉네임 업데이트
    - 이메일이나 프로필 정보가 부족한 사용자에게 필무 정보 입력 요구
    """
    profile = request.user.userprofile
    
    # 이미 이메일과 닉네임이 모두 있으면 홈으로
    if request.user.email and profile.nickname and not profile.nickname.startswith('user'):
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        nickname = request.POST.get('nickname', '').strip()

        # 이메일 검증
        if not (email and '@' in email and '.' in email):
            messages.error(request, '올바른 이메일 주소를 입력해주세요.')
            return render(request, 'core/update_email.html', {'nickname': nickname, 'email': email})

        # 닉네임 검증
        if not nickname:
            messages.error(request, '사용하실 별명을 입력해주세요.')
            return render(request, 'core/update_email.html', {'nickname': nickname, 'email': email})

        # 정보 저장
        request.user.email = email
        request.user.first_name = nickname # SIS 표준: 이름 필드 채움
        request.user.save()
        
        profile.nickname = nickname
        profile.save()
        
        messages.success(request, f'{nickname}님, 환영합니다! 정보가 성공적으로 등록되었습니다. 🎉')

        # 원래 가려던 곳(next)이 있으면 그리로, 없으면 역할 선택 페이지(첫 가입 시)로
        next_url = request.GET.get('next')
        if not next_url or next_url == 'home':
            if not profile.role:
                return redirect('select_role')
            return redirect('home')
        return redirect(next_url)

    return render(request, 'core/update_email.html', {
        'nickname': profile.nickname if profile.nickname and not profile.nickname.startswith('user') else "",
        'email': request.user.email
    })

@login_required
def delete_account(request):
    """사용자 계정 탈퇴 처리"""
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, '그동안 이용해주셔서 감사합니다. 계정이 안전하게 삭제되었습니다.')
        return redirect('home')
    
    return render(request, 'core/delete_account.html')


@login_required
def admin_dashboard_view(request):
    """superuser 전용 방문자 통계 대시보드"""
    if not request.user.is_superuser:
        messages.error(request, '관리자만 접근 가능합니다.')
        return redirect('home')

    from .utils import get_visitor_stats, get_weekly_stats
    from .models import VisitorLog, SiteConfig
    from products.models import Product
    from django.utils import timezone
    import datetime
    import logging

    logger = logging.getLogger(__name__)

    # Handle NotebookLM URL update
    if request.method == 'POST' and 'notebook_manual_url' in request.POST:
        notebook_url = request.POST.get('notebook_manual_url', '').strip()
        
        # Validate URL (must be notebooklm.google.com or empty)
        if notebook_url and not notebook_url.startswith('https://notebooklm.google.com'):
            logger.warning(f"[NotebookLM_Config] Action: URL_UPDATE, Status: VALIDATION_FAILED, URL: {notebook_url}, User: {request.user.username}")
            messages.error(request, 'NotebookLM URL은 https://notebooklm.google.com 도메인이어야 합니다.')
        else:
            # Update Product instead of SiteConfig (SIS Compliance)
            product = Product.objects.filter(title='교사 백과사전').first()
            if product:
                old_url = product.external_url
                product.external_url = notebook_url
                product.save()
                logger.info(f"[NotebookLM_Config] Action: URL_UPDATE, Status: SUCCESS, Old_URL: {old_url}, New_URL: {notebook_url}, User: {request.user.username}")
                messages.success(request, 'NotebookLM 매뉴얼 URL이 성공적으로 업데이트되었습니다.')
            else:
                messages.error(request, '교사 백과사전 서비스를 찾을 수 없습니다. (ensure_notebooklm 실행 필요)')
        
        return redirect('admin_dashboard')

    today = timezone.localdate()
    
    # Total counts
    total_count = VisitorLog.objects.count()
    human_total_count = VisitorLog.objects.filter(is_bot=False).count()
    bot_total_count = total_count - human_total_count

    # Today's counts
    today_count = VisitorLog.objects.filter(visit_date=today).count()
    today_human_count = VisitorLog.objects.filter(visit_date=today, is_bot=False).count()
    today_bot_count = today_count - today_human_count

    # Weekly/Monthly start dates
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Weekly/Monthly counts
    week_count = VisitorLog.objects.filter(visit_date__gte=week_start).count()
    week_human_count = VisitorLog.objects.filter(visit_date__gte=week_start, is_bot=False).count()
    
    month_count = VisitorLog.objects.filter(visit_date__gte=month_start).count()
    month_human_count = VisitorLog.objects.filter(visit_date__gte=month_start, is_bot=False).count()

    # Detailed stats (Humans only for the chart)
    daily_stats = get_visitor_stats(30, exclude_bots=True)
    weekly_stats = get_weekly_stats(8, exclude_bots=True)

    # Chart max value
    max_daily = max((s['count'] for s in daily_stats), default=1) or 1
    
    # Get current NotebookLM URL from Product (SIS Compliance)
    notebook_product = Product.objects.filter(title='교사 백과사전').first()
    current_notebook_url = notebook_product.external_url if notebook_product else ''

    return render(request, 'core/admin_dashboard.html', {
        'today_count': today_count,
        'today_human_count': today_human_count,
        'today_bot_count': today_bot_count,
        'week_count': week_count,
        'week_human_count': week_human_count,
        'month_count': month_count,
        'month_human_count': month_human_count,
        'total_count': total_count,
        'human_total_count': human_total_count,
        'bot_total_count': bot_total_count,
        'daily_stats': daily_stats,
        'weekly_stats': weekly_stats,
        'max_daily': max_daily,
        'current_notebook_url': current_notebook_url,
    })


@require_POST
def feedback_view(request):
    """피드백 제출 (비로그인 사용자도 가능)"""
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    category = request.POST.get('category', 'other')
    message_text = request.POST.get('message', '').strip()

    if not name or not message_text:
        messages.error(request, '이름과 내용은 필수 입력입니다.')
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="text-red-500 text-sm font-bold p-2">이름과 내용은 필수입니다.</div>',
                status=200,
            )
        return redirect('home')

    Feedback.objects.create(
        name=name,
        email=email,
        category=category if category in ('bug', 'suggestion', 'other') else 'other',
        message=message_text,
    )
    messages.success(request, '소중한 의견 감사합니다! 빠르게 확인하겠습니다.')

    if request.headers.get('HX-Request'):
        return HttpResponse(
            '<div class="text-green-600 text-sm font-bold p-2">감사합니다! 의견이 접수되었습니다.</div>',
            status=200,
        )
    return redirect('home')

def service_guide_list(request):
    """Teacher-first list of available service manuals."""
    active_products_qs = Product.objects.filter(is_active=True).order_by('display_order')
    manuals_all_qs = ServiceManual.objects.filter(product__is_active=True).select_related('product')
    manuals_qs = ServiceManual.objects.filter(
        is_published=True,
        product__is_active=True
    ).select_related('product').order_by('product__display_order', 'product__title')

    site_config = SiteConfig.load()
    featured_manuals_qs = site_config.featured_manuals.filter(
        is_published=True,
        product__is_active=True
    ).select_related('product').order_by('product__display_order', 'product__title')

    active_products = _attach_product_launch_meta(list(active_products_qs))
    active_products_count = len(active_products)
    product_map = {product.id: product for product in active_products}

    featured_manual_ids = featured_manuals_qs.values_list('id', flat=True)
    manuals = list(manuals_qs.exclude(id__in=featured_manual_ids))
    featured_manuals = list(featured_manuals_qs)
    all_manuals = featured_manuals + manuals
    for manual in all_manuals:
        prepared_product = product_map.get(manual.product_id)
        if not prepared_product:
            continue
        for attr_name in (
            'launch_href',
            'launch_is_external',
            'teacher_first_task_label',
            'teacher_first_service_label',
            'teacher_first_support_label',
            'home_card_summary',
            'public_service_name',
            'detail_context_chips',
            'home_context_chips',
        ):
            setattr(manual.product, attr_name, getattr(prepared_product, attr_name, ''))
    manual_count = manuals_qs.count()
    product_ids_with_any_manual = set(manuals_all_qs.values_list('product_id', flat=True))
    products_without_manual = [
        product for product in active_products
        if product.id not in product_ids_with_any_manual and not _is_sheetbook_cross_surface_hidden(product)
    ]
    missing_manual_count = len(products_without_manual)

    return render(request, 'core/service_guide_list.html', {
        'guide_entry_points': _build_guide_entry_points(),
        'guide_groups': _build_guide_groups(all_manuals, products_without_manual),
        'active_products_count': active_products_count,
        'manual_count': manual_count,
        'missing_manual_count': missing_manual_count,
        'teacher_first_contract_path': TEACHER_FIRST_PRODUCT_CONTRACT_PATH,
        **build_service_guide_list_seo(request).as_context(),
    })

def service_guide_detail(request, pk):
    """Detailed view of a specific manual"""
    manual = get_object_or_404(
        ServiceManual.objects.select_related('product'), 
        pk=pk,
        is_published=True,
        product__is_active=True
    )
    prepared_product = _attach_product_launch_meta([manual.product])[0]
    manual.product = prepared_product
    manual = _prepare_manual_display(manual)
    sections = list(manual.sections.all())
    for section in sections:
        section.display_title = _replace_public_service_terms(section.title, manual.product)
        section.display_content = _replace_public_service_terms(section.content, manual.product)
    launch_href, launch_is_external = _resolve_product_launch_url(manual.product)
    launch_label = f"{manual.public_service_name} 열기"
    if _is_calendar_hub_product(manual.product):
        launch_href = _home_calendar_surface_url()
        launch_label = "홈에서 캘린더 보기"

    seo_meta = build_service_guide_detail_seo(request, manual)
    response = render(request, 'core/service_guide_detail.html', {
        'manual': manual,
        'sections': sections,
        'launch_href': launch_href,
        'launch_is_external': launch_is_external,
        'launch_label': launch_label,
        **seo_meta.as_context(),
    })
    if seo_meta.robots.startswith("noindex"):
        response["X-Robots-Tag"] = seo_meta.robots.replace(",", ", ")
    return response


@require_POST
def track_product_usage(request):
    """서비스 사용 기록 API (로그인 사용자 전용)."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'ignored'}, status=200)

    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    product_id = data.get('product_id')
    action = data.get('action', 'launch')
    source = data.get('source', 'other')

    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)

    valid_actions = [c[0] for c in ProductUsageLog.ACTION_CHOICES]
    valid_sources = [c[0] for c in ProductUsageLog.SOURCE_CHOICES]
    if action not in valid_actions:
        action = 'launch'
    if source not in valid_sources:
        source = 'other'

    try:
        product = Product.objects.get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'product not found'}, status=404)

    ProductUsageLog.objects.create(
        user=request.user,
        product=product,
        action=action,
        source=source,
    )
    return JsonResponse({'status': 'ok'})


@require_POST
@login_required
def toggle_product_favorite(request):
    """서비스 즐겨찾기 토글 API."""
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    product_id = data.get('product_id')
    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)

    try:
        product = Product.objects.get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'product not found'}, status=404)

    favorite = ProductFavorite.objects.filter(user=request.user, product=product).first()
    if favorite:
        favorite.delete()
        return JsonResponse({
            'status': 'ok',
            'is_favorite': False,
            'product_id': product.id,
        })

    max_order = (
        ProductFavorite.objects
        .filter(user=request.user)
        .aggregate(max_order=Max('pin_order'))
        .get('max_order')
        or 0
    )
    ProductFavorite.objects.create(
        user=request.user,
        product=product,
        pin_order=max_order + 1,
    )
    return JsonResponse({
        'status': 'ok',
        'is_favorite': True,
        'product_id': product.id,
    })


@require_GET
@login_required
def list_product_favorites(request):
    """로그인 사용자의 즐겨찾기 목록 API."""
    favorites_qs = (
        ProductFavorite.objects
        .filter(user=request.user, product__is_active=True)
        .select_related('product')
        .order_by('pin_order', '-created_at')
    )

    favorites = []
    for favorite in favorites_qs:
        product = favorite.product
        href, is_external = _resolve_product_launch_url(product)
        favorites.append({
            'product_id': product.id,
            'title': product.title,
            'icon': product.icon,
            'href': href,
            'is_external': is_external,
            'pin_order': favorite.pin_order,
        })

    return JsonResponse({
        'status': 'ok',
        'favorites': favorites,
    })


@require_GET
@login_required
def list_workbench_bundles(request):
    bundles = _get_user_workbench_bundles(
        request.user,
        _attach_product_launch_meta(
            list(
                filter_discoverable_products(
                    Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
                )
            )
        ),
    )
    return JsonResponse({'status': 'ok', 'bundles': bundles})


@require_POST
@login_required
def save_workbench_bundle(request):
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    name = str(data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'name required'}, status=400)

    normalized_ids = _normalize_workbench_product_ids(data.get('product_ids'), require_non_empty=True)
    if not normalized_ids:
        return JsonResponse({'error': 'product_ids required'}, status=400)

    valid_ids = set(Product.objects.filter(is_active=True, id__in=normalized_ids).values_list('id', flat=True))
    if len(valid_ids) != len(normalized_ids):
        return JsonResponse({'error': 'invalid product id'}, status=400)

    bundle, created = ProductWorkbenchBundle.objects.update_or_create(
        user=request.user,
        name=name,
        defaults={'product_ids': normalized_ids},
    )
    if not created:
        bundle.updated_at = timezone.now()
        bundle.save(update_fields=['product_ids', 'updated_at'])

    return JsonResponse({
        'status': 'ok',
        'bundle': {
            'id': bundle.id,
            'name': bundle.name,
            'product_ids': normalized_ids,
            'product_count': len(normalized_ids),
        },
        'created': created,
    })


@require_POST
@login_required
def apply_workbench_bundle(request, bundle_id):
    bundle = get_object_or_404(ProductWorkbenchBundle, id=bundle_id, user=request.user)
    product_ids = _normalize_workbench_product_ids(bundle.product_ids, require_non_empty=True)
    if not product_ids:
        return JsonResponse({'error': 'bundle is empty'}, status=400)

    active_id_set = set(
        Product.objects
        .filter(is_active=True, id__in=product_ids)
        .values_list('id', flat=True)
    )
    active_ids = [product_id for product_id in product_ids if product_id in active_id_set]
    if not active_ids:
        return JsonResponse({'error': 'bundle has no active products'}, status=400)

    favorites = list(
        ProductFavorite.objects
        .filter(user=request.user, product__is_active=True)
        .order_by('pin_order', '-created_at')
    )
    favorite_map = {favorite.product_id: favorite for favorite in favorites}

    with transaction.atomic():
        for product_id in active_ids:
            if product_id not in favorite_map:
                favorite_map[product_id] = ProductFavorite.objects.create(
                    user=request.user,
                    product_id=product_id,
                    pin_order=0,
                )
        ordered_ids = []
        seen = set()
        for product_id in active_ids:
            if product_id in seen:
                continue
            ordered_ids.append(product_id)
            seen.add(product_id)
        for favorite in favorites:
            if favorite.product_id in seen:
                continue
            ordered_ids.append(favorite.product_id)
            seen.add(favorite.product_id)
        for order, product_id in enumerate(ordered_ids, start=1):
            favorite = favorite_map[product_id]
            if favorite.pin_order != order:
                ProductFavorite.objects.filter(pk=favorite.pk).update(pin_order=order)
        ProductWorkbenchBundle.objects.filter(pk=bundle.pk).update(last_used_at=timezone.now())

    return JsonResponse({
        'status': 'ok',
        'bundle_id': bundle.id,
        'bundle_name': bundle.name,
        'product_ids': ordered_ids,
    })


@require_POST
@login_required
def delete_workbench_bundle(request, bundle_id):
    bundle = get_object_or_404(ProductWorkbenchBundle, id=bundle_id, user=request.user)
    bundle_name = bundle.name
    bundle.delete()
    return JsonResponse({
        'status': 'ok',
        'bundle_id': bundle_id,
        'bundle_name': bundle_name,
    })


@require_POST
@login_required
def reorder_product_favorites(request):
    """즐겨찾기 작업대 순서를 저장한다."""
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    product_ids = data.get('product_ids')
    if not isinstance(product_ids, list) or not product_ids:
        return JsonResponse({'error': 'product_ids required'}, status=400)

    normalized_ids = []
    seen = set()
    for raw_id in product_ids:
        try:
            pid = int(raw_id)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'invalid product id'}, status=400)
        if pid in seen:
            return JsonResponse({'error': 'duplicate product id'}, status=400)
        normalized_ids.append(pid)
        seen.add(pid)

    favorites = list(
        ProductFavorite.objects
        .filter(user=request.user, product__is_active=True)
        .order_by('pin_order', '-created_at')
    )
    if not favorites:
        return JsonResponse({'error': 'favorites not found'}, status=404)

    favorite_map = {favorite.product_id: favorite for favorite in favorites}
    if not set(normalized_ids).issubset(favorite_map.keys()):
        return JsonResponse({'error': 'favorite mismatch'}, status=400)

    ordered_ids = list(normalized_ids)
    for favorite in favorites:
        if favorite.product_id not in seen:
            ordered_ids.append(favorite.product_id)

    with transaction.atomic():
        for order, product_id in enumerate(ordered_ids, start=1):
            favorite = favorite_map[product_id]
            if favorite.pin_order != order:
                ProductFavorite.objects.filter(pk=favorite.pk).update(pin_order=order)

    return JsonResponse({
        'status': 'ok',
        'product_ids': ordered_ids,
    })


@require_POST
@login_required
def set_active_classroom(request):
    """네비게이션 학급 단축키 — 세션에 현재 학급 저장."""
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    source = data.get('source', '')
    cid = data.get('classroom_id', '')
    persist_default_raw = data.get('persist_default', None)
    if persist_default_raw is None:
        # 기본 동작: HS 학급 선택 시에는 기본 학급으로 함께 저장
        persist_default = bool(source == 'hs' and cid)
    elif isinstance(persist_default_raw, str):
        persist_default = persist_default_raw.strip().lower() in {'1', 'true', 'yes', 'on'}
    else:
        persist_default = bool(persist_default_raw)

    # 선택 해제
    if not cid:
        clear_active_classroom_session(request)
        if persist_default:
            set_default_classroom_for_user(request.user, None)
        return JsonResponse({'status': 'cleared', 'default_saved': persist_default})

    if source == 'hs':
        try:
            from happy_seed.models import HSClassroom
            classroom = HSClassroom.objects.get(pk=cid, teacher=request.user)
        except Exception:
            return JsonResponse({'error': 'classroom not found'}, status=404)
        set_active_classroom_session(request, classroom)
        if persist_default:
            set_default_classroom_for_user(request.user, classroom)
        return JsonResponse({
            'status': 'ok',
            'name': classroom.name,
            'default_saved': persist_default,
        })

    return JsonResponse({'error': 'unknown source'}, status=400)


def health_check(request):
    from django.db import connection
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        logger.exception("Health check DB connection failed: %s", e)
        return JsonResponse({'status': 'error', 'db': 'unavailable'}, status=503)
