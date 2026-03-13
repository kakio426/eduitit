from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ProductFeature


class EnsureTextbooksCommandTests(TestCase):
    def test_command_repairs_existing_product_as_textbook_service_without_reactivating_visibility(self):
        Product.objects.filter(launch_route_name="textbooks:main").delete()
        Product.objects.filter(title="교과서 라이브 수업").delete()

        Product.objects.create(
            title="legacy textbooks",
            lead_text="legacy",
            description="legacy",
            price=0,
            is_active=False,
            service_type="classroom",
            icon="old",
            launch_route_name="textbooks:main",
        )

        call_command("ensure_textbooks")

        product = Product.objects.get(launch_route_name="textbooks:main")

        self.assertEqual(product.title, "교과서 라이브 수업")
        self.assertEqual(product.icon, "📘")
        self.assertFalse(product.is_active)
        self.assertGreaterEqual(product.features.count(), 3)
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)

        feature_icons = set(
            ProductFeature.objects.filter(product=product).values_list("icon", flat=True)
        )
        self.assertSetEqual(feature_icons, {"📄", "🖥️", "✏️"})
