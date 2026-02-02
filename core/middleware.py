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
            already_recorded = request.session.get(session_key, False)

            # DEBUG: print statement to check if middleware is running
            print(f"[VISITOR DEBUG] Path: {request.path} | IP: {ip} | Already recorded: {already_recorded}")
            logger.info(f"[VISITOR] Path: {request.path} | IP: {ip} | Already recorded: {already_recorded}")

            if not already_recorded:
                try:
                    # Use get_or_create to avoid duplicates for the same IP on the same day
                    obj, created = VisitorLog.objects.get_or_create(ip_address=ip, visit_date=today)
                    request.session[session_key] = True
                    print(f"[VISITOR DEBUG] DB operation - Created: {created} | IP: {ip} | Date: {today}")
                    logger.info(f"[VISITOR] DB operation - Created: {created} | IP: {ip} | Date: {today}")
                except Exception as e:
                    print(f"[VISITOR DEBUG] Error: {e}")
                    logger.error(f"[VISITOR] Error: {e}", exc_info=True)

        response = self.get_response(request)
        return response
