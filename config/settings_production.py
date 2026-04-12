"""
Django Production Settings for Render + Neon deployment.

This settings module extends the base settings and configures:
- PostgreSQL via DATABASE_URL (Neon)
- WhiteNoise for static files
- Security settings for production
"""

import os
import sys
import dj_database_url
from pathlib import Path
from importlib.util import find_spec
from django.core.exceptions import ImproperlyConfigured
from config.database import apply_database_network_overrides, normalize_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

TESTING = 'test' in sys.argv

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

# SECURITY WARNING: keep the secret key used in production secret!
# Render blueprint uses SECRET_KEY, while older local tooling may still set DJANGO_SECRET_KEY.
SECRET_KEY = (
    (os.environ.get('SECRET_KEY') or '').strip()
    or (os.environ.get('DJANGO_SECRET_KEY') or '').strip()
)
if not SECRET_KEY:
    if TESTING:
        SECRET_KEY = 'test-only-production-secret-key'
    else:
        raise ImproperlyConfigured(
            'Production SECRET_KEY is missing. Set SECRET_KEY or DJANGO_SECRET_KEY before starting config.settings_production.'
        )

# Allowed hosts
env_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [h.strip() for h in env_hosts if h.strip()]
ALLOWED_HOSTS.extend([
    '.onrender.com', 
    '.railway.app', 
    '.up.railway.app',
    'eduitit.site', 
    'www.eduitit.site', 
    'localhost', 
    '127.0.0.1'
])

# Kakao API Key
KAKAO_JS_KEY = os.environ.get('KAKAO_JS_KEY')

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://*.railway.app',
    'https://*.up.railway.app',
    'https://eduitit.site',
    'https://www.eduitit.site',
]

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    'cloudinary_storage',
    'cloudinary',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sitemaps',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'products.apps.ProductsConfig',
    'insights.apps.InsightsConfig',
    'portfolio.apps.PortfolioConfig',
    'autoarticle.apps.AutoarticleConfig',
    'fortune.apps.FortuneConfig',
    'ssambti.apps.SsambtiConfig',  # Teachable Zoo MBTI (쌤BTI)
    'signatures.apps.SignaturesConfig',
    'consent.apps.ConsentConfig',
    'artclass.apps.ArtclassConfig',
    'chess.apps.ChessConfig',
    'janggi.apps.JanggiConfig',
    'fairy_games.apps.FairyGamesConfig',
    'reflex_game.apps.ReflexGameConfig',
    'ppobgi.apps.PpobgiConfig',
    'studentmbti.apps.StudentmbtiConfig',
    'collect.apps.CollectConfig',
    'handoff.apps.HandoffConfig',
    'qrgen.apps.QrgenConfig',
    'hwpxchat.apps.HwpxchatConfig',
    'encyclopedia.apps.EncyclopediaConfig',
    'version_manager.apps.VersionManagerConfig',
    'happy_seed.apps.HappySeedConfig',
    'seed_quiz.apps.SeedQuizConfig',
    'noticegen.apps.NoticegenConfig',
    'timetable.apps.TimetableConfig',
    'classcalendar.apps.ClasscalendarConfig',
    'messagebox.apps.MessageboxConfig',
    'schoolcomm.apps.SchoolcommConfig',
    'quickdrop.apps.QuickdropConfig',
    'ocrdesk.apps.OcrdeskConfig',
    'textbooks.apps.TextbooksConfig',
    'textbook_ai.apps.TextbookAiConfig',
    'edu_materials.apps.EduMaterialsConfig',
    'edu_materials_next.apps.EduMaterialsNextConfig',
    'channels',
    'django_htmx',
    'django.contrib.humanize',
    'reservations.apps.ReservationsConfig',
    'parentcomm.apps.ParentcommConfig',
    'docviewer.apps.DocviewerConfig',
    'slidesmith.apps.SlidesmithConfig',
    'blockclass.apps.BlockclassConfig',
    'infoboard.apps.InfoboardConfig',
    'teacher_law.apps.TeacherLawConfig',
    'schoolprograms.apps.SchoolprogramsConfig',

    # Auth & Allauth
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.kakao',
    'allauth.socialaccount.providers.naver',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # WhiteNoise for static files
    'core.middleware.RequestIDMiddleware',
    'csp.middleware.CSPMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Allauth middleware
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    # Custom Middleware
    'core.middleware.MaintenanceModeMiddleware',  # 점검 모드 (제일 위쪽 처리가 좋음)
    'core.middleware.PolicyConsentMiddleware',  # 소셜 로그인 사용자 약관 동의 필수
    'core.middleware.OnboardingMiddleware',  # 모든 사용자 정보 입력 필수
    'core.middleware.BlockKnownProbePathsMiddleware',
    'core.middleware.SeoMetaFallbackMiddleware',
    'core.middleware.VisitorTrackingMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                # Custom Context Processors
                'core.context_processors.visitor_counts',
                'core.context_processors.toast_messages',
                'core.context_processors.site_config',
                'core.context_processors.seo_meta',
                'core.context_processors.search_products',
                'core.context_processors.active_classroom',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if TESTING or not REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        }
    }

