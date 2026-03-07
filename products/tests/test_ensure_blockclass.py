from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureBlockclassCommandTests(TestCase):
    def test_command_creates_blockclass_product_and_manual(self):
        call_command("ensure_blockclass")

        product = Product.objects.get(title="블록활동 실습실")
        self.assertEqual(product.launch_route_name, "blockclass:main")
        self.assertEqual(product.service_type, "classroom")
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
