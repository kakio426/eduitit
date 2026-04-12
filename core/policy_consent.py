from urllib.parse import quote

from allauth.socialaccount.models import SocialAccount
from django.urls import reverse
from django.utils import timezone

from .models import UserPolicyConsent
from .policy_meta import (
    POLICY_CONSENT_SESSION_KEY,
    PRIVACY_VERSION,
    TERMS_VERSION,
    get_current_policy_version_key,
)

SOCIAL_SIGNUP_CONSENT_SESSION_KEY = "core.social_signup_consent"


def get_latest_social_provider(user):
    provider = (
        SocialAccount.objects
        .filter(user=user)
        .order_by("-last_login", "-date_joined", "-id")
        .values_list("provider", flat=True)
        .first()
    )
    return provider or "direct"


def user_requires_policy_consent(user):
    if not getattr(user, "is_authenticated", False):
        return False

    provider = get_latest_social_provider(user)
    if provider != "direct":
        return True

    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def get_current_policy_consent(user):
    return (
        UserPolicyConsent.objects
        .filter(
            user=user,
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
        )
        .order_by("-agreed_at", "-id")
        .first()
    )


def has_current_policy_consent(user, session=None):
    session_value = f"{user.pk}:{get_current_policy_version_key()}"
    if session is not None and session.get(POLICY_CONSENT_SESSION_KEY) == session_value:
        return True

    consent = get_current_policy_consent(user)
    if consent and session is not None:
        mark_current_policy_consent(session, user)
    return consent is not None


def get_policy_consent_redirect_url(request, *, next_url=""):
    consent_path = reverse("policy_consent")
    candidate = (next_url or "").strip()
    if not candidate and request is not None and hasattr(request, "get_full_path"):
        candidate = request.get_full_path()
    if not candidate or candidate == consent_path:
        return consent_path
    return f"{consent_path}?next={quote(candidate)}"


def get_pending_social_signup(request):
    from allauth.socialaccount.internal.flows.signup import get_pending_signup

    return get_pending_signup(request)


def get_current_social_signup_consent(session):
    if session is None:
        return None
    data = session.get(SOCIAL_SIGNUP_CONSENT_SESSION_KEY)
    if not isinstance(data, dict):
        return None
    if data.get("terms_version") != TERMS_VERSION:
        return None
    if data.get("privacy_version") != PRIVACY_VERSION:
        return None
    return data


def has_current_social_signup_consent(session):
    return get_current_social_signup_consent(session) is not None


def mark_current_social_signup_consent(session, *, provider, marketing_email_opt_in):
    if session is None:
        return
    session[SOCIAL_SIGNUP_CONSENT_SESSION_KEY] = {
        "provider": (provider or "direct").strip() or "direct",
        "terms_version": TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "marketing_email_opt_in": bool(marketing_email_opt_in),
        "agreed_at": timezone.now().isoformat(),
    }


def clear_current_social_signup_consent(session):
    if session is None:
        return
    session.pop(SOCIAL_SIGNUP_CONSENT_SESSION_KEY, None)


def get_social_signup_consent_redirect_url():
    return reverse("social_signup_consent")


def get_pending_social_signup_consent_redirect(request):
    session = getattr(request, "session", None)
    sociallogin = get_pending_social_signup(request)
    if not sociallogin:
        clear_current_social_signup_consent(session)
        return ""

    consent_path = get_social_signup_consent_redirect_url()
    if request.path.startswith(consent_path):
        return ""

    if has_current_social_signup_consent(session):
        return ""

    signup_path = reverse("socialaccount_signup")
    if request.path.startswith(signup_path):
        return consent_path

    return ""


def get_pending_policy_consent_redirect(request, *, next_url=""):
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return ""

    if not user_requires_policy_consent(user):
        return ""

    if has_current_policy_consent(user, getattr(request, "session", None)):
        return ""

    return get_policy_consent_redirect_url(request, next_url=next_url)


def mark_current_policy_consent(session, user):
    session[POLICY_CONSENT_SESSION_KEY] = f"{user.pk}:{get_current_policy_version_key()}"


def clear_current_policy_consent(session):
    session.pop(POLICY_CONSENT_SESSION_KEY, None)


def get_agreement_source(user, provider):
    has_prior_consent = UserPolicyConsent.objects.filter(user=user).exists()
    if provider in {"kakao", "naver"}:
        return "social_reconsent" if has_prior_consent else "social_first_login"
    return "required_gate"
