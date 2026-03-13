from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ProductFeature


class EnsureMessageboxCommandTests(TestCase):
    def test_command_repairs_existing_product_without_reactivating_visibility(self):
        Product.objects.filter(launch_route_name="messagebox:main").delete()
        Product.objects.filter(title="업무 메시지 보관함").delete()

        Product.objects.create(
            title="legacy messagebox",
            lead_text="legacy",
            description="legacy",
            price=0,
            is_active=False,
            service_type="classroom",
            icon="old",
            launch_route_name="messagebox:main",
        )

        call_command("ensure_messagebox")

        product = Product.objects.get(launch_route_name="messagebox:main")

        self.assertEqual(product.title, "업무 메시지 보관함")
        self.assertEqual(product.icon, "🗂️")
        self.assertFalse(product.is_active)
        self.assertGreaterEqual(product.features.count(), 3)
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)

        feature_icons = set(
            ProductFeature.objects.filter(product=product).values_list("icon", flat=True)
        )
        self.assertSetEqual(feature_icons, {"📋", "📅", "🔗"})
