from allauth.socialaccount.models import SocialAccount

from .models import UserPolicyConsent
from .policy_meta import (
    POLICY_CONSENT_SESSION_KEY,
    PRIVACY_VERSION,
    TERMS_VERSION,
    get_current_policy_version_key,
)


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


def mark_current_policy_consent(session, user):
    session[POLICY_CONSENT_SESSION_KEY] = f"{user.pk}:{get_current_policy_version_key()}"


def clear_current_policy_consent(session):
    session.pop(POLICY_CONSENT_SESSION_KEY, None)


def get_agreement_source(user, provider):
    has_prior_consent = UserPolicyConsent.objects.filter(user=user).exists()
    if provider in {"kakao", "naver"}:
        return "social_reconsent" if has_prior_consent else "social_first_login"
    return "required_gate"
