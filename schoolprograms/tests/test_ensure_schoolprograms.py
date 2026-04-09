from django.core.management import call_command
from django.test import TestCase

from products.models import ManualSection, Product, ServiceManual


class EnsureSchoolProgramsCommandTests(TestCase):
    def test_ensure_command_creates_product_and_manual(self):
        call_command("ensure_schoolprograms")

        product = Product.objects.get(launch_route_name="schoolprograms:landing")
        self.assertEqual(product.title, "학교 체험·행사 찾기")
        self.assertEqual(product.service_type, "classroom")
        self.assertTrue(product.is_guest_allowed)

        manual = ServiceManual.objects.get(product=product)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(ManualSection.objects.filter(manual=manual).count(), 3)
