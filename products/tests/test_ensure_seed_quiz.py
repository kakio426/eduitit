from django.core.management import call_command
from django.test import TestCase

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class EnsureSeedQuizCommandTest(TestCase):
    def test_command_repairs_legacy_copy_and_prunes_stale_items(self):
        product = Product.objects.create(
            title="씨앗 퀴즈",
            lead_text="legacy lead",
            description="legacy description",
            price=0,
            is_active=True,
            launch_route_name="",
        )
        ProductFeature.objects.create(
            product=product,
            icon="🧪",
            title="AI 퀴즈 자동 생성",
            description="legacy feature",
        )
        ProductFeature.objects.create(
            product=product,
            icon="🧪",
            title="태블릿 최적화 UI",
            description="legacy feature",
        )
        ProductFeature.objects.create(
            product=product,
            icon="🧪",
            title="사용 팁",
            description="stale feature",
        )

        manual = ServiceManual.objects.create(
            product=product,
            title="Legacy Manual",
            description="legacy manual",
            is_published=False,
        )
        ManualSection.objects.create(
            manual=manual,
            title="시작하기",
            content="legacy",
            display_order=1,
        )
        ManualSection.objects.create(
            manual=manual,
            title="퀴즈 생성법",
            content="legacy",
            display_order=2,
        )
        ManualSection.objects.create(
            manual=manual,
            title="불필요 안내",
            content="stale",
            display_order=99,
        )

        call_command("ensure_seed_quiz")

        product.refresh_from_db()
        manual.refresh_from_db()

        self.assertEqual(product.launch_route_name, "seed_quiz:landing")
        self.assertIn("공식/공유 퀴즈 은행", product.description)
        self.assertIn("CSV 업로드", product.lead_text)

        feature_titles = list(
            ProductFeature.objects.filter(product=product)
            .order_by("id")
            .values_list("title", flat=True)
        )
        self.assertEqual(
            feature_titles,
            ["퀴즈 은행 원클릭 적용", "CSV 업로드 지원", "행복의 씨앗 연동"],
        )

        section_titles = list(
            ManualSection.objects.filter(manual=manual)
            .order_by("display_order")
            .values_list("title", flat=True)
        )
        self.assertEqual(
            section_titles,
            ["시작하기", "퀴즈 선택법", "학생 안내", "진행 현황 확인", "보상 정책"],
        )
        self.assertFalse(
            ManualSection.objects.filter(manual=manual, title="퀴즈 생성법").exists()
        )
        self.assertEqual(manual.title, "씨앗 퀴즈 시작 가이드")
        self.assertTrue(manual.is_published)

