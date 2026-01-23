import jwt
import datetime
from django.conf import settings

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
