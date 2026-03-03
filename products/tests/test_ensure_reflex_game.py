from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ServiceManual


class EnsureReflexGameCommandTest(TestCase):
    def test_command_creates_game_product_next_to_breakthrough(self):
        call_command("ensure_reflex_game")

        product = Product.objects.get(title="탭 순발력 챌린지")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.launch_route_name, "reflex_game:main")
        self.assertEqual(product.service_type, "game")
        self.assertEqual(product.display_order, 22)
        self.assertTrue(product.is_active)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

