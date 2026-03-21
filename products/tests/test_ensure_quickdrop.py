from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureQuickdropCommandTests(TestCase):
    def test_command_repairs_quickdrop_without_overwriting_admin_display_fields(self):
        Product.objects.filter(launch_route_name="quickdrop:landing").delete()
        Product.objects.filter(title="바로전송").delete()

        Product.objects.create(
            title="legacy quickdrop",
            lead_text="legacy",
            description="legacy",
            price=9900,
            is_active=False,
            is_guest_allowed=True,
            icon="old",
            color_theme="green",
            card_size="hero",
            display_order=91,
            service_type="work",
            launch_route_name="quickdrop:landing",
            solve_text="legacy",
        )

        call_command("ensure_quickdrop")

        product = Product.objects.get(launch_route_name="quickdrop:landing")

        self.assertEqual(product.title, "바로전송")
        self.assertEqual(product.icon, "⚡")
        self.assertEqual(product.launch_route_name, "quickdrop:landing")
        self.assertEqual(product.external_url, "")
        self.assertFalse(product.is_active)
        self.assertFalse(product.is_guest_allowed)
        self.assertEqual(product.color_theme, "green")
        self.assertEqual(product.card_size, "hero")
        self.assertEqual(product.display_order, 91)
        self.assertEqual(product.service_type, "work")
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)
