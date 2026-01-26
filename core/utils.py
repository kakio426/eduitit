import jwt
import datetime
from django.conf import settings


# =============================================================================
# Rate Limit 유틸리티
# =============================================================================

def has_personal_api_key(user):
    """사용자가 개인 Gemini API 키를 가지고 있는지 확인"""
    if not user or not user.is_authenticated:
        return False
    try:
        # UserProfile이 없을 수도 있으므로 safe check
        profile = getattr(user, 'userprofile', None)
        if not profile:
            return False
        api_key = profile.gemini_api_key
        return bool(api_key and api_key.strip())
    except Exception:
        return False


def ratelimit_key_for_master_only(group, request):
    """
    마스터 키 사용자 및 비회원에게 Rate Limit 적용
    - 개인 키 사용자: 고유 UUID 반환 → Rate Limit 미적용 (무제한)
    - 회원 (마스터 키): user_id 반환 → 회원용 제한 적용
    - 비회원 (게스트): client_ip 반환 → IP 기반의 엄격한 제한 적용

    사용법:
    @ratelimit(key=ratelimit_key_for_master_only, rate='10/h', block=True)
    """
    user = request.user
    
    if has_personal_api_key(user):
        import uuid
        return f'personal:{uuid.uuid4()}'
    
    if user.is_authenticated:
        return f'user:{user.id}'
    
    # 비회원은 IP 주소 기반으로 제한
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return f'ip:{ip}'

def generate_sso_token(user):
    """
    Generate a JWT token for SSO with schoolit.
    Includes user ID, username, and role (mapped to Schoolit's uppercase roles).
    """
    profile = getattr(user, 'userprofile', None)
    # schoolit은 대문자 역할을 기대함 (SCHOOL, INSTRUCTOR, COMPANY)
    role_map = {
        'school': 'SCHOOL',
        'instructor': 'INSTRUCTOR',
        'company': 'COMPANY'
    }
    
    raw_role = profile.role if profile else None
    role = role_map.get(raw_role, 'APPLICANT') # 기본값은 지원자
    
    payload = {
        'sub': str(user.id),
        'username': user.email or user.username,
        'email': user.email or f"{user.username}@eduitit.proxy",
        'name': user.first_name or user.username,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    }
    
    return jwt.encode(payload, settings.SSO_JWT_SECRET, algorithm='HS256')

def get_schoolit_url(role):
    """
    Return the appropriate schoolit SSO landing URL.
    Note: Redirect to /auth/sso first so schoolit can process the token.
    """
    base_url = settings.SCHOOLIT_URL.rstrip('/')
    # schoolit 보고서 164번 라인에 근거하여 /auth/sso 페이지로 리다이렉트
    return f"{base_url}/auth/sso"
