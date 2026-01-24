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

# Allowed hosts from environment variable (comma-separated)
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '.onrender.com,.railway.app,localhost,127.0.0.1').split(',')

# Kakao API Key
KAKAO_JS_KEY = os.environ.get('YOUR_KAKAO_API_KEY')

# CSRF trusted origins for Render
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://*.railway.app',
]

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
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
    'signatures.apps.SignaturesConfig',
    'school_violence.apps.SchoolViolenceConfig',
    'artclass.apps.ArtclassConfig',
    'padlet_bot.apps.PadletBotConfig',
    
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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Allauth middleware
    'allauth.account.middleware.AccountMiddleware',
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
# STATIC FILES (WhiteNoise)
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

if not os.path.exists(STATIC_ROOT):
    os.makedirs(STATIC_ROOT)

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =============================================================================
# MEDIA FILES
# =============================================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================================
# AUTHENTICATION
# =============================================================================

LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth Settings
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_SIGNUP_FIELDS = ['email', 'username*', 'password1*', 'password2*']
ACCOUNT_SESSION_REMEMBER = True
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
            'secret': os.environ.get('KAKAO_SECRET', ''),
            'key': ''
        }
    },
    'naver': {
        'APP': {
            'client_id': os.environ.get('NAVER_CLIENT_ID', ''),
            'secret': os.environ.get('NAVER_SECRET', ''),
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
        
        # 도메인에서 프로토콜 제거 (실수로 포함된 경우 대비)
        if production_domain:
            production_domain = production_domain.replace('https://', '').replace('http://', '').split('/')[0]

        if production_domain and current_site.domain != production_domain:
            print(f"DEBUG: SITE_ID {SITE_ID} 도메인을 {current_site.domain}에서 {production_domain}으로 업데이트합니다.")
            current_site.domain = production_domain
            current_site.name = "Eduitit Production"
            current_site.save()
        else:
            print(f"DEBUG: 현재 SITE_ID {SITE_ID} 도메인은 {current_site.domain}입니다.")
    except Exception as e:
        print(f"DEBUG: 사이트 도메인 동기화 실패: {str(e)}")
        pass

# 서버 실행 시 자동 실행되도록 앱 설정 또는 여기에 직접 호출 (단, DB 연결 가능 시점이어야 함)
# 여기서는 코드 마지막에 가벼운 가드로 시도합니다.
import threading
if os.environ.get('RUN_MAIN') != 'true': # 중복 실행 방지
    threading.Timer(5.0, sync_site_domain).start()
