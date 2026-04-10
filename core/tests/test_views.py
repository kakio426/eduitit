from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from core.models import PageViewLog, ProductUsageLog, UserPolicyConsent
from core.policy_consent import mark_current_policy_consent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from core.views import admin_dashboard_view
from products.models import Product


class AdminDashboardViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        # UserProfile is auto-created via signal, but ensure it exists
        from core.models import UserProfile
        UserProfile.objects.get_or_create(user=self.superuser)
        UserPolicyConsent.objects.create(
            user=self.superuser,
            provider='direct',
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source='required_gate',
        )
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@test.com',
            password='testpass123'
        )
        UserProfile.objects.get_or_create(user=self.regular_user)

    def _build_request(self, *, method='get', data=None, user=None):
        request_factory = getattr(self.factory, method.lower())
        request = request_factory(reverse('admin_dashboard'), data=data or {})
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.user = user or self.superuser
        mark_current_policy_consent(request.session, request.user)
        setattr(request, '_messages', FallbackStorage(request))
        return request
    
    def test_admin_can_update_notebook_manual_url(self):
        """Test that superuser can update notebook_manual_url via POST"""
        Product.objects.create(
            title='교사 백과사전',
            description='설명',
            price=0,
            is_active=True,
        )
        
        test_url = "https://notebooklm.google.com/notebook/test123"
        response = admin_dashboard_view(
            self._build_request(
                method='post',
                data={'notebook_manual_url': test_url},
            )
        )
        
        # Should redirect or return 200
        self.assertIn(response.status_code, [200, 302])
        
        # Verify URL was saved
        notebook_product = Product.objects.filter(title='교사 백과사전').order_by('id').first()
        self.assertIsNotNone(notebook_product)
        self.assertEqual(notebook_product.external_url, test_url)

    def test_non_superuser_cannot_access_admin_dashboard(self):
        """Test that regular users cannot access admin dashboard"""
        response = admin_dashboard_view(self._build_request(user=self.regular_user))
        
        # Should redirect to home
        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard_shows_top_activity_sections(self):
        product = Product.objects.create(
            title='테스트 도구',
            description='설명',
            price=0,
            is_active=True,
            launch_route_name='testtool:main',
        )
        today = timezone.localdate()
        PageViewLog.objects.create(
            user=self.superuser,
            visitor_key='user:1',
            identity_type='user',
            is_bot=False,
            path='/',
            route_name='home',
        )
        second_page_log = PageViewLog.objects.create(
            user=self.superuser,
            visitor_key='user:2',
            identity_type='user',
            is_bot=False,
            path='/quickdrop/',
            route_name='testtool:main',
        )
        PageViewLog.objects.filter(pk=second_page_log.pk).update(view_date=today)
        ProductUsageLog.objects.create(
            user=self.superuser,
            product=product,
            action='launch',
            source='home_quick',
        )

        response = admin_dashboard_view(self._build_request())
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('최근 14일 많이 본 페이지', content)
        self.assertIn('홈에서 많이 연 서비스', content)
        self.assertIn('테스트 도구', content)
