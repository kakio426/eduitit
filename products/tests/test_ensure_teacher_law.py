from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ProductFeature


class EnsureTeacherLawCommandTests(TestCase):
    def test_command_repairs_existing_product_without_reactivating_visibility(self):
        Product.objects.filter(launch_route_name="teacher_law:main").delete()
        Product.objects.filter(title="교사용 AI 법률 가이드").delete()

        Product.objects.create(
            title="legacy teacher law",
            lead_text="legacy",
            description="legacy",
            price=0,
            is_active=False,
            service_type="classroom",
            icon="old",
            launch_route_name="teacher_law:main",
        )

        call_command("ensure_teacher_law")

        product = Product.objects.get(launch_route_name="teacher_law:main")

        self.assertEqual(product.title, "교사용 AI 법률 가이드")
        self.assertEqual(product.icon, "⚖️")
        self.assertFalse(product.is_active)
        self.assertGreaterEqual(product.features.count(), 3)
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)

        feature_icons = set(
            ProductFeature.objects.filter(product=product).values_list("icon", flat=True)
        )
        self.assertSetEqual(feature_icons, {"📚", "🛟", "⚡"})
