from .models import SiteConfig
from .utils import get_daily_visitor_count, get_unique_visitor_count
from .active_classroom import (
    get_active_classroom_for_request,
    get_default_classroom_for_user,
    list_hs_classrooms_for_user,
)
from .product_visibility import filter_discoverable_products
from .service_launcher import build_service_launcher_items
from .seo import (
    DEFAULT_HOME_TITLE_KO,
    SITE_NAME,
    SITE_NAME_KO,
    SITE_WORDMARK,
    build_default_page_seo,
)
from django.utils import timezone
from django.contrib import messages as django_messages
import json
import logging

logger = logging.getLogger(__name__)

REQUEST_CACHE_MISS = object()
SERVICE_LAUNCHER_PRODUCTS_ATTR = "_eduitit_service_launcher_products"
SITE_CONFIG_REQUEST_ATTR = "_eduitit_site_config"
SERVICE_LAUNCHER_DISABLED_PREFIXES = (
    "/admin/",
    "/secret-admin-kakio/",
    "/admin-dashboard/",
    "/health/",
)
SITE_CONFIG_DISABLED_PREFIXES = (
    "/admin/",
    "/secret-admin-kakio/",
    "/admin-dashboard/",
    "/health/",
)

TOAST_TAG_MAP = {
    'debug': 'info',
    'info': 'info',
    'success': 'success',
    'warning': 'warning',
    'error': 'danger',
}


def _path_matches_prefixes(request, prefixes):
    path = str(getattr(request, "path", "") or "")
    return any(path.startswith(prefix) for prefix in prefixes)


def prime_service_launcher_products(request, products):
    setattr(request, SERVICE_LAUNCHER_PRODUCTS_ATTR, products)
    return products

def visitor_counts(request):
    """
    Returns visitor count context variables.
    Cached for performance could be added here later if needed.
    """
    is_superuser = bool(
        getattr(request, 'user', None)
        and request.user.is_authenticated
        and request.user.is_superuser
    )

    if not is_superuser:
        return {
            'show_visitor_counts': False,
            'today_visitor_count': 0,
            'total_visitor_count': 0,
        }

    try:
        today = timezone.localdate()
        today_count = get_daily_visitor_count(target_date=today, exclude_bots=True)
        total_count = get_unique_visitor_count(exclude_bots=True)

        logger.debug(f"Visitor counts - Today: {today_count}, Total: {total_count}")

        return {
            'show_visitor_counts': True,
            'today_visitor_count': today_count,
            'total_visitor_count': total_count
        }
    except Exception as e:
        logger.error(f"Error fetching visitor counts: {e}", exc_info=True)
        return {
            'show_visitor_counts': False,
            'today_visitor_count': 0,
            'total_visitor_count': 0
        }


def toast_messages(request):
    """
    Django messages framework를 활용한 toast 데이터 제공.
    각 메시지를 tag(success/danger/info/warning)와 함께 직렬화하여 Alpine.js에서 사용.
    """
    toast_list = []
    for message in django_messages.get_messages(request):
        toast_list.append({
            'message': str(message),
            'tag': TOAST_TAG_MAP.get(message.tags.split()[-1] if message.tags else 'info', 'info'),
        })
    return {'toast_messages': toast_list}


def site_config(request):
    """SiteConfig 싱글톤에서 배너 데이터를 전역 제공."""
    pinned_notice_expanded = False
    if getattr(request, 'user', None) and request.user.is_authenticated:
        try:
            pinned_notice_expanded = bool(request.user.userprofile.pinned_notice_expanded)
        except Exception:
            pinned_notice_expanded = False

    if _path_matches_prefixes(request, SITE_CONFIG_DISABLED_PREFIXES):
        return {
            'banner_text': '',
            'banner_active': False,
            'banner_color': '#7c3aed',
            'banner_link': '',
            'pinned_notice_expanded': pinned_notice_expanded,
            'notebook_manual_url': '',
        }

    try:
        config = getattr(request, SITE_CONFIG_REQUEST_ATTR, REQUEST_CACHE_MISS)
        if config is REQUEST_CACHE_MISS:
            config = SiteConfig.load()
            setattr(request, SITE_CONFIG_REQUEST_ATTR, config)
        return {
            'banner_text': config.banner_text,
            'banner_active': config.banner_active,
            'banner_color': config.banner_color,
            'banner_link': config.banner_link,
            'pinned_notice_expanded': pinned_notice_expanded,
            'notebook_manual_url': getattr(config, 'notebook_manual_url', ''),
        }
    except Exception:
        return {
            'banner_text': '',
            'banner_active': False,
            'banner_color': '#7c3aed',
            'banner_link': '',
            'pinned_notice_expanded': pinned_notice_expanded,
            'notebook_manual_url': '',
        }


