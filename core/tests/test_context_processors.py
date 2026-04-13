import json

from django.contrib import messages as django_messages
from django.core.management import call_command
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.context_processors import search_products, site_config, toast_messages
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

        user = User.objects.create_user(username="contextuser", password="pass1234")
        profile = user.userprofile
        profile.pinned_notice_expanded = True
        profile.save(update_fields=["pinned_notice_expanded"])

        request = self.factory.get("/")
        request.user = user
        context = site_config(request)

        self.assertEqual(context["banner_text"], "안내 배너")
        self.assertTrue(context["banner_active"])
        self.assertEqual(context["banner_color"], "#111111")
        self.assertEqual(context["banner_link"], "https://example.com/banner")
        self.assertTrue(context["pinned_notice_expanded"])
        self.assertIn("notebook_manual_url", context)
        self.assertEqual(context["notebook_manual_url"], "")

    def test_site_config_defaults_notice_toggle_to_collapsed_for_anonymous(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        context = site_config(request)

        self.assertFalse(context["pinned_notice_expanded"])

    def test_toast_messages_maps_error_level_to_danger_tag(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = self.client.session
        request._messages = FallbackStorage(request)

        django_messages.error(request, "알림 테스트")
        context = toast_messages(request)

        self.assertEqual(context["toast_messages"][0]["tag"], "danger")


class ServiceLauncherContextTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self):
        return self.factory.get("/")

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

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "간편 수합")
        self.assertEqual(item["title"], "간편 수합")
        self.assertEqual(item["summary"], "응답을 빠르게 모아요")
        self.assertEqual(item["group_key"], "collect_sign")
        self.assertEqual(item["group_title"], "수합·서명")
        self.assertEqual(item["href"], reverse("collect:landing"))
        self.assertFalse(item["is_external"])

    def test_service_launcher_json_uses_hwpxchat_cleanup_summary(self):
        Product.objects.create(
            title="한글문서 AI야 읽어줘",
            description="공문을 읽어 업무 카드로 정리합니다.",
            lead_text="공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.",
            solve_text="공문에서 해야 할 일을 바로 정리해요",
            result_text="실행용 업무 카드",
            price=0,
            is_active=True,
            service_type="work",
            icon="📄",
            launch_route_name="hwpxchat:main",
        )

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "한글문서 AI야 읽어줘")
        self.assertEqual(item["summary"], "공문에서 해야 할 일을 바로 정리해요")
        self.assertEqual(item["group_key"], "doc_write")
        self.assertEqual(item["href"], reverse("hwpxchat:main"))
        self.assertFalse(item["is_external"])

    def test_service_launcher_json_respects_product_is_active(self):
        Product.objects.create(
            title="학급 캘린더",
            description="일정",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="classcalendar:main",
        )
        Product.objects.create(
            title="숨김 학급 도구",
            description="표 작업",
            price=0,
            is_active=False,
            service_type="classroom",
            launch_route_name="collect:landing",
        )

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])
        titles = [item["title"] for item in payload]

        self.assertIn("학급 캘린더", titles)
        self.assertNotIn("숨김 학급 도구", titles)

    def test_service_launcher_json_supports_external_services(self):
        Product.objects.create(
            title="외부 도구",
            description="외부 페이지",
            price=0,
            is_active=True,
            service_type="etc",
            external_url="https://example.com/tool",
        )

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "외부 도구")
        self.assertEqual(item["href"], "https://example.com/tool")
        self.assertTrue(item["is_external"])
        self.assertEqual(item["group_title"], "외부 서비스")

    def test_service_launcher_json_keeps_all_discoverable_items(self):
        baseline_payload = json.loads(search_products(self._request())["service_launcher_json"])
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

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        self.assertEqual(len(payload), baseline_count + 9)
        titles = {item["title"] for item in payload}
        for index in range(9):
            self.assertIn(f"서비스 {index}", titles)

    def test_new_service_is_auto_included_after_ensure_command(self):
        call_command("ensure_docviewer")

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        titles = [item["title"] for item in payload]
        self.assertIn("문서 미리보기실", titles)

    def test_docsign_is_auto_included_after_ensure_command(self):
        call_command("ensure_docsign")

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "인쇄 NONO 온라인 사인")
        self.assertEqual(item["group_key"], "collect_sign")
        self.assertEqual(item["href"], reverse("docsign:list"))
        self.assertFalse(item["is_external"])

    def test_teacher_law_is_sorted_first_in_guide_group(self):
        Product.objects.create(
            title="다른 가이드",
            description="설명",
            price=0,
            is_active=True,
            service_type="edutech",
            display_order=0,
        )

        call_command("ensure_teacher_law")

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])
        guide_titles = [item["title"] for item in payload if item["group_key"] == "guide"]

        self.assertIn("교사용 AI 법률 가이드", guide_titles)
        self.assertIn("다른 가이드", guide_titles)
        self.assertLess(
            guide_titles.index("교사용 AI 법률 가이드"),
            guide_titles.index("다른 가이드"),
        )

    def test_reversi_is_auto_included_in_service_launcher_payload(self):
        call_command("ensure_fairy_games")

        context = search_products(self._request())
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "리버시")
        self.assertEqual(item["group_key"], "class_activity")
        self.assertEqual(item["group_title"], "수업·학급 운영")
        self.assertEqual(item["href"], reverse("fairy_games:play_reversi"))
        self.assertFalse(item["is_external"])

    @override_settings(GLOBAL_SEARCH_ENABLED=False)
    def test_service_launcher_json_absent_when_disabled(self):
        context = search_products(self._request())
        self.assertEqual(context, {})

    def test_service_launcher_json_absent_on_admin_surfaces(self):
        request = self.factory.get("/secret-admin-kakio/")

        context = search_products(request)

        self.assertEqual(context, {})
