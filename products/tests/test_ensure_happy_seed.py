from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureHappySeedCommandTests(TestCase):
    def test_command_uses_dashboard_as_launch_route(self):
        call_command("ensure_happy_seed")

        product = Product.objects.get(title="행복의 씨앗")
        self.assertEqual(product.launch_route_name, "happy_seed:dashboard")
        self.assertEqual(product.service_type, "classroom")
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
