from django.core.management import call_command
from django.test import TestCase

from products.models import ManualSection, Product, ServiceManual


class EnsureInsightsCommandTest(TestCase):
    def test_command_creates_product_with_valid_launch_route(self):
        call_command("ensure_insights")

        product = Product.objects.get(title="Insight Library")
        self.assertEqual(product.launch_route_name, "insights:list")
        self.assertEqual(product.service_type, "edutech")
        self.assertIn(product.color_theme, {code for code, _ in Product.COLOR_CHOICES})

        manual = ServiceManual.objects.get(product=product)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

    def test_command_repairs_legacy_invalid_values_and_manual(self):
        product = Product.objects.create(
            title="Insight Library",
            description="legacy",
            price=0,
            is_active=True,
            service_type="tool",
            color_theme="indigo",
            launch_route_name="",
        )
        manual = ServiceManual.objects.create(
            product=product,
            title="Legacy Manual",
            is_published=False,
        )
        ManualSection.objects.create(
            manual=manual,
            title="시작하기",
            content="legacy",
            display_order=1,
        )

        call_command("ensure_insights")

        product.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(product.launch_route_name, "insights:list")
        self.assertEqual(product.service_type, "edutech")
        self.assertEqual(product.color_theme, "purple")
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

    def test_command_deactivates_legacy_insight_product(self):
        legacy = Product.objects.create(
            title="인사이트",
            description="legacy",
            price=0,
            is_active=True,
            service_type="edutech",
        )

        call_command("ensure_insights")

        legacy.refresh_from_db()
        self.assertFalse(legacy.is_active)
