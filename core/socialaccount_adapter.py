from datetime import UTC, datetime

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db.models import Q

def _collect_social_emails(sociallogin):
    emails = []

    user_email = (getattr(getattr(sociallogin, "user", None), "email", "") or "").strip()
    if user_email:
        emails.append(user_email.lower())

    for email_address in getattr(sociallogin, "email_addresses", []) or []:
        email = (getattr(email_address, "email", "") or "").strip()
        if email:
            emails.append(email.lower())

    deduped = []
    seen = set()
    for email in emails:
        if email in seen:
            continue
        deduped.append(email)
        seen.add(email)
    return deduped


def _user_identity_score(user):
    social_count = SocialAccount.objects.filter(user=user).count()
    last_login = user.last_login or datetime.min.replace(tzinfo=UTC)
    date_joined = user.date_joined or datetime.min.replace(tzinfo=UTC)
    return (
        social_count > 0,
        social_count,
        user.is_active,
        last_login,
        date_joined,
        user.id,
    )


def resolve_existing_user_for_social_login(sociallogin):
    emails = _collect_social_emails(sociallogin)
    if not emails:
        return None

    User = get_user_model()
    query = Q()
    for email in emails:
        query |= Q(email__iexact=email)
    candidates = list(User.objects.filter(query))
    if not candidates:
        return None

    return max(candidates, key=_user_identity_score)


def maybe_connect_existing_user_by_email(request, sociallogin):
    if getattr(getattr(request, "user", None), "is_authenticated", False):
        return None
    if getattr(sociallogin, "is_existing", False):
        return None

    user = resolve_existing_user_for_social_login(sociallogin)
    if not user:
        return None

    sociallogin.connect(request, user)
    return user


class EduititSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)
        maybe_connect_existing_user_by_email(request, sociallogin)
