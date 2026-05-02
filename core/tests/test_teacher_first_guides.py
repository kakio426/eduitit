from django.test import TestCase
from django.urls import reverse

from products.models import ManualSection, Product, ServiceManual


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
        ManualSection.objects.create(
            manual=self.manual,
            title='오늘 일정 보기',
            content='홈에서 오늘 일정을 먼저 확인합니다.',
            display_order=1,
        )

    def test_service_guide_list_renders_internal_modal_center(self):
        response = self.client.get(reverse('service_guide_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '서비스 이용방법')
        self.assertContains(response, 'service-guide-modal-data')
        self.assertContains(response, 'data-service-guide-trigger')

    def test_legacy_manuals_route_stays_internal(self):
        response = self.client.get(reverse('legacy_service_guide_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '서비스 이용방법')
        self.assertNotContains(response, 'padlet.com')

    def test_tool_guide_redirects_to_internal_service_guides(self):
        response = self.client.get(reverse('tool_guide'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse('service_guide_list'))

    def test_service_guide_detail_renders_internal_modal(self):
        response = self.client.get(reverse('service_guide_detail', kwargs={'pk': self.manual.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '학급 캘린더 시작하기')
        self.assertContains(response, f'data-service-guide-autostart="{self.manual.pk}"')

    def test_topbar_guide_link_targets_current_service_manual(self):
        product = Product.objects.create(
            title='수합',
            description='자료 제출',
            price=0,
            is_active=True,
            service_type='collect_sign',
            launch_route_name='collect:landing',
            icon='folder',
            color_theme='purple',
        )
        manual = ServiceManual.objects.create(
            product=product,
            title='수합 이용방법',
            description='',
            is_published=True,
        )

        response = self.client.get(reverse('collect:landing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-service-guide-nav-link="desktop"')
        self.assertContains(response, f'href="{reverse("service_guide_detail", kwargs={"pk": manual.pk})}"')

    def test_topbar_guide_link_falls_back_to_guide_list(self):
        response = self.client.get(reverse('product_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-service-guide-nav-link="desktop"')
        self.assertContains(response, f'href="{reverse("service_guide_list")}"')

    def test_hide_navbar_screen_does_not_render_guide_entry(self):
        response = self.client.get(reverse('ppobgi:main'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-service-guide-nav-link')
