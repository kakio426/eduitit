from .models import VisitorLog
from django.utils import timezone

def visitor_counts(request):
    """
    Returns visitor count context variables.
    Cached for performance could be added here later if needed.
    """
    try:
        today = timezone.localdate()
        today_count = VisitorLog.objects.filter(visit_date=today).count()
        # total_count = VisitorLog.objects.count() # This is row count (daily unique hits sum)
        
        # Or if we want total unique IPs ever:
        # total_count = VisitorLog.objects.values('ip_address').distinct().count()
        
        # Let's stick to "Cumulative Visits" (Sum of daily uniques) as it looks better (bigger number)
        total_count = VisitorLog.objects.count()
        
        return {
            'today_visitor_count': today_count,
            'total_visitor_count': total_count
        }
    except Exception:
        return {
            'today_visitor_count': 0,
            'total_visitor_count': 0
        }