# =============================================================================
# DATABASE - PostgreSQL via Neon (DATABASE_URL)
# =============================================================================

# Use DATABASE_URL environment variable (Neon PostgreSQL)
# Fallback to SQLite for local development without DATABASE_URL
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    import re
    DATABASE_URL = normalize_database_url(DATABASE_URL)
    safe_db_url = re.sub(r':([^:@]+)@', ':****@', DATABASE_URL)

    try:
        default_db = dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
        default_db = apply_database_network_overrides(default_db, DATABASE_URL)
        DATABASES = {
            'default': default_db
        }
        hostaddr = (default_db.get('OPTIONS') or {}).get('hostaddr')
        if hostaddr:
            print(f"[DATABASE] Using PostgreSQL with IPv4 hostaddr={hostaddr}")
    except ValueError as e:
        raise ValueError(f"DATABASE_URL 파싱 실패: {safe_db_url} (원인: {e})")
else:
    # Fallback for local development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Neon PostgreSQL(PgBouncer) 호환: 서버사이드 커서 비활성화
DISABLE_SERVER_SIDE_CURSORS = True

# =============================================================================
# CACHE - Django DB Cache (worker간 공유, Redis 불필요)
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache_table",
    }
}

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================
# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'ko-kr'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_TZ = True

# =============================================================================
# STATIC FILES & MEDIA DEFINITIONS (MOVED TO BOTTOM FOR ENFORCEMENT)
# =============================================================================

# WhiteNoise configuration
# STATICFILES_STORAGE is deprecated in favor of STORAGES['staticfiles']

# =============================================================================
# MEDIA FILES
# =============================================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Static definitions moved to the bottom of the file for enforcement.

# =============================================================================
# CLOUDINARY SETTINGS
# =============================================================================
from urllib.parse import urlparse

cloudinary_url = os.environ.get('CLOUDINARY_URL', '')
cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
api_key = os.environ.get('CLOUDINARY_API_KEY', '')
api_secret = os.environ.get('CLOUDINARY_API_SECRET', '')

print("[CLOUDINARY] Production environment check")
print(f"CLOUDINARY_URL: {'SET' if cloudinary_url else '[X] NOT SET'}")
print(f"CLOUDINARY_CLOUD_NAME: {cloud_name if cloud_name else '[X] NOT SET'}")
print(f"CLOUDINARY_API_KEY: {api_key[:4] + '...' if api_key else '[X] NOT SET'}")
print(f"CLOUDINARY_API_SECRET: {'SET' if api_secret else '[X] NOT SET'}")

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': cloud_name,
    'API_KEY': api_key,
    'API_SECRET': api_secret,
}

