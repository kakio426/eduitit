from django import forms
from django.utils import timezone

from .models import (
    MARKETING_EMAIL_CONSENT_VERSION,
    UserPolicyConsent,
    UserMarketingEmailConsent,
    UserProfile,
)
from .policy_consent import (
    clear_current_social_signup_consent,
    get_current_social_signup_consent,
    mark_current_policy_consent,
)
from .policy_meta import PRIVACY_VERSION, TERMS_VERSION


def _get_request_client_ip(request):
    if request is None:
        return ""
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


class CustomSignupForm(forms.Form):
    """
    allauth ACCOUNT_SIGNUP_FORM_CLASS용 커스텀 폼.
    allauth의 BaseSignupForm이 이 클래스를 상속하므로,
    nickname 필드와 signup() 메서드만 정의하면 됩니다.
    이메일은 allauth가 처리하고, 사용자명은 내부에서 자동 생성합니다.
    """
    nickname = forms.CharField(
        max_length=50,
        required=True,
        label="닉네임",
        widget=forms.TextInput(attrs={
            'placeholder': '닉네임을 입력해주세요',
            'autocomplete': 'nickname'
        })
    )
    def signup(self, request, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.nickname = self.cleaned_data['nickname']
        profile.save()

        social_signup_consent = get_current_social_signup_consent(getattr(request, 'session', None))
        if social_signup_consent:
            provider = social_signup_consent.get('provider') or 'direct'
            UserPolicyConsent.objects.get_or_create(
                user=user,
                terms_version=TERMS_VERSION,
                privacy_version=PRIVACY_VERSION,
                defaults={
                    'provider': provider,
                    'agreed_at': timezone.now(),
                    'agreement_source': 'social_first_login',
                    'ip_address': _get_request_client_ip(request) or None,
                    'user_agent': (request.META.get('HTTP_USER_AGENT') or '').strip() if request else '',
                },
            )
            mark_current_policy_consent(request.session, user)

        if not social_signup_consent or not social_signup_consent.get('marketing_email_opt_in'):
            clear_current_social_signup_consent(getattr(request, 'session', None))
            return

        UserMarketingEmailConsent.objects.update_or_create(
            user=user,
            defaults={
                'consent_version': MARKETING_EMAIL_CONSENT_VERSION,
                'consented_at': timezone.now(),
                'consent_source': 'social_signup',
                'ip_address': _get_request_client_ip(request) or None,
                'user_agent': (request.META.get('HTTP_USER_AGENT') or '').strip() if request else '',
                'revoked_at': None,
            },
        )
        clear_current_social_signup_consent(getattr(request, 'session', None))
