"""
Django Production Settings for Render + Neon deployment.

This settings module extends the base settings and configures:
- PostgreSQL via DATABASE_URL (Neon)
- WhiteNoise for static files
- Security settings for production
"""

import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-key-for-development-only')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

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
KAKAO_JS_KEY = os.environ.get('YOUR_KAKAO_API_KEY')

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
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'products.apps.ProductsConfig',
    'insights.apps.InsightsConfig',
    'portfolio.apps.PortfolioConfig',
    'autoarticle.apps.AutoarticleConfig',
    'fortune.apps.FortuneConfig',
    'ssambti.apps.SsambtiConfig',  # Teachable Zoo MBTI (쌤BTI)
    'signatures.apps.SignaturesConfig',
    'school_violence.apps.SchoolViolenceConfig',
    'artclass.apps.ArtclassConfig',
    'padlet_bot.apps.PadletBotConfig',
    'django_htmx',
    'django.contrib.humanize',

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
    # TEMPORARILY DISABLED FOR DEBUGGING: CSP might be blocking admin static files
    # 'csp.middleware.CSPMiddleware',  # Content Security Policy
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Allauth middleware
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# =============================================================================
# DATABASE - PostgreSQL via Neon (DATABASE_URL)
# =============================================================================

# Use DATABASE_URL environment variable (Neon PostgreSQL)
# Fallback to SQLite for local development without DATABASE_URL
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Debug: Log the received URL (masking password for security)
    import re
    safe_db_url = re.sub(r':([^:@]+)@', ':****@', DATABASE_URL)
    print(f"DEBUG: Received DATABASE_URL: {safe_db_url}")

    # Clean up DATABASE_URL if it contains 'psql' command or extra quotes
    # Example issue: psql 'postgresql://...'
    DATABASE_URL = DATABASE_URL.strip()
    if DATABASE_URL.startswith("psql"):
        DATABASE_URL = DATABASE_URL.replace("psql", "", 1).strip()
    
    # Remove surrounding quotes if present
    if (DATABASE_URL.startswith("'") and DATABASE_URL.endswith("'")) or \
       (DATABASE_URL.startswith('"') and DATABASE_URL.endswith('"')):
        DATABASE_URL = DATABASE_URL[1:-1]

    # Fix: Ensure scheme is valid for dj-database-url if it starts with postgres:// 
    # (newer versions favor postgresql:// but handle postgres://, older might be strict)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    try:
        DATABASES = {
            'default': dj_database_url.parse(
                DATABASE_URL,
                conn_max_age=600,
                conn_health_checks=True,
            )
        }
    except ValueError as e:
        print(f"DEBUG: Parsing failed. Original error: {e}")
        raise ValueError(f"DATABASE_URL 형식이 올바르지 않습니다. 값: {safe_db_url}")
else:
    # Fallback for local development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
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

CLOUDINARY_STORAGE = {}

if cloudinary_url:
    try:
        parsed = urlparse(cloudinary_url)
        # 1. Start with parsed values
        CLOUDINARY_STORAGE = {
            'CLOUD_NAME': parsed.hostname or '',
            'API_KEY': parsed.username or '',
            'API_SECRET': parsed.password or '',
        }
    except Exception:
        pass

# 2. Override with individual variables if provided (Railway case)
if cloud_name: CLOUDINARY_STORAGE['CLOUD_NAME'] = cloud_name
if api_key: CLOUDINARY_STORAGE['API_KEY'] = api_key
if api_secret: CLOUDINARY_STORAGE['API_SECRET'] = api_secret

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
        # Initialization success
        USE_CLOUDINARY = True
        DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
        print(f"DEBUG: Cloudinary initialized: {CLOUDINARY_STORAGE['CLOUD_NAME']}")

    except Exception as e:
        print(f"DEBUG: Cloudinary initialization failed: {e}")
        USE_CLOUDINARY = False
else:
    USE_CLOUDINARY = False
    print("DEBUG: Cloudinary NOT configured, using local storage.")
    # Local storage is already set in the global block above.

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
ACCOUNT_SIGNUP_FIELDS = ['email', 'username*', 'password1*', 'password2*']
ACCOUNT_SESSION_REMEMBER = False  # 기본적으로 자동 로그인 해제 (보안을 위해)
SESSION_COOKIE_AGE = 3600  # 1시간 동안 활동이 없으면 로그아웃
SESSION_SAVE_EVERY_REQUEST = True  # 활동할 때마다 세션 만료 시간 연장
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # 브라우저 닫으면 로그아웃
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True # ✅ 중간 페이지 없이 바로 소셜 로그인창으로 이동

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
)
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
    "http:",
    "https://k.kakaocdn.net", # Kakao profile/assets
    "https://*.kakaocdn.net",
)
CSP_CONNECT_SRC = (
    "'self'",
    "https://api.padlet.com",
    "https://generativelanguage.googleapis.com",
    "https://assetsconfigcdn.org",      # Statsig (Loom extension)
    "https://beyondwickedmapping.org", # Statsig (Loom extension)
    "https://cloudflare-dns.com",      # DNS fallback
    "https://cdn.jsdelivr.net",        # JS source maps
    "https://*.kakao.com",             # Kakao APIs
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

# =============================================================================
# AUTO-FIX: Sync Site Domain with Production Host
# =============================================================================

def sync_site_domain():
    """DB의 Site 도메인을 현재 접속 주소와 자동으로 동기화합니다."""
    try:
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()
        production_domain = os.environ.get('ALLOWED_HOSTS', '').split(',')[0]
        
        if not production_domain or 'railway.app' not in production_domain:
            # ALLOWED_HOSTS에서 railway 도메인 찾기
            for host in os.environ.get('ALLOWED_HOSTS', '').split(','):
                host = host.strip()
                if 'railway.app' in host:
                    production_domain = host
                    break

        if production_domain and current_site.domain != production_domain:
            print(f"DEBUG: SITE_ID {SITE_ID} 도메인을 {current_site.domain}에서 {production_domain}으로 업데이트합니다.")
            current_site.domain = production_domain
            current_site.name = "Eduitit Production"
            current_site.save()
        else:
            print(f"DEBUG: 현재 SITE_ID {SITE_ID} 도메인은 {current_site.domain}입니다.")

        # 중복된 소셜 앱 설정 삭제 (MultipleObjectsReturned 방지)
        from allauth.socialaccount.models import SocialApp
        deleted_count = SocialApp.objects.all().delete()[0]
        if deleted_count > 0:
            print(f"DEBUG: {deleted_count}개의 중복 소셜 앱 설정을 삭제했습니다.")
            
    except Exception as e:
        print(f"DEBUG: 자동 동기화/정리 실패: {str(e)}")
        pass

# 서버 실행 시 자동 실행
import threading
if os.environ.get('RUN_MAIN') != 'true':
    # collectstatic 중에는 실행되지 않도록 함
    import sys
    if 'collectstatic' not in sys.argv:
        threading.Timer(5.0, sync_site_domain).start()

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
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage" if CLOUDINARY_STORAGE.get('CLOUD_NAME') else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

print("="*60)
print(f"DEBUG: STATIC_ROOT => {STATIC_ROOT}")
print(f"DEBUG: STATICFILES_DIRS => {STATICFILES_DIRS}")
print(f"DEBUG: STATICFILES_STORAGE => {STATICFILES_STORAGE}")
print("="*60)