if cloudinary_url:
    try:
        parsed = urlparse(cloudinary_url)
        # 1. Start with parsed values if individual ones aren't provided
        if not CLOUDINARY_STORAGE['CLOUD_NAME']: CLOUDINARY_STORAGE['CLOUD_NAME'] = parsed.hostname or ''
        if not CLOUDINARY_STORAGE['API_KEY']: CLOUDINARY_STORAGE['API_KEY'] = parsed.username or ''
        if not CLOUDINARY_STORAGE['API_SECRET']: CLOUDINARY_STORAGE['API_SECRET'] = parsed.password or ''
    except Exception:
        pass


# Initialize Cloudinary library
if CLOUDINARY_STORAGE.get('CLOUD_NAME') and CLOUDINARY_STORAGE.get('API_KEY'):
    try:
        import cloudinary
        cloudinary.config(
            cloud_name=CLOUDINARY_STORAGE['CLOUD_NAME'],
            api_key=CLOUDINARY_STORAGE['API_KEY'],
            api_secret=CLOUDINARY_STORAGE['API_SECRET'],
            secure=True
        )
        USE_CLOUDINARY = True
        DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

    except Exception as e:
        USE_CLOUDINARY = False
else:
    USE_CLOUDINARY = False
    # Local storage is already set in the global block above.

print(f"[CLOUDINARY] USE_CLOUDINARY = {USE_CLOUDINARY}")

# =============================================================================
# AUTHENTICATION
# =============================================================================

LOGIN_REDIRECT_URL = 'select_role'
LOGOUT_REDIRECT_URL = 'home'

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth Settings
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGIN_METHODS = {'email', 'username'}
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_EMAIL_VERIFICATION = 'none'  # ✅ 이메일 인증 선택 (필수 아님)
ACCOUNT_SIGNUP_FORM_CLASS = 'core.signup_forms.CustomSignupForm'
ACCOUNT_SESSION_REMEMBER = False  # 기본적으로 자동 로그인 해제 (보안을 위해)
ACCOUNT_RATE_LIMITS = {
    'login_failed': '10/m/ip,5/300s/key',
}
SESSION_COOKIE_AGE = 21600  # 내부 세션 정책값
SESSION_SAVE_EVERY_REQUEST = False  # 매 요청마다 DB write 방지 (성능 개선)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # 브라우저 닫으면 로그아웃
SOCIALACCOUNT_AUTO_SIGNUP = False  # ✅ 소셜 로그인 후 추가 정보(별명) 입력 화면 표시
SOCIALACCOUNT_LOGIN_ON_GET = True # ✅ 중간 페이지 없이 바로 소셜 로그인창으로 이동
SOCIALACCOUNT_ADAPTER = 'core.socialaccount_adapter.EduititSocialAccountAdapter'

# SSO Settings
SSO_JWT_SECRET = os.environ.get('SSO_JWT_SECRET', SECRET_KEY)
SCHOOLIT_URL = os.environ.get('SCHOOLIT_URL', 'https://schoolit.shop') # 실주소로 변경 권장

# Allauth Protocol
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'  # ✅ HTTPS 강제 (네이버/카카오 필수)
SOCIALACCOUNT_QUERY_EMAIL = True  # 네이버에서 이메일 요청

# Allauth Provider Settings
SOCIALACCOUNT_PROVIDERS = {
    'kakao': {
        'APP': {
            'client_id': os.environ.get('KAKAO_CLIENT_ID', ''),
            'secret': os.environ.get('KAKAO_CLIENT_SECRET', ''),  # settings.py와 동일하게 통일
            'key': ''
        }
    },
    'naver': {
        'APP': {
            'client_id': os.environ.get('NAVER_CLIENT_ID', ''),
            'secret': os.environ.get('NAVER_CLIENT_SECRET', ''),  # settings.py와 동일하게 통일
            'key': ''
        }
    }
}

# 키 누락 시 로그 출력
import logging
logger = logging.getLogger(__name__)

if not SOCIALACCOUNT_PROVIDERS['naver']['APP']['client_id']:
    logger.warning("NAVER_CLIENT_ID is not set in environment variables!")
