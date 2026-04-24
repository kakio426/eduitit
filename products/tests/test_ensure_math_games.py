from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from products.models import Product, ServiceManual


class EnsureMathGamesCommandTest(TestCase):
    def test_command_creates_product_manual_and_sections_without_duplicates(self):
        call_command("ensure_math_games")
        call_command("ensure_math_games")

        product = Product.objects.get(title="수학 전략 게임")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(Product.objects.filter(title="수학 전략 게임").count(), 1)
        self.assertEqual(product.launch_route_name, "math_games:index")
        self.assertEqual(product.service_type, "game")
        self.assertEqual(product.display_order, 24)
        self.assertEqual(reverse(product.launch_route_name), "/math-games/")
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["님", "24 게임", "힌트"],
        )
