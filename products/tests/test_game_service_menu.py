from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from products.models import Product


class GameServiceMenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for command_name in (
            "ensure_chess",
            "ensure_janggi",
            "ensure_fairy_games",
            "ensure_reflex_game",
        ):
            call_command(command_name)

    def test_product_list_surfaces_supported_game_services(self):
        response = self.client.get(reverse("product_list"))

        self.assertEqual(response.status_code, 200)
        titles = [product.title for product in response.context["products"]]
        self.assertIn("두뇌 풀가동! 교실 체스", titles)
        self.assertIn("두뇌 풀가동! 교실 장기", titles)
        self.assertIn("동물 장기", titles)
        self.assertIn("리버시", titles)
        self.assertIn("탭 순발력 챌린지", titles)

    def test_game_product_detail_launches_point_to_real_routes(self):
        expected_routes = {
            "두뇌 풀가동! 교실 체스": "chess:index",
            "두뇌 풀가동! 교실 장기": "janggi:index",
            "동물 장기": "fairy_games:play_dobutsu",
            "리버시": "fairy_games:play_reversi",
            "탭 순발력 챌린지": "reflex_game:main",
        }

        for title, route_name in expected_routes.items():
            product = Product.objects.get(title=title)
            response = self.client.get(reverse("product_detail", kwargs={"pk": product.pk}))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["launch_href"], reverse(route_name))
            self.assertTrue(response.context["can_launch"], msg=title)