if not SOCIALACCOUNT_PROVIDERS['kakao']['APP']['client_id']:
    logger.warning("KAKAO_CLIENT_ID is not set in environment variables!")

# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# SECURITY HEADERS (Production)
# =============================================================================

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

    # Required for Railway to prevent infinite redirect loops
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Security settings for HTTPS
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1년
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Cookie security (Django defaults이지만 명시)
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True         # HTMX는 쿠키가 아닌 헤더로 CSRF 전송
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'

# =============================================================================
# CONTENT SECURITY POLICY (CSP)
# =============================================================================

# CSP 설정 (django-csp)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",  # 인라인 스크립트 허용 (템플릿 내 스크립트)
    "'unsafe-eval'",    # marked.js 등 라이브러리용
    "https://cdn.tailwindcss.com",  # Tailwind CSS CDN
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",
    "https://unpkg.com",
    "https://t1.kakaocdn.net",
    "https://developers.kakao.com",
    "https://html2canvas.hertzen.com",
    "blob:", # Web Worker용
)
CSP_WORKER_SRC = ("'self'", "blob:", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://unpkg.com")
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",
    "https://fonts.googleapis.com",
    "https://unpkg.com",
    "https://hangeul.pstatic.net",
)
CSP_FONT_SRC = (
    "'self'",
    "https:",
    "data:",
    "https://fonts.gstatic.com",
    "https://cdnjs.cloudflare.com",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com",
    "https://hangeul.pstatic.net",
)
CSP_IMG_SRC = (
    "'self'",
    "data:",
    "blob:",
    "https:",
    "https://k.kakaocdn.net", # Kakao profile/assets
    "https://*.kakaocdn.net",
)
CSP_CONNECT_SRC = (
    "'self'",
    "ws:",
    "wss:",
    "https://api.padlet.com",
    "https://generativelanguage.googleapis.com",
    "https://cdn.jsdelivr.net",        # JS source maps
    "https://*.kakao.com",             # Kakao APIs
    "blob:",                           # Stockfish Worker
    "https://raw.githubusercontent.com", # Chess pieces
)

CSP_FRAME_SRC = (
    "'self'",
    "https://padlet.com",
    "https://*.kakao.com",
)
CSP_MEDIA_SRC = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'", "https://sharer.kakao.com")

# Admin 경로는 CSP 제외 (정적 파일 차단 방지)
CSP_EXCLUDE_URL_PREFIXES = ("/secret-admin-kakio/",)

# =============================================================================
# AUTO-FIX: Sync Site Domain with Production Host
# =============================================================================

def sync_site_domain():
    """DB의 Site 도메인을 커스텀 도메인(eduitit.site)으로 동기화합니다."""
    try:
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()

        # 커스텀 도메인 우선 사용 (railway.app이 아닌 실제 서비스 도메인)
        production_domain = 'eduitit.site'
        env_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
        for host in env_hosts:
            host = host.strip()
            # railway.app이 아닌 커스텀 도메인이 있으면 그것을 사용
            if host and 'railway.app' not in host and 'onrender.com' not in host and host not in ('localhost', '127.0.0.1'):
                production_domain = host
                break

        if current_site.domain != production_domain:
            current_site.domain = production_domain
            current_site.name = "Eduitit Production"
            current_site.save()

    except Exception:
        pass

def run_startup_tasks():
    # keep this hook lightweight; ensure_* runs in bootstrap_runtime
    sync_site_domain()

# 서버 실행 시 자동 실행
import threading
if os.environ.get('RUN_MAIN') != 'true':
    # collectstatic 중에는 실행되지 않도록 함
    import sys
    if 'collectstatic' not in sys.argv:
        threading.Timer(10.0, run_startup_tasks).start()

# =============================================================================
# STATIC FILES (WhiteNoise)
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# [사용자 제안] 목적지(staticfiles)가 소스(static)에 포함되지 않도록 확실히 분리
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# CRITICAL: Explicitly configure finders to locate Django admin static files
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',  # Finds files in STATICFILES_DIRS
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',  # Finds Django admin CSS/JS in app directories
]

