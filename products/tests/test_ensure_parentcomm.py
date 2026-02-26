from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureParentCommCommandTests(TestCase):
    def test_command_creates_parentcomm_product_and_manual(self):
        call_command("ensure_parentcomm")

        product = Product.objects.get(title="학부모 소통 허브")
        self.assertEqual(product.launch_route_name, "parentcomm:main")
        self.assertEqual(product.service_type, "counsel")
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

