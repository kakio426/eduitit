from types import SimpleNamespace

from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from core.models import MARKETING_EMAIL_CONSENT_VERSION, UserMarketingEmailConsent
from core.signup_forms import CustomSignupForm


class CustomSignupFormTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _build_sociallogin(self, *, email="social@example.com"):
        user = User(email=email, username="")
        return SimpleNamespace(
            user=user,
            email_addresses=[],
            provider=SimpleNamespace(name="Kakao"),
        )

    def test_signup_saves_marketing_email_consent_when_checked(self):
        user = User.objects.create_user(
            username='signupuser',
            email='signup@example.com',
            password='password123',
        )
        form = CustomSignupForm(
            data={
                'nickname': '가입선생',
                'marketing_email_opt_in': 'on',
            }
        )

        self.assertTrue(form.is_valid())

        request = self.factory.post('/accounts/3rdparty/signup/')
        request.META['REMOTE_ADDR'] = '198.51.100.30'
        request.META['HTTP_USER_AGENT'] = 'signup-form-test-agent'

        form.signup(request, user)

        consent = UserMarketingEmailConsent.objects.get(user=user)
        self.assertEqual(consent.consent_version, MARKETING_EMAIL_CONSENT_VERSION)
        self.assertEqual(consent.consent_source, 'social_signup')
        self.assertEqual(consent.ip_address, '198.51.100.30')
        self.assertEqual(consent.user_agent, 'signup-form-test-agent')
        self.assertIsNone(consent.revoked_at)

    def test_signup_does_not_create_marketing_email_consent_when_unchecked(self):
        user = User.objects.create_user(
            username='signupuser2',
            email='signup2@example.com',
            password='password123',
        )
        form = CustomSignupForm(
            data={
                'nickname': '미동의선생',
            }
        )

        self.assertTrue(form.is_valid())

        request = self.factory.post('/accounts/3rdparty/signup/')
        form.signup(request, user)

        self.assertFalse(UserMarketingEmailConsent.objects.filter(user=user).exists())

    def test_social_signup_form_only_exposes_email_nickname_and_marketing_opt_in(self):
        form = SocialSignupForm(sociallogin=self._build_sociallogin())

        self.assertEqual(
            list(form.fields.keys()),
            ["email", "nickname", "marketing_email_opt_in"],
        )
        self.assertEqual(form.fields["nickname"].label, "닉네임")

    def test_social_signup_form_keeps_marketing_opt_in_unchecked_by_default(self):
        form = SocialSignupForm(sociallogin=self._build_sociallogin())

        self.assertFalse(bool(form.fields["marketing_email_opt_in"].initial))
