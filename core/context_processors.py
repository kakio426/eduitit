from .models import VisitorLog
from django.utils import timezone
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
