from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from products.models import Product

class AutoArticleUITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
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
        
    def test_dashboard_contains_autoarticle_card(self):
        """Verify that the dashboard shows the AutoArticle card."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AutoArticle")
        self.assertContains(response, f"openModal('{self.product.id}')")

    def test_wizard_sidebar_navigation(self):
        """Verify that the wizard sidebar contains expected links."""
        response = self.client.get(reverse('autoarticle:create'))
        self.assertEqual(response.status_code, 200)
        # Check for archive link URL (rendered)
        archive_url = reverse('autoarticle:archive')
        self.assertContains(response, archive_url)
        # Check for sidebar elements
        self.assertContains(response, '환경 설정')
