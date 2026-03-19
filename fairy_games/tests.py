from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from products.models import Product


class FairyGamesRoutingTests(TestCase):
    def test_index_page(self):
        response = self.client.get(reverse("fairy_games:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "전략 게임 6종")
        self.assertContains(response, "리버시")
        self.assertContains(response, "규칙 보기")

    def test_rules_pages(self):
        for variant in ["dobutsu", "cfour", "isolation", "ataxx", "breakthrough", "reversi"]:
            response = self.client.get(reverse("fairy_games:rules", kwargs={"variant": variant}))
            self.assertEqual(response.status_code, 200, msg=f"rules failed: {variant}")

    def test_play_pages_local_only(self):
        for variant in ["dobutsu", "cfour", "isolation", "ataxx", "breakthrough", "reversi"]:
            response_default = self.client.get(reverse("fairy_games:play", kwargs={"variant": variant}))
            response_ai_query = self.client.get(
                reverse("fairy_games:play", kwargs={"variant": variant}) + "?mode=ai&difficulty=medium"
            )
            self.assertEqual(response_default.status_code, 200, msg=f"default failed: {variant}")
            self.assertEqual(response_ai_query.status_code, 200, msg=f"ai query failed: {variant}")
            self.assertContains(response_default, "로컬 대결")
            self.assertNotContains(response_default, "AI 대결")
            self.assertContains(response_ai_query, "로컬 대결")

    def test_invalid_variant_returns_404(self):
        response = self.client.get(reverse("fairy_games:play", kwargs={"variant": "invalid-variant"}))
        self.assertEqual(response.status_code, 404)

    def test_reversi_play_page_contains_accessibility_landmarks(self):
        response = self.client.get(reverse("fairy_games:play", kwargs={"variant": "reversi"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="grid"')
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, 'aria-atomic="true"')
        self.assertContains(response, 'role="dialog"')
        self.assertContains(response, 'aria-modal="true"')
        self.assertContains(response, 'id="fg-rules-title"')
        self.assertContains(response, 'id="fg-result-title"')


class FairyGamesEnsureCommandTests(TestCase):
    def test_ensure_fairy_games_sets_launch_routes_and_published_manuals(self):
        call_command("ensure_fairy_games")
        expected_routes = {
            "동물 장기": "fairy_games:play_dobutsu",
            "커넥트 포": "fairy_games:play_cfour",
            "이솔레이션": "fairy_games:play_isolation",
            "아택스": "fairy_games:play_ataxx",
            "브레이크스루": "fairy_games:play_breakthrough",
            "리버시": "fairy_games:play_reversi",
        }

        products = Product.objects.filter(title__in=expected_routes.keys(), is_active=True)
        self.assertEqual(products.count(), 6, msg="expected 6 fairy products")

        for product in products:
            expected_route = expected_routes[product.title]
            self.assertEqual(product.launch_route_name, expected_route)
            self.assertEqual(product.external_url, "")
            self.assertTrue(reverse(expected_route).endswith("/play/"))
            self.assertTrue(hasattr(product, "manual"), msg=f"manual missing: {product.title}")
            self.assertTrue(product.manual.is_published, msg=f"manual unpublished: {product.title}")
            section_titles = list(product.manual.sections.values_list("title", flat=True))
            self.assertIn("시작하기", section_titles)
            self.assertIn("로컬 대결", section_titles)
            self.assertIn("수업 활용 팁", section_titles)
            feature_titles = list(product.features.values_list("title", flat=True))
            self.assertNotIn("AI 대결", feature_titles)
