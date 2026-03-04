from django.test import TestCase
from django.core.management import call_command
from products.models import Product, ServiceManual


class SetupTest(TestCase):
    def test_ensure_classcalendar_command(self):
        call_command('ensure_classcalendar')

        product = Product.objects.filter(launch_route_name='classcalendar:main').first()
        self.assertIsNotNone(product)

        manual = ServiceManual.objects.filter(product__launch_route_name='classcalendar:main').first()
        self.assertIsNotNone(manual)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)

    def test_ensure_classcalendar_backfills_legacy_product_route(self):
        legacy = Product.objects.create(
            title="교무수첩",
            description="legacy desc",
            price=0,
            is_active=True,
            launch_route_name="",
            external_url="/products/legacy/",
            service_type="etc",
        )

        call_command('ensure_classcalendar')

        legacy.refresh_from_db()
        self.assertEqual(legacy.launch_route_name, 'classcalendar:main')
        self.assertEqual(legacy.external_url, "")
        self.assertEqual(legacy.service_type, "classroom")
