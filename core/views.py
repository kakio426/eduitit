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
from .active_classroom import (
    set_active_classroom_session,
    clear_active_classroom_session,
    set_default_classroom_for_user,
)
from django.contrib import messages
from django.db import transaction
from django.db.models import Case, Count, DateTimeField, F, IntegerField, Max, Q, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.timesince import timesince
from PIL import Image
import logging

from .teacher_first_cards import (
    build_teacher_first_product_meta,
)

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
    'news_link',
    'notice',
)


WORKBENCH_BUNDLE_LIMIT = 6
WORKBENCH_BUNDLE_PRODUCT_LIMIT = 8
WORKBENCH_SLOT_COUNT = 4
WORKBENCH_WEEKLY_BUNDLE_LIMIT = 2


def _record_sheetbook_workspace_metric(request, event_name, *, metadata=None):
    if not request.user.is_authenticated:
        return
    if not getattr(settings, "SHEETBOOK_ENABLED", False):
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

# =============================================================================
# V2 홈 목적별 섹션 매핑 (메인 4 + 보조 3)
# =============================================================================
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
        "key": "refresh",
        "title": "상담·리프레시",
        "subtitle": "학생 상담과 성향 확인을 바로",
        "icon": "fa-solid fa-heart",
        "color": "rose",
    },
    {
        "key": "guide",
        "title": "가이드·인사이트",
        "subtitle": "바로 참고하는 안내와 인사이트",
        "icon": "fa-solid fa-lightbulb",
        "color": "amber",
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
        "key": "external",
        "title": "외부 서비스",
        "subtitle": "연동/제휴 서비스",
        "icon": "fa-solid fa-up-right-from-square",
        "color": "emerald",
    },
]

