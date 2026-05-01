from unittest.mock import patch
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from edu_materials.models import EduMaterial
from edu_materials_next.learning_paths import TOPIC_PLACEHOLDER
from edu_materials_next.models import NextEduMaterial
from products.models import ManualSection, Product, ServiceManual


User = get_user_model()


class EduMaterialsNextViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="next-teacher",
            email="next-teacher@example.com",
            password="pw123456",
        )
        self.user.userprofile.nickname = "넥스트선생님"
        self.user.userprofile.save(update_fields=["nickname"])
        self.client = Client()
        self.client.force_login(self.user)

    def test_main_view_defaults_to_first_start_flow(self):
        response = self.client.get(reverse("edu_materials_next:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "첫 자료 바로 만들기")
        self.assertContains(response, "예시로 시작")
        self.assertContains(response, "내 자료 이어보기")
        self.assertContains(response, "주제 입력")
        self.assertContains(response, "저장")
        self.assertContains(response, "QR")
        self.assertNotContains(response, "비교용 새 버전")
        self.assertContains(response, "?mission=vibe-basics#build-flow")
        self.assertContains(response, "?starter=planet-lab#build-flow")
        self.assertEqual(response.context["selected_mission"]["slug"], "vibe-basics")
        self.assertEqual(response.context["selected_starter"]["slug"], "planet-lab")
        self.assertIn(TOPIC_PLACEHOLDER, response.context["generated_prompt_template"])
        self.assertIn("CDN 및 외부 리소스 규칙", response.context["generated_prompt"])

    def test_material_frame_host_recovers_iframe_load_failure(self):
        script_path = (
            Path(settings.BASE_DIR)
            / "edu_materials_next"
            / "static"
            / "edu_materials_next"
            / "material_frame_host.js"
        )
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("startPendingTimer", script)
        self.assertIn("미리보기 실패", script)
        self.assertIn("다시 시도", script)
        self.assertIn('iframe.addEventListener("error"', script)

    def test_create_material_from_learn_flow_with_starter(self):
        response = self.client.post(
            reverse("edu_materials_next:create"),
            {
                "title": "행성 운동 실험실",
                "lesson_topic": "태양계 행성의 자전과 공전",
                "starter_slug": "planet-lab",
                "html_content": "<html><body><h1>planet</h1></body></html>",
            },
        )

        self.assertEqual(response.status_code, 302)
        material = NextEduMaterial.objects.get(title="행성 운동 실험실")
        self.assertEqual(material.entry_mode, NextEduMaterial.EntryMode.LEARN)
        self.assertEqual(material.subject, "SCIENCE")
        self.assertEqual(material.grade, "5학년 1학기")
        self.assertEqual(material.unit_title, "태양계와 별")
        self.assertTrue(material.is_published)
        self.assertEqual(len(material.student_questions), 3)

    @override_settings(EDU_MATERIALS_AUTO_METADATA_DAILY_LIMIT=0)
    @patch("edu_materials_next.classification._call_json_response")
    def test_create_material_skips_auto_classification_after_limit(self, mock_call_json_response):
        cache.clear()
        response = self.client.post(
            reverse("edu_materials_next:create"),
            {
                "title": "제한 자료",
                "html_content": "<html><body><h1>lesson</h1></body></html>",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        material = NextEduMaterial.objects.get(title="제한 자료")
        self.assertEqual(material.subject, "OTHER")
        self.assertContains(response, "오늘 자동 분류 한도")
        mock_call_json_response.assert_not_called()

    def test_import_legacy_material_copies_without_mutating_source(self):
        legacy = EduMaterial.objects.create(
            teacher=self.user,
            title="old 자료",
            html_content="<html><body>legacy</body></html>",
            summary="기존 버전 자료",
            grade="4학년 1학기",
        )

        response = self.client.post(reverse("edu_materials_next:import_legacy", args=[legacy.id]))

        self.assertEqual(response.status_code, 302)
        imported = NextEduMaterial.objects.get(legacy_source_material_id=legacy.id)
        legacy.refresh_from_db()
        self.assertEqual(legacy.title, "old 자료")
        self.assertEqual(imported.entry_mode, NextEduMaterial.EntryMode.IMPORT)
        self.assertEqual(imported.html_content, legacy.html_content)
        self.assertEqual(imported.grade, legacy.grade)

    def test_import_legacy_material_deduplicates_existing_copy(self):
        legacy = EduMaterial.objects.create(
            teacher=self.user,
            title="중복 테스트 자료",
            html_content="<html><body>legacy</body></html>",
        )

        first = self.client.post(reverse("edu_materials_next:import_legacy", args=[legacy.id]))
        second = self.client.post(reverse("edu_materials_next:import_legacy", args=[legacy.id]), follow=True)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(NextEduMaterial.objects.filter(legacy_source_material_id=legacy.id).count(), 1)
        self.assertContains(second, "이미 Next에 가져왔습니다")

    def test_join_short_redirects_to_run(self):
        material = NextEduMaterial.objects.create(
            teacher=self.user,
            title="학생 입장 자료",
            html_content="<html><body>join</body></html>",
        )

        response = Client().get(reverse("edu_materials_next:join_short"), data={"code": material.access_code})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("edu_materials_next:run", args=[material.id]))

    def test_run_material_increments_view_count(self):
        material = NextEduMaterial.objects.create(
            teacher=self.user,
            title="실행 자료",
            html_content="<html><body>run</body></html>",
        )

        response = Client().get(reverse("edu_materials_next:run", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        material.refresh_from_db()
        self.assertEqual(material.view_count, 1)

    def test_detail_contains_qr_fullscreen_primary_action(self):
        material = NextEduMaterial.objects.create(
            teacher=self.user,
            title="상세 자료",
            html_content="<html><body>detail</body></html>",
        )

        response = self.client.get(reverse("edu_materials_next:detail", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "QR 전체화면 열기", count=1)
        self.assertContains(response, "학생 질문 3개")
        self.assertContains(response, "수업 후 기록")

    def test_ensure_command_creates_product_and_manual(self):
        Product.objects.filter(launch_route_name="edu_materials_next:main").delete()

        call_command("ensure_edu_materials_next")

        product = Product.objects.get(launch_route_name="edu_materials_next:main")
        manual = ServiceManual.objects.get(product=product)
        self.assertEqual(product.title, "AI 자료실 Next")
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(ManualSection.objects.filter(manual=manual).count(), 3)

    def test_ensure_command_keeps_existing_product_hidden(self):
        Product.objects.filter(launch_route_name="edu_materials_next:main").delete()

        Product.objects.create(
            title="legacy next",
            description="legacy",
            price=0,
            is_active=False,
            service_type="work",
            display_order=77,
            color_theme="blue",
            card_size="hero",
            launch_route_name="edu_materials_next:main",
        )

        call_command("ensure_edu_materials_next")

        product = Product.objects.get(launch_route_name="edu_materials_next:main")
        self.assertEqual(product.title, "AI 자료실 Next")
        self.assertFalse(product.is_active)
        self.assertEqual(product.service_type, "work")
        self.assertEqual(product.display_order, 77)
        self.assertEqual(product.color_theme, "blue")
        self.assertEqual(product.card_size, "hero")