def search_products(request):
    """글로벌 서비스 런처용 서비스 목록 JSON 제공."""
    from django.conf import settings as django_settings
    if not getattr(django_settings, 'GLOBAL_SEARCH_ENABLED', True):
        return {}

    if _path_matches_prefixes(request, SERVICE_LAUNCHER_DISABLED_PREFIXES):
        return {}

    from products.models import Product

    try:
        products = getattr(request, SERVICE_LAUNCHER_PRODUCTS_ATTR, REQUEST_CACHE_MISS)
        if products is REQUEST_CACHE_MISS:
            products = filter_discoverable_products(
                Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
            )
            setattr(request, SERVICE_LAUNCHER_PRODUCTS_ATTR, products)
        items = build_service_launcher_items(products, user=getattr(request, "user", None))
        return {'service_launcher_json': json.dumps(items, ensure_ascii=False)}
    except Exception:
        logger.exception("[ServiceLauncher] payload build failed")
        return {'service_launcher_json': '[]'}


def seo_meta(request):
    """기본 SEO/OpenGraph 메타태그 제공."""
    default_meta = build_default_page_seo(request)
    return {
        'brand_site_name': SITE_NAME,
        'brand_site_name_ko': SITE_NAME_KO,
        'brand_wordmark': SITE_WORDMARK,
        'brand_nav_wordmark': SITE_NAME_KO,
        'brand_home_title_ko': DEFAULT_HOME_TITLE_KO,
        'default_og_title': default_meta.title,
        'default_og_description': default_meta.description,
        'default_og_image': default_meta.og_image,
        'page_title': default_meta.title,
        'meta_description': default_meta.description,
        'canonical_url': default_meta.canonical_url,
        'og_title': default_meta.og_title,
        'og_description': default_meta.og_description,
        'og_url': default_meta.canonical_url,
        'og_image': default_meta.og_image,
        'og_type': default_meta.og_type,
        'robots': default_meta.robots,
        'structured_data_json_scripts': default_meta.as_context().get('structured_data_json_scripts', []),
    }


def active_classroom(request):
    """세션에서 현재 학급 정보를 모든 템플릿에 제공."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'active_classroom': None,
            'default_classroom_id': None,
            'has_hs_classrooms': False,
            'hs_classrooms_json': [],
            'hs_classrooms_payload': '[]',
            'active_classroom_name_payload': 'null',
        }

    classroom = None
    default_classroom_id = None
    classrooms_data = []
    try:
        classroom = get_active_classroom_for_request(request)
        default_classroom = get_default_classroom_for_user(request.user)
        if default_classroom:
            default_classroom_id = str(default_classroom.pk)

        qs = list_hs_classrooms_for_user(request.user)
        classrooms_data = [
            {
                'id': str(c.pk),
                'name': c.name,
                'is_default': str(c.pk) == default_classroom_id,
            }
            for c in qs
        ]
    except Exception:
        logger.exception(
            "[ActiveClassroom] 학급 컨텍스트 구성 실패 user_id=%s",
            getattr(request.user, 'id', None),
        )
    return {
        'active_classroom': classroom,
        'default_classroom_id': default_classroom_id,
        'has_hs_classrooms': bool(classrooms_data),
        'hs_classrooms_json': classrooms_data,
        'hs_classrooms_payload': json.dumps(classrooms_data, ensure_ascii=False),
        'active_classroom_name_payload': json.dumps(classroom.name if classroom else None, ensure_ascii=False),
    }
