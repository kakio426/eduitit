from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from products.models import ManualSection, Product, ServiceManual


class EnsureMancalaCommandTest(TestCase):
    def test_command_creates_product_manual_and_sections(self):
        call_command("ensure_mancala")
        call_command("ensure_mancala")

        product = Product.objects.get(title="만칼라")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(Product.objects.filter(title="만칼라").count(), 1)
        self.assertEqual(product.launch_route_name, "mancala:main")
        self.assertEqual(product.service_type, "game")
        self.assertEqual(product.display_order, 24)
        self.assertEqual(reverse(product.launch_route_name), "/mancala/")
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(ManualSection.objects.filter(manual=manual).count(), 3)
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["분배와 셈", "3D 경로", "AI 대전"],
        )
