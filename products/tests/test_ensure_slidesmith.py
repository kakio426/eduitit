from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureSlidesmithCommandTests(TestCase):
    def test_command_creates_slidesmith_product_and_manual(self):
        call_command("ensure_slidesmith")

        product = Product.objects.get(title="수업 발표 메이커")
        self.assertEqual(product.launch_route_name, "slidesmith:main")
        self.assertEqual(product.service_type, "work")
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
