from django.test import TestCase
from django.urls import reverse

from products.models import Product


class ProductCatalogTeacherFirstTests(TestCase):
    def setUp(self):
        Product.objects.create(
            title="전자 동의서",
            description="수합·서명",
            price=0,
            is_active=True,
            service_type="collect_sign",
            solve_text="동의서와 서명을 한 곳에서 받습니다.",
            launch_route_name="consent:dashboard",
        )
        Product.objects.create(
            title="교무수첩",
            description="학급 운영",
            price=0,
            is_active=True,
            service_type="classroom",
            solve_text="표와 달력을 같은 흐름으로 씁니다.",
            launch_route_name="sheetbook:index",
        )
        Product.objects.create(
            title="교실 윷놀이",
            description="게임",
            price=0,
            is_active=True,
            service_type="game",
            solve_text="쉬는 시간 활동을 바로 시작합니다.",
            launch_route_name="yut_game",
        )
        Product.objects.create(
            title="AI 도구 가이드",
            description="가이드",
            price=0,
            is_active=True,
            service_type="edutech",
            solve_text="필요할 때만 참고합니다.",
            launch_route_name="tool_guide",
        )

    def test_catalog_renders_teacher_first_headers(self):
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("전체 서비스", content)
        self.assertIn("핵심 업무", content)
        self.assertIn("교실 활동", content)
        self.assertIn("도움말 · 외부 서비스", content)
        self.assertIn("이용방법", content)

    def test_catalog_removes_english_showcase_copy(self):
        response = self.client.get(reverse("product_list"))
        content = response.content.decode("utf-8")

        self.assertNotIn("Digital Solutions", content)
        self.assertNotIn("Play Now", content)
        self.assertNotIn("Details", content)

    def test_catalog_header_uses_short_teacher_first_copy(self):
        response = self.client.get(reverse("product_list"))
        content = response.content.decode("utf-8")

        self.assertIn("해야 하는 일을 먼저 찾으세요", content)
        self.assertIn("주요 작업 먼저", content)
        self.assertNotIn("교실에서 자주 하는 일을 기준으로 서비스를 정리했습니다", content)

    def test_catalog_context_contains_grouped_sections(self):
        response = self.client.get(reverse("product_list"))
        self.assertIn("sections", response.context)
        self.assertIn("aux_sections", response.context)
        self.assertIn("games", response.context)
        self.assertGreaterEqual(len(response.context["sections"]), 1)
        self.assertGreaterEqual(len(response.context["games"]), 1)

    def test_catalog_cards_use_task_first_labels_with_service_name_as_supporting_text(self):
        response = self.client.get(reverse("product_list"))
        content = response.content.decode("utf-8")

        self.assertRegex(content, r'(?s)동의서와 서명을 한 곳에서 받습니다\..*전자 동의서')
        self.assertRegex(content, r'(?s)표와 달력을 같은 흐름으로 씁니다\..*교무수첩')
