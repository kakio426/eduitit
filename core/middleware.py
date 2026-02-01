from .models import VisitorLog
from django.utils import timezone

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Exclude static, media, and admin paths to reduce DB load
        if not any(request.path.startswith(p) for p in ['/static/', '/media/', '/admin/', '/favicon.ico']):
            ip = get_client_ip(request)
            today = timezone.localdate()
            
            # Check session to avoid DB hit on every request for the same user session
            if not request.session.get('vh_recorded_date') == str(today):
                try:
                    # Try to create a log entry for this IP and date
                    VisitorLog.objects.get_or_create(ip_address=ip, visit_date=today)
                    # Mark session as recorded for today
                    request.session['vh_recorded_date'] = str(today)
                except Exception:
                    # Fail silently to avoid 500 errors on tracking
                    pass
        
        response = self.get_response(request)
        return response
