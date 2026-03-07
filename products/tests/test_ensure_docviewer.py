from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureDocviewerCommandTests(TestCase):
    def test_command_creates_docviewer_product_and_manual(self):
        call_command("ensure_docviewer")

        product = Product.objects.get(title="문서 미리보기실")
        self.assertEqual(product.launch_route_name, "docviewer:main")
        self.assertEqual(product.service_type, "work")
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
