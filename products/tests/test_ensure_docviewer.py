from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureDocviewerCommandTests(TestCase):
    def test_command_creates_internal_docviewer_product_and_manual(self):
        call_command("ensure_docviewer")

        product = Product.objects.get(title="문서 미리보기실")
        self.assertEqual(product.launch_route_name, "docviewer:main")
        self.assertEqual(product.service_type, "work")
        self.assertFalse(product.is_active)
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

    def test_command_deactivates_existing_public_product(self):
        product = Product.objects.create(
            title="문서 미리보기실",
            description="legacy",
            price=0,
            is_active=True,
            service_type="work",
            launch_route_name="docviewer:main",
        )

        call_command("ensure_docviewer")
        product.refresh_from_db()

        self.assertFalse(product.is_active)