if not os.path.exists(STATIC_ROOT):
    os.makedirs(STATIC_ROOT)

# WhiteNoise configuration
# CRITICAL FIX: USE_FINDERS=True allows WhiteNoise to serve admin static files directly
# from app directories without requiring collectstatic to succeed first
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = True  # FIXED: Enable finders to serve Django admin CSS/JS

# Django 6.0+ STORAGES 설정
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage" if USE_CLOUDINARY else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# =============================================================================
# MAINTENANCE MODE
# Railway 대시보드에서 환경변수 MAINTENANCE_MODE=True 설정 시 즉시 활성화.
# MaintenanceModeMiddleware가 superuser 외 모든 요청에 503 반환.
# 롤백: Railway 환경변수에서 MAINTENANCE_MODE 제거 또는 False로 변경.
# =============================================================================
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'False').lower() in ('true', '1', 'yes')
AUTOARTICLE_EXPORT_LAYOUT = os.getenv('AUTOARTICLE_EXPORT_LAYOUT', 'v1')
# Home layout rollout: set HOME_LAYOUT_VERSION to v1, v2, v4, v5, or v6 to lock a version.
# If unset, legacy HOME_V2_ENABLED fallback still decides between v1 and v2 only.
HOME_LAYOUT_VERSION = os.environ.get('HOME_LAYOUT_VERSION', '').strip().lower()
# Legacy fallback flag for v1/v2 only. Keep until v1/v2 paths and rollback rules are retired.
HOME_V2_ENABLED = os.environ.get('HOME_V2_ENABLED', 'True').lower() == 'true'
# Mobile home V4 rollout: keep the current hamburger menu by default.
# Set HOME_V4_MOBILE_CALENDAR_FIRST_ENABLED=True to switch mobile V4 to calendar-first quick tools.
HOME_V4_MOBILE_CALENDAR_FIRST_ENABLED = os.environ.get(
    'HOME_V4_MOBILE_CALENDAR_FIRST_ENABLED',
    'False',
).lower() == 'true'
HOME_TEACHER_BUDDY_ENABLED = os.environ.get(
    'HOME_TEACHER_BUDDY_ENABLED',
    'False',
).lower() == 'true'
ALLOW_TABLET_ACCESS = os.environ.get('ALLOW_TABLET_ACCESS', 'True').lower() in ('true', '1', 'yes')
GLOBAL_SEARCH_ENABLED = os.environ.get('GLOBAL_SEARCH_ENABLED', 'True').lower() in ('true', '1', 'yes')


def _rollout_env(name, default="", aliases=None):
    value = os.environ.get(name)
    if value is None and aliases:
        for alias in aliases:
            alias_value = os.environ.get(alias)
            if alias_value is not None:
                value = alias_value
                break
    if value is None:
        return default
    return value


def _rollout_env_bool(name, default='False', aliases=None):
    return str(_rollout_env(name, default=default, aliases=aliases)).strip().lower() in ('true', '1', 'yes')


def _rollout_env_csv(name, aliases=None):
    raw = _rollout_env(name, default='', aliases=aliases)
    return [item.strip() for item in str(raw).split(',') if item.strip()]


SHEETBOOK_ENABLED = _rollout_env_bool('SHEETBOOK_ENABLED', default='False', aliases=('sheetbook_enabled',))
SHEETBOOK_DISCOVERY_VISIBLE = _rollout_env_bool(
    'SHEETBOOK_DISCOVERY_VISIBLE',
    default='False',
    aliases=('sheetbook_discovery_visible',),
)
SHEETBOOK_APP_AVAILABLE = find_spec('sheetbook.apps') is not None
if SHEETBOOK_APP_AVAILABLE:
    INSTALLED_APPS.append('sheetbook.apps.SheetbookConfig')
elif SHEETBOOK_ENABLED:
    print('[SHEETBOOK] disabled: sheetbook package not available')
    SHEETBOOK_ENABLED = False
    SHEETBOOK_DISCOVERY_VISIBLE = False
