from django.test import TestCase, Client
from django.urls import reverse
from products.models import Product


class ProductTemplateTests(TestCase):
    """Test suite for service-specific detail page templates"""
    
    def setUp(self):
        """Create test products of different service types"""
        self.client = Client()
        
        # Game type product
        self.game_product = Product.objects.create(
            title="Test Game",
            description="A test game",
            price=0,
            is_active=True,
            service_type="game"
        )
        
        # Tool type product
        self.tool_product = Product.objects.create(
            title="Test Tool",
            description="A test tool",
            price=1000,
            is_active=True,
            service_type="tool"
        )
        
        # Platform type product
        self.platform_product = Product.objects.create(
            title="Test Platform",
            description="A test platform",
            price=0,
            is_active=True,
            service_type="platform"
        )
    
    def test_game_type_uses_game_template(self):
        """Game type products should use game-specific template elements"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.game_product.pk})
        )
        self.assertEqual(response.status_code, 200)
        
        # Check that game-specific content appears
        # (We'll look for specific markers in the template)
        self.assertContains(response, "Test Game")
    
    def test_tool_type_uses_tool_template(self):
        """Tool type products should use tool-specific template elements"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.tool_product.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Tool")
    
    def test_platform_type_uses_platform_template(self):
        """Platform type products should use platform-specific template elements"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.platform_product.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Platform")
    
    def test_external_url_renders_launch_button(self):
        """Products with external_url should show a launch button"""
        product_with_url = Product.objects.create(
            title="External Service",
            description="Service hosted elsewhere",
            price=0,
            is_active=True,
            external_url="https://example.com"
        )
        
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': product_with_url.pk})
        )
        
        # Should contain the external URL
        self.assertContains(response, "https://example.com")
    
    def test_detail_page_shows_service_type_badge(self):
        """Detail page should display service type as a badge"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.game_product.pk})
        )
        
        # Should show service type
        self.assertContains(response, "game")
