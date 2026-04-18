import os

from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.core.paginator import Paginator
from django.urls import NoReverseMatch
from django.core.cache import cache
from products.models import Product, ServiceManual
from .forms import UserProfileUpdateForm
from .guide_links import SERVICE_GUIDE_PADLET_URL
from .home_agent_registry import (
    MESSAGE_CAPTURE_PLACEHOLDER,
    MESSAGE_CAPTURE_REVERSE_SEED,
    build_home_agent_mode_payload,
    get_home_agent_runtime_spec,
    get_home_agent_service_definitions,
    resolve_home_agent_mode_links,
    resolve_home_agent_starter_items,
    resolve_home_agent_ui_options,
)
from .home_agent_runtime import (
    HomeAgentConfigError,
    HomeAgentProviderError,
    generate_home_agent_preview,
)
from .home_agent_service_bridge import (
    HomeAgentExecutionError,
    execute_service_action,
)
from .home_surface_context import (
    HomeSurfaceProviderCards,
    HomeSurfaceProviderSpec,
    HomeSurfaceTemplateParts,
    build_home_surface_legacy_aliases,
    build_home_surface_slots,
    build_home_surface_template_context,
)
from .models import (
    UserProfile,
    UserPolicyConsent,
    Post,
    Comment,
    CommentReport,
    Feedback,
    ProductUsageLog,
    ProductFavorite,
    ProductWorkbenchBundle,
    UserModeration,
)
from .forms import PolicyConsentForm, SocialSignupConsentForm
from allauth.account.internal.decorators import login_not_required
from .policy_consent import (
    clear_current_social_signup_consent,
    get_agreement_source,
    get_latest_social_provider,
    get_pending_social_signup,
    get_social_signup_consent_redirect_url,
    has_current_social_signup_consent,
    mark_current_social_signup_consent,
    get_pending_policy_consent_redirect,
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
from .context_processors import prime_service_launcher_products
from . import service_launcher as service_launcher_utils
from .product_visibility import filter_discoverable_products
from .active_classroom import (
    get_active_classroom_for_request,
    set_active_classroom_session,
    clear_active_classroom_session,
    set_default_classroom_for_user,
)
from .service_launcher import (
    CALENDAR_HUB_PUBLIC_NAME,
    CLASS_ACTIVITY_ROUTE_NAMES,
    HOME_AUXILIARY_SECTIONS,
    HOME_MAIN_SECTIONS,
    HOME_SECTION_FALLBACK_BY_TYPE,
    HOME_SECTION_META_BY_KEY,
    get_public_product_name as _get_public_product_name,
    is_calendar_hub_product as _is_calendar_hub_product,
    replace_public_service_terms as _replace_public_service_terms,
    resolve_home_section_key as _resolve_home_section_key,
    resolve_product_launch_url as _resolve_product_launch_url,
)
from .prompt_lab_data import get_prompt_lab_catalog
from .seo import (
    PageSeoMeta,
    SITE_CANONICAL_BASE_URL,
    build_about_page_seo,
    build_home_page_seo,
    build_prompt_lab_page_seo,
)
from .teacher_first_cards import build_favorite_service_title, build_workbench_card_meta
from .teacher_buddy import (
    TeacherBuddyError,
    attach_teacher_buddy_avatar_context,
    build_teacher_buddy_avatar_context,
    build_teacher_buddy_panel_context,
    build_teacher_buddy_public_share_context,
    build_teacher_buddy_settings_context,
    build_teacher_buddy_share_svg,
    build_teacher_buddy_urls,
    draw_teacher_buddy,
    record_teacher_buddy_progress,
    record_teacher_buddy_sns_reward,
    redeem_teacher_buddy_coupon,
    select_teacher_buddy,
    select_teacher_buddy_profile,
    unlock_teacher_buddy_skin,
)
from .teacher_activity import (
    ACTIVITY_CATEGORY_SERVICE_USE,
    award_teacher_activity,
)
from messagebox.developer_chat import build_developer_chat_home_card_context
from django.contrib import messages
from django.db import transaction
from django.db.models import Case, Count, DateTimeField, F, IntegerField, Max, Q, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from urllib.parse import urlencode
from PIL import Image
import json
import logging
import random

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
POST_SURFACE_VARIANT_DEFAULT = ''
POST_SURFACE_VARIANT_HOME_RAIL = 'home_rail'
POST_SURFACE_VARIANT_ALLOWED = {
    POST_SURFACE_VARIANT_DEFAULT,
    POST_SURFACE_VARIANT_HOME_RAIL,
}


WORKBENCH_BUNDLE_LIMIT = 6
WORKBENCH_BUNDLE_PRODUCT_LIMIT = 8
WORKBENCH_SLOT_COUNT = 4
WORKBENCH_WEEKLY_BUNDLE_LIMIT = 2
ADMIN_ACTIVITY_WINDOW_DAYS = 14
HOME_MOBILE_SECTION_ORDER = (
    'workbench',
    'calendar',
    'quickdrop',
    'reservations',
    'sns',
)
HOME_V5_MOBILE_SECTION_ORDER = HOME_MOBILE_SECTION_ORDER
HOME_PROMOTED_MOBILE_SERVICE_KEYS = {'quickdrop'}
HOME_UTILITY_SERVICE_KEYS = {'quickdrop', 'schoolcomm'}
ADMIN_PAGE_NAME_BY_ROUTE = {
    'home': '홈',
    'about': '소개',
    'dashboard': '내 서비스',
    'community_feed': '커뮤니티',
    'prompt_lab': '프롬프트 연구실',
    'settings': '설정',
    'policy': '정책',
}

HOME_V7_AGENT_TACIT_RULES = (
    {
        'rule_key': 'field_trip_bus_ratio',
        'label': '현장학습 차량 비율',
        'summary': '학생 수와 좌석 수를 먼저 맞춥니다.',
        'scope': 'school',
        'related_service_keys': ('classcalendar', 'reservations'),
        'related_signal_types': ('calendar_day',),
        'trigger_keywords': ('현장학습', '버스', '차량'),
        'required_context': ('학생 수', '차량 좌석', '보조 인솔 여부'),
        'decision_hints': ('학생 수와 좌석 수를 먼저 맞춥니다.', '학년 일정과 기사 배치를 같이 봅니다.'),
        'examples': ('현장학습 이동 차량 수 확인',),
    },
    {
        'rule_key': 'attendance_proof_required',
        'label': '출결 증빙',
        'summary': '결석 사유와 증빙 여부를 먼저 확인합니다.',
        'scope': 'school',
        'related_service_keys': ('classcalendar', 'noticegen'),
        'related_signal_types': ('calendar_day',),
        'trigger_keywords': ('출결', '증빙', '결석'),
        'required_context': ('결석 사유', '제출 서류', '마감일'),
        'decision_hints': ('증빙이 필요한 일정은 알림장 첫 줄에 둡니다.',),
        'examples': ('체험학습 결석 증빙 체크',),
    },
    {
        'rule_key': 'school_approval_chain',
        'label': '학교 승인 순서',
        'summary': '교사 단독 처리 전에 내부 승인 순서를 먼저 확인합니다.',
        'scope': 'school',
        'related_service_keys': ('teacher_law', 'reservations'),
        'related_signal_types': ('calendar_day',),
        'trigger_keywords': ('승인', '보고', '결재'),
        'required_context': ('담당자', '관리자 공유 여부'),
        'decision_hints': ('학교 내부 보고 순서를 먼저 정리합니다.',),
        'examples': ('특별실 외부 행사 승인 절차',),
    },
    {
        'rule_key': 'notice_priority_order',
        'label': '알림장 우선순위',
        'summary': '시간 변경과 준비물을 가장 먼저 둡니다.',
        'scope': 'classroom',
        'related_service_keys': ('noticegen',),
        'related_signal_types': ('calendar_day',),
        'trigger_keywords': ('알림장', '가정통신문', '준비물'),
        'required_context': ('시간 변경', '준비물', '회신 여부'),
        'decision_hints': ('시간 변경과 준비물을 첫 줄에 둡니다.', '생활지도 문구는 마지막에 짧게 둡니다.'),
        'examples': ('준비물 안내가 있는 알림장 정리',),
    },
    {
        'rule_key': 'classroom_broadcast_tone',
        'label': '교실 방송 말투',
        'summary': '짧고 또렷한 문장으로 끊어 읽습니다.',
        'scope': 'classroom',
        'related_service_keys': ('tts_announce', 'quickdrop'),
        'related_signal_types': ('calendar_day',),
        'trigger_keywords': ('방송', '읽어주기', '안내'),
        'required_context': ('대상 학년', '방송 길이'),
        'decision_hints': ('한 문장을 짧게 끊어 읽습니다.', '행동 지시는 마지막에 둡니다.'),
        'examples': ('쉬는 시간 종료 방송',),
    },
)

HOME_V7_AGENT_WORKFLOWS = (
    {
        'workflow_key': 'field_trip_preparation',
        'label': '현장학습 준비',
        'summary': '일정, 승인, 안내문을 한 번에 맞춥니다.',
        'primary_service_key': 'classcalendar',
        'related_service_keys': ('noticegen', 'reservations'),
        'trigger_signals': ('calendar_day',),
        'required_context_questions': ('언제 출발하나요?', '차량과 인솔 인원은 몇 명인가요?'),
        'read_steps': ('오늘 일정 확인', '현장학습 메모 확인'),
        'suggest_steps': ('준비물과 시간 안내 정리', '차량 비율 점검'),
        'confirmable_write_steps': ('알림장 초안 열기', '예약 요청 값 정리'),
        'emit_signals': ('calendar_day',),
        'tacit_rule_keys': ('field_trip_bus_ratio', 'attendance_proof_required'),
    },
    {
        'workflow_key': 'daily_notice_flow',
        'label': '일일 알림장',
        'summary': '오늘 일정에서 바로 안내문 초안을 만듭니다.',
        'primary_service_key': 'noticegen',
        'related_service_keys': ('classcalendar', 'quickdrop'),
        'trigger_signals': ('calendar_day',),
        'required_context_questions': ('오늘 꼭 안내할 일정이 있나요?',),
        'read_steps': ('오늘 일정 확인',),
        'suggest_steps': ('핵심 문장 2~3개로 정리'),
        'confirmable_write_steps': ('알림장 열기',),
        'emit_signals': ('calendar_day',),
        'tacit_rule_keys': ('notice_priority_order',),
    },
    {
        'workflow_key': 'reservation_request_flow',
        'label': '예약 요청',
        'summary': '날짜, 시간, 장소를 먼저 맞춥니다.',
        'primary_service_key': 'reservations',
        'related_service_keys': ('classcalendar',),
        'trigger_signals': ('calendar_day',),
        'required_context_questions': ('언제 사용하나요?', '어느 특별실이 필요한가요?'),
        'read_steps': ('사용 날짜 확인',),
        'suggest_steps': ('교시 또는 시간을 정리', '장소를 확정'),
        'confirmable_write_steps': ('예약 화면 열기',),
        'emit_signals': ('calendar_day',),
        'tacit_rule_keys': ('school_approval_chain',),
    },
    {
        'workflow_key': 'collect_signature_cycle',
        'label': '서명 수합',
        'summary': '안내문과 회수 순서를 먼저 맞춥니다.',
        'primary_service_key': 'noticegen',
        'related_service_keys': ('quickdrop',),
        'trigger_signals': ('calendar_day',),
        'required_context_questions': ('회수 마감일은 언제인가요?',),
        'read_steps': ('안내문 핵심 정리',),
        'suggest_steps': ('회수 문구를 분리',),
        'confirmable_write_steps': ('알림장 초안 열기',),
        'emit_signals': ('calendar_day',),
        'tacit_rule_keys': ('attendance_proof_required',),
    },
    {
        'workflow_key': 'student_activity_launch',
        'label': '학생 활동 시작',
        'summary': '교실 방송과 바로전송 문구를 함께 준비합니다.',
        'primary_service_key': 'tts_announce',
        'related_service_keys': ('quickdrop', 'classcalendar'),
        'trigger_signals': ('calendar_day',),
        'required_context_questions': ('학생에게 바로 전달할 문구가 있나요?',),
        'read_steps': ('오늘 활동 시간 확인',),
        'suggest_steps': ('방송 문구를 짧게 정리',),
        'confirmable_write_steps': ('읽어주기 실행', '바로전송 실행'),
        'emit_signals': ('calendar_day',),
        'tacit_rule_keys': ('classroom_broadcast_tone',),
    },
)


def _get_request_client_ip(request):
    forwarded_for = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip()


def _get_admin_dashboard_page_name(path, route_name, product_by_route):
    route_name = str(route_name or '').strip()
    if path == '/':
        return '홈'

    product = product_by_route.get(route_name)
    if product is not None:
        return _get_public_product_name(product)

    friendly_name = ADMIN_PAGE_NAME_BY_ROUTE.get(route_name)
    if friendly_name:
        return friendly_name

    if route_name:
        return route_name
    return path


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


def _is_truthy(raw_value):
    return str(raw_value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _get_compact_posts(request):
    raw_value = request.GET.get('compact_posts') or request.POST.get('compact_posts')
    if raw_value is None:
        return False
    return _is_truthy(raw_value)


def _get_post_surface_variant(request):
    raw_value = request.GET.get('surface_variant') or request.POST.get('surface_variant')
    if raw_value is None:
        return POST_SURFACE_VARIANT_DEFAULT

    surface_variant = str(raw_value).strip().lower()
    if surface_variant in POST_SURFACE_VARIANT_ALLOWED:
        return surface_variant
    return POST_SURFACE_VARIANT_DEFAULT


def _render_post_list_partial(request, page_obj, feed_scope, *, pinned_notice_posts=None):
    empty_title = None
    empty_subtitle = None
    if feed_scope == POST_FEED_SCOPE_NOTICE:
        empty_title = "등록된 공지사항이 없습니다."
        empty_subtitle = "새 공지가 올라오면 여기서 바로 확인할 수 있어요."
    if pinned_notice_posts is None:
        pinned_notice_posts = _build_pinned_notice_queryset(feed_scope=feed_scope)
    _attach_teacher_buddy_avatar_context_safe(
        getattr(page_obj, "object_list", []),
        user=request.user,
        label='post list partial page posts',
    )
    _attach_teacher_buddy_avatar_context_safe(
        pinned_notice_posts,
        user=request.user,
        label='post list partial pinned notices',
    )

    return render(
        request,
        'core/partials/post_feed_container.html',
        {
            'posts': page_obj,
            'page_obj': page_obj,
            'pinned_notice_posts': pinned_notice_posts,
            'post_list_target_id': _get_post_list_target_id(request),
            'feed_scope': feed_scope,
            'compact_posts': _get_compact_posts(request),
            'surface_variant': _get_post_surface_variant(request),
            'empty_title': empty_title,
            'empty_subtitle': empty_subtitle,
            'teacher_buddy_current_avatar': _build_teacher_buddy_avatar_context_safe(
                request.user,
                source='post list partial',
            ),
            'sns_compose_prefill': str(request.GET.get('compose') or '').strip(),
        },
    )


def _build_post_feed_base_queryset():
    now = timezone.now()
    active_feature_window = (
        Q(featured_from__isnull=False, featured_from__lte=now)
        & (Q(featured_until__isnull=True) | Q(featured_until__gte=now))
    )

    return (
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


def _build_pinned_notice_queryset(feed_scope=POST_FEED_SCOPE_ALL):
    if feed_scope not in {POST_FEED_SCOPE_ALL, POST_FEED_SCOPE_NOTICE}:
        return Post.objects.none()

    return (
        _build_post_feed_base_queryset()
        .filter(post_type='notice', is_notice_pinned=True)
        .order_by('-updated_at', '-created_at')
    )


def _build_post_feed_queryset(feed_scope=POST_FEED_SCOPE_ALL):
    queryset = _build_post_feed_base_queryset().exclude(post_type='notice', is_notice_pinned=True)

    if feed_scope == POST_FEED_SCOPE_NOTICE:
        queryset = queryset.filter(post_type__in=POST_FEED_NOTICE_TYPES)

    return queryset.order_by('-active_feature_order', '-active_feature_from', '-created_at')


def _get_home_layout_version():
    raw_version = str(getattr(settings, 'HOME_LAYOUT_VERSION', '') or '').strip().lower()
    if raw_version in {'v1', 'v2', 'v4', 'v5', 'v6'}:
        return raw_version

    fallback_version = 'v6'
    if raw_version:
        logger.warning(
            "[HomeLayout] Invalid HOME_LAYOUT_VERSION=%r; falling back to %s",
            raw_version,
            fallback_version,
        )
    else:
        logger.warning(
            "[HomeLayout] HOME_LAYOUT_VERSION is unset; falling back to %s",
            fallback_version,
        )
    return fallback_version


def _get_teacher_buddy_home_context(user):
    panel = build_teacher_buddy_panel_context(user)
    if not panel:
        return {
            'teacher_buddy_panel': None,
            'teacher_buddy_urls': {},
            'teacher_buddy_current_avatar': _build_teacher_buddy_avatar_context_safe(
                user,
                source='teacher buddy home empty panel',
            ),
        }
    return {
        'teacher_buddy_panel': panel,
        'teacher_buddy_urls': build_teacher_buddy_urls(),
        'teacher_buddy_current_avatar': _build_teacher_buddy_avatar_context_safe(
            user,
            source='teacher buddy home panel',
        ),
    }


def _build_home_surface_developer_chat_card_fallback(user):
    return {
        'enabled': bool(getattr(user, 'is_authenticated', False)),
        'title': '개발자야 도와줘',
        'summary': '',
        'cta_label': '메시지 열기',
        'url': reverse('messagebox:developer_chat'),
        'preview_threads': [],
        'is_admin': False,
        'unread_count': 0,
        'unread_thread_count': 0,
    }


def _build_home_surface_teacher_buddy_provider(user):
    try:
        return _get_teacher_buddy_home_context(user)
    except Exception:
        logger.exception(
            '[home surface] teacher buddy provider failed user_id=%s',
            getattr(user, 'id', None),
        )
        return {
            'teacher_buddy_panel': None,
            'teacher_buddy_urls': {},
            'teacher_buddy_current_avatar': _build_teacher_buddy_avatar_context_safe(
                user,
                source='teacher buddy provider fallback',
            ),
        }


def _build_home_surface_developer_chat_provider(user):
    try:
        return build_developer_chat_home_card_context(user)
    except Exception:
        logger.exception(
            '[home surface] developer chat provider failed user_id=%s',
            getattr(user, 'id', None),
        )
        return _build_home_surface_developer_chat_card_fallback(user)


def _build_teacher_buddy_avatar_context_safe(user, *, source):
    if not getattr(user, 'is_authenticated', False):
        return None
    try:
        return build_teacher_buddy_avatar_context(user)
    except Exception:
        logger.exception(
            '[home surface] teacher buddy avatar context failed source=%s user_id=%s',
            source,
            getattr(user, 'id', None),
        )
        return None


def _build_teacher_buddy_settings_context_safe(user, *, source):
    if not getattr(user, 'is_authenticated', False):
        return None
    try:
        return build_teacher_buddy_settings_context(user)
    except Exception:
        logger.exception(
            '[teacher buddy] settings context failed source=%s user_id=%s',
            source,
            getattr(user, 'id', None),
        )
        return None


def _attach_teacher_buddy_avatar_context_safe(items, *, user, label):
    try:
        attach_teacher_buddy_avatar_context(items)
    except Exception:
        logger.exception(
            '[home surface] teacher buddy avatar attach failed label=%s user_id=%s',
            label,
            getattr(user, 'id', None),
        )


def _get_sns_compose_prefill(request):
    return str(request.GET.get('compose') or '').strip()


def _post_create_error_response(request, message, *, status=400):
    if request.headers.get('HX-Request'):
        return HttpResponse(
            f'<div class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-600">{message}</div>',
            status=status,
        )
    messages.error(request, message)
    return redirect('home')


def _request_prefers_json(request):
    accept = str(request.headers.get('Accept', '') or '').lower()
    requested_with = str(request.headers.get('X-Requested-With', '') or '').lower()
    return requested_with == 'xmlhttprequest' or 'application/json' in accept


def _request_payload_data(request):
    if request.POST:
        return request.POST
    try:
        return json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}


def _teacher_buddy_redirect_response(request):
    return redirect(f"{reverse('home')}#teacher-buddy-panel")


def _teacher_buddy_settings_redirect_response():
    return redirect(f"{reverse('settings')}#teacher-buddy-settings")


def _build_teacher_buddy_admin_shortcuts(user):
    shortcuts = []
    if not getattr(user, "is_authenticated", False):
        return shortcuts

    if user.has_perm("core.add_teacherbuddygiftcoupon"):
        try:
            shortcuts.append(
                {
                    "label": "쿠폰 만들기",
                    "href": reverse("admin:core_teacherbuddygiftcoupon_add"),
                    "is_primary": True,
                }
            )
        except NoReverseMatch:
            pass

    try:
        from handoff.views import HANDOFF_PROXY_MANAGER_USERNAMES
    except Exception:
        HANDOFF_PROXY_MANAGER_USERNAMES = set()

    if getattr(user, "is_superuser", False) and getattr(user, "username", "") in HANDOFF_PROXY_MANAGER_USERNAMES:
        try:
            shortcuts.append(
                {
                    "label": "인원 찾는 대시보드",
                    "href": reverse("handoff:dashboard"),
                    "is_primary": False,
                }
            )
        except NoReverseMatch:
            pass

    return shortcuts


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


def _build_home_section_surface_meta(*, section_key="", icon="", route_name=""):
    return {
        "home_icon_class": service_launcher_utils.resolve_home_icon_class(
            icon=icon,
            route_name=route_name,
        ),
        "home_accent_token": service_launcher_utils.resolve_home_accent_token(
            section_key=section_key,
            route_name=route_name,
        ),
    }


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
        **_build_home_section_surface_meta(
            section_key=section.get("key", ""),
            icon=section.get("icon", ""),
        ),
        "products": preview_items,
        "overflow_products": overflow_items,
        "total_count": len(items),
        "remaining_count": remaining_count,
        "has_more": remaining_count > 0,
    }


def _build_home_display_groups(sections, aux_sections):
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
    "docsign:list": ["내 문서 사인", "PDF 업로드", "교사 1인", "3분 안팎"],
    "signatures:landing": ["서명 받아야 할 때", "휴대폰 응답", "학급 전체", "10분 안팎"],
    "handoff:landing": ["배부 뒤 확인", "휴대폰 응답", "학급 전체", "10분 안팎"],
    "reservations:dashboard_landing": ["일정 잡을 때", "PC·모바일", "개별·소그룹", "5분 안팎"],
    "reservations:landing": ["일정 잡을 때", "PC·모바일", "개별·소그룹", "5분 안팎"],
    "hwpxchat:main": ["공문 정리", "PC 권장", "교사 1인", "10분 안팎"],
    "tts_announce": ["학급 방송", "PC·모바일", "학급 전체", "1분 안팎"],
    "chess:index": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "chess:play": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "janggi:index": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "janggi:play": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "fairy_games:play_dobutsu": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "fairy_games:play_cfour": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "fairy_games:play_isolation": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "fairy_games:play_ataxx": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "fairy_games:play_breakthrough": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "fairy_games:play_reversi": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "reflex_game:main": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
    "yut_game": ["수업 중 활동", "모둠·전체", "교실 화면", "5분 안팎"],
}

