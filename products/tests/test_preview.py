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

    def test_preview_uses_launch_route_name_when_provided(self):
        self.product.launch_route_name = "collect:landing"
        self.product.save(update_fields=["launch_route_name"])

        response = self.client.get(self.url)
        self.assertEqual(response.context["launch_href"], reverse("collect:landing"))
        self.assertFalse(response.context["launch_is_external"])

    def test_preview_external_url_takes_priority_over_launch_route_name(self):
        self.product.external_url = "https://example.com/direct"
        self.product.launch_route_name = "collect:landing"
        self.product.save(update_fields=["external_url", "launch_route_name"])

        response = self.client.get(self.url)
        self.assertEqual(response.context["launch_href"], "https://example.com/direct")
        self.assertTrue(response.context["launch_is_external"])
