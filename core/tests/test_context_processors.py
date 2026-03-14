import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.context_processors import search_products, site_config
from core.models import SiteConfig
from products.models import Product


class ContextProcessorTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_site_config_includes_banner_fields_and_safe_notebook_key(self):
        """SiteConfig 전역 컨텍스트는 배너 필드와 안전한 notebook_manual_url 키를 제공한다."""
        config = SiteConfig.load()
        config.banner_text = "안내 배너"
        config.banner_active = True
        config.banner_color = "#111111"
        config.banner_link = "https://example.com/banner"
        config.save()

        request = self.factory.get("/")
        context = site_config(request)

        self.assertEqual(context["banner_text"], "안내 배너")
        self.assertTrue(context["banner_active"])
        self.assertEqual(context["banner_color"], "#111111")
        self.assertEqual(context["banner_link"], "https://example.com/banner")
        self.assertIn("notebook_manual_url", context)
        self.assertEqual(context["notebook_manual_url"], "")


class ServiceLauncherContextTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="launcher-user",
            password="password",
            email="launcher@example.com",
        )

    def _request(self, *, authenticated=False):
        request = self.factory.get("/")
        request.user = self.user if authenticated else AnonymousUser()
        return request

    def test_service_launcher_json_contains_direct_launch_fields(self):
        Product.objects.create(
            title="간편 수합",
            description="설명",
            solve_text="응답을 빠르게 모아요",
            price=0,
            is_active=True,
            service_type="collect_sign",
            icon="📥",
            launch_route_name="collect:landing",
        )

        context = search_products(self._request(authenticated=True))
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "간편 수합")
        self.assertEqual(item["title"], "간편 수합")
        self.assertEqual(item["summary"], "응답을 빠르게 모아요")
        self.assertEqual(item["group_key"], "collect_sign")
        self.assertEqual(item["group_title"], "수합·서명")
        self.assertEqual(item["href"], reverse("collect:landing"))
        self.assertFalse(item["is_external"])

    def test_service_launcher_json_respects_product_is_active(self):
        Product.objects.create(
            title="교무수첩",
            description="표 작업",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="sheetbook:index",
        )
        Product.objects.create(
            title="학급 캘린더",
            description="일정",
            price=0,
            is_active=False,
            service_type="classroom",
            launch_route_name="classcalendar:main",
        )

        context = search_products(self._request(authenticated=True))
        payload = json.loads(context["service_launcher_json"])
        titles = [item["title"] for item in payload]

        self.assertIn("학급 기록 보드", titles)
        self.assertNotIn("학급 캘린더", titles)

    def test_service_launcher_json_supports_public_external_services_for_guest(self):
        Product.objects.create(
            title="유튜브 탈알고리즘",
            description="외부 페이지",
            price=0,
            is_active=True,
            service_type="etc",
            external_url="https://motube-woad.vercel.app/",
        )

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "유튜브 탈알고리즘")
        self.assertEqual(item["href"], "https://motube-woad.vercel.app/")
        self.assertTrue(item["is_external"])
        self.assertEqual(item["group_title"], "외부 서비스")

    def test_service_launcher_json_keeps_all_discoverable_items(self):
        baseline_payload = json.loads(search_products(self._request(authenticated=True))["service_launcher_json"])
        baseline_count = len(baseline_payload)
        for index in range(9):
            Product.objects.create(
                title=f"서비스 {index}",
                description="설명",
                price=0,
                is_active=True,
                service_type="work",
                launch_route_name="collect:landing",
            )

        context = search_products(self._request(authenticated=True))
        payload = json.loads(context["service_launcher_json"])

        self.assertEqual(len(payload), baseline_count + 9)
        titles = {item["title"] for item in payload}
        for index in range(9):
            self.assertIn(f"서비스 {index}", titles)

    def test_new_service_is_auto_included_after_ensure_command(self):
        call_command("ensure_docviewer")

        context = search_products(self._request(authenticated=True))
        payload = json.loads(context["service_launcher_json"])

        titles = [item["title"] for item in payload]
        self.assertIn("문서 미리보기실", titles)

    def test_guest_service_launcher_only_shows_public_candidates_in_curated_order(self):
        Product.objects.create(
            title="쌤BTI",
            description="성향 분석",
            price=0,
            is_active=True,
            service_type="counsel",
            launch_route_name="ssambti:main",
        )
        Product.objects.create(
            title="AI 도구 가이드",
            description="도구 안내",
            price=0,
            is_active=True,
            service_type="edutech",
            launch_route_name="tool_guide",
        )
        Product.objects.create(
            title="Insight Library",
            description="인사이트",
            price=0,
            is_active=True,
            service_type="edutech",
            launch_route_name="insights:list",
        )
        Product.objects.create(
            title="유튜브 탈알고리즘",
            description="외부 탐색",
            price=0,
            is_active=True,
            service_type="etc",
            external_url="https://motube-woad.vercel.app/",
        )
        Product.objects.create(
            title="토닥토닥 선생님 운세",
            description="운세",
            price=0,
            is_active=True,
            service_type="counsel",
            launch_route_name="fortune:saju",
        )
        Product.objects.create(
            title="왁자지껄 교실 윷놀이",
            description="교실 활동",
            price=0,
            is_active=True,
            service_type="game",
            launch_route_name="yut_game",
        )
        Product.objects.create(
            title="간편 수합",
            description="숨겨질 운영 도구",
            price=0,
            is_active=True,
            service_type="collect_sign",
            launch_route_name="collect:landing",
        )

        payload = json.loads(search_products(self._request())["service_launcher_json"])
        titles = [item["title"] for item in payload]

        self.assertIn("쌤BTI", titles)
        self.assertIn("AI 도구 가이드", titles)
        self.assertIn("Insight Library", titles)
        self.assertIn("유튜브 탈알고리즘", titles)
        self.assertIn("토닥토닥 선생님 운세", titles)
        self.assertIn("왁자지껄 교실 윷놀이", titles)
        self.assertLess(titles.index("쌤BTI"), titles.index("AI 도구 가이드"))
        self.assertLess(titles.index("AI 도구 가이드"), titles.index("Insight Library"))
        self.assertLess(titles.index("Insight Library"), titles.index("유튜브 탈알고리즘"))
        self.assertLess(titles.index("유튜브 탈알고리즘"), titles.index("토닥토닥 선생님 운세"))
        self.assertLess(titles.index("토닥토닥 선생님 운세"), titles.index("왁자지껄 교실 윷놀이"))
        self.assertNotIn("간편 수합", titles)

    @override_settings(GLOBAL_SEARCH_ENABLED=False)
    def test_service_launcher_json_absent_when_disabled(self):
        context = search_products(self._request())
        self.assertEqual(context, {})
