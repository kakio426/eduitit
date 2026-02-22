from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ServiceManual


class EnsurePpobgiCommandTest(TestCase):
    def test_command_creates_product_under_classroom_category(self):
        call_command("ensure_ppobgi")

        product = Product.objects.get(title="별빛 추첨기")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.launch_route_name, "ppobgi:main")
        self.assertEqual(product.service_type, "classroom")
        self.assertTrue(product.is_active)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
