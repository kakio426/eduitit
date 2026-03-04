from django.test import TestCase
from django.urls import reverse

from products.models import Product, ServiceManual


class ServiceGuideDetailLaunchTests(TestCase):
    def test_internal_launch_route_renders_start_link(self):
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

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("classcalendar:main")}"')
        self.assertNotContains(response, "준비 중인 서비스입니다")
