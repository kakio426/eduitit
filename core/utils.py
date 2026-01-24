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
        api_key = user.userprofile.gemini_api_key
        return bool(api_key and api_key.strip())
    except Exception:
        return False


def ratelimit_key_for_master_only(group, request):
    """
    마스터 키 사용자에게만 Rate Limit 적용
    - 개인 키 사용자: None 반환 → Rate Limit 미적용
    - 마스터 키 사용자: user_id 반환 → Rate Limit 적용

    사용법:
    @ratelimit(key=ratelimit_key_for_master_only, rate='10/h', block=True)
    """
    user = request.user
    if has_personal_api_key(user):
        # 개인 키 사용자는 Rate Limit 건너뛰기
        # 고유한 키를 매번 생성하여 사실상 무제한
        import uuid
        return f'personal:{uuid.uuid4()}'
    else:
        # 마스터 키 사용자는 user_id 기반으로 제한
        return f'master:{user.id}'

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
