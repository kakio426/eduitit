from django.test import TestCase
from django.urls import reverse

from products.models import ManualSection, Product, ServiceManual


class ServiceGuideDetailLaunchTests(TestCase):
    def test_service_guide_detail_renders_internal_slide_modal(self):
        product = Product.objects.create(
            title="학급 캘린더",
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
            title="학급 캘린더 사용법",
            description="설명",
            is_published=True,
        )
        ManualSection.objects.create(
            manual=manual,
            title="오늘 보기 확인",
            content="오늘 일정과 메모를 먼저 확인합니다.",
            display_order=1,
        )

        response = self.client.get(reverse("service_guide_detail", kwargs={"pk": manual.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학급 캘린더 사용법")
        self.assertContains(response, "service-guide-modal-data")
        self.assertContains(response, f'data-service-guide-autostart="{manual.pk}"')
        self.assertContains(response, "오늘 보기 확인")