PUBLIC_EXPERIENCE_ROUTE_NAMES = {
    "chess:play",
    "janggi:play",
    "reflex_game:main",
    "yut_game",
} | CLASS_ACTIVITY_ROUTE_NAMES

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
} | CLASS_ACTIVITY_ROUTE_NAMES

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
        "preferred_routes": ["collect:landing", "consent:landing", "docsign:list", "signatures:landing", "handoff:landing"],
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
        "is_guest_allowed": True,
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
        "preferred_routes": ["collect:landing", "consent:landing", "docsign:list", "signatures:landing"],
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


def _canonical_home_service_key(product):
    route_name = _product_route_name(product)
    title = _product_title_text(product)
    if route_name == "schoolcomm:main" or title in {"학교 커뮤니티", "우리끼리 채팅방", "끼리끼리 채팅방"}:
        return "schoolcomm"
    if route_name == "quickdrop:landing" or title == "바로전송":
        return "quickdrop"
    return ""


def _is_calendar_hub_product(product):
    return _product_route_name(product) == "classcalendar:main"


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
        is_guest_allowed = bool(getattr(product, "is_guest_allowed", False) or is_guest_allowed)

    supports_guest_preview = service_launcher_utils.product_supports_guest_preview(
        product,
        route_name=route_name,
        is_guest_allowed=is_guest_allowed,
    )
    can_preview_without_login = (
        supports_guest_preview
        or service_type == "game"
        or route_name in PUBLIC_EXPERIENCE_ROUTE_NAMES
    )
    if can_preview_without_login:
        access_status_label = "외부 이동" if launch_is_external else "미리보기 가능"
    else:
        access_status_label = "로그인 필요"

    state_badges = []
    if service_type == "game" or route_name in STUDENT_PARTICIPATION_ROUTE_NAMES:
        state_badges.append("학생 참여")
    if route_name in FILE_REQUIRED_ROUTE_NAMES:
        state_badges.append("파일 필요")
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
    route_name = _product_route_name(product)

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
    if route_name == "hwpxchat:main":
        task_label = "공문에서 해야 할 일을 바로 정리해요"
        support_label = "공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요."

    if not support_label:
        if _is_calendar_hub_product(product):
            support_label = '오늘 일정에서 안내장, 수합, 예약까지 바로 이어갑니다.'

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


def _build_guest_entry_copy_meta(product):
    route_name = _product_route_name(product)
    access_status_label = getattr(product, "home_access_status_label", "") or ""

    if route_name == "collect:landing" and access_status_label != "로그인 필요":
        return {
            "home_guest_status_label": "비로그인 참여",
            "home_guest_summary": "입장코드나 QR이 있으면 바로 제출에 참여합니다.",
            "home_guest_cta_label": "참여 열기",
            "detail_access_copy": "입장코드나 QR로 제출 참여는 로그인 없이 열리고, 새 요청 만들기는 로그인 후 이어집니다.",
            "detail_start_label": "참여 열기",
        }

    return {}


def _is_home_utility_product(product):
    return _canonical_home_service_key(product) in HOME_UTILITY_SERVICE_KEYS


def _filter_home_mobile_workbench_items(favorite_items, *, limit=4):
    filtered_items = [
        item for item in favorite_items
        if not _is_home_utility_product(item.get('product'))
    ]
    return filtered_items[:limit]


def _build_home_quickdrop_card(user, favorite_products, product_list):
    quickdrop_product = next(
        (product for product in product_list if _product_route_name(product) == "quickdrop:landing"),
        None,
    )
    if quickdrop_product is None:
        try:
            from quickdrop.services import ensure_service_product, get_service

            quickdrop_product = get_service()
            if quickdrop_product is None:
                quickdrop_product = ensure_service_product()
        except Exception:
            logger.exception("[home quickdrop] failed to ensure quickdrop product")
            return None
    if quickdrop_product is None or not getattr(quickdrop_product, "is_active", False):
        return None

    summary = ""
    has_recent_item = False
    channel = None
    history_url = reverse("quickdrop:open")
    try:
        from quickdrop.services import get_or_create_personal_channel

        channel = get_or_create_personal_channel(user)
        day_start = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        today_items = channel.items.filter(created_at__gte=day_start).order_by("-created_at", "-id")
        latest_item = today_items.first()
        if latest_item is not None:
            has_recent_item = True
            if getattr(latest_item, "kind", "") == "image":
                filename = str(getattr(latest_item, "filename", "") or "").strip()
                summary = filename[:50] if filename else "최근 사진 1장이 도착해 있습니다."
            else:
                latest_text = " ".join(str(getattr(latest_item, "text", "") or "").split())
                if latest_text:
                    summary = latest_text[:72] + ("..." if len(latest_text) > 72 else "")
        history_url = f'{reverse("quickdrop:channel", kwargs={"slug": channel.slug})}?focus=history#history-panel'
    except Exception:
        logger.exception("[home quickdrop] failed to build quickdrop card context")

    return {
        "title": getattr(quickdrop_product, "public_service_name", "") or getattr(quickdrop_product, "title", "") or "바로전송",
        "summary": summary,
        "has_recent_item": has_recent_item,
        "open_url": reverse("quickdrop:open"),
        "manage_url": reverse("quickdrop:landing"),
        "history_url": history_url,
        "send_text_url": reverse("quickdrop:send_text", kwargs={"slug": channel.slug}) if channel is not None else "",
        "send_file_url": reverse("quickdrop:send_file", kwargs={"slug": channel.slug}) if channel is not None else "",
        "shortcut_url": reverse("quickdrop:landing"),
        "shortcut_aria_label": "새 기기 추가",
        "shortcut_label": "새 기기 추가",
        "shortcut_symbol": "+",
        "secondary_url": reverse("quickdrop:landing"),
        "secondary_label": "새 기기 추가",
        "secondary_label_v6": "오늘 보낸 내용",
        "compose_placeholder": "예) 회의 링크, 메모, 주소",
        "file_accept": "image/*,.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.hwp,.hwpx,.zip",
        "textarea_aria_label": "보낼 내용",
        "submit_label": "지금 보내기",
        "success_message": "바로전송으로 보냈어요.",
        "error_action_name": "바로전송",
        "icon_text": "↔",
        "composer_enabled": True,
        "primary_label": "바로 열기",
    }


def _build_home_v7_agent_conversations(request):
    empty_payload = {
        'title': '끼리끼리 채팅방',
        'workspace_name': '',
        'open_url': _safe_reverse('schoolcomm:main') or '',
        'refresh_url': _safe_reverse('home_agent_conversations') or '',
        'user_ws_url': '/schoolcomm/ws/users/me/',
        'items': (),
    }
    if request is None or not getattr(getattr(request, 'user', None), 'is_authenticated', False):
        return empty_payload

    try:
        from schoolcomm.services import (
            build_home_card,
            build_workspace_dashboard,
            get_default_workspace_for_user,
        )
    except Exception:
        logger.exception('[home agent] failed to import schoolcomm services')
        return empty_payload

    try:
        home_card = build_home_card(request.user) or {}
        workspace = get_default_workspace_for_user(request.user, create=False)
        open_url = str(home_card.get('open_url') or home_card.get('manage_url') or _safe_reverse('schoolcomm:main') or '').strip()
        if workspace is None:
            return {
                'title': str(home_card.get('title') or '끼리끼리 채팅방').strip() or '끼리끼리 채팅방',
                'workspace_name': '',
                'open_url': open_url,
                'refresh_url': _safe_reverse('home_agent_conversations') or '',
                'user_ws_url': '/schoolcomm/ws/users/me/',
                'items': (),
            }

        dashboard = build_workspace_dashboard(workspace, request.user)
        candidate_rooms = []
        for room in [dashboard.get('notice_room'), dashboard.get('shared_room')]:
            if room:
                candidate_rooms.append(room)
        candidate_rooms.extend(list(dashboard.get('dm_rooms') or [])[:8])

        room_kind_label = {
            'notice': '공지',
            'shared': '자료',
            'dm': '대화',
            'group_dm': '그룹',
        }
        items = []
        for room in candidate_rooms:
            room_kind = str(room.get('room_kind') or '').strip().lower()
            room_id = str(room.get('id') or '').strip()
            name = str(room.get('name') or '').strip()
            summary = str(room.get('summary') or '').strip()
            unread_count = int(room.get('unread_count') or 0)
            if not name or not room_id:
                continue
            avatar_label = ''.join(part[:1] for part in name.split()[:2]).strip() or name[:2]
            items.append({
                'kind': 'room',
                'key': f"room:{room_id}",
                'entity_key': room_id,
                'renderer_key': 'human-chat',
                'title': name,
                'summary': summary,
                'meta': room_kind_label.get(room_kind, '대화'),
                'status': room_kind_label.get(room_kind, '대화'),
                'avatar_label': avatar_label[:2],
                'open_url': str(room.get('url') or open_url).strip(),
                'snapshot_url': reverse('schoolcomm:api_room_snapshot', kwargs={'room_id': room_id}),
                'send_url': reverse('schoolcomm:api_room_messages', kwargs={'room_id': room_id}),
                'unread_count': unread_count,
                'badge': str(unread_count) if unread_count else '',
            })

        return {
            'title': str(home_card.get('title') or '끼리끼리 채팅방').strip() or '끼리끼리 채팅방',
            'workspace_name': str(home_card.get('workspace_name') or workspace.name or '').strip(),
            'open_url': open_url,
            'refresh_url': _safe_reverse('home_agent_conversations') or '',
            'user_ws_url': '/schoolcomm/ws/users/me/',
            'renderer_key': 'human-chat',
            'items': tuple(items),
        }
    except Exception:
        logger.exception('[home agent] failed to build schoolcomm conversations')
        return empty_payload


def _build_home_v7_agent_signal_layer(calendar_summary):
    calendar_summary = dict(calendar_summary or {})
    today_workspace = dict(calendar_summary.get('today_workspace') or {})
    date_key = str(today_workspace.get('date_key') or timezone.localdate().isoformat())
    date_label = str(today_workspace.get('date_label') or '오늘')
    signals = [{
        'signal_key': f'calendar-day:{date_key}',
        'service_key': 'classcalendar',
        'signal_type': 'calendar_day',
        'title': date_label,
        'entity_key': 'calendar_day',
        'surface_role': 'time',
        'date': date_key,
        'status': f"일정 {today_workspace.get('today_event_count', 0)}건",
        'chip_label': '오늘',
        'payload_summary': f"할 일 {today_workspace.get('today_task_count', 0)}건",
    }]
    return {
        'signals': signals,
        'signal_keys': tuple(signal['signal_key'] for signal in signals),
        'service_keys': ('classcalendar',),
        'signal_types': ('calendar_day',),
        'entity_keys': ('calendar_day',),
        'by_service_key': {'classcalendar': signals},
        'by_signal_type': {'calendar_day': signals},
        'by_entity_key': {'calendar_day': signals},
        'by_surface_role': {'time': signals},
    }


def _build_home_v7_agent_tacit_registry():
    rules = [dict(rule) for rule in HOME_V7_AGENT_TACIT_RULES]
    by_rule_key = {}
    by_service_key = {}
    by_signal_type = {}
    for rule in rules:
        rule_key = str(rule.get('rule_key') or '').strip()
        if rule_key:
            by_rule_key[rule_key] = rule
        for service_key in rule.get('related_service_keys', ()):
            normalized = str(service_key or '').strip()
            if normalized:
                by_service_key.setdefault(normalized, []).append(rule)
        for signal_type in rule.get('related_signal_types', ()):
            normalized = str(signal_type or '').strip()
            if normalized:
                by_signal_type.setdefault(normalized, []).append(rule)
    return {
        'rules': rules,
        'by_rule_key': by_rule_key,
        'by_service_key': by_service_key,
        'by_signal_type': by_signal_type,
    }


def _build_home_v7_agent_workflow_registry():
    definitions = [dict(workflow) for workflow in HOME_V7_AGENT_WORKFLOWS]
    by_workflow_key = {}
    by_service_key = {}
    by_signal_type = {}
    by_tacit_rule = {}
    for workflow in definitions:
        workflow_key = str(workflow.get('workflow_key') or '').strip()
        if workflow_key:
            by_workflow_key[workflow_key] = workflow
        service_keys = [workflow.get('primary_service_key')] + list(workflow.get('related_service_keys', ()))
        for service_key in service_keys:
            normalized = str(service_key or '').strip()
            if normalized:
                by_service_key.setdefault(normalized, []).append(workflow)
        for signal_type in workflow.get('trigger_signals', ()):
            normalized = str(signal_type or '').strip()
            if normalized:
                by_signal_type.setdefault(normalized, []).append(workflow)
        for rule_key in workflow.get('tacit_rule_keys', ()):
            normalized = str(rule_key or '').strip()
            if normalized:
                by_tacit_rule.setdefault(normalized, []).append(workflow)
    return {
        'definitions': definitions,
        'by_workflow_key': by_workflow_key,
        'by_service_key': by_service_key,
        'by_signal_type': by_signal_type,
        'by_tacit_rule': by_tacit_rule,
    }


def _build_home_v7_router_tool(
    request,
    product_list,
    *,
    title,
    preferred_routes,
    fallback_route='',
    meta='바로 열기',
):
    route_names = []
    for route_name in [*(preferred_routes or ()), fallback_route]:
        normalized = str(route_name or '').strip().lower()
        if normalized and normalized not in route_names:
            route_names.append(normalized)
    product_by_route = {
        _product_route_name(product): product
        for product in product_list
        if _product_route_name(product)
    }
    product = next(
        (product_by_route.get(route_name) for route_name in route_names if product_by_route.get(route_name) is not None),
        None,
    )
    link_item = None
    if product is not None:
        link_items = _build_product_link_items([product], include_section_meta=True, user=request.user)
        link_item = link_items[0] if link_items else None
    href = ''
    is_external = False
    if link_item is not None:
        href = link_item.get('href', '')
        is_external = bool(link_item.get('is_external'))
    elif fallback_route:
        href = _safe_reverse(fallback_route) or ''
    return {
        'title': title,
        'product_id': getattr(product, 'id', None),
        'href': href,
        'is_external': is_external,
        'meta': meta,
    }


def _build_home_v7_context_router_preview(
    request,
    calendar_summary,
    *,
    product_list,
    signal_layer=None,
    tacit_registry=None,
    workflow_registry=None,
):
    tool_map = {
        'schedule': _build_home_v7_router_tool(
            request,
            product_list,
            title='일정',
            preferred_routes=('classcalendar:main',),
            fallback_route='classcalendar:main',
            meta='캘린더 열기',
        ),
        'notice': _build_home_v7_router_tool(
            request,
            product_list,
            title='알림장',
            preferred_routes=('noticegen:main',),
            fallback_route='noticegen:main',
            meta='초안 만들기',
        ),
        'teacher-law': _build_home_v7_router_tool(
            request,
            product_list,
            title='교사 법률',
            preferred_routes=('teacher_law:main',),
            fallback_route='teacher_law:main',
            meta='상황 질문하기',
        ),
        'reservation': _build_home_v7_router_tool(
            request,
            product_list,
            title='특별실 예약',
            preferred_routes=('reservations:dashboard_landing', 'reservations:landing'),
            fallback_route='reservations:dashboard_landing',
            meta='예약 요청 만들기',
        ),
        'pdf': _build_home_v7_router_tool(
            request,
            product_list,
            title='PDF',
            preferred_routes=('hwpxchat:main',),
            fallback_route='hwpxchat:main',
            meta='문서 요약',
        ),
        'tts': _build_home_v7_router_tool(
            request,
            product_list,
            title='TTS',
            preferred_routes=('tts_announce',),
            fallback_route='tts_announce',
            meta='방송 문구',
        ),
        'quickdrop': _build_home_v7_router_tool(
            request,
            product_list,
            title='바로전송',
            preferred_routes=('quickdrop:landing',),
            fallback_route='quickdrop:landing',
            meta='텍스트 보내기',
        ),
        'messagebox': _build_home_v7_router_tool(
            request,
            product_list,
            title='메시지 저장',
            preferred_routes=('messagebox:main',),
            fallback_route='messagebox:main',
            meta='보관함 열기',
        ),
    }
    quickdrop_card = _build_home_quickdrop_card(request.user, [], product_list) or {}
    tacit_registry = tacit_registry or _build_home_v7_agent_tacit_registry()
    workflow_registry = workflow_registry or _build_home_v7_agent_workflow_registry()
    calendar_summary = dict(calendar_summary or {})
    today_workspace = dict(calendar_summary.get('today_workspace') or {})
    route_map = {
        'messagebox:main': reverse('messagebox:main'),
        'classcalendar:api_message_capture_save': reverse('classcalendar:api_message_capture_save'),
    }
    message_capture_links = {
        'parse_saved_template': reverse(
            'classcalendar:api_message_capture_parse_saved',
            kwargs={'capture_id': MESSAGE_CAPTURE_REVERSE_SEED},
        ).replace(MESSAGE_CAPTURE_REVERSE_SEED, MESSAGE_CAPTURE_PLACEHOLDER),
        'commit_template': reverse(
            'classcalendar:api_message_capture_commit',
            kwargs={'capture_id': MESSAGE_CAPTURE_REVERSE_SEED},
        ).replace(MESSAGE_CAPTURE_REVERSE_SEED, MESSAGE_CAPTURE_PLACEHOLDER),
    }
    link_sources = {
        'tool': tool_map,
        'route': route_map,
        'quickdrop_card': quickdrop_card,
        'message_capture': message_capture_links,
    }

    modes = []
    for definition in get_home_agent_service_definitions():
        service_key = str(definition.service_key or '').strip()
        mode_workflows = workflow_registry.get('by_service_key', {}).get(service_key, [])
        mode_rules = tacit_registry.get('by_service_key', {}).get(service_key, [])
        workflow_keys = tuple(
            workflow.get('workflow_key')
            for workflow in mode_workflows
            if workflow.get('workflow_key')
        )
        tacit_rule_keys = tuple(
            rule.get('rule_key')
            for rule in mode_rules
            if rule.get('rule_key')
        )
        links = resolve_home_agent_mode_links(definition, sources=link_sources)
        starter_items = resolve_home_agent_starter_items(definition, request=request)
        ui_options = resolve_home_agent_ui_options(definition, request=request)
        tool = tool_map.get(definition.tool_key) or {}
        modes.append(
            build_home_agent_mode_payload(
                definition,
                product_id=tool.get('product_id'),
                links=links,
                starter_items=starter_items,
                ui_options=ui_options,
                workflow_keys=workflow_keys,
                tacit_rule_keys=tacit_rule_keys,
            )
        )

    context_questions = []
    seen_questions = set()
    for workflow in workflow_registry.get('definitions', []):
        for question in workflow.get('required_context_questions', ()):
            normalized = str(question or '').strip()
            if normalized and normalized not in seen_questions:
                seen_questions.add(normalized)
                context_questions.append(normalized)

    signal_sources = list((signal_layer or {}).get('signal_types', ()))
    signal_sources.extend(
        f"tacit_rule:{rule_key}"
        for rule_key in list(tacit_registry.get('by_rule_key', {}).keys())[:3]
    )
    signal_sources.extend(
        f"workflow:{workflow_key}"
        for workflow_key in list(workflow_registry.get('by_workflow_key', {}).keys())[:3]
    )
    conversations = _build_home_v7_agent_conversations(request)
    service_rail_items = [
        {
            'kind': 'service',
            'key': f"service:{mode['key']}",
            'entity_key': mode['key'],
            'mode_key': mode['key'],
            'renderer_key': mode['renderer_key'],
            'title': mode['label'],
            'summary': mode.get('helper') or mode.get('empty_prompt') or '',
            'meta': 'AI',
            'status': mode.get('helper') or '',
            'icon_class': mode.get('icon_class') or 'fa-regular fa-circle',
            'avatar_label': '',
            'unread_count': 0,
            'badge': '',
            'open_url': mode.get('service_href') or '',
        }
        for mode in modes
    ]
    rail_sections = (
        {
            'key': 'services',
            'label': 'AI 서비스',
            'items': tuple(service_rail_items),
        },
        {
            'key': 'rooms',
            'label': conversations.get('title') or '끼리끼리 채팅방',
            'items': tuple(conversations.get('items') or ()),
        },
    )

    return {
        'workspace_title': 'AI 교무비서',
        'workspace_summary': '',
        'workspace_selector_title': '서비스',
        'workspace_search_placeholder': '서비스와 대화 찾기',
        'initial_mode': 'notice',
        'initial_rail_key': 'service:notice',
        'modes': modes,
        'rail_sections': rail_sections,
        'conversations': conversations,
        'reason': '',
        'signal_sources': tuple(signal_sources) or ('calendar_day',),
        'selected_date_label': today_workspace.get('date_label', ''),
        'agent_runtime': {
            'provider': str(os.environ.get('HOME_AGENT_LLM_PROVIDER') or 'deepseek').strip().lower() or 'deepseek',
            'fallback_provider': str(os.environ.get('HOME_AGENT_LLM_FALLBACK_PROVIDER') or 'openclaw').strip().lower() or 'openclaw',
            'execution_mode': 'service-bridge+llm-fallback',
            'preview_url': reverse('home_agent_preview'),
            'execute_url': reverse('home_agent_execute'),
        },
        'knowledge_summary': {
            'tacit_rule_count': len(tacit_registry.get('rules', [])),
            'workflow_count': len(workflow_registry.get('definitions', [])),
        },
        'tacit_rules': tacit_registry.get('rules', []),
        'workflow_definitions': workflow_registry.get('definitions', []),
        'tacit_rule_keys': tuple(tacit_registry.get('by_rule_key', {}).keys()),
        'workflow_keys': tuple(workflow_registry.get('by_workflow_key', {}).keys()),
        'context_questions': tuple(context_questions[:6]),
    }


