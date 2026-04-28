from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from products.models import ManualSection, Product, ServiceManual


class EnsureBambooCommandTest(TestCase):
    def test_command_creates_product_manual_and_sections(self):
        call_command("ensure_bamboo")
        call_command("ensure_bamboo")

        product = Product.objects.get(title="교사 대나무숲")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(Product.objects.filter(title="교사 대나무숲").count(), 1)
        self.assertEqual(product.launch_route_name, "bamboo:feed")
        self.assertEqual(product.service_type, "counsel")
        self.assertTrue(product.is_guest_allowed)
        self.assertEqual(reverse(product.launch_route_name), "/bamboo/")
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(ManualSection.objects.filter(manual=manual).count(), 3)
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["3중 안전", "풍자 우화", "익명 피드"],
        )
