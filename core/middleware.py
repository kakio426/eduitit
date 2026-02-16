import logging
import time
import uuid
from urllib.parse import quote

from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .logging_filters import clear_current_request_id, set_current_request_id
from .models import VisitorLog

logger = logging.getLogger(__name__)


class BlockKnownProbePathsMiddleware:
    """
    Block common WordPress probe paths that are irrelevant for this Django app.
    Keeps scanners out of app logic and visitor tracking DB writes.
    """

    BLOCKED_EXACT = {"/wp-login.php", "/xmlrpc.php"}
    BLOCKED_PREFIXES = ("/wordpress/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path in self.BLOCKED_EXACT or any(path.startswith(p) for p in self.BLOCKED_PREFIXES):
            logger.info("[PROBE_BLOCK] path=%s ip=%s", path, get_client_ip(request) or "0.0.0.0")
            return HttpResponseNotFound()
        return self.get_response(request)


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = uuid.uuid4().hex[:12]
        set_current_request_id(request_id)
        request.request_id = request_id

        start = time.perf_counter()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            path = getattr(request, 'path', '')
            if not any(path.startswith(p) for p in ['/static/', '/media/']):
                status_code = getattr(response, 'status_code', 500)
                logger.info(
                    '[REQUEST] rid=%s method=%s path=%s status=%s latency_ms=%s',
                    request_id,
                    request.method,
                    path,
                    status_code,
                    latency_ms,
                )
            clear_current_request_id()

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

            logger.info(f"[VISITOR] Path: {request.path} | IP: {ip} | Already recorded: {already_recorded}")

            if not already_recorded:
                try:
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    
                    # Common bot keywords
                    bot_keywords = [
                        'bot', 'spider', 'crawler', 'slurp', 'mediapartners', 'uptime',
                        'lighthouse', 'search', 'facebookexternalhit', 'pinterest',
                        'gptbot', 'chatgpt', 'yandex', 'naver', 'yeti'
                    ]
                    is_bot = any(keyword in user_agent.lower() for keyword in bot_keywords)

                    # Use update_or_create to save user_agent and is_bot if it already exists, 
                    # but typically it shouldn't hit this if already_recorded works correctly.
                    obj, created = VisitorLog.objects.get_or_create(
                        ip_address=ip, 
                        visit_date=today,
                        defaults={
                            'user_agent': user_agent,
                            'is_bot': is_bot
                        }
                    )
                    request.session[session_key] = True
                    logger.info(f"[VISITOR] DB operation - Created: {created} | IP: {ip} | Bot: {is_bot} | Date: {today}")
                except Exception as e:
                    logger.error(f"[VISITOR] Error: {e}", exc_info=True)

        response = self.get_response(request)
        return response


class OnboardingMiddleware:
    """
    모든 가입자(소셜 로그인 포함)가 이메일과 닉네임을 반드시 갖도록 강제하는 미들웨어.
    - 로그인 상태인데 이메일이 없거나, 닉네임이 기본값(userXX)인 경우 
    - 정보 입력 페이지로 리다이렉트합니다.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        if request.user.is_authenticated:
            profile = getattr(request.user, 'userprofile', None)
            
            # 이메일이 없거나, 닉네임이 없거나, 닉네임이 여전히 'user'로 시작하는 자동생성된 것이라면
            needs_onboarding = (
                not request.user.email or 
                not profile or 
                not profile.nickname or 
                profile.nickname.startswith('user')
            )

            if needs_onboarding:
                # AJAX 요청이나 API 경로는 리다이렉트 하지 않음 (JSON 응답을 기대하므로)
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
                is_api = request.path.startswith('/api/') or '/api/' in request.path
                
                if is_ajax or is_api:
                    return self.get_response(request)

                allowed_paths = [
                    '/accounts/',
                    '/update-email/',
                    '/delete-account/',
                    '/admin/',
                    '/secret-admin-kakio/',
                    '/static/',
                    '/media/',
                ]
                allowed_paths.extend(getattr(settings, 'ONBOARDING_EXEMPT_PATH_PREFIXES', []))

                if not any(request.path.startswith(path) for path in allowed_paths):
                    return redirect(f"{reverse('update_email')}?next={quote(request.get_full_path())}")

        response = self.get_response(request)
        return response


class MaintenanceModeMiddleware:
    """
    점검 모드를 관리하는 미들웨어.
    - settings.MAINTENANCE_MODE가 True인 경우 작동합니다.
    - 관리자(is_superuser)는 점검 중에도 모든 페이지에 접근 가능합니다.
    - 일반 사용자는 모든 요청 시 점검 페이지로 이동하거나 점검 템플릿을 보게 됩니다.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.shortcuts import render

        # 점검 모드 스위치가 켜져 있는지 확인
        is_maintenance = getattr(settings, 'MAINTENANCE_MODE', False)
        
        if is_maintenance:
            # 관리자(내 계정)는 점검 중에도 사이트를 볼 수 있어야 함
            if request.user.is_authenticated and request.user.is_superuser:
                return self.get_response(request)

            # 관리자 페이지 접근은 허용 (로그인해야 하니까)
            if any(request.path.startswith(p) for p in ['/admin/', '/secret-admin-kakio/', '/accounts/login/']):
                return self.get_response(request)

            # 정적 파일 접근 허용
            if any(request.path.startswith(p) for p in ['/static/', '/media/']):
                return self.get_response(request)

            # 그 외 모든 사용자는 점검 페이지 렌더링
            return render(request, 'core/maintenance.html', {'hide_navbar': True}, status=503)

        return self.get_response(request)
