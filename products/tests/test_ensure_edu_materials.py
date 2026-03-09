from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ProductFeature


class EnsureEduMaterialsCommandTests(TestCase):
    def test_command_creates_split_education_materials_product(self):
        Product.objects.filter(launch_route_name="edu_materials:main").delete()
        Product.objects.filter(title="교육 자료실").delete()

        Product.objects.create(
            title="legacy edu materials",
            lead_text="legacy",
            description="legacy",
            price=0,
            is_active=False,
            service_type="classroom",
            icon="old",
            launch_route_name="edu_materials:main",
        )

        call_command("ensure_edu_materials")

        product = Product.objects.get(launch_route_name="edu_materials:main")

        self.assertEqual(product.title, "교육 자료실")
        self.assertEqual(product.icon, "🧩")
        self.assertTrue(product.is_active)
        self.assertGreaterEqual(product.features.count(), 3)
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)

        feature_icons = set(
            ProductFeature.objects.filter(product=product).values_list("icon", flat=True)
        )
        self.assertSetEqual(feature_icons, {"🧪", "🛡️", "📎"})
