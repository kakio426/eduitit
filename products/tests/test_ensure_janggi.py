from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ServiceManual


class EnsureJanggiCommandTest(TestCase):
    def test_command_syncs_launch_route_manual_and_features(self):
        call_command("ensure_janggi")

        product = Product.objects.get(title="두뇌 풀가동! 교실 장기")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.launch_route_name, "janggi:index")
        self.assertEqual(product.service_type, "game")
        self.assertTrue(product.is_active)
        self.assertTrue(manual.is_published)
        self.assertEqual(manual.title, "교실 장기 사용법")
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["한 화면 로컬 대전", "AI 대전 구조", "규칙 가이드"],
        )
        self.assertCountEqual(
            list(manual.sections.values_list("title", flat=True)),
            ["시작하기", "AI 모드 연결", "수업 활용 팁"],
        )
