from .models import VisitorLog
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
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


class EmailRequiredMiddleware:
    """
    기존 가입자 중 이메일이 없는 사용자에게 이메일 입력 요구
    - 로그인 상태 && 이메일 없음 → 이메일 입력 페이지로 리다이렉트
    - 특정 경로는 예외 처리 (무한 루프 방지)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 로그인한 사용자이면서 이메일이 없는 경우
        if request.user.is_authenticated and not request.user.email:
            # 예외 경로 (이 경로들은 이메일 없이도 접근 가능)
            allowed_paths = [
                '/accounts/logout/',
                '/update-email/',  # 이메일 업데이트 페이지 자체
                '/admin/',  # 관리자 페이지
                '/static/',  # 정적 파일
                '/media/',   # 미디어 파일
            ]

            # 현재 경로가 예외 경로가 아니면 이메일 입력 페이지로 리다이렉트
            if not any(request.path.startswith(path) for path in allowed_paths):
                return redirect('update_email')

        response = self.get_response(request)
        return response
