from django.test import TestCase
from django.core.exceptions import ValidationError
from products.models import Product


class ProductModelTests(TestCase):
    """Test suite for Product model extensions"""
    
    def test_product_icon_field_exists(self):
        """Product should have an icon field"""
        product = Product.objects.create(
            title="Test Product",
            description="Test description",
            price=0,
            is_active=True,
            icon="🎲"
        )
        self.assertEqual(product.icon, "🎲")
    
    def test_product_color_theme_field_exists(self):
        """Product should have a color_theme field"""
        product = Product.objects.create(
            title="Test Product",
            description="Test description",
            price=0,
            is_active=True,
            color_theme="purple"
        )
        self.assertEqual(product.color_theme, "purple")
    
    def test_product_card_size_field_exists(self):
        """Product should have a card_size field"""
        product = Product.objects.create(
            title="Test Product",
            description="Test description",
            price=0,
            is_active=True,
            card_size="small"
        )
        self.assertEqual(product.card_size, "small")
    
    def test_product_display_order_field_exists(self):
        """Product should have a display_order field for sorting"""
        product = Product.objects.create(
            title="Test Product",
            description="Test description",
            price=0,
            is_active=True,
            display_order=10
        )
        self.assertEqual(product.display_order, 10)
    
    def test_product_service_type_field_exists(self):
        """Product should have a service_type field"""
        product = Product.objects.create(
            title="Test Product",
            description="Test description",
            price=0,
            is_active=True,
            service_type="game"
        )
        self.assertEqual(product.service_type, "game")
    
    def test_product_external_url_field_exists(self):
        """Product should have an external_url field for linking to external services"""
        product = Product.objects.create(
            title="Test Product",
            description="Test description",
            price=0,
            is_active=True,
            external_url="https://example.com"
        )
        self.assertEqual(product.external_url, "https://example.com")
    
    def test_display_order_sorting(self):
        """Products should be sortable by display_order"""
        # Clear any existing products to avoid interference
        Product.objects.all().delete()
        
        product1 = Product.objects.create(
            title="Product 1",
            description="First",
            price=0,
            is_active=True,
            display_order=3
        )
        product2 = Product.objects.create(
            title="Product 2",
            description="Second",
            price=0,
            is_active=True,
            display_order=1
        )
        product3 = Product.objects.create(
            title="Product 3",
            description="Third",
            price=0,
            is_active=True,
            display_order=2
        )
        
        # Get products ordered by display_order
        products = Product.objects.filter(is_active=True).order_by('display_order')
        
        # Verify order
        self.assertEqual(products[0].title, "Product 2")  # display_order=1
        self.assertEqual(products[1].title, "Product 3")  # display_order=2
        self.assertEqual(products[2].title, "Product 1")  # display_order=3
    
    def test_default_values(self):
        """New fields should have sensible defaults"""
        product = Product.objects.create(
            title="Test Product",
            description="Test description",
            price=0,
            is_active=True
        )
        
        # Check defaults
        self.assertEqual(product.icon, "🛠️")
        self.assertEqual(product.color_theme, "purple")
        self.assertEqual(product.card_size, "small")
        self.assertEqual(product.display_order, 0)
        self.assertEqual(product.service_type, "tool")
        self.assertEqual(product.external_url, "")
