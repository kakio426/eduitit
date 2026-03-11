from .models import VisitorLog, SiteConfig
from .active_classroom import (
    get_active_classroom_for_request,
    get_default_classroom_for_user,
    list_hs_classrooms_for_user,
)
from .product_visibility import filter_discoverable_products
from .service_launcher import build_service_launcher_items
from django.utils import timezone
from django.contrib import messages as django_messages
import logging

logger = logging.getLogger(__name__)

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
        today_count = VisitorLog.objects.filter(visit_date=today).count()
        total_count = VisitorLog.objects.count()

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
    각 메시지를 tag(success/error/info/warning)와 함께 직렬화하여 Alpine.js에서 사용.
    """
    TAG_MAP = {
        'debug': 'info',
        'info': 'info',
        'success': 'success',
        'warning': 'warning',
        'error': 'error',
    }
    toast_list = []
    for message in django_messages.get_messages(request):
        toast_list.append({
            'message': str(message),
            'tag': TAG_MAP.get(message.tags.split()[-1] if message.tags else 'info', 'info'),
        })
    return {'toast_messages': toast_list}


def site_config(request):
    """SiteConfig 싱글톤에서 배너 데이터를 전역 제공."""
    try:
        config = SiteConfig.load()
        return {
            'banner_text': config.banner_text,
            'banner_active': config.banner_active,
            'banner_color': config.banner_color,
            'banner_link': config.banner_link,
            'notebook_manual_url': getattr(config, 'notebook_manual_url', ''),
        }
    except Exception:
        return {
            'banner_text': '',
            'banner_active': False,
            'banner_color': '#7c3aed',
            'banner_link': '',
            'notebook_manual_url': '',
        }


def search_products(request):
    """글로벌 서비스 런처용 서비스 목록 JSON 제공."""
    from django.conf import settings as django_settings
    if not getattr(django_settings, 'GLOBAL_SEARCH_ENABLED', True):
        return {}

    from products.models import Product
    import json

    try:
        products = filter_discoverable_products(
            Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
        )
        items = build_service_launcher_items(products)
        return {'service_launcher_json': json.dumps(items, ensure_ascii=False)}
    except Exception:
        logger.exception("[ServiceLauncher] payload build failed")
        return {'service_launcher_json': '[]'}


def seo_meta(request):
    """
    기본 OpenGraph 메타태그 제공.
    각 앱 view에서 context로 override 가능:
      return render(request, 'template.html', {
          'og_title': '커스텀 타이틀',
          'og_description': '커스텀 설명',
      })
    """
    return {
        'default_og_title': 'Eduitit - 선생님의 스마트한 하루',
        'default_og_description': 'AI 프롬프트 레시피, 도구 가이드, 교육용 게임까지. 교실에서의 혁신을 지금 시작하세요.',
        'default_og_image': 'https://eduitit.site/static/images/eduitit_og.png',
        'og_url': request.build_absolute_uri(),
    }


def active_classroom(request):
    """세션에서 현재 학급 정보를 모든 템플릿에 제공."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'active_classroom': None,
            'default_classroom_id': None,
            'has_hs_classrooms': False,
            'hs_classrooms_json': [],
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
    }
