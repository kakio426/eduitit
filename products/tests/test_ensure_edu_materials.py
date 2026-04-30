from django.core.management import call_command
from django.test import TestCase

from core.models import UserProfile
from edu_materials.models import EduMaterial
from products.management.commands.ensure_edu_materials import (
    CURRICULUM_LAB_OWNER_NICKNAME,
    CURRICULUM_LAB_OWNER_USERNAME,
    CURRICULUM_LAB_SPECS,
    _build_curriculum_lab_html,
)
from products.models import Product, ProductFeature


class EnsureEduMaterialsCommandTests(TestCase):
    def test_command_repairs_existing_materials_product_without_reactivating_visibility(self):
        Product.objects.filter(launch_route_name="edu_materials:main").delete()
        Product.objects.filter(title__in=["교육 자료실", "AI 수업자료 메이커"]).delete()

        Product.objects.create(
            title="legacy edu materials",
            lead_text="legacy",
            description="legacy",
            price=0,
            is_active=False,
            service_type="classroom",
            icon="old",
            launch_route_name="edu_materials:main",
        )

        call_command("ensure_edu_materials")

        product = Product.objects.get(launch_route_name="edu_materials:main")

        self.assertEqual(product.title, "AI 수업자료 메이커")
        self.assertEqual(product.icon, "🧩")
        self.assertFalse(product.is_active)
        self.assertGreaterEqual(product.features.count(), 3)
        self.assertTrue(product.manual.is_published)
        self.assertGreaterEqual(product.manual.sections.count(), 3)
        self.assertEqual(product.manual.title, "AI 수업자료 메이커 사용 가이드")

        feature_icons = set(
            ProductFeature.objects.filter(product=product).values_list("icon", flat=True)
        )
        self.assertSetEqual(feature_icons, {"🧪", "🛡️", "📎"})

    def test_command_seeds_curriculum_lab_materials_idempotently(self):
        call_command("ensure_edu_materials")

        materials = EduMaterial.objects.filter(
            teacher__username=CURRICULUM_LAB_OWNER_USERNAME,
            title__in=[spec["title"] for spec in CURRICULUM_LAB_SPECS],
            is_published=True,
        )

        self.assertEqual(materials.count(), len(CURRICULUM_LAB_SPECS))
        self.assertEqual(
            set(materials.values_list("subject", flat=True)),
            {"MATH", "SCIENCE"},
        )
        self.assertTrue(
            materials.filter(grade="초등학교 3~4학년").exists()
        )
        self.assertTrue(
            materials.filter(grade="초등학교 5~6학년").exists()
        )
        self.assertTrue(
            materials.filter(html_content__contains="const config =").exists()
        )
        self.assertTrue(
            UserProfile.objects.filter(
                user__username=CURRICULUM_LAB_OWNER_USERNAME,
                nickname=CURRICULUM_LAB_OWNER_NICKNAME,
            ).exists()
        )

        call_command("ensure_edu_materials")

        self.assertEqual(
            EduMaterial.objects.filter(
                teacher__username=CURRICULUM_LAB_OWNER_USERNAME,
                title__in=[spec["title"] for spec in CURRICULUM_LAB_SPECS],
            ).count(),
            len(CURRICULUM_LAB_SPECS),
        )

    def test_seeded_curriculum_lab_material_opens_detail_and_run_pages(self):
        call_command("ensure_edu_materials")
        material = EduMaterial.objects.get(title="분모가 달라도 같은 크기 실험실")

        list_response = self.client.get("/edu-materials/?q=분모")
        detail_response = self.client.get(f"/edu-materials/{material.id}/")
        run_response = self.client.get(f"/edu-materials/{material.id}/run/")

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, material.title)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, material.title)
        self.assertEqual(run_response.status_code, 200)
        self.assertContains(run_response, material.title)

    def test_seeded_magnet_material_uses_facing_poles_and_drag(self):
        spec = next(item for item in CURRICULUM_LAB_SPECS if item["mode"] == "magnet")
        html = _build_curriculum_lab_html(spec)

        self.assertIn("오른쪽 자석을 직접 끌고", spec["summary"])
        self.assertIn("오른쪽 왼쪽 끝 극", html)
        self.assertIn('const leftFacingPole = "S"', html)
        self.assertIn("const attracts = leftFacingPole !== rightFacingPole", html)
        self.assertIn("addEventListener(\"pointerdown\", beginMagnetDrag)", html)
        self.assertIn("dragOffsetX", html)
        self.assertIn("오른쪽 자석을 좌우로 끌어 거리 조절", html)

    def test_seeded_volume_material_uses_layered_stack_visual(self):
        spec = next(item for item in CURRICULUM_LAB_SPECS if item["mode"] == "volume")
        html = _build_curriculum_lab_html(spec)

        self.assertIn("바닥 한 층", html)
        self.assertIn("층으로 쌓기", html)
        self.assertIn("drawSlab", html)
        self.assertIn("부피는 바닥 한 층의 개수에 층수를 곱하면 됩니다.", html)
