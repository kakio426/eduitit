from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from core.models import MARKETING_EMAIL_CONSENT_VERSION, UserMarketingEmailConsent
from core.signup_forms import CustomSignupForm


class CustomSignupFormTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

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
