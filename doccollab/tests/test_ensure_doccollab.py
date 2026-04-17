from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ServiceManual


class EnsureDoccollabCommandTests(TestCase):
    def test_command_creates_product_manual_and_features(self):
        call_command("ensure_doccollab")

        product = Product.objects.get(title="함께문서실")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.launch_route_name, "doccollab:main")
        self.assertEqual(product.service_type, "work")
        self.assertTrue(product.is_active)
        self.assertIn("HWP와 HWPX", product.lead_text)
        self.assertTrue(manual.is_published)
        self.assertEqual(manual.title, "함께문서실 사용 가이드")
        self.assertIn("HWP 또는 HWPX", manual.description)
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["오늘 작업", "같이 편집", "저장과 공식본"],
        )
        self.assertCountEqual(
            list(manual.sections.values_list("title", flat=True)),
            ["시작", "같이 쓰기", "저장"],
        )
