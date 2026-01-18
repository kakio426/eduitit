from django.test import TestCase
from products.models import Product

class ProductModelTest(TestCase):
    def test_product_creation(self):
        product = Product.objects.create(
            title="HWP to PDF Converter",
            description="A powerful tool to convert HWP files to PDF.",
            price=15000,
            is_active=True
        )
        self.assertEqual(product.title, "HWP to PDF Converter")
        self.assertTrue(product.is_active)
