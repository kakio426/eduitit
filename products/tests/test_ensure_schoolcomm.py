from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureSchoolcommCommandTests(TestCase):
    def test_command_creates_service_product_and_manual(self):
        Product.objects.filter(launch_route_name="schoolcomm:main").delete()
        Product.objects.filter(title="학교 커뮤니티").delete()
        Product.objects.filter(title="우리끼리 채팅방").delete()

        call_command("ensure_schoolcomm")

        product = Product.objects.get(launch_route_name="schoolcomm:main")
        self.assertEqual(product.title, "우리끼리 채팅방")
        self.assertEqual(product.icon, "💬")
        self.assertEqual(product.service_type, "classroom")
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)
