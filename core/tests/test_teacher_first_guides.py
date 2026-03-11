from django.test import TestCase
from django.urls import reverse

from core.models import SiteConfig
from products.models import Product, ServiceManual


class TeacherFirstGuidePagesTests(TestCase):
    def setUp(self):
        self.classroom_product = Product.objects.create(
            title='학급 캘린더',
            description='학급 운영',
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='classcalendar:main',
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
            title='학급 캘린더 시작하기',
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

        self.assertIn('막힐 때만 짧게 보는 안내', content)
        self.assertIn('처음 시작', content)
        self.assertIn('학급 캘린더', content)
        self.assertIn('자주 하는 업무', content)
        self.assertIn('상담 예약', content)
        self.assertNotIn('추천 이용방법', content)
        self.assertNotIn('교무수첩', content)

    def test_service_guide_list_uses_short_reference_copy(self):
        response = self.client.get(reverse('service_guide_list'))
        content = response.content.decode('utf-8')

        self.assertIn('무엇을 설명하는지보다 언제 열면 되는지 먼저 보이도록', content)
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

        self.assertRegex(content, r'(?s)학급 캘린더 시작하기.*학급 캘린더')
        self.assertRegex(content, r'(?s)가정통신문 빠르게 만들기.*가정통신문')

    def test_service_guide_list_does_not_promote_record_board_as_calendar_peer(self):
        sheetbook_product = Product.objects.create(
            title='학급 기록 보드',
            description='기록 작업',
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='sheetbook:index',
            icon='📒',
            color_theme='blue',
        )
        ServiceManual.objects.create(
            product=sheetbook_product,
            title='학급 기록 보드 이어쓰기',
            description='기록 흐름 안내',
            is_published=True,
        )

        response = self.client.get(reverse('service_guide_list'))
        content = response.content.decode('utf-8')

        self.assertIn('학급 캘린더', content)
        self.assertNotIn('기록 보드 이어쓰기', content)
        self.assertNotIn('학급 기록 보드 이어쓰기', content)
