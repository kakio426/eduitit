from django.core.management import call_command
from django.test import TestCase

from products.models import Product, ProductFeature


class EnsureTTSAnnounceCommandTests(TestCase):
    def test_command_repairs_existing_product_without_reactivating_visibility(self):
        Product.objects.filter(launch_route_name="tts_announce").delete()
        Product.objects.filter(title="교실 방송 TTS").delete()

        Product.objects.create(
            title="legacy tts",
            lead_text="legacy",
            description="legacy",
            price=0,
            is_active=False,
            service_type="classroom",
            icon="old",
            launch_route_name="tts_announce",
        )

        call_command("ensure_tts_announce")

        product = Product.objects.get(launch_route_name="tts_announce")

        self.assertEqual(product.title, "교실 방송 TTS")
        self.assertEqual(product.icon, "📣")
        self.assertFalse(product.is_active)
        self.assertGreaterEqual(product.features.count(), 3)
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)

        feature_titles = set(
            ProductFeature.objects.filter(product=product).values_list("title", flat=True)
        )
        self.assertSetEqual(
            feature_titles,
            {
                "직접 입력해 바로 읽기",
                "학생 대상 빠른 문구",
                "시간표 안내도 함께",
            },
        )
