from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ServiceManual


class EnsureSlidesmithCommandTests(TestCase):
    def test_command_creates_slidesmith_product_and_manual(self):
        call_command("ensure_slidesmith")

        product = Product.objects.get(title="초간단 PPT 만들기")
        self.assertEqual(product.launch_route_name, "slidesmith:main")
        self.assertEqual(product.service_type, "work")
        self.assertGreaterEqual(product.features.count(), 3)

        manual = product.manual
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

    def test_command_renames_legacy_product_and_manual_titles(self):
        product = Product.objects.create(
            title="수업 발표 메이커",
            description="desc",
            price=0,
            is_active=True,
        )
        manual = ServiceManual.objects.create(
            product=product,
            title="수업 발표 메이커 사용 가이드",
            description="",
            is_published=False,
        )

        call_command("ensure_slidesmith")

        product.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(product.title, "초간단 PPT 만들기")
        self.assertEqual(product.launch_route_name, "slidesmith:main")
        self.assertEqual(manual.title, "초간단 PPT 만들기 사용 가이드")
        self.assertTrue(manual.is_published)
