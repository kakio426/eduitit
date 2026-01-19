from django.test import TestCase, Client
from django.urls import reverse
from products.models import Product

class HomeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Clean up existing products from migrations to have a clean state if needed,
        # or just rely on containing checks.
        # But data migrations run. So '🐎 온라인 윷놀이' might already exist.
        
        # Determine if Yut needed to be created
        if not Product.objects.filter(title="🐎 온라인 윷놀이").exists():
            Product.objects.create(title="🐎 온라인 윷놀이", description="Game", price=0, is_active=True)
            
        # Create a standard product
        self.std_product = Product.objects.create(title="Standard Tool", description="Desc", price=100, is_active=True)

    def test_home_view_context_and_links(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check Yut Noli presence and Instant Access Link
        self.assertIn("🐎 온라인 윷놀이", content)
        # Should link to yut_game directly
        self.assertIn("href='/products/yut/'", content)
        
        # Check Standard Product behavior
        self.assertIn("Standard Tool", content)
        # Should link to detail page
        expected_url = f"/products/{self.std_product.pk}/"
        self.assertIn(f"href='{expected_url}'", content)
