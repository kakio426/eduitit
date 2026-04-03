import hashlib
import logging
import time
import uuid
from urllib.parse import quote

from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .logging_filters import clear_current_request_id, set_current_request_id
from .models import SiteConfig, VisitorLog
from .openclo_login import OPENCLO_LOGIN_URL
from .policy_consent import has_current_policy_consent, user_requires_policy_consent

logger = logging.getLogger(__name__)

PUBLIC_ACCESS_PATH_PREFIXES = ("/portfolio/",)
PUBLIC_ACCESS_EXACT_PATHS = {"/portfolio"}
LIGHTWEIGHT_BYPASS_PREFIXES = ("/health/",)
ADMIN_SURFACE_PREFIXES = ("/admin/", "/secret-admin-kakio/", "/admin-dashboard/")
VISITOR_TRACKING_EXCLUDED_PREFIXES = (
    "/static/",
    "/media/",
    "/favicon.ico",
    *ADMIN_SURFACE_PREFIXES,
    *LIGHTWEIGHT_BYPASS_PREFIXES,
)
SITE_CONFIG_REQUEST_ATTR = "_eduitit_site_config"
REQUEST_CACHE_MISS = object()
VISITOR_IDENTITY_SESSION_KEY = "visitor_identity"


def is_public_access_path(path):
    return path in PUBLIC_ACCESS_EXACT_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_ACCESS_PATH_PREFIXES)


def is_lightweight_bypass_path(path):
    return any(path.startswith(prefix) for prefix in LIGHTWEIGHT_BYPASS_PREFIXES)


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


def is_probable_bot(user_agent):
    bot_keywords = [
        'bot', 'spider', 'crawler', 'slurp', 'mediapartners', 'uptime',
        'lighthouse', 'search', 'facebookexternalhit', 'pinterest',
        'gptbot', 'chatgpt', 'yandex', 'naver', 'yeti'
    ]
    normalized_user_agent = (user_agent or "").lower()
    return any(keyword in normalized_user_agent for keyword in bot_keywords)


def get_or_create_session_visitor_id(request):
    session = getattr(request, "session", None)
    if session is None:
        return uuid.uuid4().hex

    visitor_id = session.get(VISITOR_IDENTITY_SESSION_KEY)
    if visitor_id:
        return visitor_id

    visitor_id = uuid.uuid4().hex
    session[VISITOR_IDENTITY_SESSION_KEY] = visitor_id
    return visitor_id


def build_visitor_identity(request, *, ip, is_bot):
    if is_bot:
        return {
            "identity_type": VisitorLog.IDENTITY_BOT,
            "visitor_key": f"bot:{ip}",
            "session_visitor_key": None,
            "user": None,
        }

    session_visitor_key = f"session:{get_or_create_session_visitor_id(request)}"
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return {
            "identity_type": VisitorLog.IDENTITY_USER,
            "visitor_key": f"user:{user.pk}",
            "session_visitor_key": session_visitor_key,
            "user": user,
        }

    return {
        "identity_type": VisitorLog.IDENTITY_SESSION,
        "visitor_key": session_visitor_key,
        "session_visitor_key": session_visitor_key,
        "user": None,
    }


def build_visitor_session_key(today, visitor_key):
    digest = hashlib.sha256(visitor_key.encode("utf-8")).hexdigest()[:12]
    return f"visitor_recorded_{today.isoformat()}_{digest}"


