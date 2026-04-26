from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from products.models import Product, ServiceManual


class EnsureColorbeatCommandTest(TestCase):
    def test_command_creates_product_manual_and_sections_without_duplicates(self):
        call_command("ensure_colorbeat")
        call_command("ensure_colorbeat")

        product = Product.objects.get(title="알록달록 비트메이커")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(Product.objects.filter(title="알록달록 비트메이커").count(), 1)
        self.assertEqual(product.launch_route_name, "colorbeat:main")
        self.assertEqual(product.service_type, "game")
        self.assertEqual(product.display_order, 25)
        self.assertEqual(reverse(product.launch_route_name), "/colorbeat/")
        self.assertTrue(manual.is_published)
        self.assertEqual(manual.sections.count(), 3)
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["8칸 비트", "소리 세트", "코드 보기"],
        )
        self.assertCountEqual(
            list(manual.sections.values_list("title", flat=True)),
            ["시작", "비트", "코드"],
        )
