from django.test import TestCase, Client
from django.urls import reverse
from products.models import Product, ProductFeature

class ProductPreviewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            title="Test Product",
            description="Test Description",
            price=0,
            is_active=True
        )
        self.feature = ProductFeature.objects.create(
            product=self.product,
            title="Test Feature",
            description="Feature Description",
            icon="fa-solid fa-star"
        )
        self.url = reverse('product_preview', args=[self.product.id])

    def test_preview_view_status_code(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_preview_view_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'products/partials/preview_modal.html')

    def test_preview_view_content(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Test Product")
        self.assertContains(response, "Test Feature")
        self.assertContains(response, "Feature Description")
