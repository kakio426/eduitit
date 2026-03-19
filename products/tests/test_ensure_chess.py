from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ServiceManual


class EnsureChessCommandTest(TestCase):
    def test_command_syncs_launch_route_manual_and_features(self):
        call_command("ensure_chess")

        product = Product.objects.get(title="두뇌 풀가동! 교실 체스")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.launch_route_name, "chess:index")
        self.assertEqual(product.service_type, "game")
        self.assertTrue(product.is_active)
        self.assertTrue(manual.is_published)
        self.assertEqual(manual.title, "교실 체스 사용법")
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["무료 AI 대전 (Stockfish)", "1대1 로컬 대전", "규칙 가이드"],
        )
        self.assertCountEqual(
            list(manual.sections.values_list("title", flat=True)),
            ["시작하기", "AI 대전", "규칙 가이드"],
        )