def _build_home_schoolcomm_card(user, favorite_products, product_list):
    try:
        from schoolcomm.services import build_home_card

        return build_home_card(user)
    except Exception:
        logger.exception("[home schoolcomm] failed to build schoolcomm card context")
        return None


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
        guide_url_map[manual.product_id] = SERVICE_GUIDE_PADLET_URL
    return guide_url_map


def _attach_product_launch_meta(products, user=None):
    """Attach launch target metadata so templates can navigate directly without modal."""
    guide_url_map = _build_product_guide_url_map(products)
    prepared = []
    for product in products:
        try:
            launch_href, launch_is_external = _resolve_product_launch_url(product, user=user)
            product.launch_href = launch_href
            product.launch_is_external = launch_is_external
            product.guide_url = guide_url_map.get(product.id, "")
            product.sample_url = ""
            for attr_name, attr_value in _build_teacher_first_product_labels(product).items():
                setattr(product, attr_name, attr_value)
            product.home_card_summary = _build_home_card_summary(product)
            guest_entry_meta = _build_guest_entry_copy_meta(product)
            product.home_guest_status_label = (
                guest_entry_meta.get("home_guest_status_label")
                or getattr(product, "home_access_status_label", "")
            )
            product.home_guest_summary = (
                guest_entry_meta.get("home_guest_summary")
                or product.home_card_summary
            )
            product.home_guest_cta_label = guest_entry_meta.get("home_guest_cta_label", "")
            product.product_access_copy_override = guest_entry_meta.get("detail_access_copy", "")
            product.product_start_label_override = guest_entry_meta.get("detail_start_label", "")
            product.home_compact_title = ""
            product.home_icon_class = service_launcher_utils.resolve_home_icon_class(product)
            product.home_accent_token = service_launcher_utils.resolve_home_accent_token(product)
            if _product_route_name(product) == "messagebox:main":
                product.home_compact_title = "메시지 보관"
            prepared.append(product)
        except Exception:
            logger.exception(
                "[home surface] product launch meta failed user_id=%s product_id=%s",
                getattr(user, "id", None),
                getattr(product, "id", None),
            )
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


def _build_product_link_items(products, include_section_meta=False, user=None):
    """템플릿에서 공통으로 쓰는 서비스 링크 아이템 구성."""
    items = []
    for product in products:
        try:
            href, is_external = _resolve_product_launch_url(product, user=user)
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
                'home_icon_class': getattr(product, 'home_icon_class', '') or service_launcher_utils.resolve_home_icon_class(product),
                'home_accent_token': getattr(product, 'home_accent_token', '') or service_launcher_utils.resolve_home_accent_token(product),
            }
            if include_section_meta:
                section_key = _resolve_home_section_key(product)
                section_meta = HOME_SECTION_META_BY_KEY.get(section_key, {})
                item['section_key'] = section_key
                item['section_title'] = section_meta.get('title', '추천 도구')
                item['section_subtitle'] = section_meta.get('subtitle', '')
            items.append(item)
        except Exception:
            logger.exception(
                "[home surface] product link item failed user_id=%s product_id=%s",
                getattr(user, "id", None),
                getattr(product, "id", None),
            )
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


def _get_product_usage_stats(user, products, *, since=None):
    if not getattr(user, 'is_authenticated', False):
        return {}

    product_ids = [getattr(product, 'id', None) for product in products if getattr(product, 'id', None)]
    if not product_ids:
        return {}

    usage_qs = ProductUsageLog.objects.filter(
        user=user,
        product__is_active=True,
        product_id__in=product_ids,
    )
    if since is not None:
        usage_qs = usage_qs.filter(created_at__gte=since)

    usage_rows = usage_qs.values('product_id').annotate(
        count=Count('id'),
        last_used=Max('created_at'),
    )
    return {
        row['product_id']: {
            'count': row['count'],
            'last_used': row['last_used'],
        }
        for row in usage_rows
    }


