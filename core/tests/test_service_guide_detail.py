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
        self.assertContains(response, "학급 캘린더 열기")
        self.assertContains(response, "학급 캘린더 사용법")
        self.assertContains(response, "다른 안내 보기")
        self.assertNotContains(response, "준비 중인 서비스입니다")
        self.assertNotContains(response, "이제 직접 사용해보세요!")
        self.assertNotContains(response, "교무수첩")
