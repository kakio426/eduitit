from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from products.models import Product

class AutoArticleUITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='password')
        profile = self.user.userprofile
        profile.nickname = "담임선생님"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        UserPolicyConsent.objects.create(
            user=self.user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=self.user.date_joined,
            agreement_source="test",
        )
        self.client.login(username='testuser', password='password')
        
        # Create a product for AutoArticle if it doesn't exist
        self.product = Product.objects.create(
            title="AutoArticle",
            description="AI Article Generator",
            external_url="/autoarticle/",
            price=0,
            is_active=True,
            icon="fa-newspaper",
            color_theme="purple"
        )
        
    def test_dashboard_redirects_to_home(self):
        """The legacy dashboard entry should keep routing teachers to home."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("home"))

    def test_wizard_sidebar_navigation(self):
        """Verify that the wizard sidebar contains expected links."""
        response = self.client.get(reverse('autoarticle:create'))
        self.assertEqual(response.status_code, 200)
        # Check for archive link URL (rendered)
        archive_url = reverse('autoarticle:archive')
        self.assertContains(response, archive_url)
        # Check for sidebar elements
        self.assertContains(response, '환경 설정')
