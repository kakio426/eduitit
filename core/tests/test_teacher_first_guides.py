from django.test import TestCase
from django.urls import reverse

from core.guide_links import SERVICE_GUIDE_PADLET_URL
from products.models import Product, ServiceManual


class TeacherFirstGuidePagesTests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            title='학급 캘린더',
            description='학급 운영',
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='classcalendar:main',
            icon='📘',
            color_theme='blue',
        )
        self.manual = ServiceManual.objects.create(
            product=product,
            title='학급 캘린더 시작하기',
            description='바로 쓰는 핵심 흐름',
            is_published=True,
        )

    def test_service_guide_list_redirects_to_padlet(self):
        response = self.client.get(reverse('service_guide_list'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], SERVICE_GUIDE_PADLET_URL)

    def test_tool_guide_redirects_to_padlet(self):
        response = self.client.get(reverse('tool_guide'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], SERVICE_GUIDE_PADLET_URL)

    def test_service_guide_detail_redirects_to_padlet(self):
        response = self.client.get(reverse('service_guide_detail', kwargs={'pk': self.manual.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], SERVICE_GUIDE_PADLET_URL)