def migrate_today_session_log_to_user(*, today, session_visitor_key, user_visitor_key, user, ip, user_agent):
    if not session_visitor_key or session_visitor_key == user_visitor_key:
        return

    session_log = (
        VisitorLog.objects
        .filter(visit_date=today, visitor_key=session_visitor_key, is_bot=False)
        .first()
    )
    if not session_log:
        return

    existing_user_log = (
        VisitorLog.objects
        .filter(visit_date=today, visitor_key=user_visitor_key)
        .first()
    )
    if existing_user_log:
        session_log.delete()
        return existing_user_log

    session_log.visitor_key = user_visitor_key
    session_log.identity_type = VisitorLog.IDENTITY_USER
    session_log.user = user
    session_log.ip_address = ip
    session_log.user_agent = user_agent
    session_log.save(update_fields=["visitor_key", "identity_type", "user", "ip_address", "user_agent"])
    return session_log

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Consent public signer flow: do not store IP/User-Agent in visitor logs.
        if request.path.startswith('/consent/public/') or is_lightweight_bypass_path(request.path):
            return self.get_response(request)

        # Exclude static, media, and admin paths to reduce DB load
        if not any(request.path.startswith(p) for p in VISITOR_TRACKING_EXCLUDED_PREFIXES):
            ip = get_client_ip(request)
            if not ip:
                ip = '0.0.0.0' # Fallback for unknown IPs

            today = timezone.localdate()
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            is_bot = is_probable_bot(user_agent)
            identity = build_visitor_identity(request, ip=ip, is_bot=is_bot)
            session_key = build_visitor_session_key(today, identity["visitor_key"])
            session = getattr(request, "session", None)
            already_recorded = bool(session and session.get(session_key, False))

            logger.info(f"[VISITOR] Path: {request.path} | IP: {ip} | Already recorded: {already_recorded}")

            if not already_recorded:
                try:
                    if identity["identity_type"] == VisitorLog.IDENTITY_USER:
                        migrate_today_session_log_to_user(
                            today=today,
                            session_visitor_key=identity["session_visitor_key"],
                            user_visitor_key=identity["visitor_key"],
                            user=identity["user"],
                            ip=ip,
                            user_agent=user_agent,
                        )

                    obj, created = VisitorLog.objects.update_or_create(
                        visit_date=today,
                        visitor_key=identity["visitor_key"],
                        defaults={
                            'ip_address': ip,
                            'user': identity["user"],
                            'visitor_key': identity["visitor_key"],
                            'identity_type': identity["identity_type"],
                            'user_agent': user_agent,
                            'is_bot': is_bot,
                        }
                    )
                    if session is not None:
                        session[session_key] = True
                    logger.info(
                        "[VISITOR] DB operation - Created: %s | VisitorKey: %s | Identity: %s | IP: %s | Bot: %s | Date: %s",
                        created,
                        identity["visitor_key"],
                        identity["identity_type"],
                        ip,
                        is_bot,
                        today,
                    )
                except Exception as e:
                    logger.error(f"[VISITOR] Error: {e}", exc_info=True)

        response = self.get_response(request)
        return response


class PolicyConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_lightweight_bypass_path(request.path):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return self.get_response(request)

        if is_public_access_path(request.path):
            return self.get_response(request)

        if not user_requires_policy_consent(request.user):
            return self.get_response(request)

        if has_current_policy_consent(request.user, request.session):
            return self.get_response(request)

        consent_path = reverse('policy_consent')
        allowed_prefixes = [
            consent_path,
            reverse('policy'),
            '/accounts/logout/',
            '/delete-account/',
            '/admin/',
            '/secret-admin-kakio/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]
        if any(request.path.startswith(prefix) for prefix in allowed_prefixes):
            return self.get_response(request)

        redirect_url = f"{consent_path}?next={quote(request.get_full_path())}"

        if request.path.startswith('/api/') or '/api/' in request.path:
            return JsonResponse(
                {
                    'error': 'policy_consent_required',
                    'redirect_url': redirect_url,
                },
                status=403,
            )

        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = redirect_url
            return response

        return redirect(redirect_url)


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

        if is_lightweight_bypass_path(request.path):
            return self.get_response(request)

        if request.user.is_authenticated:
            if is_public_access_path(request.path):
                return self.get_response(request)

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

    @staticmethod
    def _get_site_config(request):
        config = getattr(request, SITE_CONFIG_REQUEST_ATTR, REQUEST_CACHE_MISS)
        if config is not REQUEST_CACHE_MISS:
            return config

        try:
            config = SiteConfig.load()
        except Exception:
            config = None

        setattr(request, SITE_CONFIG_REQUEST_ATTR, config)
        return config

    def _is_site_config_maintenance_enabled(self, request):
        config = self._get_site_config(request)
        return bool(getattr(config, "maintenance_mode", False))

    def __call__(self, request):
        from django.conf import settings
        from django.shortcuts import render

        if is_lightweight_bypass_path(request.path):
            return self.get_response(request)

        # 점검 스위치 우선순위:
        # 1) 환경변수 MAINTENANCE_MODE (기존 방식 유지)
        # 2) 관리자 SiteConfig.maintenance_mode (운영 편의)
        is_maintenance = bool(getattr(settings, 'MAINTENANCE_MODE', False))
        if not is_maintenance:
            is_maintenance = self._is_site_config_maintenance_enabled(request)
        
        if is_maintenance:
            # 관리자(내 계정)는 점검 중에도 사이트를 볼 수 있어야 함
            if request.user.is_authenticated and request.user.is_superuser:
                return self.get_response(request)

            # 관리자 페이지 접근은 허용 (로그인해야 하니까)
            if any(request.path.startswith(p) for p in ['/admin/', '/secret-admin-kakio/', '/accounts/login/', OPENCLO_LOGIN_URL]):
                return self.get_response(request)

            # 정적 파일 접근 허용
            if any(request.path.startswith(p) for p in ['/static/', '/media/']):
                return self.get_response(request)

            # 그 외 모든 사용자는 점검 페이지 렌더링
            return render(request, 'core/maintenance.html', {'hide_navbar': True}, status=503)

        return self.get_response(request)