SHEETBOOK_BETA_USERNAMES = _rollout_env_csv('SHEETBOOK_BETA_USERNAMES', aliases=('sheetbook_beta_usernames',))
SHEETBOOK_BETA_EMAILS = _rollout_env_csv('SHEETBOOK_BETA_EMAILS', aliases=('sheetbook_beta_emails',))
SHEETBOOK_BETA_USER_IDS = _rollout_env_csv('SHEETBOOK_BETA_USER_IDS', aliases=('sheetbook_beta_user_ids',))
SHEETBOOK_SCHEDULE_DEFAULT_DURATION_MINUTES = int(os.environ.get('SHEETBOOK_SCHEDULE_DEFAULT_DURATION_MINUTES', '50'))
SHEETBOOK_PERIOD_FIRST_CLASS_HOUR = int(os.environ.get('SHEETBOOK_PERIOD_FIRST_CLASS_HOUR', '9'))
SHEETBOOK_PERIOD_FIRST_CLASS_MINUTE = int(os.environ.get('SHEETBOOK_PERIOD_FIRST_CLASS_MINUTE', '0'))
SHEETBOOK_GRID_BULK_BATCH_SIZE = int(os.environ.get('SHEETBOOK_GRID_BULK_BATCH_SIZE', '400'))
SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE = float(os.environ.get('SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE', '60'))
SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE = float(
    os.environ.get('SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE', '50')
)
SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE = int(os.environ.get('SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE', '5'))
SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE = int(
    os.environ.get('SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE', '5')
)
SHEETBOOK_ROLLOUT_STRICT_STARTUP = os.environ.get('SHEETBOOK_ROLLOUT_STRICT_STARTUP', 'False').lower() in ('true', '1', 'yes')
SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP = os.environ.get('SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP', 'False').lower() in ('true', '1', 'yes')
SHEETBOOK_ROLLOUT_RECOMMEND_DAYS = int(os.environ.get('SHEETBOOK_ROLLOUT_RECOMMEND_DAYS', '14'))
FEATURE_MESSAGE_CAPTURE_ENABLED = _rollout_env_bool(
    'FEATURE_MESSAGE_CAPTURE_ENABLED',
    default='False',
    aliases=('feature_message_capture_enabled',),
)
FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES = _rollout_env_csv(
    'FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES',
    aliases=('feature_message_capture_allowlist_usernames',),
)
FEATURE_MESSAGE_CAPTURE_ALLOWLIST_EMAILS = _rollout_env_csv(
    'FEATURE_MESSAGE_CAPTURE_ALLOWLIST_EMAILS',
    aliases=('feature_message_capture_allowlist_emails',),
)
FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USER_IDS = _rollout_env_csv(
    'FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USER_IDS',
    aliases=('feature_message_capture_allowlist_user_ids',),
)
FEATURE_MESSAGE_CAPTURE_ITEM_TYPES = _rollout_env_bool(
    'FEATURE_MESSAGE_CAPTURE_ITEM_TYPES',
    default='False',
    aliases=('feature_message_capture_item_types',),
)
FEATURE_MESSAGE_CAPTURE_CLASSIFIER_SHADOW = _rollout_env_bool(
    'FEATURE_MESSAGE_CAPTURE_CLASSIFIER_SHADOW',
    default='False',
    aliases=('feature_message_capture_classifier_shadow',),
)
FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST = _rollout_env_bool(
    'FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST',
    default='False',
    aliases=('feature_message_capture_classifier_assist',),
)
FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST_THRESHOLD = float(
    _rollout_env('FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST_THRESHOLD', default='0.80', aliases=('feature_message_capture_classifier_assist_threshold',))
)
ONBOARDING_EXEMPT_PATH_PREFIXES = []
DUTYTICKER_STUDENT_GAMES_MAX_AGE_SECONDS = int(os.environ.get('DUTYTICKER_STUDENT_GAMES_MAX_AGE_SECONDS', '28800'))
DUTYTICKER_STUDENT_GAMES_LAUNCH_TICKET_TTL_SECONDS = int(
    os.environ.get('DUTYTICKER_STUDENT_GAMES_LAUNCH_TICKET_TTL_SECONDS', '900')
)
SEED_QUIZ_BATCH_ENABLED = os.environ.get('SEED_QUIZ_BATCH_ENABLED', 'False').lower() in ('true', '1', 'yes')
SEED_QUIZ_ALLOW_RAG = os.environ.get('SEED_QUIZ_ALLOW_RAG', 'False').lower() in ('true', '1', 'yes')
SEED_QUIZ_CSV_MAX_FILE_BYTES = int(os.environ.get('SEED_QUIZ_CSV_MAX_FILE_BYTES', str(2 * 1024 * 1024)))
SEED_QUIZ_CSV_MAX_ROWS = int(os.environ.get('SEED_QUIZ_CSV_MAX_ROWS', '1200'))
SEED_QUIZ_CSV_MAX_SETS = int(os.environ.get('SEED_QUIZ_CSV_MAX_SETS', '400'))
LAW_API_OC = os.environ.get('LAW_API_OC', '').strip()
TEACHER_LAW_ENABLED = os.environ.get('TEACHER_LAW_ENABLED', 'False').lower() in ('true', '1', 'yes')
TEACHER_LAW_DAILY_LIMIT_PER_USER = int(os.environ.get('TEACHER_LAW_DAILY_LIMIT_PER_USER', '15'))
TEACHER_LAW_TOTAL_TIMEOUT_SECONDS = int(os.environ.get('TEACHER_LAW_TOTAL_TIMEOUT_SECONDS', '20'))
TEACHER_LAW_SEARCH_TIMEOUT_SECONDS = int(os.environ.get('TEACHER_LAW_SEARCH_TIMEOUT_SECONDS', '4'))
TEACHER_LAW_DETAIL_TIMEOUT_SECONDS = int(os.environ.get('TEACHER_LAW_DETAIL_TIMEOUT_SECONDS', '4'))
TEACHER_LAW_LLM_TIMEOUT_SECONDS = int(os.environ.get('TEACHER_LAW_LLM_TIMEOUT_SECONDS', '12'))
TEACHER_LAW_SEARCH_RESULT_LIMIT = int(os.environ.get('TEACHER_LAW_SEARCH_RESULT_LIMIT', '5'))
TEACHER_LAW_DETAIL_FETCH_LIMIT = int(os.environ.get('TEACHER_LAW_DETAIL_FETCH_LIMIT', '3'))
TEACHER_LAW_FAQ_CACHE_TTL_SECONDS = int(os.environ.get('TEACHER_LAW_FAQ_CACHE_TTL_SECONDS', '43200'))

# Fortune async rollout flags (safe default: OFF)
# - STREAM: /fortune/api/streaming/ 경로에서 AsyncOpenAI 직접 사용
# - API: /fortune/api/, /fortune/api/daily/, analyze_topic 경로에서 async 수집 사용
FORTUNE_ASYNC_STREAM_ENABLED = os.getenv('FORTUNE_ASYNC_STREAM_ENABLED', 'False').lower() in ('true', '1', 'yes')
FORTUNE_ASYNC_API_ENABLED = os.getenv('FORTUNE_ASYNC_API_ENABLED', 'False').lower() in ('true', '1', 'yes')

# =============================================================================
# LOGGING (settings.py와 동기화)
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id': {
            '()': 'core.logging_filters.RequestIDFilter',
        },
    },
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} [{request_id}] {name} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['request_id'],
        },
    },
    'loggers': {
        'core.middleware': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'core.context_processors': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'core.auth_security': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# =============================================================================
# SENTRY ERROR TRACKING (production only)
# =============================================================================
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN and not DEBUG:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            send_default_pii=False,
        )
    except Exception:
        pass
else:
    pass  # Sentry disabled (no DSN or DEBUG mode)
