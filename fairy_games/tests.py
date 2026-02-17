from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from products.models import Product


class FairyGamesRoutingTests(TestCase):
    def test_index_page(self):
        response = self.client.get(reverse("fairy_games:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "전략 게임 5종")
        self.assertContains(response, "규칙 보기")

    def test_rules_pages(self):
        for variant in ["dobutsu", "cfour", "isolation", "ataxx", "breakthrough"]:
            response = self.client.get(reverse("fairy_games:rules", kwargs={"variant": variant}))
            self.assertEqual(response.status_code, 200, msg=f"rules failed: {variant}")

    def test_play_pages_local_and_ai(self):
        for variant in ["dobutsu", "cfour", "isolation", "ataxx", "breakthrough"]:
            response_local = self.client.get(reverse("fairy_games:play", kwargs={"variant": variant}) + "?mode=local")
            response_ai = self.client.get(
                reverse("fairy_games:play", kwargs={"variant": variant}) + "?mode=ai&difficulty=medium"
            )
            self.assertEqual(response_local.status_code, 200, msg=f"local failed: {variant}")
            self.assertEqual(response_ai.status_code, 200, msg=f"ai failed: {variant}")
            self.assertContains(response_local, "로컬 대결")
            self.assertContains(response_ai, "AI 대결")

    def test_invalid_variant_returns_404(self):
        response = self.client.get(reverse("fairy_games:play", kwargs={"variant": "invalid-variant"}))
        self.assertEqual(response.status_code, 404)


class FairyGamesEnsureCommandTests(TestCase):
    def test_ensure_fairy_games_creates_expected_urls_and_published_manuals(self):
        call_command("ensure_fairy_games")
        expected_urls = [
            "/fairy-games/dobutsu/play/?mode=local",
            "/fairy-games/cfour/play/?mode=local",
            "/fairy-games/isolation/play/?mode=local",
            "/fairy-games/ataxx/play/?mode=local",
            "/fairy-games/breakthrough/play/?mode=local",
        ]

        products = Product.objects.filter(external_url__in=expected_urls, is_active=True)
        self.assertEqual(products.count(), 5, msg="expected 5 fairy products with valid urls")

        for product in products:
            self.assertTrue(hasattr(product, "manual"), msg=f"manual missing: {product.title}")
            self.assertTrue(product.manual.is_published, msg=f"manual unpublished: {product.title}")
            section_titles = list(product.manual.sections.values_list("title", flat=True))
            self.assertIn("시작하기", section_titles)
            self.assertIn("대결 모드", section_titles)