HOME_SECTION_BY_ROUTE = {
    "collect:landing": "collect_sign",
    "consent:landing": "collect_sign",
    "signatures:landing": "collect_sign",
    "signatures:list": "collect_sign",
    "handoff:landing": "collect_sign",
    "noticegen:main": "doc_write",
    "hwpxchat:main": "doc_write",
    "version_manager:landing": "doc_write",
    "hwp_converter:landing": "doc_write",
    "classcalendar:main": "class_ops",
    "happy_seed:landing": "class_ops",
    "reservations:dashboard_landing": "class_ops",
    "reservations:landing": "class_ops",
    "textbooks:main": "class_ops",
    "edu_materials:main": "class_ops",
    "qrgen:landing": "class_ops",
    "seed_quiz:landing": "class_ops",
    "ppobgi:main": "class_ops",
    "artclass:main": "class_ops",
    "studentmbti:landing": "refresh",
    "studentmbti:dashboard": "refresh",
    "ssambti:main": "refresh",
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
    ("퀴즈", "class_ops"),
    ("qr", "class_ops"),
    ("행복의 씨앗", "class_ops"),
    ("추첨기", "class_ops"),
    ("미술 수업", "class_ops"),
    ("윷놀이", "class_activity"),
    ("체스", "class_activity"),
    ("장기", "class_activity"),
    ("커넥트 포", "class_activity"),
    ("이솔레이션", "class_activity"),
    ("아택스", "class_activity"),
    ("브레이크스루", "class_activity"),
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

HOME_COMPANION_SECTION_MAP = {
    'collect_sign': ['doc_write', 'class_ops'],
    'doc_write': ['collect_sign', 'class_ops'],
    'class_ops': ['doc_write', 'collect_sign'],
    'class_activity': ['class_ops'],
    'refresh': ['doc_write'],
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


def _resolve_home_section_key(product):
    route_name = (product.launch_route_name or "").strip().lower()
    if route_name in HOME_SECTION_BY_ROUTE:
        return HOME_SECTION_BY_ROUTE[route_name]

    title = (product.title or "").strip().lower()
    for keyword, section_key in HOME_SECTION_KEYWORDS:
        if keyword.lower() in title:
            return section_key

    external_url = (product.external_url or "").strip().lower()
    if external_url.startswith("http://") or external_url.startswith("https://"):
        return "external"

    return HOME_SECTION_FALLBACK_BY_TYPE.get(product.service_type, "guide")


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


def _resolve_product_launch_url(product):
    """Resolve direct launch URL for quick actions."""
    route_name = (product.launch_route_name or '').strip()
    external_url = (product.external_url or '').strip()

    # Absolute URLs are treated as truly external services.
    if external_url.startswith("http://") or external_url.startswith("https://"):
        return external_url, True

    if route_name:
        try:
            return reverse(route_name), False
        except NoReverseMatch:
            logger.warning("Launch route missing for product '%s' (%s).", product.title, route_name)

    # Legacy internal path fallback (e.g. /products/yut/)
    if external_url:
        return external_url, False

    return reverse('product_detail', kwargs={'pk': product.pk}), False


def _build_home_calendar_summary(today_context, sheetbook_workspace):
    default_href = reverse("classcalendar:main")
    date_text = sheetbook_workspace.get("today_date_text") or today_context.get("today_date_text") or timezone.localdate().strftime("%Y-%m-%d")
    rows = sheetbook_workspace.get("today_rows") or []
    if rows:
        entries = [
            {
                "title": row.get("title", ""),
                "subtitle": row.get("sheetbook_title", ""),
                "href": row.get("href") or default_href,
            }
            for row in rows[:2]
        ]
        return {
            "title": "오늘 일정",
            "date_text": date_text,
            "count_text": f"{len(rows)}건",
            "entries": entries,
            "href": default_href,
        }

    calendar_item = None
    for item in today_context.get("today_items", []):
        if item.get("href") == default_href or "학급 일정" in str(item.get("title", "")):
            calendar_item = item
            break

    if calendar_item:
        return {
            "title": "오늘 일정",
            "date_text": date_text,
            "count_text": calendar_item.get("count_text") or "1건",
            "entries": [
                {
                    "title": calendar_item.get("title", ""),
                    "subtitle": calendar_item.get("description", ""),
                    "href": calendar_item.get("href") or default_href,
                }
            ],
            "href": default_href,
        }

    return {
        "title": "오늘 일정",
        "date_text": date_text,
        "count_text": "0건",
        "entries": [],
        "href": default_href,
    }


def _build_home_sns_post_preview(post):
    raw_title = getattr(post, "og_title", "") or getattr(post, "content", "")
    raw_excerpt = getattr(post, "og_description", "") or getattr(post, "content", "")
    title = Truncator(strip_tags(raw_title)).chars(48)
    excerpt = Truncator(strip_tags(raw_excerpt)).chars(88)
    if excerpt and excerpt == title:
        excerpt = ""

    author = getattr(post, "author", None)
    profile = getattr(author, "userprofile", None) if author else None
    author_display = getattr(profile, "nickname", "") or getattr(author, "username", "") or ""
    created_value = getattr(post, "created_at", None)
    created_label = ""
    if created_value:
        created_label = f"{timesince(created_value, timezone.now()).split(',')[0]} 전"

    thumbnail = ""
    image_field = getattr(post, "image", None)
    if image_field:
        try:
            thumbnail = image_field.url
        except Exception:
            thumbnail = ""
    if not thumbnail:
        thumbnail = getattr(post, "og_image_url", "") or ""

    post_type = getattr(post, "post_type", "general")
    source_url = getattr(post, "source_url", "") or ""
    if post_type == "news_link" and source_url:
        detail_href = source_url
        detail_external = True
    else:
        detail_href = reverse("post_detail_partial", kwargs={"pk": getattr(post, "id", 0)})
        detail_external = False

    badge_label = ""
    badge_tone = "neutral"
    if post_type == "notice":
        badge_label = "공지"
        badge_tone = "notice"
    elif post_type == "news_link":
        badge_label = "링크"
        badge_tone = "link"

    return {
        "title": title,
        "excerpt": excerpt,
        "thumbnail": thumbnail,
        "post_type": post_type,
        "author_display": author_display,
        "created_label": created_label,
        "post_id": getattr(post, "id", None),
        "has_more_content": bool(excerpt),
        "detail_href": detail_href,
        "detail_external": detail_external,
        "badge_label": badge_label,
        "badge_tone": badge_tone,
    }


def _build_home_sns_summary(page_obj):
    post_list = list(getattr(page_obj, "object_list", [])[:2]) if page_obj is not None else []
    latest_posts = [_build_home_sns_post_preview(post) for post in post_list]
    notice_count = sum(1 for post in post_list if getattr(post, "post_type", "") == "notice")

    return {
        "title": "SNS",
        "latest_posts": latest_posts,
        "notice_count": notice_count,
        "href": reverse("home"),
    }


def _attach_product_launch_meta(products):
    """Attach launch target metadata so templates can navigate directly without modal."""
    prepared = []
    for product in products:
        launch_href, launch_is_external = _resolve_product_launch_url(product)
        product.launch_href = launch_href
        product.launch_is_external = launch_is_external
        for attr_name, attr_value in build_teacher_first_product_meta(product).items():
            setattr(product, attr_name, attr_value)
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
        preview_titles = [getattr(product_map[pid], 'card_title', '') or getattr(product_map[pid], 'teacher_first_task_label', '') or product_map[pid].title for pid in normalized_ids[:3]]
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
        preview_titles = [getattr(product_map[pid], 'card_title', '') or getattr(product_map[pid], 'teacher_first_task_label', '') or product_map[pid].title for pid in normalized_ids[:2]]
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
        item = {
            'product': product,
            'href': href,
            'is_external': is_external,
        }
        if include_section_meta:
            section_key = _resolve_home_section_key(product)
            section_meta = HOME_SECTION_META_BY_KEY.get(section_key, {})
            item['section_key'] = section_key
            item['section_title'] = section_meta.get('title', '추천 도구')
            item['section_subtitle'] = section_meta.get('subtitle', '')
        items.append(item)
    return items


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

    from products.views import (
        _build_qr_data_url,
        _build_student_games_launch_url,
        _create_student_games_token,
        _student_games_max_age_seconds,
    )

    token = _create_student_games_token(request)
    launch_url = _build_student_games_launch_url(request, token)
    return {
        "student_games_launch_url": launch_url,
        "student_games_qr_data_url": _build_qr_data_url(launch_url),
        "student_games_expires_hours": max(1, _student_games_max_age_seconds() // 3600),
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
        from classcalendar.models import CalendarEvent

        calendar_event_count = CalendarEvent.objects.filter(
            author=request.user,
            start_time__date=today,
        ).count()
        if calendar_event_count > 0:
            today_items.append(
                {
                    "title": "오늘 학급 일정",
                    "count_text": f"{calendar_event_count}건",
                    "description": "오늘 예정된 학급 일정이 있습니다. 캘린더를 확인해 보세요.",
                    "emoji": "📅",
                    "href": reverse("classcalendar:main"),
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


def _build_sheetbook_workspace_context(request):
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

    if not request.user.is_authenticated or not getattr(settings, "SHEETBOOK_ENABLED", False):
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


def _home_v2(request, products, posts, page_obj, feed_scope):
    """Feature flag on 시 호출되는 V2 홈."""
    product_list = _attach_product_launch_meta(list(products))
    sections, aux_sections, games = get_purpose_sections(
        product_list,
        preview_limit={
            "default": 2,
            "class_ops": 3,
        },
    )

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
        workbench_bundles = _get_user_workbench_bundles(request.user, product_list)
        weekly_bundle_items = _get_weekly_workbench_bundle_highlights(request.user, product_list)
        today_context = _build_today_context(request)
        sheetbook_workspace_context = _build_sheetbook_workspace_context(request)
        home_calendar_summary = _build_home_calendar_summary(today_context, sheetbook_workspace_context.get('sheetbook_workspace', {}))
        home_sns_summary = _build_home_sns_summary(page_obj)

        return render(request, 'core/home_authenticated_v2.html', {
            'products': products,
            'sections': sections,
            'aux_sections': aux_sections,
            'games': games,
            'quick_actions': quick_action_items,
            'favorite_items': favorite_items,
            'workbench_primary_items': favorite_items,
            'workbench_slots': workbench_slots,
            'favorite_product_ids': [p.id for p in favorite_products],
            'recent_items': recent_items,
            'workbench_recent_items': recent_items,
            'companion_items': companion_items,
            'discovery_items': discovery_items,
            'workbench_bundles': workbench_bundles,
            'weekly_bundle_items': weekly_bundle_items,
            'home_calendar_summary': home_calendar_summary,
            'home_sns_summary': home_sns_summary,
            'posts': posts,
            'page_obj': page_obj,
            'feed_scope': feed_scope,
            **today_context,
            **sheetbook_workspace_context,
            **_build_home_student_games_qr_context(request),
        })

    featured_product = next((p for p in product_list if p.is_featured), product_list[0] if product_list else None)
    return render(request, 'core/home_v2.html', {
        'products': products,
        'featured_product': featured_product,
        'sections': sections,
        'aux_sections': aux_sections,
        'games': games,
        'posts': posts,
        'page_obj': page_obj,
        'feed_scope': feed_scope,
    })

def home(request):
    # Order by display_order first, then by creation date
    products = Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
    feed_scope = _get_post_feed_scope(request)

    # SNS Posts - 모든 사용자에게 제공 (최신순 정렬)
    posts = _build_post_feed_queryset(feed_scope=feed_scope)

    # 페이징 처리 (PC 우측 및 모바일 하단 SNS 위젯용)
    from django.core.paginator import Paginator
    paginator = Paginator(posts, 5) # 한 페이지에 5개씩
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # HTMX 요청이면 post_list 영역만 반환
    if request.headers.get('HX-Request'):
        return _render_post_list_partial(request, page_obj, feed_scope)

    # V2 홈: Feature flag on 시 분기
    if settings.HOME_V2_ENABLED:
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
    })

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
    return render(request, 'core/prompt_lab.html')

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
        'description': '교무수첩, 달력, 학급 운영 도구처럼 매일 쓰는 흐름을 먼저 보여줍니다.',
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

def policy_view(request):
    """이용약관 및 개인정보처리방침 페이지"""
    return render(request, 'core/policy.html')

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
    for manual in featured_manuals + manuals:
        prepared_product = product_map.get(manual.product_id)
        if not prepared_product:
            continue
        for attr_name in (
            'launch_href',
            'launch_is_external',
            'teacher_first_task_label',
            'teacher_first_service_label',
            'teacher_first_support_label',
            'card_title',
            'card_subtitle',
            'card_summary',
        ):
            setattr(manual.product, attr_name, getattr(prepared_product, attr_name, ''))
    manual_count = manuals_qs.count()
    product_ids_with_any_manual = set(manuals_all_qs.values_list('product_id', flat=True))
    products_without_manual = [
        product for product in active_products
        if product.id not in product_ids_with_any_manual
    ]
    missing_manual_count = len(products_without_manual)

    return render(request, 'core/service_guide_list.html', {
        'entry_points': _build_teacher_first_entry_points('manuals'),
        'guide_sections': _build_service_guide_sections(manuals, products_without_manual),
        'manuals': manuals,
        'featured_manuals': featured_manuals,
        'products_without_manual': products_without_manual,
        'active_products_count': active_products_count,
        'manual_count': manual_count,
        'missing_manual_count': missing_manual_count,
        'teacher_first_contract_path': TEACHER_FIRST_PRODUCT_CONTRACT_PATH,
    })

def service_guide_detail(request, pk):
    """Detailed view of a specific manual"""
    manual = get_object_or_404(
        ServiceManual.objects.select_related('product'), 
        pk=pk,
        is_published=True,
        product__is_active=True
    )
    sections = manual.sections.all()
    launch_href, launch_is_external = _resolve_product_launch_url(manual.product)
    
    return render(request, 'core/service_guide_detail.html', {
        'manual': manual,
        'sections': sections,
        'launch_href': launch_href,
        'launch_is_external': launch_is_external,
    })


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
    bundles = _get_user_workbench_bundles(request.user, _attach_product_launch_meta(list(Product.objects.filter(is_active=True).order_by('display_order', '-created_at'))))
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
