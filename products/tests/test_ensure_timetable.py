from django.core.management import call_command
from django.test import TestCase

from products.models import Product


class EnsureTimetableCommandTests(TestCase):
    def test_command_creates_timetable_as_work_service(self):
        call_command("ensure_timetable")
        product = Product.objects.get(title="전담 시간표·특별실 배치 도우미")
        self.assertEqual(product.launch_route_name, "timetable:main")
        self.assertEqual(product.service_type, "work")

    def test_command_repairs_legacy_classroom_service_type(self):
        Product.objects.create(
            title="전담 시간표·특별실 배치 도우미",
            description="legacy",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="timetable:main",
        )

        call_command("ensure_timetable")
        product = Product.objects.get(title="전담 시간표·특별실 배치 도우미")
        self.assertEqual(product.service_type, "work")
