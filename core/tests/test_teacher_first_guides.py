from django.test import TestCase
from django.urls import reverse

from core.models import SiteConfig
from products.models import Product, ServiceManual


class TeacherFirstGuidePagesTests(TestCase):
    def setUp(self):
        self.classroom_product = Product.objects.create(
            title='교무수첩',
            description='학급 운영',
            price=0,
            is_active=True,
            service_type='classroom',
            icon='📘',
            color_theme='blue',
        )
        self.work_product = Product.objects.create(
            title='가정통신문',
            description='문서 작성',
            price=0,
            is_active=True,
            service_type='work',
            icon='📝',
            color_theme='purple',
        )
        self.pending_product = Product.objects.create(
            title='상담 예약',
            description='상담 일정 잡기',
            price=0,
            is_active=True,
            service_type='counsel',
            icon='📞',
            color_theme='green',
        )

        self.classroom_manual = ServiceManual.objects.create(
            product=self.classroom_product,
            title='교무수첩 시작하기',
            description='바로 쓰는 핵심 흐름',
            is_published=True,
        )
        self.work_manual = ServiceManual.objects.create(
            product=self.work_product,
            title='가정통신문 빠르게 만들기',
            description='문서 작성 핵심 단계',
            is_published=True,
        )

    def test_service_guide_list_uses_teacher_first_entry_points_and_grouped_sections(self):
        SiteConfig.load().featured_manuals.add(self.classroom_manual)

        response = self.client.get(reverse('service_guide_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('빠른 사용 안내', content)
        self.assertIn('홈', content)
        self.assertIn('전체 서비스', content)
        self.assertIn('지금 많이 찾는 안내', content)
        self.assertIn('문서·작성', content)
        self.assertIn('학급 운영', content)
        self.assertIn('안내 준비 중', content)
        self.assertNotIn('추천 이용방법', content)
        self.assertNotIn('전체 이용방법', content)

    def test_service_guide_list_uses_short_reference_copy(self):
        response = self.client.get(reverse('service_guide_list'))
        content = response.content.decode('utf-8')

        self.assertIn('막힐 때만 짧게 확인할 수 있도록', content)
        self.assertNotIn('홈에서 바로 시작하고, 막히는 순간에만 짧게 확인하는 안내만 남겼습니다.', content)

    def test_tool_guide_is_secondary_reference_not_showroom_modal(self):
        response = self.client.get(reverse('tool_guide'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('외부 AI 도구 참고', content)
        self.assertIn('교실 업무는 Eduitit에서 먼저 시작', content)
        self.assertIn('글쓰기·정리 도움', content)
        self.assertIn('디자인·발표', content)
        self.assertIn('개발·운영 참고', content)
        self.assertNotIn('2026 Edu-Tech Guide', content)
        self.assertNotIn('modalOpen', content)
        self.assertNotIn('업데이트 확인', content)

    def test_service_guide_cards_put_task_title_before_service_name(self):
        SiteConfig.load().featured_manuals.add(self.classroom_manual)

        response = self.client.get(reverse('service_guide_list'))
        content = response.content.decode('utf-8')

        self.assertRegex(content, r'(?s)교무수첩 시작하기.*교무수첩')
        self.assertRegex(content, r'(?s)가정통신문 빠르게 만들기.*가정통신문')
