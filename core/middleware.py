from .models import VisitorLog
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
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
            if not ip:
                ip = '0.0.0.0' # Fallback for unknown IPs

            today = timezone.localdate()

            # Check session to avoid DB hit on every request
            session_key = f'visitor_recorded_{today}'
            if not request.session.get(session_key):
                try:
                    # Use get_or_create to avoid duplicates for the same IP on the same day
                    obj, created = VisitorLog.objects.get_or_create(ip_address=ip, visit_date=today)
                    request.session[session_key] = True
                    if created:
                        logger.info(f"New visitor recorded: {ip} on {today}")
                except Exception as e:
                    logger.error(f"VisitorLog Error: {e}", exc_info=True)

        response = self.get_response(request)
        return response
