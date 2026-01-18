from django.test import TestCase
from django.urls import reverse
from products.models import Product

class ProductViewTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title="Test Tool",
            description="Test Description",
            price=100.00,
            is_active=True
        )

    def test_product_list_view(self):
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)

    def test_product_detail_view(self):
        response = self.client.get(reverse('product_detail', args=[self.product.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.description)
