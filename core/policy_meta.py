from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse

TERMS_VERSION = "2026-03-14.1"
PRIVACY_VERSION = "2026-03-14.1"
LAST_UPDATED_DISPLAY = "2026년 3월 14일"
POLICY_CONSENT_SESSION_KEY = "core.current_policy_consent"

PROVIDER_LABELS = {
    "kakao": "카카오",
    "naver": "네이버",
    "direct": "일반 로그인",
}


def get_policy_meta():
    return {
        "terms_version": TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "last_updated_display": LAST_UPDATED_DISPLAY,
        "summary": (
            "Eduitit 이용을 위해 이용약관 및 개인정보처리방침 동의가 필요합니다. "
            "내용을 확인한 뒤 동의해 주세요."
        ),
        "service_summary": (
            "동의 후 Eduitit의 캘린더, 수합, 서명, 동의서, 예약, 메시지 저장, "
            "커뮤니티, AI 기능을 이용할 수 있습니다."
        ),
    }


def get_current_policy_version_key():
    return f"{TERMS_VERSION}:{PRIVACY_VERSION}"


def get_provider_label(provider):
    return PROVIDER_LABELS.get(provider, provider or PROVIDER_LABELS["direct"])


def get_safe_next_url(request, fallback=None):
    candidate = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback or reverse("select_role")
