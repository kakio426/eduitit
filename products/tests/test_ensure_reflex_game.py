from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ServiceManual


class EnsureReflexGameCommandTest(TestCase):
    def test_command_creates_game_product_next_to_breakthrough(self):
        call_command("ensure_reflex_game")

        product = Product.objects.get(title="탭 순발력 챌린지")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.launch_route_name, "reflex_game:main")
        self.assertEqual(product.service_type, "game")
        self.assertEqual(product.display_order, 22)
        self.assertTrue(product.is_active)
        self.assertTrue(manual.is_published)
        self.assertEqual(manual.title, "탭 순발력 챌린지 사용 가이드")
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["반응속도 측정", "반칙 감지", "전체화면 지원"],
        )
        self.assertCountEqual(
            list(manual.sections.values_list("title", flat=True)),
            ["시작하기", "반칙 규칙", "대결 운영"],
        )
