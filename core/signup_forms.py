from django import forms
from django.utils import timezone

from .models import (
    MARKETING_EMAIL_CONSENT_VERSION,
    UserMarketingEmailConsent,
    UserProfile,
)


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
    marketing_email_opt_in = forms.BooleanField(
        required=False,
        label="[선택] 신규 기능, 이벤트, 혜택 안내 이메일 받기",
        help_text=(
            "서비스 운영에 꼭 필요한 안내 메일과는 별도로, "
            "신규 기능과 이벤트 소식을 이메일로 받을 수 있어요."
        ),
        widget=forms.CheckboxInput(attrs={
            'class': 'signup-check-input',
        }),
    )

    def signup(self, request, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.nickname = self.cleaned_data['nickname']
        profile.save()

        if not self.cleaned_data.get('marketing_email_opt_in'):
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
