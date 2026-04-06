from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureSchoolcommCommandTests(TestCase):
    def test_command_creates_service_product_and_manual(self):
        Product.objects.filter(launch_route_name="schoolcomm:main").delete()
        Product.objects.filter(title="학교 커뮤니티").delete()
        Product.objects.filter(title="우리끼리 채팅방").delete()
        Product.objects.filter(title="끼리끼리 채팅방").delete()

        call_command("ensure_schoolcomm")

        product = Product.objects.get(launch_route_name="schoolcomm:main")
        self.assertEqual(product.title, "끼리끼리 채팅방")
        self.assertEqual(product.icon, "💬")
        self.assertEqual(product.service_type, "classroom")
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)

    def test_command_keeps_existing_product_hidden(self):
        Product.objects.filter(launch_route_name="schoolcomm:main").delete()

        Product.objects.create(
            title="legacy schoolcomm",
            description="legacy",
            price=0,
            is_active=False,
            service_type="work",
            display_order=91,
            color_theme="green",
            card_size="hero",
            launch_route_name="schoolcomm:main",
        )

        call_command("ensure_schoolcomm")

        product = Product.objects.get(launch_route_name="schoolcomm:main")
        self.assertEqual(product.title, "끼리끼리 채팅방")
        self.assertFalse(product.is_active)
        self.assertEqual(product.service_type, "work")
        self.assertEqual(product.display_order, 91)
        self.assertEqual(product.color_theme, "green")
        self.assertEqual(product.card_size, "hero")
        self.assertTrue(product.manual.is_published)
