from django.test import TestCase
from django.contrib.auth.models import User
from core.models import UserProfile
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
            title="가이드 인사이트",
            description="가이드",
            price=0,
            is_active=True,
            service_type="edutech",
            solve_text="필요한 인사이트를 빠르게 확인합니다.",
            launch_route_name="insights:list",
        )
        Product.objects.create(
            title="상담 리프레시",
            description="상담",
            price=0,
            is_active=True,
            service_type="counsel",
            solve_text="상담 전 성향과 분위기를 먼저 살핍니다.",
            launch_route_name="studentmbti:landing",
        )

    def test_catalog_renders_teacher_first_headers(self):
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("전체 서비스", content)
        self.assertIn("핵심 업무", content)
        self.assertIn("상담·리프레시", content)
        self.assertIn("가이드·인사이트", content)
        self.assertIn("교실 활동", content)
        self.assertNotIn("도움말 · 외부 서비스", content)
        self.assertIn("이용방법", content)
        self.assertIn("https://padlet.com/kakio1q2w/eduitit-wrjbzmk8oufxdzcv", content)

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

    def test_catalog_promotes_refresh_and_guide_into_main_sections(self):
        response = self.client.get(reverse("product_list"))
        section_keys = [section["key"] for section in response.context["sections"]]
        aux_keys = [section["key"] for section in response.context["aux_sections"]]

        self.assertIn("refresh", section_keys)
        self.assertIn("guide", section_keys)
        self.assertNotIn("refresh", aux_keys)
        self.assertNotIn("guide", aux_keys)

    def test_catalog_cards_use_compact_teacher_first_copy(self):
        response = self.client.get(reverse("product_list"))
        content = response.content.decode("utf-8")

        self.assertRegex(content, r'(?s)동의서와 서명을 한 곳에서 받습니다\..*전자 동의서')
        self.assertRegex(content, r'(?s)표와 달력을 같은 흐름으로 씁니다\..*교무수첩')

    def test_catalog_context_has_compact_card_fields(self):
        response = self.client.get(reverse("product_list"))
        products = [product for section in response.context["sections"] for product in section["products"]]
        target = next(product for product in products if product.title == "교무수첩")

        self.assertEqual(target.card_title, "표와 달력을 같은 흐름으로 씁니다.")
        self.assertEqual(target.card_subtitle, "교무수첩")

    def test_catalog_strips_leading_emoji_from_teacher_first_labels(self):
        Product.objects.create(
            title="📒 교무수첩",
            description="학급 운영",
            price=0,
            is_active=True,
            service_type="classroom",
            icon="📒",
            solve_text="📒 표와 일정을 한 번에 정리합니다.",
            launch_route_name="sheetbook:index",
        )

        response = self.client.get(reverse("product_list"))
        content = response.content.decode("utf-8")
        products = [product for section in response.context["sections"] for product in section["products"]]
        emoji_product = next(product for product in products if product.title == "📒 교무수첩")

        self.assertEqual(emoji_product.teacher_first_task_label, "표와 일정을 한 번에 정리합니다.")
        self.assertEqual(emoji_product.teacher_first_service_label, "교무수첩")
        self.assertIn("표와 일정을 한 번에 정리합니다.", content)
        self.assertNotIn("📒 표와 일정을 한 번에 정리합니다.", content)
    def test_catalog_shows_student_games_entry_for_authenticated_teacher(self):
        user = User.objects.create_user(
            username='catalogteacher',
            password='pass1234',
            email='catalogteacher@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.nickname = '담임'
        profile.role = 'school'
        profile.save(update_fields=['nickname', 'role'])
        self.client.force_login(user)

        response = self.client.get(reverse("product_list"))
        content = response.content.decode("utf-8")

        self.assertIn("학생용 게임 입장", content)
        self.assertIn("학생 링크 복사", content)
        self.assertIn("학생 화면 미리보기", content)

    def test_catalog_hides_student_games_entry_for_anonymous_user(self):
        response = self.client.get(reverse("product_list"))
        content = response.content.decode("utf-8")

        self.assertNotIn("학생용 게임 입장", content)
