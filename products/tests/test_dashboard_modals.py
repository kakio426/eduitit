from pathlib import Path

from django.conf import settings
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import UserProfile
from products.models import Product


class DashboardModalTest(TestCase):
    """Test that dashboard renders modal triggers for all products"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            email='testuser@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = '테스트유저'
        profile.role = ''
        profile.save()
        self.client.login(username='testuser', password='testpass')
        
        # Create test products
        self.product1 = Product.objects.create(
            title="Test Product 1",
            description="Description 1",
            price=0,
            is_active=True,
            icon="🧪",
            color_theme="purple"
        )
        self.product2 = Product.objects.create(
            title="Test Product 2",
            description="Description 2",
            price=0,
            is_active=True,
            external_url="/test/",
            icon="🔬",
            color_theme="blue"
        )
    
    def test_all_products_have_modal_triggers(self):
        """Verify product cards include data-product-id for modal open flow"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        self.assertIn(f'data-product-id="{self.product1.id}"', content)
        self.assertIn(f'data-product-id="{self.product2.id}"', content)
    
    def test_modal_trigger_includes_product_id(self):
        """Verify modal opener script exists in the loaded dashboard assets."""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        
        self.assertIn('data-product-id=', content)
        self.assertIn('/static/core/js/base.js', content)

        base_js = Path(settings.BASE_DIR) / 'core' / 'static' / 'core' / 'js' / 'base.js'
        self.assertIn('window.openModal', base_js.read_text(encoding='utf-8'),
                     "Base dashboard asset should include modal open handler script")
