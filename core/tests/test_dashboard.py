from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from products.models import Product, UserOwnedProduct

class DashboardTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='password123')
        self.product1 = Product.objects.create(title="Owned Tool", description="Desc", price=100)
        self.product2 = Product.objects.create(title="Unowned Tool", description="Desc", price=200)
        UserOwnedProduct.objects.create(user=self.user, product=self.product1)

    def test_dashboard_access_denied_anonymous(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login

    def test_dashboard_content_for_logged_in_user(self):
        self.client.login(username='tester', password='password123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Owned Tool")
        self.assertNotContains(response, "Unowned Tool")
