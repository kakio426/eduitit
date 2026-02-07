from .models import VisitorLog, SiteConfig
from django.utils import timezone
from django.contrib import messages as django_messages
import logging

logger = logging.getLogger(__name__)

def visitor_counts(request):
    """
    Returns visitor count context variables.
    Cached for performance could be added here later if needed.
    """
    try:
        today = timezone.localdate()
        today_count = VisitorLog.objects.filter(visit_date=today).count()
        total_count = VisitorLog.objects.count()

        logger.debug(f"Visitor counts - Today: {today_count}, Total: {total_count}")

        return {
            'today_visitor_count': today_count,
            'total_visitor_count': total_count
        }
    except Exception as e:
        logger.error(f"Error fetching visitor counts: {e}", exc_info=True)
        return {
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
        }
    except Exception:
        return {
            'banner_text': '',
            'banner_active': False,
            'banner_color': '#7c3aed',
            'banner_link': '',
        }


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
