from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsurePdfhubCommandTests(TestCase):
    def test_command_creates_pdfhub_product_and_manual(self):
        call_command("ensure_pdfhub")

        product = Product.objects.get(title="PDF 작업실")
        self.assertEqual(product.launch_route_name, "pdfhub:main")
        self.assertEqual(product.service_type, "work")
        self.assertEqual(product.icon, "fa-solid fa-file-pdf")
        self.assertEqual(product.display_order, 18)
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
