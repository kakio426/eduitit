from django.test import TestCase, Client
from django.urls import reverse
from products.models import Product


class ProductViewTests(TestCase):
    """Test suite for product views following TDD approach"""
    
    def setUp(self):
        """Create test products"""
        self.client = Client()
        
        # Create featured product
        self.featured_product = Product.objects.create(
            title="Featured Tool",
            description="This is featured",
            price=0,
            is_active=True,
            is_featured=True
        )
        
        # Create active but not featured products
        self.active_product1 = Product.objects.create(
            title="Active Tool 1",
            description="This is active but not featured",
            price=0,
            is_active=True,
            is_featured=False
        )
        
        self.active_product2 = Product.objects.create(
            title="Active Tool 2",
            description="Another active tool",
            price=0,
            is_active=True,
            is_featured=False
        )
        
        # Create inactive product
        self.inactive_product = Product.objects.create(
            title="Inactive Tool",
            description="This should not appear",
            price=0,
            is_active=False,
            is_featured=False
        )
    
    def test_all_active_products_display_on_homepage(self):
        """All active products should appear on homepage regardless of featured status"""
        response = self.client.get(reverse('home'))
        
        # Check that all active products are in context
        products = response.context['products']
        
        # Count active products in database
        active_count = Product.objects.filter(is_active=True).count()
        self.assertEqual(products.count(), active_count)
        
        # Verify our test products are included
        product_titles = [p.title for p in products]
        self.assertIn("Featured Tool", product_titles)
        self.assertIn("Active Tool 1", product_titles)
        self.assertIn("Active Tool 2", product_titles)
        
        # Verify inactive product is NOT included
        self.assertNotIn("Inactive Tool", product_titles)
    
    def test_featured_product_appears_in_hero_card(self):
        """Featured product should be available in context for hero card"""
        response = self.client.get(reverse('home'))
        
        # Check featured_product exists in context
        self.assertIn('featured_product', response.context)
        
        # Verify it's the correct product
        featured = response.context['featured_product']
        self.assertEqual(featured.title, "Featured Tool")
        self.assertTrue(featured.is_featured)
    
    def test_product_detail_page_returns_200(self):
        """Product detail page should return 200 for valid product"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.active_product1.pk})
        )
        self.assertEqual(response.status_code, 200)
    
    def test_product_detail_page_shows_correct_product(self):
        """Product detail page should display correct product information"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.active_product1.pk})
        )
        
        # Check product is in context
        self.assertEqual(response.context['product'].title, "Active Tool 1")
        
        # Check title appears in rendered HTML
        self.assertContains(response, "Active Tool 1")
