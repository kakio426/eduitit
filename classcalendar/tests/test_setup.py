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