def _build_home_representative_slots(
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
    candidate_products = []
    for section in [*sections, *aux_sections]:
        candidate_products.extend(section.get('products', []))
        candidate_products.extend(section.get('overflow_products', []))
    candidate_products.extend(games or [])
    candidate_products.extend(favorite_products)
    candidate_products.extend(recent_products)
    candidate_products.extend(quick_actions)
    candidate_products.extend(discovery_products)
    candidate_products = _dedupe_products(
        [
            product
            for product in candidate_products
            if _resolve_home_section_key(product) != 'external'
            and not _is_home_utility_product(product)
        ]
    )
    rotation_seed = timezone.localdate().toordinal() + int(getattr(user, 'id', 0) or 0)
    shuffled_products = list(candidate_products)
    random.Random(rotation_seed).shuffle(shuffled_products)
    return [
        {'product': product, 'slot_kind': 'random'}
        for product in shuffled_products[:limit]
    ]


def _build_home_recommendations(companion_items, discovery_items, *, exclude_ids=None, limit=3):
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


CLASS_OPS_NAV_HIDDEN_ROUTE_NAMES = {
    'qrgen:landing',
    'textbooks:main',
    'tts_announce',
}

CLASS_OPS_NAV_HIDDEN_TITLES = {
    '교과서 라이브 수업',
    '교실 방송 TTS',
    '수업 QR 생성기',
}

CLASS_OPS_NAV_RESERVATION_ROUTE_NAMES = {
    'reservations:dashboard_landing',
    'reservations:landing',
}

CLASS_OPS_NAV_RESERVATION_TITLES = {
    '학교 예약 시스템',
}

CLASS_OPS_NAV_RESERVATION_INDEX = 2


def _is_hidden_class_ops_nav_product(product):
    route_name = _product_route_name(product)
    title = _product_title_text(product)
    return route_name in CLASS_OPS_NAV_HIDDEN_ROUTE_NAMES or title in CLASS_OPS_NAV_HIDDEN_TITLES


def _is_class_ops_reservation_nav_product(product):
    route_name = _product_route_name(product)
    title = _product_title_text(product)
    return (
        route_name in CLASS_OPS_NAV_RESERVATION_ROUTE_NAMES
        or title in CLASS_OPS_NAV_RESERVATION_TITLES
    )


def _reorder_class_ops_nav_products(products):
    visible_products = []
    reservation_products = []

    for product in list(products or []):
        if _is_class_ops_reservation_nav_product(product):
            reservation_products.append(product)
            continue
        visible_products.append(product)

    if not reservation_products:
        return visible_products

    insert_index = min(CLASS_OPS_NAV_RESERVATION_INDEX, len(visible_products))
    return [
        *visible_products[:insert_index],
        *reservation_products,
        *visible_products[insert_index:],
    ]


def _filter_home_nav_products(section_key, products):
    nav_products = list(products or [])
    if section_key != 'class_ops':
        return nav_products

    # The home calendar panel and dedicated utility cards already cover their
    # entry points, so keep the menu focused on the remaining classroom-operation tools.
    filtered_products = [
        product for product in nav_products
        if (
            not _is_calendar_hub_product(product)
            and not _is_home_utility_product(product)
            and not _is_hidden_class_ops_nav_product(product)
        )
    ]
    return _reorder_class_ops_nav_products(filtered_products)


DIRECT_HOME_NAV_ROUTE_META = {
    'schoolprograms:landing': {
        'key': 'schoolprograms',
        'title': '학교 체험·행사 찾기',
        'subtitle': '학교로 찾아오는 체험학습·행사를 바로 찾기',
        'color': 'violet',
    },
}


def _build_home_direct_nav_section(product, *, fallback_color='slate'):
    route_name = str(getattr(product, 'launch_route_name', '') or '').strip().lower()
    meta = DIRECT_HOME_NAV_ROUTE_META.get(route_name, {})
    href = getattr(product, 'launch_href', '') or ''
    if not href:
        return None

    return {
        'key': meta.get('key') or route_name.replace(':', '-'),
        'title': getattr(product, 'public_service_name', '') or getattr(product, 'title', '') or meta.get('title') or '도구',
        'subtitle': getattr(product, 'home_card_summary', '') or getattr(product, 'description', '') or meta.get('subtitle') or '',
        'icon': getattr(product, 'icon', '') or 'fa-solid fa-star',
        'color': meta.get('color') or fallback_color,
        'count': 1,
        'products': [product],
        'is_direct': True,
        'href': href,
        'is_external': bool(getattr(product, 'launch_is_external', False)),
        'product_id': getattr(product, 'id', None),
        'launch_route_name': route_name,
        **_build_home_section_surface_meta(
            section_key=meta.get('key') or route_name.replace(':', '-'),
            icon=getattr(product, 'icon', ''),
            route_name=route_name,
        ),
    }


def _split_home_direct_nav_sections(section_key, products, *, fallback_color='slate'):
    if section_key != 'class_ops':
        return list(products or []), []

    nav_products = []
    direct_sections = []
    for product in list(products or []):
        route_name = str(getattr(product, 'launch_route_name', '') or '').strip().lower()
        if route_name not in DIRECT_HOME_NAV_ROUTE_META:
            nav_products.append(product)
            continue
        direct_section = _build_home_direct_nav_section(product, fallback_color=fallback_color)
        if direct_section is None:
            nav_products.append(product)
            continue
        direct_sections.append(direct_section)
    return nav_products, direct_sections


def _build_home_nav_sections(primary_display_sections, secondary_display_sections, games):
    nav_sections = []

    for section in [*primary_display_sections, *secondary_display_sections]:
        nav_products = _filter_home_nav_products(section['key'], [
            *section.get('products', []),
            *section.get('overflow_products', []),
        ])
        nav_products, direct_sections = _split_home_direct_nav_sections(
            section['key'],
            nav_products,
            fallback_color=section.get('color', 'slate'),
        )
        if not nav_products:
            nav_sections.extend(direct_sections)
            continue
        nav_sections.append({
            'key': section['key'],
            'title': section['title'],
            'subtitle': section['subtitle'],
            'icon': section['icon'],
            'color': section.get('color', 'slate'),
            'count': len(nav_products),
            'products': nav_products,
            'home_icon_class': section.get('home_icon_class')
            or service_launcher_utils.resolve_home_icon_class(icon=section.get('icon', '')),
            'home_accent_token': section.get('home_accent_token')
            or service_launcher_utils.resolve_home_accent_token(section_key=section.get('key', '')),
        })
        nav_sections.extend(direct_sections)

    if games:
        nav_sections.append({
            'key': 'games',
            'title': '게임·활동',
            'subtitle': '쉬는 시간에 바로 여는 활동',
            'icon': 'fa-solid fa-gamepad',
            'color': 'rose',
            'count': len(games),
            'products': games,
            'home_icon_class': 'fa-solid fa-gamepad',
            'home_accent_token': service_launcher_utils.resolve_home_accent_token(section_key='games'),
        })

    return nav_sections


def _ensure_home_direct_nav_sections(nav_sections, product_list):
    grouped_sections = []
    direct_sections_by_key = {}

    for section in list(nav_sections or []):
        if section.get('is_direct'):
            direct_sections_by_key.setdefault(section['key'], section)
            continue
        grouped_sections.append(section)

    for product in list(product_list or []):
        route_name = str(getattr(product, 'launch_route_name', '') or '').strip().lower()
        meta = DIRECT_HOME_NAV_ROUTE_META.get(route_name)
        if not meta:
            continue
        key = meta.get('key') or route_name.replace(':', '-')
        if key in direct_sections_by_key:
            continue
        direct_section = _build_home_direct_nav_section(
            product,
            fallback_color=meta.get('color', 'slate'),
        )
        if direct_section is not None:
            direct_sections_by_key[key] = direct_section

    ordered_direct_sections = []
    for route_name, meta in DIRECT_HOME_NAV_ROUTE_META.items():
        key = meta.get('key') or route_name.replace(':', '-')
        direct_section = direct_sections_by_key.pop(key, None)
        if direct_section is not None:
            ordered_direct_sections.append(direct_section)

    ordered_direct_sections.extend(direct_sections_by_key.values())
    return [*grouped_sections, *ordered_direct_sections]


def _build_home_mobile_quick_items(favorite_products, nav_sections, *, limit=4):
    candidate_products = list(favorite_products or [])

    for section in nav_sections:
        products = list(section.get('products') or [])
        if products:
            candidate_products.append(products[0])

    for section in nav_sections:
        products = list(section.get('products') or [])
        if len(products) > 1:
            candidate_products.extend(products[1:])

    quick_products = _dedupe_products(candidate_products, limit=limit * 2)
    quick_items = []

    for product in quick_products:
        href = getattr(product, 'launch_href', '') or ''
        if not href:
            continue
        raw_title = (
            getattr(product, 'public_service_name', '')
            or getattr(product, 'title', '')
            or '도구'
        )
        quick_items.append({
            'product': product,
            'title': build_favorite_service_title(raw_title) or raw_title,
            'href': href,
            'is_external': bool(getattr(product, 'launch_is_external', False)),
            'icon': getattr(product, 'icon', '') or '',
        })
        if len(quick_items) >= limit:
            break

    return quick_items


# Compatibility-only aliases for remaining v2/v4/v5 imports and fallback paths.
(
    _build_home_v2_display_groups,
    _filter_home_v5_mobile_workbench_items,
    _build_home_v4_representative_slots,
    _build_home_v4_recommendations,
    _filter_home_v4_nav_products,
    _build_home_v4_direct_nav_section,
    _split_home_v4_direct_nav_sections,
    _build_home_v4_nav_sections,
    _ensure_home_v4_direct_nav_sections,
    _build_home_v4_mobile_quick_items,
) = (
    _build_home_display_groups,
    _filter_home_mobile_workbench_items,
    _build_home_representative_slots,
    _build_home_recommendations,
    _filter_home_nav_products,
    _build_home_direct_nav_section,
    _split_home_direct_nav_sections,
    _build_home_nav_sections,
    _ensure_home_direct_nav_sections,
    _build_home_mobile_quick_items,
)


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
        if limit and len(selected) >= limit:
            break

    if limit:
        return selected[:limit]
    return selected



def _get_home_companion_items(seed_products, product_list, *, exclude_ids=None, limit=3, user=None):
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
            href, is_external = _resolve_product_launch_url(product, user=user)
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


def _build_home_community_summary_posts(page_obj, *, pinned_notice_posts=None, limit=2):
    pinned_items = list(pinned_notice_posts or [])
    pinned_ids = {post.id for post in pinned_items}
    object_list = pinned_items + [
        post
        for post in list(getattr(page_obj, "object_list", []) or [])
        if post.id not in pinned_ids
    ]
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


def _build_sns_preview_posts(page_obj, *, pinned_notice_posts=None, limit=3):
    pinned_items = list(pinned_notice_posts or [])
    feed_items = list(getattr(page_obj, "object_list", []) or [])
    merged: list[Post] = []
    seen_ids: set[int] = set()
    for post in [*pinned_items, *feed_items]:
        post_id = getattr(post, "id", None)
        if not post_id or post_id in seen_ids:
            continue
        seen_ids.add(post_id)
        merged.append(post)
        if len(merged) >= limit:
            break
    _attach_teacher_buddy_avatar_context_safe(
        merged,
        user=None,
        label='sns preview posts',
    )
    return merged


def _build_home_reservation_card(user):
    if not getattr(user, "is_authenticated", False):
        return None

    from reservations.utils import list_user_accessible_schools

    items = []
    for entry in list_user_accessible_schools(user):
        school = entry["school"]
        summary = ""
        if entry["role"] in {"edit", "view"} and entry["owner_name"]:
            summary = f'{entry["owner_name"]} 선생님'
        items.append({
            "school_name": school.name,
            "role_label": entry["role_label"],
            "role_tone": entry["role_tone"],
            "summary": summary,
            "href": entry["reservation_url"],
        })

    if not items:
        return None

    return {
        "items": items,
        "count": len(items),
        "dashboard_url": reverse("reservations:dashboard_landing"),
    }


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
                "service_name": spec["service_name"],
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


def _build_home_login_continue_url(next_url, *, login_url=""):
    base_login_url = str(login_url or reverse("account_login") or "").strip()
    if not base_login_url:
        return ""

    candidate = str(next_url or "").strip()
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return base_login_url
    return f"{base_login_url}?{urlencode({'next': candidate})}"


GUEST_NOTICE_TRIAL_LIMIT = 2
GUEST_NOTICE_TRIAL_ACTION_SPECS = (
    {
        "title": "알림장 쓰기",
        "description": "학부모 안내 문장을 바로 만듭니다.",
        "icon_class": "fa-solid fa-note-sticky",
        "topic": "notice",
    },
    {
        "title": "주간학습 쓰기",
        "description": "이번 주 학습 안내 문장을 바로 만듭니다.",
        "icon_class": "fa-solid fa-calendar-week",
        "topic": "activity",
    },
)


def _get_guest_notice_trial_used_count(request):
    if getattr(request.user, "is_authenticated", False):
        return 0

    session = getattr(request, "session", None)
    if session is None:
        return 0

    session_key = str(getattr(session, "session_key", "") or "").strip()
    if not session_key:
        return 0

    from noticegen.models import NoticeGenerationAttempt

    return NoticeGenerationAttempt.objects.filter(
        user__isnull=True,
        session_key=session_key,
        charged=True,
    ).count()


def _build_guest_notice_trial_context(request, *, login_url):
    noticegen_url = reverse("noticegen:main")
    used_count = _get_guest_notice_trial_used_count(request)
    remaining_count = max(GUEST_NOTICE_TRIAL_LIMIT - used_count, 0)
    trial_completed = remaining_count <= 0
    login_continue_url = _build_home_login_continue_url(noticegen_url, login_url=login_url)
    action_cards = []

    for spec in GUEST_NOTICE_TRIAL_ACTION_SPECS:
        base_href = f"{noticegen_url}?{urlencode({'target': 'parent', 'topic': spec['topic']})}"
        action_cards.append(
            {
                "title": spec["title"],
                "description": spec["description"],
                "icon_class": spec["icon_class"],
                "href": (
                    _build_home_login_continue_url(base_href, login_url=login_url)
                    if trial_completed
                    else base_href
                ),
                "badge_label": "로그인 후" if trial_completed else "로그인 없이",
                "cta_label": "로그인하고 쓰기" if trial_completed else spec["title"],
            }
        )

    summary = (
        "알림장과 주간학습 멘트를 로그인 없이 2회까지 바로 써봅니다."
        if not trial_completed
        else "비회원 체험 2회를 모두 사용했습니다. 로그인 후 계속 작성합니다."
    )
    return {
        "guest_notice_trial_actions": action_cards,
        "guest_notice_trial_limit": GUEST_NOTICE_TRIAL_LIMIT,
        "guest_notice_trial_used_count": used_count,
        "guest_notice_trial_remaining_count": remaining_count,
        "guest_notice_trial_completed": trial_completed,
        "guest_notice_trial_status_label": (
            "체험 완료"
            if trial_completed
            else f"남은 체험 {remaining_count} / {GUEST_NOTICE_TRIAL_LIMIT}"
        ),
        "guest_notice_trial_summary": summary,
        "guest_notice_trial_login_url": login_continue_url,
        "guest_notice_trial_login_summary": "체험 2회 이후에는 로그인 후 같은 화면에서 이어서 씁니다.",
    }


GUEST_PUBLIC_SECTION_ORDER = {
    "collect_sign": 0,
    "class_ops": 1,
    "doc_write": 2,
    "refresh": 3,
    "guide": 4,
    "external": 5,
    "class_activity": 6,
}

GUEST_LOCKED_SECTION_ORDER = {
    "class_ops": 0,
    "doc_write": 1,
    "collect_sign": 2,
    "guide": 3,
    "refresh": 4,
    "external": 5,
    "class_activity": 6,
}

PUBLIC_HOME_PRIMARY_ACTION_ROUTE_PRIORITY = (
    "collect:landing",
    "noticegen:main",
    "qrgen:landing",
    "happy_seed:landing",
    "timetable:main",
    "ssambti:main",
)

PUBLIC_HOME_PRIMARY_ACTION_TITLE_PRIORITY = (
    "간편 수합",
    "알림장 & 주간학습 멘트 생성기",
    "수업 QR 생성기",
    "행복의 씨앗",
    "전담 시간표·특별실 배치 도우미",
    "쌤BTI",
)

PUBLIC_HOME_CONTINUE_CATEGORY_LABELS = (
    "수합·서명",
    "문서·작성",
    "학급 운영",
)

PUBLIC_PLATFORM_SHOWCASE_PRIORITY_SPECS = (
    {
        "route_names": ("noticegen:main",),
        "titles": ("알림장 & 주간학습 멘트 생성기",),
    },
    {
        "route_names": ("collect:landing",),
        "titles": ("간편 수합",),
    },
    {
        "route_names": ("docsign:list",),
        "titles": ("인쇄 NONO 온라인 사인",),
    },
    {
        "route_names": ("signatures:list",),
        "titles": ("가뿐하게 서명 톡",),
    },
    {
        "route_names": ("reservations:dashboard_landing", "reservations:landing"),
        "titles": ("학교 예약 시스템",),
    },
    {
        "route_names": ("classcalendar:main",),
        "titles": ("학급 캘린더", "교무수첩"),
    },
    {
        "route_names": ("teacher_law:main",),
        "titles": ("교사용 AI 법률 가이드",),
    },
)

PUBLIC_PLATFORM_GROUP_SPECS = (
    {
        "key": "family_contact",
        "title": "가정 연락",
        "summary": "알림과 안내를 바로 정리합니다.",
        "preferred_routes": ("noticegen:main", "parentcomm:main"),
        "preferred_titles": ("알림장 & 주간학습 멘트 생성기",),
        "fallback_group_keys": ("family_contact",),
    },
    {
        "key": "collect_sign",
        "title": "수합·서명",
        "summary": "응답과 서명을 바로 받습니다.",
        "preferred_routes": ("collect:landing", "consent:landing", "docsign:list", "signatures:list", "handoff:landing"),
        "preferred_titles": ("간편 수합", "동의서는 나에게 맡겨", "인쇄 NONO 온라인 사인", "가뿐하게 서명 톡", "배부 체크"),
        "fallback_group_keys": ("collect_sign",),
    },
    {
        "key": "class_preparation",
        "title": "수업 준비",
        "summary": "수업 도구와 활동을 바로 엽니다.",
        "preferred_routes": ("artclass:setup", "happy_seed:landing", "seed_quiz:landing"),
        "preferred_titles": ("미술 수업 도우미", "몽글몽글 미술 수업", "행복의 씨앗", "씨앗 퀴즈", "씨앗퀴즈"),
        "fallback_group_keys": ("class_preparation",),
    },
    {
        "key": "schedule_reservation",
        "title": "일정·예약",
        "summary": "일정과 예약을 한 번에 봅니다.",
        "preferred_routes": ("classcalendar:main", "reservations:dashboard_landing", "reservations:landing"),
        "preferred_titles": ("학급 캘린더", "학교 예약 시스템", "교무수첩"),
        "fallback_group_keys": ("schedule_reservation",),
    },
    {
        "key": "records",
        "title": "문서·자료 정리",
        "summary": "문서와 자료를 빠르게 정리합니다.",
        "preferred_routes": ("quickdrop:landing", "hwpxchat:main", "infoboard:dashboard"),
        "preferred_titles": ("바로전송", "한글문서 AI야 읽어줘", "인포보드"),
        "fallback_group_keys": ("records", "family_contact"),
    },
    {
        "key": "teacher_support",
        "title": "법률·참고",
        "summary": "법률과 참고 도구를 바로 찾습니다.",
        "preferred_routes": ("teacher_law:main", "schoolprograms:landing"),
        "preferred_titles": ("교사용 AI 법률 가이드", "학교 체험·행사 찾기"),
        "fallback_group_keys": ("teacher_support",),
    },
)

PUBLIC_PLATFORM_GROUP_KEY_BY_ROUTE = {
    "noticegen:main": "family_contact",
    "parentcomm:main": "family_contact",
    "collect:landing": "collect_sign",
    "consent:landing": "collect_sign",
    "consent:dashboard": "collect_sign",
    "docsign:list": "collect_sign",
    "signatures:landing": "collect_sign",
    "signatures:list": "collect_sign",
    "handoff:landing": "collect_sign",
    "artclass:setup": "class_preparation",
    "happy_seed:landing": "class_preparation",
    "seed_quiz:landing": "class_preparation",
    "classcalendar:main": "schedule_reservation",
    "reservations:dashboard_landing": "schedule_reservation",
    "reservations:landing": "schedule_reservation",
    "quickdrop:landing": "records",
    "hwpxchat:main": "records",
    "infoboard:dashboard": "records",
    "teacher_law:main": "teacher_support",
    "schoolprograms:landing": "teacher_support",
}

PUBLIC_PLATFORM_GROUP_KEY_BY_HOME_SECTION = {
    "collect_sign": "collect_sign",
    "class_ops": "schedule_reservation",
    "doc_write": "records",
    "guide": "teacher_support",
    "refresh": "teacher_support",
}

PUBLIC_PLATFORM_GROUP_SORT_ORDER = {
    "family_contact": 0,
    "collect_sign": 1,
    "class_preparation": 2,
    "schedule_reservation": 3,
    "records": 4,
    "teacher_support": 5,
}


def _product_requires_guest_login(product):
    return getattr(product, "home_access_status_label", "") == "로그인 필요"


def _guest_access_status_copy(product):
    return (
        getattr(product, "home_guest_status_label", "")
        or getattr(product, "home_access_status_label", "")
        or "미리보기 가능"
    )


def _build_home_guest_highlight_card(product, *, login_url=""):
    access_status_label = _guest_access_status_copy(product)
    route_name = _product_route_name(product)
    launch_href = getattr(product, "launch_href", "") or ""
    launch_is_external = bool(getattr(product, "launch_is_external", False))
    href = launch_href
    is_external = launch_is_external
    cta_label = "새 창에서 시작" if launch_is_external else "지금 시작"
    if access_status_label == "로그인 필요":
        href = _build_home_login_continue_url(launch_href, login_url=login_url)
        is_external = False
        cta_label = "로그인 후 시작"
    elif not launch_is_external:
        cta_label = getattr(product, "home_guest_cta_label", "") or cta_label
    return {
        "id": getattr(product, "id", ""),
        "title": getattr(product, "public_service_name", "") or getattr(product, "title", "") or "도구",
        "description": getattr(product, "home_guest_summary", "") or getattr(product, "home_card_summary", "") or getattr(product, "teacher_first_support_label", "") or getattr(product, "description", ""),
        "service_name": getattr(product, "teacher_first_task_label", "") or "",
        "icon": getattr(product, "icon", ""),
        "home_icon_class": getattr(product, "home_icon_class", "") or service_launcher_utils.resolve_home_icon_class(product),
        "home_accent_token": getattr(product, "home_accent_token", "") or service_launcher_utils.resolve_home_accent_token(product),
        "service_type": getattr(product, "service_type", ""),
        "route_name": route_name,
        "href": href,
        "is_external": is_external,
        "cta_label": cta_label,
        "guide_url": getattr(product, "guide_url", "") or "",
        "access_status_label": access_status_label,
        "state_badges": list(getattr(product, "home_state_badges", []) or []),
    }


def _build_home_guest_highlight_cards(
    product_list,
    *,
    requires_login,
    limit=4,
    include_games=False,
    login_url="",
):
    section_order = GUEST_LOCKED_SECTION_ORDER if requires_login else GUEST_PUBLIC_SECTION_ORDER
    cards = []
    seen_ids = set()

    def _sort_key(product):
        section_key = _resolve_home_section_key(product)
        is_game = getattr(product, "service_type", "") == "game"
        return (
            section_order.get(section_key, 99),
            1 if is_game else 0,
            getattr(product, "display_order", 9999),
            getattr(product, "title", ""),
        )

    for product in sorted(product_list, key=_sort_key):
        if getattr(product, "id", None) in seen_ids:
            continue
        if _product_requires_guest_login(product) != requires_login:
            continue
        if not include_games and getattr(product, "service_type", "") == "game":
            continue
        card = _build_home_guest_highlight_card(product, login_url=login_url)
        if not card["href"]:
            continue
        cards.append(card)
        seen_ids.add(getattr(product, "id", None))
        if len(cards) >= limit:
            break
    return cards


def _build_home_guest_rotation_cards(product_list, *, login_url=""):
    rotation_limit = max(len(product_list), 1)
    cards = _build_home_guest_highlight_cards(
        product_list,
        requires_login=False,
        limit=rotation_limit,
        include_games=True,
        login_url=login_url,
    )
    return [
        {
            "id": card["id"],
            "title": card["title"],
            "description": card["description"],
            "icon": card["icon"],
            "home_icon_class": card.get("home_icon_class", ""),
            "home_accent_token": card.get("home_accent_token", ""),
            "href": card["href"],
            "is_external": card["is_external"],
            "cta_label": "새 창에서 시작" if card["is_external"] else "지금 시작",
        }
        for card in cards
        if card.get("href")
    ]


def _build_home_public_primary_action_card(guest_public_cards, games):
    candidate_cards = [card for card in list(guest_public_cards or []) if card.get("href")]
    if not candidate_cards:
        for game in list(games or []):
            launch_href = str(getattr(game, "launch_href", "") or "").strip()
            if not launch_href:
                continue
            return {
                "id": getattr(game, "id", ""),
                "title": getattr(game, "public_service_name", "") or getattr(game, "title", "") or "교실 활동",
                "description": getattr(game, "home_card_summary", "") or "학생과 바로 시작할 수 있는 공개 활동입니다.",
                "service_name": "",
                "home_icon_class": getattr(game, "home_icon_class", "") or service_launcher_utils.resolve_home_icon_class(game),
                "home_accent_token": getattr(game, "home_accent_token", "") or service_launcher_utils.resolve_home_accent_token(game),
                "service_type": getattr(game, "service_type", ""),
                "route_name": _product_route_name(game),
                "href": launch_href,
                "is_external": bool(getattr(game, "launch_is_external", False)),
                "access_status_label": "미리보기 가능",
            }
        return None

    for route_name in PUBLIC_HOME_PRIMARY_ACTION_ROUTE_PRIORITY:
        matched_card = next(
            (card for card in candidate_cards if str(card.get("route_name", "") or "").strip().lower() == route_name),
            None,
        )
        if matched_card:
            return matched_card

    normalized_title_map = {
        str(card.get("title", "") or "").strip(): card
        for card in candidate_cards
    }
    for title in PUBLIC_HOME_PRIMARY_ACTION_TITLE_PRIORITY:
        matched_card = normalized_title_map.get(title)
        if matched_card:
            return matched_card

    return next(
        (card for card in candidate_cards if not card.get("is_external")),
        candidate_cards[0],
    )


def _build_home_public_secondary_cards(guest_public_cards, primary_action_card, *, limit=5):
    secondary_cards = []
    primary_id = primary_action_card.get("id") if primary_action_card else None

    for card in list(guest_public_cards or []):
        if not card.get("href"):
            continue
        if primary_id and card.get("id") == primary_id:
            continue
        secondary_cards.append(card)
        if limit and len(secondary_cards) >= limit:
            break
    return secondary_cards


def _resolve_public_platform_group_key(product):
    route_name = _product_route_name(product)
    if route_name in PUBLIC_PLATFORM_GROUP_KEY_BY_ROUTE:
        return PUBLIC_PLATFORM_GROUP_KEY_BY_ROUTE[route_name]

    home_section_key = _resolve_home_section_key(product)
    return PUBLIC_PLATFORM_GROUP_KEY_BY_HOME_SECTION.get(home_section_key, "")


def _build_home_public_platform_item(product, *, login_url, section_key=""):
    if not product:
        return None

    if not getattr(product, "launch_href", ""):
        return None

    if getattr(product, "service_type", "") == "game":
        return None

    prepared_product = _attach_home_guest_landing_meta(product, login_url=login_url)
    if not prepared_product or not getattr(prepared_product, "home_landing_cta_href", ""):
        return None

    group_key = section_key or _resolve_public_platform_group_key(prepared_product)
    if not group_key:
        return None

    return {
        "id": getattr(prepared_product, "id", ""),
        "title": getattr(prepared_product, "public_service_name", "") or getattr(prepared_product, "title", "") or "도구",
        "summary": getattr(prepared_product, "home_landing_summary", "") or getattr(prepared_product, "home_card_summary", "") or "",
        "href": getattr(prepared_product, "home_landing_cta_href", "") or "",
        "cta_label": getattr(prepared_product, "home_landing_cta_label", "") or "열기",
        "is_external": bool(getattr(prepared_product, "home_landing_cta_is_external", False)),
        "access_status_label": _guest_access_status_copy(prepared_product),
        "home_icon_class": getattr(prepared_product, "home_icon_class", "") or service_launcher_utils.resolve_home_icon_class(prepared_product),
        "home_accent_token": getattr(prepared_product, "home_accent_token", "") or service_launcher_utils.resolve_home_accent_token(prepared_product),
        "section_key": group_key,
        "route_name": _product_route_name(prepared_product),
        "service_name": getattr(prepared_product, "teacher_first_task_label", "") or "",
        "context_chips": list(getattr(prepared_product, "home_context_chips", []) or [])[:3],
    }


def _match_public_platform_product(product_list, *, route_names=(), titles=(), excluded_ids=None):
    excluded_ids = set(excluded_ids or ())
    normalized_titles = {str(title or "").strip() for title in titles if str(title or "").strip()}
    normalized_routes = {str(route_name or "").strip().lower() for route_name in route_names if str(route_name or "").strip()}

    for product in product_list:
        product_id = getattr(product, "id", None)
        if product_id in excluded_ids:
            continue

        if normalized_routes and _product_route_name(product) in normalized_routes:
            return product

        if normalized_titles and str(getattr(product, "public_service_name", "") or getattr(product, "title", "") or "").strip() in normalized_titles:
            return product

    return None


def _build_home_public_platform_showcase_items(product_list, *, login_url, limit=6):
    showcase_items = []
    seen_ids = set()

    for spec in PUBLIC_PLATFORM_SHOWCASE_PRIORITY_SPECS:
        matched_product = _match_public_platform_product(
            product_list,
            route_names=spec.get("route_names", ()),
            titles=spec.get("titles", ()),
            excluded_ids=seen_ids,
        )
        item = _build_home_public_platform_item(matched_product, login_url=login_url)
        if not item:
            continue
        showcase_items.append(item)
        seen_ids.add(item["id"])

    if len(showcase_items) >= limit:
        return showcase_items[:limit]

    def _fallback_sort_key(product):
        group_key = _resolve_public_platform_group_key(product)
        return (
            PUBLIC_PLATFORM_GROUP_SORT_ORDER.get(group_key, 99),
            getattr(product, "display_order", 9999),
            str(getattr(product, "title", "") or ""),
        )

    for product in sorted(product_list, key=_fallback_sort_key):
        product_id = getattr(product, "id", None)
        if product_id in seen_ids:
            continue
        item = _build_home_public_platform_item(product, login_url=login_url)
        if not item:
            continue
        showcase_items.append(item)
        seen_ids.add(product_id)
        if len(showcase_items) >= limit:
            break

    return showcase_items


def _build_home_public_platform_groups(product_list, *, login_url, showcase_items=None, limit=3):
    showcase_items = list(showcase_items or [])
    groups = []

    for spec in PUBLIC_PLATFORM_GROUP_SPECS:
        items = []
        seen_ids = set()

        for route_name in spec.get("preferred_routes", ()):
            matched_product = _match_public_platform_product(
                product_list,
                route_names=(route_name,),
                excluded_ids=seen_ids,
            )
            item = _build_home_public_platform_item(
                matched_product,
                login_url=login_url,
                section_key=spec["key"],
            )
            if not item:
                continue
            items.append(item)
            seen_ids.add(item["id"])
            if len(items) >= limit:
                break

        if len(items) < limit:
            for title in spec.get("preferred_titles", ()):
                matched_product = _match_public_platform_product(
                    product_list,
                    titles=(title,),
                    excluded_ids=seen_ids,
                )
                item = _build_home_public_platform_item(
                    matched_product,
                    login_url=login_url,
                    section_key=spec["key"],
                )
                if not item:
                    continue
                items.append(item)
                seen_ids.add(item["id"])
                if len(items) >= limit:
                    break

        if len(items) < limit:
            for product in product_list:
                if getattr(product, "id", None) in seen_ids:
                    continue
                item = _build_home_public_platform_item(product, login_url=login_url)
                if not item:
                    continue
                if item["section_key"] not in spec.get("fallback_group_keys", ()):
                    continue
                item["section_key"] = spec["key"]
                items.append(item)
                seen_ids.add(item["id"])
                if len(items) >= limit:
                    break

        if len(items) < limit:
            for showcase_item in showcase_items:
                if showcase_item.get("id") in seen_ids:
                    continue
                if showcase_item.get("section_key") not in spec.get("fallback_group_keys", ()):
                    continue
                items.append({
                    **showcase_item,
                    "section_key": spec["key"],
                })
                seen_ids.add(showcase_item.get("id"))
                if len(items) >= limit:
                    break

        if items:
            groups.append(
                {
                    "key": spec["key"],
                    "title": spec["title"],
                    "summary": spec["summary"],
                    "items": items[:limit],
                }
            )

    return groups


def _build_home_featured_summary(product):
    title = str(
        getattr(product, "public_service_name", "") or getattr(product, "title", "") or ""
    ).strip()
    for candidate in (
        getattr(product, "solve_text", ""),
        getattr(product, "lead_text", ""),
        getattr(product, "description", ""),
    ):
        summary = _replace_public_service_terms(str(candidate or "").strip(), product)
        if summary and summary != title:
            return summary
    return getattr(product, "home_card_summary", "") or title


def _attach_home_guest_landing_meta(product, *, login_url):
    if not product:
        return None

    access_status = _guest_access_status_copy(product)
    launch_href = getattr(product, "launch_href", "") or ""
    launch_is_external = bool(getattr(product, "launch_is_external", False))
    guest_summary = getattr(product, "home_guest_summary", "") or _build_home_featured_summary(product)
    guest_cta_label = getattr(product, "home_guest_cta_label", "") or "지금 시작"

    if launch_is_external:
        cta_href = launch_href
        cta_label = "새 창에서 시작"
    elif access_status == "로그인 필요":
        cta_href = _build_home_login_continue_url(launch_href, login_url=login_url)
        cta_label = "로그인 후 시작"
    else:
        cta_href = launch_href or login_url
        cta_label = guest_cta_label

    product.home_landing_summary = guest_summary
    product.home_landing_cta_href = cta_href
    product.home_landing_cta_label = cta_label
    product.home_landing_cta_is_external = launch_is_external
    product.home_icon_class = getattr(product, "home_icon_class", "") or service_launcher_utils.resolve_home_icon_class(product)
    product.home_accent_token = getattr(product, "home_accent_token", "") or service_launcher_utils.resolve_home_accent_token(product)
    return product


def _build_home_public_representative_products(product_list, *, login_url):
    priority_specs = [
        {
            "route_names": {"artclass:setup"},
            "titles": {"미술 수업 도우미", "몽글몽글 미술 수업"},
        },
        {
            "route_names": {"reservations:dashboard_landing", "reservations:landing"},
            "titles": {"학교 예약 시스템"},
        },
        {
            "route_names": {"collect:landing", "collect:dashboard"},
            "titles": {"간편 수합"},
        },
        {
            "route_names": {"signatures:list"},
            "titles": {"가뿐하게 서명 톡"},
        },
    ]
    seen_ids = set()
    representative_products = []

    for spec in priority_specs:
        matched_product = next(
            (
                product
                for product in product_list
                if getattr(product, "id", None) not in seen_ids
                and (
                    _product_route_name(product) in spec["route_names"]
                    or str(getattr(product, "title", "") or "").strip() in spec["titles"]
                )
            ),
            None,
        )
        if not matched_product:
            continue
        representative_products.append(
            _attach_home_guest_landing_meta(
                matched_product,
                login_url=login_url,
            )
        )
        seen_ids.add(getattr(matched_product, "id", None))

    return representative_products


def _build_home_guest_entry_context(product_list, guest_public_cards, games, *, login_url):
    guest_locked_cards = _build_home_guest_highlight_cards(
        product_list,
        requires_login=True,
        limit=3,
        login_url=login_url,
    )
    guest_primary_action_card = next(
        (card for card in guest_public_cards if not card.get("is_external")),
        guest_public_cards[0] if guest_public_cards else None,
    )
    if guest_primary_action_card is None:
        guest_game = next(
            (game for game in list(games or []) if getattr(game, "launch_href", "")),
            None,
        )
        if guest_game is not None:
            guest_primary_action_card = {
                "title": getattr(guest_game, "public_service_name", "") or getattr(guest_game, "title", "") or "교실 활동",
                "description": getattr(guest_game, "home_card_summary", "") or "학생과 함께 바로 열 수 있는 공개 활동입니다.",
                "href": getattr(guest_game, "launch_href", "") or "",
                "is_external": bool(getattr(guest_game, "launch_is_external", False)),
                "access_status_label": "미리보기 가능",
            }
    guest_continue_action_card = guest_locked_cards[0] if guest_locked_cards else None
    guest_continue_url = (
        guest_continue_action_card.get("href", "")
        if guest_continue_action_card
        else _build_home_login_continue_url("", login_url=login_url)
    )
    return {
        "guest_locked_cards": guest_locked_cards,
        "guest_primary_action_card": guest_primary_action_card,
        "guest_continue_action_card": guest_continue_action_card,
        "guest_continue_url": guest_continue_url,
    }


def _build_home_entry_action_from_product(product):
    if product is None:
        return None
    href = str(getattr(product, "launch_href", "") or "").strip()
    if not href:
        return None
    return {
        "title": getattr(product, "public_service_name", "") or getattr(product, "title", "") or "도구",
        "description": getattr(product, "home_card_summary", "") or getattr(product, "teacher_first_support_label", "") or "필요한 순간 바로 열 수 있습니다.",
        "href": href,
        "is_external": bool(getattr(product, "launch_is_external", False)),
    }


def _build_home_entry_panel_context(
    *,
    favorite_items,
    representative_slots,
    discovery_items,
    calendar_surface,
):
    starter_product = None
    starter_title = "처음이라면 여기서 시작하세요"
    starter_description = "게스트 홈에서 보던 흐름 그대로, 도구 하나를 먼저 열고 오늘 일정으로 이어갈 수 있습니다."

    if favorite_items:
        starter_product = favorite_items[0].get("product")
        starter_title = "자주 쓰는 도구부터 다시 시작하세요"
        starter_description = "가장 먼저 쓸 도구 하나를 열고, 필요하면 오늘 일정으로 바로 이어가세요."
    elif representative_slots:
        starter_product = next(
            (slot.get("product") for slot in representative_slots if slot.get("product") is not None),
            None,
        )
    elif discovery_items:
        starter_product = discovery_items[0].get("product")

    primary_action = _build_home_entry_action_from_product(starter_product)
    calendar_href = (
        str(calendar_surface.get("main_url", "") or "").strip()
        or str(calendar_surface.get("today_url", "") or "").strip()
        or str(calendar_surface.get("calendar_center_url", "") or "").strip()
    )
    secondary_action = None
    if calendar_href:
        secondary_action = {
            "title": "오늘 일정 보기",
            "description": "하루 흐름을 먼저 확인하고 필요한 도구로 이어갑니다.",
            "href": calendar_href,
            "is_external": False,
        }

    if primary_action is None and secondary_action is None:
        return None

    return {
        "eyebrow": "오늘 바로 할 일",
        "title": starter_title,
        "description": starter_description,
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "is_first_run": not bool(favorite_items),
    }


def _build_home_action_from_link_item(item, *, cta_label="바로 열기"):
    if not item:
        return None
    href = str(item.get("href", "") or "").strip()
    if not href:
        return None
    title = (
        item.get("favorite_full_title")
        or item.get("favorite_title")
        or getattr(item.get("product"), "public_service_name", "")
        or getattr(item.get("product"), "title", "")
        or "도구"
    )
    description = (
        item.get("workbench_summary")
        or item.get("section_subtitle")
        or item.get("section_title")
        or getattr(item.get("product"), "home_card_summary", "")
        or "필요한 순간 바로 열 수 있습니다."
    )
    return {
        "title": title,
        "description": description,
        "href": href,
        "is_external": bool(item.get("is_external", False)),
        "cta_label": cta_label,
    }


def _build_home_action_from_recommendation(item, *, cta_label="열기"):
    if not item:
        return None
    href = str(item.get("href", "") or "").strip()
    if not href:
        return None
    return {
        "title": item.get("title") or "도구",
        "description": item.get("reason_label") or "추천 도구",
        "href": href,
        "is_external": bool(item.get("is_external", False)),
        "cta_label": cta_label,
    }


def _build_home_action_from_card(card, *, cta_label="바로 시작"):
    if not card:
        return None
    href = str(card.get("href", "") or "").strip()
    if not href:
        return None
    return {
        "title": card.get("service_name") or card.get("title") or "도구",
        "description": card.get("description") or "필요한 순간 바로 열 수 있습니다.",
        "href": href,
        "is_external": bool(card.get("is_external", False)),
        "cta_label": cta_label,
        "access_status_label": card.get("access_status_label", ""),
    }


def _dedupe_home_actions(actions, *, limit=None):
    deduped = []
    seen = set()
    for action in actions:
        if not action or not action.get("href"):
            continue
        key = (
            str(action.get("href", "")).strip(),
            str(action.get("title", "")).strip(),
        )
        if key in seen:
            continue
        deduped.append(action)
        seen.add(key)
        if limit and len(deduped) >= limit:
            break
    return deduped


def _dedupe_home_actions_by_href(actions, *, limit=None):
    deduped = []
    seen_hrefs = set()
    for action in actions:
        if not action or not action.get("href"):
            continue
        href = str(action.get("href", "")).strip()
        if href in seen_hrefs:
            continue
        deduped.append(action)
        seen_hrefs.add(href)
        if limit and len(deduped) >= limit:
            break
    return deduped


def _build_home_today_primary_action(*, home_user_mode, calendar_surface):
    calendar_href = (
        str(calendar_surface.get("today_create_url", "") or "").strip()
        or str(calendar_surface.get("main_url", "") or "").strip()
        or str(calendar_surface.get("today_url", "") or "").strip()
        or str(calendar_surface.get("calendar_center_url", "") or "").strip()
    )
    if not calendar_href:
        return None

    if home_user_mode == "authenticated":
        return {
            "title": "오늘 일정 추가",
            "description": "일정을 하나 넣어두면 필요한 도구로 바로 이어집니다.",
            "href": calendar_href,
            "is_external": False,
            "cta_label": "오늘 일정 추가",
        }

    return {
        "title": "로그인 후 일정 이어보기",
        "description": "일정과 메모는 로그인 후 그대로 이어갈 수 있습니다.",
        "href": _build_home_login_continue_url(calendar_href),
        "is_external": False,
        "cta_label": "로그인 후 일정 이어보기",
    }


def _build_home_empty_action_board(*, home_user_mode, primary_action, support_actions, calendar_surface):
    today_primary_action = _build_home_today_primary_action(
        home_user_mode=home_user_mode,
        calendar_surface=calendar_surface,
    )
    recovery_actions = _dedupe_home_actions_by_href(
        [today_primary_action, *list(support_actions or [])],
        limit=3,
    )

    if home_user_mode == "guest":
        return {
            "workbench": {
                "title": "로그인 없이 먼저 써볼 수 있어요",
                "description": "가벼운 업무부터 바로 열고, 마음에 들면 로그인 후 작업대로 이어가세요.",
                "primary_action": primary_action,
                "secondary_actions": recovery_actions,
            },
            "recommendations": {
                "title": "지금 많이 쓰는 공개 도구를 먼저 보여드릴게요",
                "description": "첫 화면에서는 바로 끝나는 교실 업무 도구만 압축해서 보여줍니다.",
                "primary_action": primary_action,
                "secondary_actions": recovery_actions,
            },
            "today_flow": {
                "title": "로그인하면 오늘 일정까지 이어집니다",
                "description": "비회원 체험 후 일정과 메모는 로그인해서 그대로 이어갈 수 있어요.",
                "primary_action": today_primary_action,
                "secondary_actions": _dedupe_home_actions_by_href(
                    [primary_action, *support_actions],
                    limit=2,
                ),
            },
        }

    return {
        "workbench": {
            "title": "자주 쓰는 도구를 아직 고르지 않았어요",
            "description": "먼저 열어 본 도구를 다음부터 작업대로 더 빠르게 이어갈 수 있습니다.",
            "primary_action": primary_action,
            "secondary_actions": recovery_actions,
        },
        "recommendations": {
            "title": "아직 띄울 추천 도구가 없습니다",
            "description": "첫 도구를 먼저 열면 다음에 이어질 흐름까지 맞춰 추천해 드립니다.",
            "primary_action": primary_action,
            "secondary_actions": recovery_actions,
        },
        "today_flow": {
            "title": "오늘 일정이 아직 없습니다",
            "description": "일정을 하나 넣어두면 멘트, 수합, 준비 흐름으로 바로 이어집니다.",
            "primary_action": today_primary_action,
            "secondary_actions": _dedupe_home_actions_by_href(
                [primary_action, *support_actions],
                limit=2,
            ),
        },
    }


def _build_authenticated_home_default_actions(*, product_list, calendar_surface):
    try_now_cards = _build_home_try_now_cards(product_list)
    cards_by_key = {
        card.get("key"): card
        for card in try_now_cards
        if card.get("key")
    }
    primary_action = _build_home_action_from_card(
        cards_by_key.get("notice"),
        cta_label="알림장 멘트 바로 만들기",
    )
    if primary_action is not None:
        primary_action = {
            **primary_action,
            "eyebrow": "지금 바로 할 일",
            "meta": "처음에는 교실 업무 하나부터 바로 끝내는 흐름이 가장 덜 헷갈립니다.",
        }
    support_actions = _dedupe_home_actions_by_href(
        [
            _build_home_action_from_card(
                cards_by_key.get("collect"),
                cta_label="간편 수합 시작",
            ),
            _build_home_today_primary_action(
                home_user_mode="authenticated",
                calendar_surface=calendar_surface,
            ),
        ],
        limit=2,
    )
    return primary_action, support_actions


def _build_authenticated_home_action_context(
    *,
    product_list,
    favorite_items,
    recent_items,
    representative_slots,
    representative_recommendations,
    home_entry_panel,
    calendar_surface,
):
    primary_action = None
    secondary_action = None
    if home_entry_panel:
        primary_action = home_entry_panel.get("primary_action")
        secondary_action = home_entry_panel.get("secondary_action")
    if primary_action is None and favorite_items:
        primary_action = _build_home_action_from_link_item(favorite_items[0])
    if primary_action is None and representative_slots:
        primary_action = _build_home_entry_action_from_product(representative_slots[0].get("product"))
    if primary_action is not None:
        primary_action = {
            **primary_action,
            "eyebrow": "지금 바로 할 일",
            "meta": "설명보다 바로 열리는 첫 도구 하나가 오늘 흐름을 가장 빠르게 만듭니다.",
            "cta_label": primary_action.get("cta_label") or "바로 열기",
        }

    support_actions = _dedupe_home_actions(
        [
            {
                **secondary_action,
                "cta_label": secondary_action.get("cta_label") or "오늘 흐름 보기",
            }
            if secondary_action
            else None,
            *[
                _build_home_action_from_recommendation(item, cta_label="열기")
                for item in representative_recommendations[:2]
            ],
            _build_home_action_from_link_item(recent_items[0], cta_label="다시 열기")
            if recent_items
            else None,
        ],
        limit=3,
    )
    is_first_run = bool(home_entry_panel and home_entry_panel.get("is_first_run"))
    if is_first_run and not favorite_items and not recent_items:
        default_primary_action, default_support_actions = _build_authenticated_home_default_actions(
            product_list=product_list,
            calendar_surface=calendar_surface,
        )
        if default_primary_action is not None:
            primary_action = default_primary_action
        if default_support_actions:
            support_actions = default_support_actions
    return {
        "home_primary_action": primary_action,
        "home_support_actions": support_actions,
        "home_empty_action_board": _build_home_empty_action_board(
            home_user_mode="authenticated",
            primary_action=primary_action,
            support_actions=support_actions,
            calendar_surface=calendar_surface,
        ),
        "home_locked_sections": [],
    }


def _build_home_guest_calendar_surface(request):
    home_surface_url = _home_calendar_surface_url()
    today_key = timezone.localdate().isoformat()
    return {
        "messagebox_home_card": {
            "enabled": False,
            "title": "AI 업무 메시지 보관함",
            "description": "",
            "primary_action_label": "새 메시지 보관",
            "url": "",
        },
        "today_workspace": {
            "date_label": "비회원 체험",
            "date_key": today_key,
            "focus_heading": "",
            "focus_description": "",
            "focus_empty_message": "로그인하면 오늘 일정과 메모를 바로 이어서 볼 수 있어요.",
            "today_event_count": 0,
            "today_task_count": 0,
            "today_events": [],
            "today_memos": [],
            "review_groups": [],
            "has_items": False,
            "today_all_url": home_surface_url,
            "today_memo_url": home_surface_url,
            "today_review_url": home_surface_url,
        },
        "today_url": home_surface_url,
        "today_focus": "all",
        "today_all_url": home_surface_url,
        "today_memo_url": home_surface_url,
        "today_review_url": home_surface_url,
        "main_url": home_surface_url,
        "calendar_center_url": home_surface_url,
        "home_surface_url": home_surface_url,
        "calendar_page_url": home_surface_url,
        "calendar_api_base_url": "",
        "calendar_load_error": False,
        "calendar_load_error_title": "",
        "calendar_load_error_message": "",
        "calendar_load_error_retry_url": "",
        "calendar_load_error_retry_label": "",
        "calendar_load_error_secondary_url": "",
        "calendar_load_error_secondary_label": "",
        "initial_selected_date": today_key,
        "initial_open_create": False,
        "initial_open_event_id": "",
        "initial_open_task_id": "",
        "initial_focus_search": False,
        "initial_search_query": "",
        "calendar_embed_mode": "home",
        "is_embedded_on_home": True,
        "is_compact_surface": True,
        "hide_navbar": False,
    }


def _build_guest_home_action_context(request, *, product_list):
    login_url = reverse("account_login")
    try_now_cards = _build_home_try_now_cards(product_list)
    support_cards = _build_home_try_now_support_cards(product_list)
    all_cards_by_key = {
        card.get("key"): card
        for card in [*try_now_cards, *support_cards]
        if card.get("key")
    }
    primary_card = all_cards_by_key.get("notice") or (try_now_cards[0] if try_now_cards else None)
    primary_action = _build_home_action_from_card(primary_card, cta_label="바로 만들기")
    if primary_action is not None:
        primary_action = {
            **primary_action,
            "eyebrow": "지금 바로 할 일",
            "meta": "비회원은 2회까지 바로 써볼 수 있어요.",
        }
    support_actions = _dedupe_home_actions(
        [
            _build_home_action_from_card(all_cards_by_key.get("collect"), cta_label="수합 시작"),
            _build_home_action_from_card(all_cards_by_key.get("qrgen"), cta_label="QR 만들기"),
        ],
        limit=2,
    )
    locked_cards = _build_home_guest_highlight_cards(
        product_list,
        requires_login=True,
        limit=3,
        login_url=login_url,
    )
    locked_actions = _dedupe_home_actions(
        [
            {
                **_build_home_action_from_card(card, cta_label="로그인 후 열기"),
                "description": card.get("description")
                or "로그인하면 지금 하던 흐름과 이어서 열 수 있습니다.",
            }
            for card in locked_cards
        ],
        limit=3,
    )
    calendar_surface = _build_home_guest_calendar_surface(request)
    return {
        "home_primary_action": primary_action,
        "home_support_actions": support_actions,
        "home_empty_action_board": _build_home_empty_action_board(
            home_user_mode="guest",
            primary_action=primary_action,
            support_actions=support_actions,
            calendar_surface=calendar_surface,
        ),
        "home_locked_sections": locked_actions,
        "home_calendar_surface": calendar_surface,
    }


def _build_home_guest_representative_slots(product_list, *, exclude_ids=None, limit=4):
    exclude_ids = set(exclude_ids or [])
    candidates = _build_home_guest_highlight_cards(
        product_list,
        requires_login=False,
        limit=max(len(product_list), 1),
        include_games=False,
    )
    product_map = {getattr(product, "id", None): product for product in product_list}
    selected_products = []
    for card in candidates:
        product_id = card.get("id")
        if not product_id or product_id in exclude_ids:
            continue
        product = product_map.get(product_id)
        if product is None:
            continue
        selected_products.append(product)
        if len(selected_products) >= limit:
            break
    return [{"product": product, "slot_kind": "guest"} for product in selected_products]


def _filter_home_sections_by_access(sections, *, requires_login):
    filtered_sections = []
    for section in sections:
        all_items = [*section.get("products", []), *section.get("overflow_products", [])]
        matching_items = [
            product for product in all_items
            if _product_requires_guest_login(product) == requires_login
        ]
        if not matching_items:
            continue
        filtered_sections.append(
            _build_section_payload(
                section,
                matching_items,
                preview_limit=len(section.get("products", [])) or 2,
            )
        )
    return filtered_sections


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
    if not bool(getattr(product, "is_active", False)):
        return None

    route_name = _product_route_name(product)
    service_type = str(getattr(product, "service_type", "") or "").strip()

    if route_name in {"classcalendar:main", "reservations:dashboard_landing", "reservations:landing"}:
        return "today_ops"
    if route_name in {"collect:landing", "consent:landing", "docsign:list", "signatures:landing", "handoff:landing"} or service_type == "collect_sign":
        return "collect"
    if service_type == "game" or route_name in CLASS_ACTIVITY_ROUTE_NAMES:
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
    return {
        "title": "메인 캘린더는 홈에서 시작합니다",
        "description": "홈의 캘린더 요약에서 오늘 일정과 메모를 먼저 보고, 필요할 때만 월간 확장 보기로 이동하세요.",
        "href": reverse("home"),
        "is_external": False,
        "guide_url": SERVICE_GUIDE_PADLET_URL,
        "guide_is_external": True,
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
        if bool(getattr(product, "is_active", False))
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
            "description": "홈 캘린더에서 자주 이어지는 흐름을 한곳에서 빠르게 찾을 수 있습니다.",
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


def _home_v2(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """Feature flag on 시 호출되는 V2 홈."""
    product_list = _attach_product_launch_meta(list(products), user=request.user)
    login_url = reverse("account_login")
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
    primary_display_sections, secondary_display_sections = _build_home_display_groups(sections, aux_sections)
    guest_public_cards = _build_home_guest_highlight_cards(product_list, requires_login=False, limit=4)
    if not guest_public_cards:
        guest_public_cards = _build_home_guest_highlight_cards(
            product_list,
            requires_login=False,
            limit=4,
            include_games=True,
        )
    guest_entry_context = _build_home_guest_entry_context(
        product_list,
        guest_public_cards,
        games,
        login_url=login_url,
    )
    guest_primary_display_sections = _filter_home_sections_by_access(
        primary_display_sections,
        requires_login=True,
    )
    guest_secondary_display_sections = _filter_home_sections_by_access(
        secondary_display_sections,
        requires_login=True,
    )
    sns_summary_posts = _build_home_community_summary_posts(
        page_obj,
        pinned_notice_posts=pinned_notice_posts,
        limit=2,
    )
    sns_preview_posts = _build_sns_preview_posts(
        page_obj,
        pinned_notice_posts=pinned_notice_posts,
        limit=3,
    )
    community_summary = {
        'title': '실시간 소통',
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
            user=request.user,
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

        quick_action_items = _build_product_link_items(
            quick_actions,
            include_section_meta=True,
            user=request.user,
        )
        favorite_items = _build_product_link_items(
            favorite_products,
            include_section_meta=True,
            user=request.user,
        )
        workbench_slots = _build_workbench_slots(favorite_items)
        recent_items = _build_product_link_items(
            recent_products,
            include_section_meta=True,
            user=request.user,
        )
        discovery_items = _build_product_link_items(
            discovery_products,
            include_section_meta=True,
            user=request.user,
        )
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
        home_frontend_config = {
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
            'home_frontend_config': home_frontend_config,
            'home_v2_frontend_config': home_frontend_config,
            'community_summary': community_summary,
            'posts': page_obj,
            'page_obj': page_obj,
            'pinned_notice_posts': pinned_notice_posts,
            'feed_scope': feed_scope,
            'sns_compose_prefill': _get_sns_compose_prefill(request),
            **_get_teacher_buddy_home_context(request.user),
            **home_calendar_surface,
            **build_home_page_seo(request).as_context(),
            **today_context,
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
        'guest_public_cards': guest_public_cards,
        'guest_primary_display_sections': guest_primary_display_sections,
        'guest_secondary_display_sections': guest_secondary_display_sections,
        'games': games,
        'community_summary': community_summary,
        'public_calendar_entry': _build_public_calendar_entry_context(),
        **guest_entry_context,
        'posts': page_obj,
        'page_obj': page_obj,
        'pinned_notice_posts': pinned_notice_posts,
        'feed_scope': feed_scope,
        'sns_compose_prefill': _get_sns_compose_prefill(request),
        **build_home_page_seo(request).as_context(),
    })


def _build_home_public_landing_context(request, products):
    product_list = _attach_product_launch_meta(list(products), user=request.user)
    login_url = reverse('account_login')
    guest_notice_trial_context = _build_guest_notice_trial_context(
        request,
        login_url=login_url,
    )
    guest_rotation_cards = _build_home_guest_rotation_cards(product_list, login_url=login_url)
    guest_public_cards = _build_home_guest_highlight_cards(
        product_list,
        requires_login=False,
        limit=6,
        login_url=login_url,
    )
    if not guest_public_cards:
        guest_public_cards = _build_home_guest_highlight_cards(
            product_list,
            requires_login=False,
            limit=6,
            include_games=True,
            login_url=login_url,
        )
    representative_products = _build_home_public_representative_products(
        product_list,
        login_url=login_url,
    )
    featured_product = representative_products[0] if representative_products else next(
        (p for p in product_list if p.is_featured),
        product_list[0] if product_list else None,
    )
    featured_product = _attach_home_guest_landing_meta(
        featured_product,
        login_url=login_url,
    )
    guest_entry_context = _build_home_guest_entry_context(
        product_list,
        guest_public_cards,
        [],
        login_url=login_url,
    )
    public_primary_action_card = _build_home_public_primary_action_card(
        guest_public_cards,
        [],
    )
    public_secondary_cards = _build_home_public_secondary_cards(
        guest_public_cards,
        public_primary_action_card,
    )
    return {
        'products': products,
        'featured_product': featured_product,
        'representative_products': representative_products,
        'guest_rotation_cards': guest_rotation_cards,
        'guest_public_cards': guest_public_cards,
        'public_primary_action_card': public_primary_action_card,
        'public_secondary_cards': public_secondary_cards,
        'guest_continue_category_labels': PUBLIC_HOME_CONTINUE_CATEGORY_LABELS,
        'login_url': login_url,
        **guest_notice_trial_context,
        **guest_entry_context,
        **build_home_page_seo(request).as_context(),
    }


def _build_home_public_v6_landing_context(request, products):
    context = _build_home_public_landing_context(request, products)
    product_list = _attach_product_launch_meta(list(products), user=request.user)
    login_url = context["login_url"]
    showcase_items = _build_home_public_platform_showcase_items(
        product_list,
        login_url=login_url,
    )
    platform_groups = _build_home_public_platform_groups(
        product_list,
        login_url=login_url,
        showcase_items=showcase_items,
    )
    context.update(
        {
            "public_platform_showcase_items": showcase_items,
            "public_platform_groups": platform_groups,
            "public_portfolio_panel": {
                "href": reverse("portfolio:list"),
                "eyebrow": "현장 사례",
                "title": "에듀잇티 포트폴리오",
                "summary": "교실 적용 사례와 연수 기록을 보고 도입 맥락을 빠르게 파악합니다.",
                "cta_label": "포트폴리오 보기",
                "chips": ("교실 적용", "연수 기록", "도입 참고"),
            },
            "public_primary_cta": {
                "label": "업무 둘러보기",
                "fallback_href": "#public-platform-map",
                "fallback_target_id": "public-platform-map",
                "aria_label": "업무 둘러보기",
            },
            "hide_navbar": True,
        }
    )
    return context


def _home_public_v4(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """비로그인 사용자를 위한 공개 홈 V4."""
    return render(
        request,
        'core/home_public_v4.html',
        _build_home_public_landing_context(request, products),
    )


def _home_public_v5(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """모바일 우선 공개 홈 V5."""
    return render(
        request,
        'core/home_public_v5.html',
        {
            **_build_home_public_landing_context(request, products),
            'home_design_version': 'v5',
        },
    )


def _home_public_v6(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """비로그인 첫 진입의 canonical 공개 홈 V6."""
    return render(
        request,
        'core/home_public_v6_canonical.html',
        {
            **_build_home_public_v6_landing_context(request, products),
            'home_design_version': 'v6',
        },
    )


def _build_home_surface_reservation_provider(user):
    try:
        return _build_home_reservation_card(user)
    except Exception:
        logger.exception(
            '[home surface] reservation provider failed user_id=%s',
            getattr(user, 'id', None),
        )
        return None


def _build_home_surface_quickdrop_provider(request, *, favorite_products, product_list):
    try:
        return _build_home_quickdrop_card(
            request.user,
            favorite_products=favorite_products,
            product_list=product_list,
        )
    except Exception:
        logger.exception(
            '[home surface] quickdrop provider failed user_id=%s',
            getattr(request.user, 'id', None),
        )
        return None


def _build_home_surface_calendar_fallback(request):
    home_surface_url = _home_calendar_surface_url()
    home_reload_url = _safe_reverse('home') or home_surface_url
    calendar_center_url = _safe_reverse('classcalendar:center') or home_surface_url
    calendar_api_base_url = _safe_reverse('classcalendar:main')
    today_key = timezone.localdate().isoformat()
    empty_messagebox_home_card = {
        'enabled': False,
        'title': 'AI 업무 메시지 보관함',
        'description': '',
        'primary_action_label': '새 메시지 보관',
        'url': '',
    }
    today_workspace = {
        'date_label': '오늘',
        'date_key': today_key,
        'focus_heading': '',
        'focus_description': '',
        'focus_empty_message': '일시적인 문제로 오늘 일정을 아직 보여드리지 못했습니다.',
        'today_event_count': 0,
        'today_task_count': 0,
        'today_events': [],
        'today_memos': [],
        'review_groups': [],
        'has_items': False,
        'today_all_url': home_surface_url,
        'today_memo_url': home_surface_url,
        'today_review_url': home_surface_url,
    }
    return {
        'service': None,
        'title': '학급 캘린더',
        'events_json': [],
        'tasks_json': [],
        'hub_items_json': [],
        'day_markers_json': {},
        'integration_settings_json': {},
        'reservation_windows': [],
        'share_enabled': False,
        'share_url': '',
        'calendar_owner_options_json': [],
        'owner_collaborators': [],
        'incoming_calendars': [],
        'message_capture_enabled': False,
        'message_capture_item_types_enabled': False,
        'message_capture_limits_json': {
            'max_files': 0,
            'max_file_bytes': 0,
            'allowed_extensions': [],
        },
        'message_capture_urls_json': {
            'parse': '',
            'save': '',
            'archive': '',
            'parse_saved_template': '',
            'archive_detail_template': '',
            'link_template': '',
            'commit_template': '',
            'complete_template': '',
            'delete_template': '',
            'messagebox_main': '',
        },
        'messagebox_home_card': empty_messagebox_home_card,
        'calendar_page_variant': 'main',
        'today_workspace': today_workspace,
        'today_url': home_surface_url,
        'today_focus': 'all',
        'today_all_url': home_surface_url,
        'today_memo_url': home_surface_url,
        'today_review_url': home_surface_url,
        'main_url': calendar_center_url,
        'calendar_center_url': calendar_center_url,
        'home_surface_url': home_surface_url,
        'calendar_page_url': home_surface_url,
        'calendar_api_base_url': calendar_api_base_url,
        'calendar_load_error': True,
        'calendar_load_error_title': '일정을 불러오지 못했습니다',
        'calendar_load_error_message': '잠시 후 다시 시도하거나 전체 캘린더에서 확인해 주세요.',
        'calendar_load_error_retry_url': home_reload_url,
        'calendar_load_error_retry_label': '홈 다시 불러오기',
        'calendar_load_error_secondary_url': calendar_center_url or calendar_api_base_url,
        'calendar_load_error_secondary_label': '전체 캘린더 열기',
        'initial_selected_date': today_key,
        'initial_open_create': False,
        'initial_open_event_id': '',
        'initial_open_task_id': '',
        'initial_focus_search': False,
        'initial_search_query': '',
        'calendar_embed_mode': 'home',
        'is_embedded_on_home': True,
        'is_compact_surface': True,
        'hide_navbar': False,
    }


def _build_home_surface_calendar_provider(request):
    try:
        from classcalendar.views import build_calendar_surface_context

        calendar_surface = build_calendar_surface_context(
            request,
            page_variant='main',
            embedded_surface='home',
        )
        calendar_surface.setdefault('calendar_load_error', False)
        calendar_surface.setdefault('calendar_load_error_title', '')
        calendar_surface.setdefault('calendar_load_error_message', '')
        calendar_surface.setdefault('calendar_load_error_retry_url', '')
        calendar_surface.setdefault('calendar_load_error_retry_label', '')
        calendar_surface.setdefault('calendar_load_error_secondary_url', '')
        calendar_surface.setdefault('calendar_load_error_secondary_label', '')
        return calendar_surface
    except Exception:
        logger.exception(
            '[home surface] calendar provider failed user_id=%s',
            getattr(request.user, 'id', None),
        )
        return _build_home_surface_calendar_fallback(request)


def _build_home_surface_provider_registry(request, *, favorite_products, product_list):
    # Keep provider definitions centralized so the home surface can add/remove cards
    # without reshaping the view contract or touching the templates.
    return (
        HomeSurfaceProviderSpec(
            key='reservation_home_card',
            label='reservation provider',
            fallback_factory=lambda: None,
            builder=lambda: _build_home_surface_reservation_provider(request.user),
        ),
        HomeSurfaceProviderSpec(
            key='developer_chat_home_card',
            label='developer chat provider',
            fallback_factory=lambda: _build_home_surface_developer_chat_card_fallback(request.user),
            builder=lambda: _build_home_surface_developer_chat_provider(request.user),
        ),
        HomeSurfaceProviderSpec(
            key='teacher_buddy',
            label='teacher buddy provider',
            fallback_factory=lambda: {
                'teacher_buddy_panel': None,
                'teacher_buddy_urls': {},
                'teacher_buddy_current_avatar': _build_teacher_buddy_avatar_context_safe(
                    request.user,
                    source='teacher buddy provider registry fallback',
                ),
            },
            builder=lambda: _build_home_surface_teacher_buddy_provider(request.user),
        ),
        HomeSurfaceProviderSpec(
            key='quickdrop_home_card',
            label='quickdrop provider',
            fallback_factory=lambda: None,
            builder=lambda: _build_home_surface_quickdrop_provider(
                request,
                favorite_products=favorite_products,
                product_list=product_list,
            ),
        ),
        HomeSurfaceProviderSpec(
            key='calendar',
            label='calendar provider',
            fallback_factory=lambda: _build_home_surface_calendar_fallback(request),
            builder=lambda: _build_home_surface_calendar_provider(request),
        ),
    )


def _build_home_surface_provider_cards(request, *, favorite_products, product_list):
    provider_values = {}
    for provider_spec in _build_home_surface_provider_registry(
        request,
        favorite_products=favorite_products,
        product_list=product_list,
    ):
        provider_values[provider_spec.key] = _build_home_surface_safe_value(
            request,
            label=provider_spec.label,
            fallback_factory=provider_spec.fallback_factory,
            builder=provider_spec.builder,
        )
    return HomeSurfaceProviderCards.from_mapping(provider_values)


def _build_home_surface_safe_value(request, *, label, fallback_factory, builder):
    try:
        return builder()
    except Exception:
        logger.exception(
            '[home surface] %s failed user_id=%s',
            label,
            getattr(request.user, 'id', None),
        )
        return fallback_factory()


def _build_home_surface_usage_state(request, *, product_list):
    favorite_products = _get_user_favorite_products(request.user, product_list)
    recent_products = _get_recently_used_products(
        request.user,
        product_list,
        exclude_ids={product.id for product in favorite_products},
        limit=4,
    )
    quick_actions = _get_usage_based_quick_actions(request.user, product_list)
    return {
        'favorite_products': favorite_products,
        'recent_products': recent_products,
        'quick_actions': quick_actions,
    }


def _build_home_surface_discovery_state(
    request,
    *,
    product_list,
    favorite_products,
    recent_products,
    quick_actions,
    sections,
    aux_sections,
    games,
):
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
        user=request.user,
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

    representative_slots = _build_home_representative_slots(
        request.user,
        favorite_products=favorite_products,
        recent_products=recent_products,
        quick_actions=quick_actions,
        discovery_products=discovery_products,
        sections=sections,
        aux_sections=aux_sections,
        games=games,
    )
    return {
        'companion_items': companion_items,
        'discovery_products': discovery_products,
        'representative_slots': representative_slots,
    }


def _build_home_surface_mobile_recommend_items(*, representative_recommendations, discovery_items):
    home_mobile_recommend_items = list(representative_recommendations)
    if home_mobile_recommend_items:
        return home_mobile_recommend_items

    return [
        {
            'title': item.get('favorite_title')
            or getattr(item.get('product'), 'public_service_name', '')
            or getattr(item.get('product'), 'title', '')
            or '도구',
            'href': item.get('href', ''),
            'is_external': item.get('is_external', False),
            'reason_label': item.get('section_title') or '추천 도구',
        }
        for item in discovery_items[:4]
        if item.get('href')
    ]


def _build_home_surface_frontend_config(*, favorite_product_ids=()):
    return {
        'toggleFavoriteUrl': reverse('toggle_product_favorite'),
        'listFavoriteUrl': reverse('list_product_favorites'),
        'reorderFavoriteUrl': reverse('reorder_product_favorites'),
        'favoriteProductIds': list(favorite_product_ids or ()),
        'trackUsageUrl': reverse('track_product_usage'),
    }


def build_home_surface_context(
    request,
    *,
    products,
    page_obj,
    pinned_notice_posts,
    feed_scope,
    home_design_version,
):
    product_list = _build_home_surface_safe_value(
        request,
        label='product launch meta',
        fallback_factory=list,
        builder=lambda: _attach_product_launch_meta(list(products), user=request.user),
    )
    section_product_list = [
        product
        for product in product_list
        if str(getattr(product, 'launch_route_name', '') or '').strip().lower() != 'messagebox:main'
    ]
    sections, aux_sections, games = _build_home_surface_safe_value(
        request,
        label='purpose sections',
        fallback_factory=lambda: ([], [], []),
        builder=lambda: get_purpose_sections(
            section_product_list,
            preview_limit=2,
        ),
    )
    primary_display_sections, secondary_display_sections = _build_home_surface_safe_value(
        request,
        label='display groups',
        fallback_factory=lambda: ([], []),
        builder=lambda: _build_home_display_groups(sections, aux_sections),
    )
    home_nav_sections = _build_home_surface_safe_value(
        request,
        label='navigation sections',
        fallback_factory=list,
        builder=lambda: _ensure_home_direct_nav_sections(
            _build_home_nav_sections(
                primary_display_sections,
                secondary_display_sections,
                games,
            ),
            product_list,
        ),
    )
    sns_summary_posts = _build_home_surface_safe_value(
        request,
        label='community summary',
        fallback_factory=list,
        builder=lambda: _build_home_community_summary_posts(
            page_obj,
            pinned_notice_posts=pinned_notice_posts,
            limit=2,
        ),
    )
    sns_preview_posts = _build_home_surface_safe_value(
        request,
        label='community preview',
        fallback_factory=list,
        builder=lambda: _build_sns_preview_posts(
            page_obj,
            pinned_notice_posts=pinned_notice_posts,
            limit=3,
        ),
    )
    community_summary = {
        'title': '실시간 소통',
        'posts': sns_summary_posts,
        'full_url': reverse('community_feed'),
    }

    UserProfile.objects.get_or_create(user=request.user)
    usage_state = _build_home_surface_safe_value(
        request,
        label='usage state',
        fallback_factory=lambda: {
            'favorite_products': [],
            'recent_products': [],
            'quick_actions': [],
        },
        builder=lambda: _build_home_surface_usage_state(
            request,
            product_list=product_list,
        ),
    )
    favorite_products = usage_state['favorite_products']
    recent_products = usage_state['recent_products']
    quick_actions = usage_state['quick_actions']

    discovery_state = _build_home_surface_safe_value(
        request,
        label='discovery state',
        fallback_factory=lambda: {
            'companion_items': [],
            'discovery_products': [],
            'representative_slots': [],
        },
        builder=lambda: _build_home_surface_discovery_state(
            request,
            product_list=product_list,
            favorite_products=favorite_products,
            recent_products=recent_products,
            quick_actions=quick_actions,
            sections=sections,
            aux_sections=aux_sections,
            games=games,
        ),
    )
    companion_items = discovery_state['companion_items']
    discovery_products = discovery_state['discovery_products']

    favorite_items = _build_home_surface_safe_value(
        request,
        label='favorite items',
        fallback_factory=list,
        builder=lambda: _build_product_link_items(
            favorite_products,
            include_section_meta=True,
            user=request.user,
        ),
    )
    quick_action_items = _build_home_surface_safe_value(
        request,
        label='quick action items',
        fallback_factory=list,
        builder=lambda: _build_product_link_items(
            quick_actions,
            include_section_meta=True,
            user=request.user,
        ),
    )
    recent_items = _build_home_surface_safe_value(
        request,
        label='recent items',
        fallback_factory=list,
        builder=lambda: _build_product_link_items(
            recent_products,
            include_section_meta=True,
            user=request.user,
        ),
    )
    discovery_items = _build_home_surface_safe_value(
        request,
        label='discovery items',
        fallback_factory=list,
        builder=lambda: _build_product_link_items(
            discovery_products,
            include_section_meta=True,
            user=request.user,
        ),
    )
    provider_cards = _build_home_surface_provider_cards(
        request,
        favorite_products=favorite_products,
        product_list=product_list,
    )
    schoolcomm_home_card = _build_home_surface_safe_value(
        request,
        label='schoolcomm card',
        fallback_factory=lambda: None,
        builder=lambda: _build_home_schoolcomm_card(
            request.user,
            favorite_products=favorite_products,
            product_list=product_list,
        ),
    )
    representative_slots = discovery_state['representative_slots']
    home_entry_panel = _build_home_surface_safe_value(
        request,
        label='home entry panel',
        fallback_factory=lambda: None,
        builder=lambda: _build_home_entry_panel_context(
            favorite_items=favorite_items,
            representative_slots=representative_slots,
            discovery_items=discovery_items,
            calendar_surface=provider_cards.calendar,
        ),
    )
    representative_recommendations = _build_home_surface_safe_value(
        request,
        label='representative recommendations',
        fallback_factory=list,
        builder=lambda: _build_home_recommendations(
            companion_items,
            discovery_items,
            exclude_ids=(
                {product.id for product in favorite_products}
                | {slot['product'].id for slot in representative_slots}
            ),
            limit=3,
        ),
    )
    home_mobile_calendar_first_enabled = bool(
        getattr(settings, 'HOME_V4_MOBILE_CALENDAR_FIRST_ENABLED', False)
    )
    home_mobile_quick_items = _build_home_surface_safe_value(
        request,
        label='mobile quick items',
        fallback_factory=list,
        builder=lambda: _build_home_mobile_quick_items(
            favorite_products,
            home_nav_sections,
            limit=4,
        ),
    )
    home_mobile_workbench_items = _build_home_surface_safe_value(
        request,
        label='mobile workbench items',
        fallback_factory=list,
        builder=lambda: _filter_home_mobile_workbench_items(favorite_items, limit=4),
    )
    home_mobile_recommend_items = _build_home_surface_mobile_recommend_items(
        representative_recommendations=representative_recommendations,
        discovery_items=discovery_items,
    )
    home_frontend_config = _build_home_surface_frontend_config(
        favorite_product_ids=[product.id for product in favorite_products],
    )
    home_v7_signal_layer = _build_home_v7_agent_signal_layer(provider_cards.calendar)
    home_v7_tacit_registry = _build_home_v7_agent_tacit_registry()
    home_v7_workflow_registry = _build_home_v7_agent_workflow_registry()
    home_v7_agent_workspace = _build_home_v7_context_router_preview(
        request,
        provider_cards.calendar,
        product_list=product_list,
        signal_layer=home_v7_signal_layer,
        tacit_registry=home_v7_tacit_registry,
        workflow_registry=home_v7_workflow_registry,
    )
    home_mobile_section_order = HOME_MOBILE_SECTION_ORDER
    slots = build_home_surface_slots(
        home_nav_sections=home_nav_sections,
        home_mobile_section_order=home_mobile_section_order,
        favorite_items=favorite_items,
        favorite_products=favorite_products,
        recent_items=recent_items,
        home_mobile_workbench_items=home_mobile_workbench_items,
        representative_slots=representative_slots,
        representative_recommendations=representative_recommendations,
        home_mobile_recommend_items=home_mobile_recommend_items,
        discovery_items=discovery_items,
        schoolcomm_home_card=schoolcomm_home_card,
        provider_cards=provider_cards,
        community_summary=community_summary,
        sns_preview_posts=sns_preview_posts,
    )
    action_context = _build_authenticated_home_action_context(
        product_list=product_list,
        favorite_items=favorite_items,
        recent_items=recent_items,
        representative_slots=representative_slots,
        representative_recommendations=representative_recommendations,
        home_entry_panel=home_entry_panel,
        calendar_surface=provider_cards.calendar,
    )
    template_context = build_home_surface_template_context(HomeSurfaceTemplateParts(
        products=products,
        sections=sections,
        aux_sections=aux_sections,
        primary_display_sections=primary_display_sections,
        secondary_display_sections=secondary_display_sections,
        games=games,
        quick_actions=quick_action_items,
        favorite_items=favorite_items,
        recent_items=recent_items,
        discovery_items=discovery_items,
        provider_cards=provider_cards,
        schoolcomm_home_card=schoolcomm_home_card,
        representative_slots=representative_slots,
        representative_recommendations=representative_recommendations,
        home_nav_sections=home_nav_sections,
        home_mobile_section_order=home_mobile_section_order,
        home_mobile_workbench_items=home_mobile_workbench_items,
        home_mobile_recommend_items=home_mobile_recommend_items,
        home_frontend_config=home_frontend_config,
        home_design_version=home_design_version,
        community_summary=community_summary,
        sns_preview_posts=sns_preview_posts,
        home_entry_panel=home_entry_panel,
        page_obj=page_obj,
        pinned_notice_posts=pinned_notice_posts,
        feed_scope=feed_scope,
        home_surface_slots=slots,
        home_user_mode='authenticated',
        home_primary_action=action_context['home_primary_action'],
        home_support_actions=action_context['home_support_actions'],
        home_empty_action_board=action_context['home_empty_action_board'],
        home_locked_sections=action_context['home_locked_sections'],
        sns_compose_prefill=_get_sns_compose_prefill(request),
    ))
    template_context.update(
        build_home_surface_legacy_aliases(
            home_nav_sections=home_nav_sections,
            home_mobile_calendar_first_enabled=home_mobile_calendar_first_enabled,
            home_mobile_quick_items=home_mobile_quick_items,
            home_mobile_workbench_items=home_mobile_workbench_items,
            home_mobile_recommend_items=home_mobile_recommend_items,
            home_frontend_config=home_frontend_config,
            home_v5_mobile_section_order=HOME_V5_MOBILE_SECTION_ORDER,
        )
    )
    template_context.update(provider_cards.teacher_buddy)
    template_context.update({
        'home_v7_signal_layer': home_v7_signal_layer,
        'home_v7_tacit_registry': home_v7_tacit_registry,
        'home_v7_workflow_registry': home_v7_workflow_registry,
        'home_v7_agent_workspace': home_v7_agent_workspace,
    })
    template_context.update(
        _build_home_surface_safe_value(
            request,
            label='student games qr',
            fallback_factory=dict,
            builder=lambda: _build_home_student_games_qr_context(request),
        )
    )
    template_context.update(provider_cards.calendar)
    template_context.update(
        _build_home_surface_safe_value(
            request,
            label='home seo',
            fallback_factory=dict,
            builder=lambda: build_home_page_seo(request).as_context(),
        )
    )
    return {
        'slots': slots.as_dict(),
        'legacy_context': template_context,
    }


def build_guest_home_surface_context(
    request,
    *,
    products,
    page_obj,
    pinned_notice_posts,
    feed_scope,
    home_design_version,
):
    product_list = _build_home_surface_safe_value(
        request,
        label='guest product launch meta',
        fallback_factory=list,
        builder=lambda: _attach_product_launch_meta(list(products), user=request.user),
    )

    section_product_list = [
        product
        for product in product_list
        if str(getattr(product, 'launch_route_name', '') or '').strip().lower() != 'messagebox:main'
    ]
    sections, aux_sections, games = _build_home_surface_safe_value(
        request,
        label='guest purpose sections',
        fallback_factory=lambda: ([], [], []),
        builder=lambda: get_purpose_sections(
            section_product_list,
            preview_limit=2,
        ),
    )
    primary_display_sections, secondary_display_sections = _build_home_surface_safe_value(
        request,
        label='guest display groups',
        fallback_factory=lambda: ([], [], []),
        builder=lambda: _build_home_display_groups(sections, aux_sections),
    )
    sns_summary_posts = _build_home_surface_safe_value(
        request,
        label='guest community summary',
        fallback_factory=list,
        builder=lambda: _build_home_community_summary_posts(
            page_obj,
            pinned_notice_posts=pinned_notice_posts,
            limit=2,
        ),
    )
    sns_preview_posts = _build_home_surface_safe_value(
        request,
        label='guest community preview',
        fallback_factory=list,
        builder=lambda: _build_sns_preview_posts(
            page_obj,
            pinned_notice_posts=pinned_notice_posts,
            limit=3,
        ),
    )
    community_summary = {
        'title': '실시간 소통',
        'posts': sns_summary_posts,
        'full_url': reverse('community_feed'),
    }

    guest_action_context = _build_guest_home_action_context(
        request,
        product_list=product_list,
    )
    login_url = reverse('account_login')
    for product in product_list:
        if _product_requires_guest_login(product):
            launch_href = str(getattr(product, 'launch_href', '') or '').strip()
            product.launch_href = _build_home_login_continue_url(launch_href, login_url=login_url)
            product.launch_is_external = False
    home_nav_sections = _build_home_surface_safe_value(
        request,
        label='guest navigation sections',
        fallback_factory=list,
        builder=lambda: _ensure_home_direct_nav_sections(
            _build_home_nav_sections(
                primary_display_sections,
                secondary_display_sections,
                games,
            ),
            product_list,
        ),
    )
    home_calendar_surface = guest_action_context['home_calendar_surface']
    home_primary_action = guest_action_context['home_primary_action']
    home_support_actions = guest_action_context['home_support_actions']
    home_empty_action_board = guest_action_context['home_empty_action_board']
    home_locked_sections = guest_action_context['home_locked_sections']

    excluded_product_ids = {
        getattr(product, 'id', None)
        for product in product_list
        if getattr(product, 'launch_route_name', '') in {'noticegen:main', 'collect:landing', 'qrgen:landing'}
    }
    representative_slots = _build_home_guest_representative_slots(
        product_list,
        exclude_ids=excluded_product_ids,
        limit=4,
    )
    representative_recommendations = [
        {
            'title': action.get('title') or '도구',
            'href': action.get('href') or '',
            'is_external': bool(action.get('is_external', False)),
            'reason_label': '로그인 후 이어짐',
        }
        for action in home_locked_sections[:3]
        if action.get('href')
    ]

    favorite_items = []
    recent_items = []
    discovery_items = []
    home_mobile_workbench_items = []
    home_mobile_recommend_items = representative_recommendations
    home_frontend_config = _build_home_surface_frontend_config()
    home_mobile_section_order = HOME_MOBILE_SECTION_ORDER
    provider_cards = HomeSurfaceProviderCards(
        quickdrop_home_card=None,
        reservation_home_card=None,
        developer_chat_home_card=None,
        calendar=home_calendar_surface,
        teacher_buddy={},
    )
    slots = build_home_surface_slots(
        home_nav_sections=home_nav_sections,
        home_mobile_section_order=home_mobile_section_order,
        favorite_items=favorite_items,
        favorite_products=[],
        recent_items=recent_items,
        home_mobile_workbench_items=home_mobile_workbench_items,
        representative_slots=representative_slots,
        representative_recommendations=representative_recommendations,
        home_mobile_recommend_items=home_mobile_recommend_items,
        discovery_items=discovery_items,
        schoolcomm_home_card=None,
        provider_cards=provider_cards,
        community_summary=community_summary,
        sns_preview_posts=sns_preview_posts,
    )
    template_context = build_home_surface_template_context(HomeSurfaceTemplateParts(
        products=products,
        sections=sections,
        aux_sections=aux_sections,
        primary_display_sections=primary_display_sections,
        secondary_display_sections=secondary_display_sections,
        games=games,
        quick_actions=[],
        favorite_items=favorite_items,
        recent_items=recent_items,
        discovery_items=discovery_items,
        provider_cards=provider_cards,
        schoolcomm_home_card=None,
        representative_slots=representative_slots,
        representative_recommendations=representative_recommendations,
        home_nav_sections=home_nav_sections,
        home_mobile_section_order=home_mobile_section_order,
        home_mobile_workbench_items=home_mobile_workbench_items,
        home_mobile_recommend_items=home_mobile_recommend_items,
        home_frontend_config=home_frontend_config,
        home_design_version=home_design_version,
        community_summary=community_summary,
        sns_preview_posts=sns_preview_posts,
        home_entry_panel=None,
        page_obj=page_obj,
        pinned_notice_posts=pinned_notice_posts,
        feed_scope=feed_scope,
        home_surface_slots=slots,
        home_user_mode='guest',
        home_primary_action=home_primary_action,
        home_support_actions=home_support_actions,
        home_empty_action_board=home_empty_action_board,
        home_locked_sections=home_locked_sections,
        sns_compose_prefill=_get_sns_compose_prefill(request),
    ))
    template_context.update(
        build_home_surface_legacy_aliases(
            home_nav_sections=home_nav_sections,
            home_mobile_calendar_first_enabled=False,
            home_mobile_quick_items=[],
            home_mobile_workbench_items=home_mobile_workbench_items,
            home_mobile_recommend_items=home_mobile_recommend_items,
            home_frontend_config=home_frontend_config,
            home_v5_mobile_section_order=HOME_V5_MOBILE_SECTION_ORDER,
        )
    )
    template_context.update(home_calendar_surface)
    template_context.update(
        _build_home_surface_safe_value(
            request,
            label='guest home seo',
            fallback_factory=dict,
            builder=lambda: build_home_page_seo(request).as_context(),
        )
    )
    return {
        'slots': slots.as_dict(),
        'legacy_context': template_context,
    }


def _build_home_authenticated_surface_response(
    request,
    products,
    posts,
    page_obj,
    feed_scope,
    pinned_notice_posts,
    *,
    template_name='core/home_authenticated_v4.html',
    home_design_version='v4',
):
    """환경변수로 안전하게 롤아웃하는 인증 홈 공통 응답."""
    home_surface = build_home_surface_context(
        request,
        products=products,
        page_obj=page_obj,
        pinned_notice_posts=pinned_notice_posts,
        feed_scope=feed_scope,
        home_design_version=home_design_version,
    )
    return render(request, template_name, home_surface['legacy_context'])


def _build_home_guest_surface_response(
    request,
    products,
    posts,
    page_obj,
    feed_scope,
    pinned_notice_posts,
    *,
    template_name='core/home_authenticated_v6_canonical.html',
    home_design_version='v6',
):
    home_surface = build_guest_home_surface_context(
        request,
        products=products,
        page_obj=page_obj,
        pinned_notice_posts=pinned_notice_posts,
        feed_scope=feed_scope,
        home_design_version=home_design_version,
    )
    return render(request, template_name, home_surface['legacy_context'])


_build_home_authenticated_v4_response = _build_home_authenticated_surface_response


def _home_v4(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """환경변수로 안전하게 롤아웃하는 인증 홈 V4."""
    return _build_home_authenticated_surface_response(
        request,
        products,
        posts,
        page_obj,
        feed_scope,
        pinned_notice_posts,
        template_name='core/home_authenticated_v4.html',
        home_design_version='v4',
    )


def _home_v5(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """환경변수로 opt-in 미리보기하는 인증 홈 V5."""
    return _build_home_authenticated_surface_response(
        request,
        products,
        posts,
        page_obj,
        feed_scope,
        pinned_notice_posts,
        template_name='core/home_authenticated_v5.html',
        home_design_version='v5',
    )


def _home_v6(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """로그인 홈의 단일 canonical V6 렌더러."""
    return _build_home_authenticated_surface_response(
        request,
        products,
        posts,
        page_obj,
        feed_scope,
        pinned_notice_posts,
        template_name='core/home_authenticated_v6_canonical.html',
        home_design_version='v6',
    )


def _home_guest_v6(request, products, posts, page_obj, feed_scope, pinned_notice_posts):
    """비로그인 홈의 canonical V6 렌더러."""
    return _home_public_v6(
        request,
        products,
        posts,
        page_obj,
        feed_scope,
        pinned_notice_posts,
    )


def home(request):
    feed_scope = _get_post_feed_scope(request)

    # SNS Posts - 모든 사용자에게 제공 (최신순 정렬)
    posts = _build_post_feed_queryset(feed_scope=feed_scope)
    pinned_notice_posts = _build_pinned_notice_queryset(feed_scope=feed_scope)

    # 페이징 처리 (PC 우측 및 모바일 하단 SNS 위젯용)
    paginator = Paginator(posts, 5) # 한 페이지에 5개씩
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # HTMX 요청이면 post_list 영역만 반환
    if request.headers.get('HX-Request'):
        return _render_post_list_partial(
            request,
            page_obj,
            feed_scope,
            pinned_notice_posts=pinned_notice_posts,
        )

    _build_teacher_buddy_avatar_context_safe(
        request.user,
        source='home main request',
    )
    _attach_teacher_buddy_avatar_context_safe(
        getattr(page_obj, 'object_list', []),
        user=request.user,
        label='home main page posts',
    )
    _attach_teacher_buddy_avatar_context_safe(
        pinned_notice_posts,
        user=request.user,
        label='home main pinned notices',
    )
    # 홈 전체 렌더가 아닐 때는 서비스 런처용 제품 목록이 필요 없다.
    products = prime_service_launcher_products(
        request,
        filter_discoverable_products(
            Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
        ),
    )

    if request.user.is_authenticated:
        return _home_v6(request, products, posts, page_obj, feed_scope, pinned_notice_posts)

    return _home_guest_v6(request, products, posts, page_obj, feed_scope, pinned_notice_posts)


def community_feed(request):
    feed_scope = _get_post_feed_scope(request)
    if not request.headers.get('HX-Request'):
        home_url = reverse('home')
        if feed_scope == POST_FEED_SCOPE_NOTICE:
            home_url = f"{home_url}?feed_scope={POST_FEED_SCOPE_NOTICE}"
        return redirect(f"{home_url}#home-community-section")

    posts = _build_post_feed_queryset(feed_scope=feed_scope)
    paginator = Paginator(posts, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return _render_post_list_partial(request, page_obj, feed_scope)


@login_required
def dashboard(request):
    return redirect('home')

@login_required
def post_create(request):
    if request.method != 'POST':
        return redirect('home')

    if _rate_limit_exceeded('post_create', request.user.id, [(60, 1), (3600, 5), (86400, 12)]):
        return _post_create_error_response(
            request,
            '게시글은 1분 1개, 1시간 5개, 하루 12개까지 작성할 수 있어요.',
            status=429,
        )

    content = request.POST.get('content')
    image = request.FILES.get('image')
    submit_kind = (request.POST.get('submit_kind') or 'general').strip().lower()
    post_type = 'notice' if request.user.is_staff and submit_kind == 'notice' else 'general'
    is_notice_pinned = (
        request.user.is_staff
        and post_type == 'notice'
        and _is_truthy(request.POST.get('pin_notice_to_top'))
    )
    allow_notice_dismiss = is_notice_pinned and _is_truthy(request.POST.get('allow_notice_dismiss'))

    if image:
        MAX_SIZE = 10 * 1024 * 1024
        ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

        if image.size > MAX_SIZE:
            return _post_create_error_response(request, '이미지 크기는 10MB 이하만 가능합니다.')

        if image.content_type not in ALLOWED_TYPES:
            return _post_create_error_response(
                request,
                '허용되지 않는 파일 형식입니다. (JPEG, PNG, GIF, WebP만 가능)',
            )

        try:
            img = Image.open(image)
            img.verify()
            image.seek(0)
        except Exception:
            return _post_create_error_response(request, '올바른 이미지 파일이 아닙니다.')

    if not (content or image):
        return _post_create_error_response(request, '내용이나 이미지를 하나는 넣어 주세요.')

    post = Post.objects.create(
        author=request.user,
        content=content,
        image=image,
        post_type=post_type,
        is_notice_pinned=is_notice_pinned,
        allow_notice_dismiss=allow_notice_dismiss,
    )
    sns_reward_payload = record_teacher_buddy_sns_reward(request.user, post)

    if request.headers.get('HX-Request'):
        feed_scope = _get_post_feed_scope(request)
        posts = _build_post_feed_queryset(feed_scope=feed_scope)
        paginator = Paginator(posts, 5)
        page_obj = paginator.get_page(1)
        response = _render_post_list_partial(request, page_obj, feed_scope)
        if sns_reward_payload:
            response['HX-Trigger'] = json.dumps({'teacherBuddy:snsReward': sns_reward_payload})
        return response

    if sns_reward_payload:
        level = messages.success if sns_reward_payload.get('reward_granted') else messages.info
        level(request, sns_reward_payload.get('message') or '메이트 상태를 확인했어요.')
    return redirect('home')


@login_required
@require_POST
def toggle_pinned_notice_expanded(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.pinned_notice_expanded = _is_truthy(request.POST.get('expanded'))
    profile.save(update_fields=['pinned_notice_expanded'])

    if profile.pinned_notice_expanded:
        messages.success(request, '고정 공지를 펼쳐서 볼게요.')
    else:
        messages.success(request, '고정 공지를 제목만 보이게 접어둘게요.')

    return redirect(get_safe_next_url(request, fallback=reverse('home')))


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
        _attach_teacher_buddy_avatar_context_safe(
            [post],
            user=request.user,
            label='post like partial',
        )
        return render(
            request,
            'core/partials/post_item.html',
            {
                'post': post,
                'surface_variant': _get_post_surface_variant(request),
            },
        )
        
    return redirect('home')

@login_required
def comment_create(request, pk):
    post = _resolve_post_for_action(pk, request.user)
    if post is None:
        return HttpResponse("Not found", status=404)

    if request.method == 'POST':
        content = (request.POST.get('content') or '').strip()
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

        if not content:
            if request.headers.get('HX-Request'):
                return HttpResponse("댓글 내용을 먼저 입력해 주세요.", status=400)
            messages.error(request, '댓글 내용을 먼저 입력해 주세요.')
            return redirect('home')

        Comment.objects.create(
            post=post,
            author=request.user,
            content=content
        )
            
    if request.headers.get('HX-Request'):
        _attach_teacher_buddy_avatar_context_safe(
            [post],
            user=request.user,
            label='comment create partial',
        )
        return render(
            request,
            'core/partials/post_item.html',
            {
                'post': post,
                'surface_variant': _get_post_surface_variant(request),
            },
        )
        
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
    surface_variant = _get_post_surface_variant(request)
    
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
                form_error_message = '이미지 크기는 10MB 이하만 가능합니다.'
                messages.error(request, form_error_message)
                return render(
                    request,
                    'core/partials/post_edit_form.html',
                    {
                        'post': post,
                        'form_error_message': form_error_message,
                        'surface_variant': surface_variant,
                    },
                )

            if image.content_type not in ALLOWED_TYPES:
                form_error_message = '허용되지 않는 파일 형식입니다. JPEG, PNG, GIF, WebP만 올릴 수 있어요.'
                messages.error(request, form_error_message)
                return render(
                    request,
                    'core/partials/post_edit_form.html',
                    {
                        'post': post,
                        'form_error_message': form_error_message,
                        'surface_variant': surface_variant,
                    },
                )

            try:
                img = Image.open(image)
                img.verify()
                image.seek(0)
                post.image = image
            except Exception:
                form_error_message = '올바른 이미지 파일이 아닙니다.'
                messages.error(request, form_error_message)
                return render(
                    request,
                    'core/partials/post_edit_form.html',
                    {
                        'post': post,
                        'form_error_message': form_error_message,
                        'surface_variant': surface_variant,
                    },
                )

        if not (content or '').strip():
            form_error_message = '게시글 내용을 먼저 입력해 주세요.'
            return render(
                request,
                'core/partials/post_edit_form.html',
                {
                    'post': post,
                    'form_error_message': form_error_message,
                    'surface_variant': surface_variant,
                },
            )

        post.content = content
        post.save()
        # Return the updated post item (expanded)
        _attach_teacher_buddy_avatar_context_safe(
            [post],
            user=request.user,
            label='post edit partial',
        )
        return render(
            request,
            'core/partials/post_item.html',
            {
                'post': post,
                'is_first': True,
                'surface_variant': surface_variant,
            },
        )
            
    # GET: Return the edit form
    return render(
        request,
        'core/partials/post_edit_form.html',
        {
            'post': post,
            'surface_variant': surface_variant,
        },
    )

@login_required
def post_detail_partial(request, pk):
    """Helper view to return the read-only post item (e.g. for Cancel button)"""
    post = _resolve_post_for_action(pk, request.user)
    if post is None:
        return HttpResponse("Not found", status=404)
    # Force expansion when returning from edit mode
    _attach_teacher_buddy_avatar_context_safe(
        [post],
        user=request.user,
        label='post detail partial',
    )
    return render(
        request,
        'core/partials/post_item.html',
        {
            'post': post,
            'is_first': True,
            'surface_variant': _get_post_surface_variant(request),
        },
    )

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
    surface_variant = _get_post_surface_variant(request)
    
    # Only author can edit
    if comment.author != request.user:
        return HttpResponse("Unauthorized", status=403)
        
    if request.method == 'POST':
        content = (request.POST.get('content') or '').strip()
        if content:
            comment.content = content
            comment.save()
            return render(
                request,
                'core/partials/comment_item.html',
                {
                    'comment': comment,
                    'surface_variant': surface_variant,
                },
            )
        return render(
            request,
            'core/partials/comment_edit_form.html',
            {
                'comment': comment,
                'form_error_message': '댓글 내용을 먼저 입력해 주세요.',
                'surface_variant': surface_variant,
            },
        )
            
    # GET: Return the edit form
    return render(
        request,
        'core/partials/comment_edit_form.html',
        {
            'comment': comment,
            'surface_variant': surface_variant,
        },
    )

@login_required
def comment_item_partial(request, pk):
    """Helper view to return the read-only comment item"""
    comment = get_object_or_404(Comment, pk=pk)
    return render(
        request,
        'core/partials/comment_item.html',
        {
            'comment': comment,
            'surface_variant': _get_post_surface_variant(request),
        },
    )


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
        return render(
            request,
            'core/partials/comment_item.html',
            {
                'comment': comment,
                'surface_variant': _get_post_surface_variant(request),
            },
        )

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
        'description': '학급 캘린더와 학급 운영 도구처럼 매일 쓰는 흐름을 먼저 보여줍니다.',
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
    return redirect(SERVICE_GUIDE_PADLET_URL)


def about(request):
    # Stats could be dynamic later
    stats = {
        'lecture_hours': 120, # Placeholder
        'tools_built': Product.objects.count() + 5, # Approx
        'students': 500, # Placeholder
    }
    return render(
        request,
        'core/about.html',
        {
            'stats': stats,
            **build_about_page_seo(request).as_context(),
        },
    )

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
    buddy_settings = _build_teacher_buddy_settings_context_safe(
        request.user,
        source='settings view',
    )
    developer_chat_home_card = _build_home_surface_developer_chat_provider(request.user)
    if buddy_settings:
        buddy_settings = {
            **buddy_settings,
            'share_url': f"{SITE_CANONICAL_BASE_URL}{buddy_settings['share_path']}",
            'share_image_url': f"{SITE_CANONICAL_BASE_URL}{buddy_settings['share_image_path']}",
            'share_title': f"{profile.nickname or request.user.username}님의 교실 메이트",
            'admin_shortcuts': _build_teacher_buddy_admin_shortcuts(request.user),
        }
    
    return render(
        request,
        'core/settings.html',
        {
            'form': form,
            'profile': profile,
            'teacher_buddy_settings': buddy_settings,
            'teacher_buddy_urls': build_teacher_buddy_urls() if buddy_settings else {},
            'teacher_buddy_current_avatar': _build_teacher_buddy_avatar_context_safe(
                request.user,
                source='settings view',
            ),
            'developer_chat_home_card': developer_chat_home_card,
            'kakao_js_key': getattr(settings, 'KAKAO_JS_KEY', ''),
        },
    )


@require_GET
def teacher_buddy_profile_sheet(request, public_share_token):
    try:
        share_context = build_teacher_buddy_public_share_context(public_share_token)
    except TeacherBuddyError:
        return HttpResponse("Not found", status=404)

    return render(
        request,
        'core/partials/teacher_buddy_profile_sheet.html',
        {
            'share_context': share_context,
        },
    )


@require_GET
def teacher_buddy_share_page(request, public_share_token):
    try:
        share_context = build_teacher_buddy_public_share_context(public_share_token)
    except TeacherBuddyError:
        return HttpResponse("Not found", status=404)

    seo = PageSeoMeta(
        title=f"{share_context['nickname']}님의 교실 메이트 | Eduitit",
        description=share_context['buddy']['share_caption'],
        canonical_url=share_context['share_url'],
        og_title=f"{share_context['nickname']}님의 교실 메이트",
        og_description=share_context['share_copy_text'],
        og_image=share_context['share_image_url'],
    )
    return render(
        request,
        'core/teacher_buddy_share.html',
        {
            'share_context': share_context,
            **seo.as_context(),
        },
    )


@require_GET
def teacher_buddy_share_image(request, public_share_token):
    try:
        share_context = build_teacher_buddy_public_share_context(public_share_token)
    except TeacherBuddyError:
        return HttpResponse("Not found", status=404)

    response = HttpResponse(
        build_teacher_buddy_share_svg(share_context),
        content_type='image/svg+xml; charset=utf-8',
    )
    response['Content-Disposition'] = f'inline; filename="eduitit-buddy-{share_context["buddy"]["key"]}.svg"'
    response['Cache-Control'] = 'public, max-age=300'
    return response

@login_required
def select_role(request):
    """역할 선택 및 닉네임 설정 화면"""
    policy_redirect_url = get_pending_policy_consent_redirect(
        request,
        next_url=request.get_full_path(),
    )
    if policy_redirect_url:
        return redirect(policy_redirect_url)

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


@login_not_required
def social_signup_consent_view(request):
    sociallogin = get_pending_social_signup(request)
    if not sociallogin:
        clear_current_social_signup_consent(getattr(request, 'session', None))
        return redirect('account_login')

    if has_current_social_signup_consent(getattr(request, 'session', None)):
        return redirect('socialaccount_signup')

    provider = getattr(getattr(sociallogin, 'account', None), 'provider', '') or 'direct'
    form = SocialSignupConsentForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        mark_current_social_signup_consent(
            request.session,
            provider=provider,
            marketing_email_opt_in=form.cleaned_data.get('marketing_email_opt_in'),
        )
        return redirect('socialaccount_signup')

    policy_meta = get_policy_meta()
    return render(
        request,
        'core/social_signup_consent.html',
        {
            'form': form,
            'policy_meta': policy_meta,
            'provider': provider,
            'provider_label': get_provider_label(provider),
            'next_url': get_social_signup_consent_redirect_url(),
            'terms_url': f"{reverse('policy')}#terms",
            'privacy_url': f"{reverse('policy')}#privacy",
            'operations_url': f"{reverse('policy')}#operations",
            'hide_navbar': True,
        },
    )

@login_required
def update_email(request):
    """
    기존 사용자 이메일 및 닉네임 업데이트
    - 이메일이나 프로필 정보가 부족한 사용자에게 필무 정보 입력 요구
    """
    policy_redirect_url = get_pending_policy_consent_redirect(
        request,
        next_url=request.get_full_path(),
    )
    if policy_redirect_url:
        return redirect(policy_redirect_url)

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
            messages.error(request, '사용하실 닉네임을 입력해주세요.')
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
        logout(request)
        user.delete()
        messages.success(request, '그동안 이용해주셔서 감사합니다. 계정이 안전하게 삭제되었습니다.')
        return redirect('home')
    
    return render(request, 'core/delete_account.html')


@login_required
def admin_dashboard_view(request):
    """superuser 전용 활동/방문자 대시보드"""
    if not request.user.is_superuser:
        messages.error(request, '관리자만 접근 가능합니다.')
        return redirect('home')

    from .utils import (
        get_daily_visitor_count,
        get_product_usage_source_stats,
        get_top_page_views,
        get_top_product_usage,
        get_unique_visitor_count,
        get_visitor_stats,
        get_weekly_stats,
    )
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
    
    # Total unique counts
    total_count = get_unique_visitor_count()
    human_total_count = get_unique_visitor_count(exclude_bots=True)
    bot_total_count = total_count - human_total_count

    # Today's unique counts
    today_count = get_daily_visitor_count(target_date=today)
    today_human_count = get_daily_visitor_count(target_date=today, exclude_bots=True)
    today_bot_count = today_count - today_human_count

    # Weekly/Monthly start dates
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Weekly/Monthly unique counts
    week_count = get_unique_visitor_count(start_date=week_start)
    week_human_count = get_unique_visitor_count(start_date=week_start, exclude_bots=True)
    
    month_count = get_unique_visitor_count(start_date=month_start)
    month_human_count = get_unique_visitor_count(start_date=month_start, exclude_bots=True)

    # Detailed stats (Humans only for the chart)
    daily_stats = get_visitor_stats(30, exclude_bots=True)
    weekly_stats = get_weekly_stats(8, exclude_bots=True)
    top_page_views = get_top_page_views(
        days=ADMIN_ACTIVITY_WINDOW_DAYS,
        exclude_bots=True,
        limit=8,
    )
    top_product_launches = get_top_product_usage(
        days=ADMIN_ACTIVITY_WINDOW_DAYS,
        limit=8,
    )
    product_source_stats = get_product_usage_source_stats(days=ADMIN_ACTIVITY_WINDOW_DAYS)

    # Chart max value
    max_daily = max((s['count'] for s in daily_stats), default=1) or 1
    max_weekly = max((s['count'] for s in weekly_stats), default=1) or 1

    product_by_route = {
        str(getattr(product, 'launch_route_name', '') or '').strip(): product
        for product in Product.objects.filter(is_active=True).exclude(launch_route_name='')
    }
    product_ids = [row['product_id'] for row in top_product_launches if row.get('product_id')]
    product_by_id = {
        product.id: product
        for product in Product.objects.filter(pk__in=product_ids)
    }
    top_page_rows = [
        {
            **row,
            'display_name': _get_admin_dashboard_page_name(
                row.get('path', ''),
                row.get('route_name', ''),
                product_by_route,
            ),
        }
        for row in top_page_views
    ]
    source_label_map = dict(ProductUsageLog.SOURCE_CHOICES)
    top_product_rows = []
    for row in top_product_launches:
        product = product_by_id.get(row.get('product_id'))
        top_product_rows.append(
            {
                **row,
                'display_name': _get_public_product_name(product) if product is not None else row.get('product__title') or '서비스',
            }
        )
    product_source_rows = [
        {
            **row,
            'display_name': source_label_map.get(row.get('source'), row.get('source') or '기타'),
        }
        for row in product_source_stats
    ]
    
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
        'max_weekly': max_weekly,
        'activity_window_days': ADMIN_ACTIVITY_WINDOW_DAYS,
        'top_page_views': top_page_rows,
        'top_product_launches': top_product_rows,
        'product_source_stats': product_source_rows,
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
    return redirect(SERVICE_GUIDE_PADLET_URL)

def service_guide_detail(request, pk):
    return redirect(SERVICE_GUIDE_PADLET_URL)


@require_POST
def track_product_usage(request):
    """서비스 사용 기록 API (로그인 사용자 전용)."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'ignored'}, status=200)

    data = _request_payload_data(request)
    if not data:
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
    payload = {'status': 'ok'}
    if action == 'launch':
        try:
            award_teacher_activity(
                request.user,
                category=ACTIVITY_CATEGORY_SERVICE_USE,
                source_key=f"product:{product.id}",
                occurred_at=timezone.now(),
                related_object=product,
                metadata={"source": source, "action": action},
            )
        except Exception:
            logger.exception(
                "teacher activity service_use award failed user_id=%s product_id=%s source=%s",
                request.user.id,
                product.id,
                source,
            )
    buddy_payload = record_teacher_buddy_progress(request.user, product, source)
    if buddy_payload:
        payload['buddy'] = buddy_payload
    return JsonResponse(payload)


@require_POST
@login_required
def home_agent_preview(request):
    data = _request_payload_data(request)
    mode_key = str(data.get('mode_key') or '').strip()
    text = str(data.get('text') or '').strip()
    selected_date_label = str(data.get('selected_date_label') or '').strip()
    preferred_provider = str(data.get('provider') or '').strip()
    context_payload = data.get('context') if isinstance(data.get('context'), dict) else {}

    if not mode_key:
        return JsonResponse({'error': 'mode_key required'}, status=400)
    if not text:
        return JsonResponse({'error': 'text required'}, status=400)

    try:
        payload = generate_home_agent_preview(
            mode_key=mode_key,
            text=text,
            selected_date_label=selected_date_label,
            preferred_provider=preferred_provider,
            context=context_payload,
            request=request,
        )
    except HomeAgentConfigError as exc:
        return JsonResponse({'error': str(exc)}, status=503)
    except HomeAgentProviderError as exc:
        status_code = 400 if str(exc) in {'지원하지 않는 agent 모드입니다.', '내용을 먼저 입력해 주세요.'} else 503
        return JsonResponse({'error': str(exc)}, status=status_code)

    return JsonResponse({
        'status': 'ok',
        'preview': payload.get('preview', {}),
        'execution': payload.get('execution', {}),
        'message': payload.get('message', ''),
        'provider': payload.get('provider', ''),
        'model': payload.get('model', ''),
    })


@require_GET
@login_required
def home_agent_conversations(request):
    conversations = _build_home_v7_agent_conversations(request)
    return JsonResponse({
        'status': 'ok',
        'conversations': conversations,
        'rail_section': {
            'key': 'rooms',
            'label': conversations.get('title') or '끼리끼리 채팅방',
            'items': conversations.get('items') or (),
        },
    })


@require_POST
@login_required
def home_agent_execute(request):
    data = _request_payload_data(request)
    mode_key = str(data.get('mode_key') or '').strip()
    action_data = data.get('data') if isinstance(data.get('data'), dict) else {}

    if not mode_key:
        return JsonResponse({'error': 'mode_key required'}, status=400)

    mode_spec = get_home_agent_runtime_spec(mode_key)
    if mode_spec is None:
        return JsonResponse({'error': '지원하지 않는 agent 모드입니다.'}, status=400)

    try:
        payload = execute_service_action(
            request=request,
            mode_key=mode_key,
            mode_spec=mode_spec,
            data=action_data,
        )
    except HomeAgentExecutionError as exc:
        return JsonResponse(
            {
                'error': str(exc),
                'field_errors': getattr(exc, 'field_errors', {}) or {},
            },
            status=getattr(exc, 'status_code', 400),
        )

    return JsonResponse({
        'status': 'ok',
        'preview': payload.get('preview', {}),
        'message': payload.get('message', ''),
        'provider': payload.get('provider', ''),
        'model': payload.get('model', ''),
    })


@require_POST
@login_required
def teacher_buddy_draw(request):
    try:
        payload = draw_teacher_buddy(request.user)
    except TeacherBuddyError as exc:
        if _request_prefers_json(request):
            return JsonResponse({'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return _teacher_buddy_redirect_response(request)

    if _request_prefers_json(request):
        return JsonResponse(payload)

    messages.success(request, payload['message'])
    return _teacher_buddy_redirect_response(request)


@require_POST
@login_required
def teacher_buddy_redeem_coupon_view(request):
    data = _request_payload_data(request)
    coupon_code = str(data.get('coupon_code', '') or '').strip()
    try:
        payload = redeem_teacher_buddy_coupon(request.user, coupon_code)
    except TeacherBuddyError as exc:
        if _request_prefers_json(request):
            return JsonResponse({'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return _teacher_buddy_settings_redirect_response()

    if _request_prefers_json(request):
        return JsonResponse(payload)

    messages.success(request, payload['message'])
    return _teacher_buddy_settings_redirect_response()


@require_POST
@login_required
def teacher_buddy_select_view(request):
    data = _request_payload_data(request)
    buddy_key = str(data.get('buddy_key', '') or '').strip()
    skin_key = str(data.get('skin_key', '') or '').strip()
    try:
        payload = select_teacher_buddy(request.user, buddy_key, skin_key)
    except TeacherBuddyError as exc:
        if _request_prefers_json(request):
            return JsonResponse({'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return _teacher_buddy_settings_redirect_response()

    if _request_prefers_json(request):
        return JsonResponse(payload)

    messages.success(request, payload['message'])
    return _teacher_buddy_settings_redirect_response()


@require_POST
@login_required
def teacher_buddy_select_profile_view(request):
    data = _request_payload_data(request)
    buddy_key = str(data.get('buddy_key', '') or '').strip()
    skin_key = str(data.get('skin_key', '') or '').strip()
    try:
        payload = select_teacher_buddy_profile(request.user, buddy_key, skin_key)
    except TeacherBuddyError as exc:
        if _request_prefers_json(request):
            return JsonResponse({'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return _teacher_buddy_settings_redirect_response()

    if _request_prefers_json(request):
        return JsonResponse(payload)

    messages.success(request, payload['message'])
    return _teacher_buddy_settings_redirect_response()


@require_POST
@login_required
def teacher_buddy_unlock_skin_view(request):
    data = _request_payload_data(request)
    buddy_key = str(data.get('buddy_key', '') or '').strip()
    skin_key = str(data.get('skin_key', '') or '').strip()
    try:
        payload = unlock_teacher_buddy_skin(request.user, buddy_key, skin_key)
    except TeacherBuddyError as exc:
        if _request_prefers_json(request):
            return JsonResponse({'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return _teacher_buddy_settings_redirect_response()

    if _request_prefers_json(request):
        return JsonResponse(payload)

    messages.success(request, payload['message'])
    return _teacher_buddy_settings_redirect_response()


@require_POST
@login_required
def toggle_product_favorite(request):
    """서비스 즐겨찾기 토글 API."""
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
        href, is_external = _resolve_product_launch_url(product, user=request.user)
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
            ),
            user=request.user,
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
    return JsonResponse({'status': 'ok'})


def database_health_check(request):
    from django.db import connection
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        logger.exception("Health check DB connection failed: %s", e)
        return JsonResponse({'status': 'error', 'db': 'unavailable'}, status=503)
