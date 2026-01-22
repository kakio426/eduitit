from django.test import TestCase, Client
from django.contrib.auth.models import User
from products.models import Product


class DashboardModalTest(TestCase):
    """Test that dashboard renders modal triggers for all products"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
        # Create test products
        self.product1 = Product.objects.create(
            title="Test Product 1",
            description="Description 1",
            price=1000,
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
        """Verify each product card calls openModal function"""
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # Count active products
        active_products = Product.objects.filter(is_active=True).count()
        
        # Count openModal calls in rendered HTML
        content = response.content.decode('utf-8')
        modal_trigger_count = content.count('openModal(')
        
        self.assertEqual(
            modal_trigger_count, 
            active_products,
            f"Expected {active_products} modal triggers, found {modal_trigger_count}"
        )
    
    def test_modal_trigger_includes_product_id(self):
        """Verify modal triggers pass product ID"""
        response = self.client.get('/dashboard/')
        content = response.content.decode('utf-8')
        
        # Check that openModal is called (the template variable will be rendered as the actual ID)
        self.assertIn('openModal(', content,
                     "Dashboard should have openModal calls")
        
        # Count that we have the right number of onclick attributes
        import re
        onclick_count = len(re.findall(r'onclick="openModal\(\d+\)"', content))
        self.assertEqual(onclick_count, 2, 
                        f"Expected 2 onclick handlers, found {onclick_count}")
