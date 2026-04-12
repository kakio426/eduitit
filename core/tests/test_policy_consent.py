from types import SimpleNamespace
from unittest.mock import patch
from datetime import timedelta

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse
from django.utils import timezone

from core.account_adapter import EduititAccountAdapter
from core.models import UserPolicyConsent
from core.policy_consent import (
    get_current_social_signup_consent,
    mark_current_social_signup_consent,
)
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from core.views import social_signup_consent_view


class PolicyConsentTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='social_teacher',
            email='social@example.com',
            password='password123',
            is_staff=False,
        )
        profile = self.user.userprofile
        profile.nickname = '열정선생'
        profile.role = 'school'
        profile.save(update_fields=['nickname', 'role'])
        SocialAccount.objects.create(
            user=self.user,
            provider='kakao',
            uid='kakao-social-teacher',
            extra_data={},
        )
        self.client.login(username='social_teacher', password='password123')

    def create_current_consent(self, **overrides):
        defaults = {
            'provider': 'kakao',
            'terms_version': TERMS_VERSION,
            'privacy_version': PRIVACY_VERSION,
            'agreed_at': timezone.now(),
            'agreement_source': 'social_first_login',
            'ip_address': '127.0.0.1',
            'user_agent': 'test-agent',
        }
        defaults.update(overrides)
        return UserPolicyConsent.objects.create(user=self.user, **defaults)

    def test_social_user_without_consent_redirects_from_home(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(response, f"{reverse('policy_consent')}?next={reverse('home')}")

    @override_settings(HOME_LAYOUT_VERSION='v2', HOME_V2_ENABLED=True)
    def test_social_user_without_consent_still_redirects_when_env_requests_v2(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(response, f"{reverse('policy_consent')}?next={reverse('home')}")

    def test_social_user_without_consent_redirects_from_select_role(self):
        response = self.client.get(reverse('select_role'))

        self.assertRedirects(response, f"{reverse('policy_consent')}?next={reverse('select_role')}")

    def test_social_user_without_consent_redirects_from_update_email(self):
        response = self.client.get(reverse('update_email'))

        self.assertRedirects(response, f"{reverse('policy_consent')}?next={reverse('update_email')}")

    def test_social_user_without_consent_can_open_public_portfolio(self):
        response = self.client.get(reverse('portfolio:list'))

        self.assertEqual(response.status_code, 200)

    def test_policy_consent_requires_both_checkboxes(self):
        response = self.client.post(reverse('policy_consent'), {'agree_terms': 'on'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '필수 약관 동의 후 서비스를 이용할 수 있습니다.')
        self.assertEqual(UserPolicyConsent.objects.count(), 0)

    def test_policy_consent_page_starts_with_unchecked_required_boxes_and_clear_button_hint(self):
        response = self.client.get(reverse('policy_consent'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '필수 2개를 확인하면 버튼이 켜집니다.')
        self.assertFalse(bool(response.context['form'].fields['agree_terms'].initial))
        self.assertFalse(bool(response.context['form'].fields['agree_privacy'].initial))

    def test_policy_consent_submission_saves_record_and_redirects(self):
        response = self.client.post(
            reverse('policy_consent'),
            {
                'agree_terms': 'on',
                'agree_privacy': 'on',
                'next': reverse('home'),
            },
            REMOTE_ADDR='203.0.113.10',
            HTTP_USER_AGENT='policy-consent-test-agent',
        )

        self.assertRedirects(response, reverse('home'))
        consent = UserPolicyConsent.objects.get(user=self.user)
        self.assertEqual(consent.provider, 'kakao')
        self.assertEqual(consent.terms_version, TERMS_VERSION)
        self.assertEqual(consent.privacy_version, PRIVACY_VERSION)
        self.assertEqual(consent.agreement_source, 'social_first_login')
        self.assertEqual(consent.ip_address, '203.0.113.10')
        self.assertEqual(consent.user_agent, 'policy-consent-test-agent')

    def test_existing_policy_consent_allows_home(self):
        self.create_current_consent()

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

    def test_version_change_creates_reconsent_row(self):
        UserPolicyConsent.objects.create(
            user=self.user,
            provider='kakao',
            terms_version='2026-02-26',
            privacy_version='2026-02-26',
            agreed_at=timezone.now() - timedelta(days=7),
            agreement_source='social_first_login',
        )

        response = self.client.post(
            reverse('policy_consent'),
            {'agree_terms': 'on', 'agree_privacy': 'on', 'next': reverse('home')},
        )

        self.assertRedirects(response, reverse('home'))
        current = UserPolicyConsent.objects.get(
            user=self.user,
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
        )
        self.assertEqual(current.agreement_source, 'social_reconsent')

    def test_htmx_request_gets_hx_redirect(self):
        response = self.client.get(reverse('home'), HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response['HX-Redirect'],
            f"{reverse('policy_consent')}?next={reverse('home')}",
        )

    def test_api_request_gets_json_error(self):
        response = self.client.get(reverse('list_product_favorites'))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'policy_consent_required')

    def test_policy_page_reflects_current_versions(self):
        response = self.client.get(reverse('policy'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, TERMS_VERSION)
        self.assertContains(response, PRIVACY_VERSION)
        self.assertContains(response, '메시지 저장')
        self.assertContains(response, '정책 동의 기록')
        self.assertContains(response, '선택 수신 동의 정보')
        self.assertContains(response, '신규 기능·이벤트·혜택 안내 이메일')
        self.assertContains(response, '교사·교직원 내부 업무용 기능')
        self.assertContains(response, '보호자명')
        self.assertContains(response, '공개 링크')
        self.assertContains(response, '쿠키, 세션 및 로컬 저장소')
        self.assertContains(response, 'Railway')
        self.assertContains(response, 'Neon')
        self.assertContains(response, 'Cloudinary')
        self.assertContains(response, 'DeepSeek API')
        self.assertContains(response, '운영정책')
        self.assertContains(response, '외부 링크 및 외부 서비스')
        self.assertContains(response, '고의 또는 중과실')
        self.assertContains(response, '학부모 동의서(consent)')
        self.assertNotContains(response, '아이디어 도용')


class DirectPolicyConsentTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='direct_admin',
            email='direct-admin@example.com',
            password='password123',
        )
        profile = self.user.userprofile
        profile.nickname = '직접관리자'
        profile.role = 'school'
        profile.save(update_fields=['nickname', 'role'])
        self.client.login(username='direct_admin', password='password123')

    def test_direct_admin_without_consent_redirects_from_home(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(response, f"{reverse('policy_consent')}?next={reverse('home')}")

    def test_direct_admin_consent_submission_saves_direct_provider_record(self):
        response = self.client.post(
            reverse('policy_consent'),
            {
                'agree_terms': 'on',
                'agree_privacy': 'on',
                'next': reverse('home'),
            },
            REMOTE_ADDR='198.51.100.12',
            HTTP_USER_AGENT='direct-policy-consent-test-agent',
        )

        self.assertRedirects(response, reverse('home'))
        consent = UserPolicyConsent.objects.get(user=self.user)
        self.assertEqual(consent.provider, 'direct')
        self.assertEqual(consent.terms_version, TERMS_VERSION)
        self.assertEqual(consent.privacy_version, PRIVACY_VERSION)
        self.assertEqual(consent.agreement_source, 'required_gate')
        self.assertEqual(consent.ip_address, '198.51.100.12')
        self.assertEqual(consent.user_agent, 'direct-policy-consent-test-agent')

    def test_direct_non_admin_user_is_not_gated(self):
        self.client.logout()
        regular_user = User.objects.create_user(
            username='direct_regular',
            email='regular@example.com',
            password='password123',
        )
        regular_profile = regular_user.userprofile
        regular_profile.nickname = '직접일반사용자'
        regular_profile.role = 'school'
        regular_profile.save(update_fields=['nickname', 'role'])
        self.client.login(username='direct_regular', password='password123')

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)


class PolicyConsentAdminExceptionTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='direct_admin',
            email='admin@example.com',
            password='password123',
        )
        profile = self.admin_user.userprofile
        profile.nickname = '운영자'
        profile.role = 'school'
        profile.save(update_fields=['nickname', 'role'])
        self.client.login(username='direct_admin', password='password123')

    def test_admin_site_is_exempt_but_service_screen_is_not(self):
        admin_response = self.client.get('/secret-admin-kakio/')
        home_response = self.client.get(reverse('home'))

        self.assertEqual(admin_response.status_code, 200)
        self.assertRedirects(home_response, f"{reverse('policy_consent')}?next={reverse('home')}")


class PolicyConsentRedirectAdapterTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = EduititAccountAdapter()
        self.user = User.objects.create_user(
            username='adapter_social_user',
            email='adapter-social@example.com',
            password='password123',
        )
        profile = self.user.userprofile
        profile.nickname = '리다이렉트선생'
        profile.save(update_fields=['nickname'])
        SocialAccount.objects.create(
            user=self.user,
            provider='kakao',
            uid='adapter-social-user',
            extra_data={},
        )

    def _build_request(self, path='/accounts/kakao/login/callback/'):
        request = self.factory.get(path)
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.user = self.user
        return request

    def test_login_redirect_routes_social_user_without_consent_to_policy_gate(self):
        request = self._build_request()

        response_url = self.adapter.get_login_redirect_url(request)

        self.assertEqual(
            response_url,
            f"{reverse('policy_consent')}?next={reverse('select_role')}",
        )

    def test_signup_redirect_routes_social_user_without_consent_to_policy_gate(self):
        request = self._build_request('/accounts/3rdparty/signup/')

        response_url = self.adapter.get_signup_redirect_url(request)

        self.assertEqual(
            response_url,
            f"{reverse('policy_consent')}?next={reverse('select_role')}",
        )

    def test_login_redirect_keeps_default_target_after_current_consent(self):
        UserPolicyConsent.objects.create(
            user=self.user,
            provider='kakao',
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source='social_first_login',
        )
        request = self._build_request()

        response_url = self.adapter.get_login_redirect_url(request)

        self.assertEqual(response_url, reverse('select_role'))


class SocialSignupConsentFlowTestCase(TestCase):
    def _build_sociallogin(self, provider='kakao'):
        return SimpleNamespace(
            account=SimpleNamespace(provider=provider),
            provider=SimpleNamespace(name=provider.title()),
        )

    def test_social_signup_page_redirects_to_consent_before_email_and_nickname(self):
        with patch(
            'core.policy_consent.get_pending_social_signup',
            return_value=self._build_sociallogin(),
        ):
            response = self.client.get(reverse('socialaccount_signup'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('social_signup_consent'))

    def test_social_signup_consent_page_starts_with_unchecked_required_boxes(self):
        with patch(
            'core.views.get_pending_social_signup',
            return_value=self._build_sociallogin(),
        ):
            response = self.client.get(reverse('social_signup_consent'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '동의 후 시작합니다')
        self.assertFalse(bool(response.context['form'].fields['agree_terms'].initial))
        self.assertFalse(bool(response.context['form'].fields['agree_privacy'].initial))
        self.assertFalse(bool(response.context['form'].fields['marketing_email_opt_in'].initial))

    def test_social_signup_consent_submission_stashes_consent_in_session(self):
        with patch(
            'core.views.get_pending_social_signup',
            return_value=self._build_sociallogin('naver'),
        ):
            response = self.client.post(
                reverse('social_signup_consent'),
                {
                    'agree_terms': 'on',
                    'agree_privacy': 'on',
                    'marketing_email_opt_in': 'on',
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('socialaccount_signup'))
        consent = get_current_social_signup_consent(self.client.session)
        self.assertIsNotNone(consent)
        self.assertEqual(consent['provider'], 'naver')
        self.assertTrue(consent['marketing_email_opt_in'])

    def test_social_signup_consent_requires_both_required_checkboxes(self):
        with patch(
            'core.views.get_pending_social_signup',
            return_value=self._build_sociallogin(),
        ):
            response = self.client.post(
                reverse('social_signup_consent'),
                {'agree_terms': 'on'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '필수 약관 동의 후 서비스를 이용할 수 있습니다.')
        self.assertIsNone(get_current_social_signup_consent(self.client.session))

    def test_social_signup_consent_page_redirects_to_signup_when_already_confirmed(self):
        request = RequestFactory().get(reverse('social_signup_consent'))
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        mark_current_social_signup_consent(
            request.session,
            provider='kakao',
            marketing_email_opt_in=False,
        )
        request.user = AnonymousUser()
        with patch(
            'core.views.get_pending_social_signup',
            return_value=self._build_sociallogin(),
        ):
            response = social_signup_consent_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('socialaccount_signup'))
