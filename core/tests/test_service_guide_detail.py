from django.test import TestCase
from django.urls import reverse

from core.guide_links import SERVICE_GUIDE_PADLET_URL
from products.models import Product, ServiceManual


class ServiceGuideDetailLaunchTests(TestCase):
    def test_service_guide_detail_redirects_to_padlet(self):
        product = Product.objects.create(
            title="교무수첩",
            description="학급 운영 캘린더",
            price=0,
            is_active=True,
            launch_route_name="classcalendar:main",
            external_url="",
            service_type="classroom",
            icon="📅",
            color_theme="blue",
            card_size="small",
        )
        manual = ServiceManual.objects.create(
            product=product,
            title="교무수첩 사용법",
            description="설명",
            is_published=True,
        )

        response = self.client.get(reverse("service_guide_detail", kwargs={"pk": manual.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], SERVICE_GUIDE_PADLET_URL)
