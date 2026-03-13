from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureSheetbookCommandTests(TestCase):
    def test_command_creates_sheetbook_product_and_manual(self):
        call_command("ensure_sheetbook")

        product = Product.objects.get(title="교무수첩")
        self.assertEqual(product.launch_route_name, "sheetbook:index")
        self.assertEqual(product.service_type, "classroom")
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

    def test_command_preserves_admin_managed_category_fields_and_visibility(self):
        product = Product.objects.create(
            title="교무수첩",
            lead_text="legacy",
            description="legacy",
            price=0,
            is_active=False,
            icon="🛠️",
            color_theme="red",
            card_size="small",
            display_order=777,
            service_type="edutech",
            launch_route_name="",
        )

        call_command("ensure_sheetbook")

        product.refresh_from_db()
        self.assertEqual(product.launch_route_name, "sheetbook:index")
        self.assertFalse(product.is_active)
        self.assertEqual(product.service_type, "edutech")
        self.assertEqual(product.color_theme, "red")
        self.assertEqual(product.display_order, 777)
