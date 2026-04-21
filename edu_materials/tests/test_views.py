import importlib
import uuid
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse

from edu_materials.classification import EduMaterialClassificationError, apply_auto_metadata, extract_visible_text
from edu_materials.models import EduMaterial
from edu_materials.runtime import build_runtime_html


User = get_user_model()


class EduMaterialViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="edu-teacher",
            email="edu-teacher@example.com",
            password="pw123456",
        )
        self.user.userprofile.nickname = "자료선생님"
        self.user.userprofile.save(update_fields=["nickname"])
        self.client = Client()
        self.client.force_login(self.user)

    def _mock_classification_payload(self, **overrides):
        payload = {
            "subject": "SCIENCE",
            "grade": "4학년 1학기",
            "unit_title": "화산과 지진",
            "material_type": "practice",
            "tags": ["화산", "실험", "시뮬레이션"],
            "summary": "화산 원리를 실험형으로 익히는 웹자료",
            "confidence": 0.88,
        }
        payload.update(overrides)
        return payload

    def _create_other_user(self):
        other_user = User.objects.create_user(
            username="another-teacher",
            email="another@example.com",
            password="pw123456",
        )
        other_user.userprofile.nickname = "옆반선생님"
        other_user.userprofile.save(update_fields=["nickname"])
        return other_user

    @patch("edu_materials.classification._call_json_response")
    def test_create_material_from_paste(self, mock_call_json_response):
        mock_call_json_response.return_value = self._mock_classification_payload()

        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "화산 시뮬레이션",
                "input_mode": "paste",
                "html_content": "<html><body><h1>lesson</h1><p>화산 실험</p></body></html>",
            },
        )

        self.assertEqual(response.status_code, 302)
        material = EduMaterial.objects.get(title="화산 시뮬레이션")
        self.assertEqual(material.input_mode, EduMaterial.INPUT_PASTE)
        self.assertIn("lesson", material.html_content)
        self.assertTrue(material.is_published)
        self.assertRegex(material.access_code or "", r"^\d{6}$")
        self.assertEqual(material.subject, "SCIENCE")
        self.assertEqual(material.grade, "4학년 1학기")
        self.assertEqual(material.unit_title, "화산과 지진")
        self.assertEqual(material.material_type, EduMaterial.MaterialType.PRACTICE)
        self.assertEqual(material.tags, ["화산", "실험", "시뮬레이션"])
        self.assertEqual(material.summary, "화산 원리를 실험형으로 익히는 웹자료")
        self.assertEqual(material.metadata_status, EduMaterial.MetadataStatus.DONE)
        self.assertIn("시뮬레이션", material.search_text)

    @patch("edu_materials.classification._call_json_response")
    def test_create_material_success_message_guides_to_startboard(self, mock_call_json_response):
        mock_call_json_response.return_value = self._mock_classification_payload()

        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "초안 안내 자료",
                "input_mode": "paste",
                "html_content": "<html><body>draft</body></html>",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "자료를 저장했고 학생 공유도 바로 켰습니다")
        self.assertContains(response, "미리보기와 공유판만 확인해 주세요")

    @patch("edu_materials.classification._call_json_response")
    def test_create_material_from_html_file(self, mock_call_json_response):
        mock_call_json_response.return_value = self._mock_classification_payload(
            material_type="reference",
            tags=["자료", "도표", "정리"],
        )
        upload = SimpleUploadedFile("volcano.html", b"<html><body>volcano</body></html>", content_type="text/html")

        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "파일형 자료",
                "input_mode": "file",
                "html_file": upload,
            },
        )

        self.assertEqual(response.status_code, 302)
        material = EduMaterial.objects.get(title="파일형 자료")
        self.assertEqual(material.input_mode, EduMaterial.INPUT_FILE)
        self.assertEqual(material.original_filename, "volcano.html")
        self.assertRegex(material.access_code or "", r"^\d{6}$")
        self.assertEqual(material.material_type, EduMaterial.MaterialType.REFERENCE)
        self.assertIn("volcano", material.html_content)
        self.assertTrue(material.is_published)

    @patch("edu_materials.classification._call_json_response")
    def test_create_material_is_published_even_without_publish_requested(self, mock_call_json_response):
        mock_call_json_response.return_value = self._mock_classification_payload()

        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "바로 공개 자료",
                "input_mode": "paste",
                "html_content": "<html><body>publish</body></html>",
                "publish_now": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        material = EduMaterial.objects.get(title="바로 공개 자료")
        self.assertTrue(material.is_published)

    @patch("edu_materials.classification._call_json_response", side_effect=EduMaterialClassificationError("boom"))
    def test_create_material_keeps_saved_material_when_classification_fails(self, _mock_call_json_response):
        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "분류 실패 자료",
                "input_mode": "paste",
                "html_content": "<html><body><p>lesson</p></body></html>",
            },
        )

        self.assertEqual(response.status_code, 302)
        material = EduMaterial.objects.get(title="분류 실패 자료")
        self.assertEqual(material.metadata_status, EduMaterial.MetadataStatus.FAILED)
        self.assertEqual(material.subject, "OTHER")
        self.assertIn("lesson", material.search_text)

    def test_non_html_file_is_rejected(self):
        upload = SimpleUploadedFile("volcano.txt", b"plain text", content_type="text/plain")
        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "잘못된 파일",
                "input_mode": "file",
                "html_file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EduMaterial.objects.filter(title="잘못된 파일").exists())

    def test_create_material_requires_title(self):
        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "",
                "input_mode": "paste",
                "html_content": "<html><body>lesson</body></html>",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(EduMaterial.objects.count(), 0)

    @patch("edu_materials.classification._call_json_response")
    def test_update_material_from_paste(self, mock_call_json_response):
        mock_call_json_response.return_value = self._mock_classification_payload(
            material_type="quiz",
            tags=["퀴즈", "복습", "확인"],
            summary="화산 단원 핵심 개념을 복습하는 퀴즈 자료",
        )
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="이전 제목",
            html_content="<html><body>before</body></html>",
        )

        response = self.client.post(
            reverse("edu_materials:update", args=[material.id]),
            {
                "title": "수정된 제목",
                "html_content": "<html><body>after quiz</body></html>",
            },
        )

        self.assertEqual(response.status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.title, "수정된 제목")
        self.assertEqual(material.input_mode, EduMaterial.INPUT_PASTE)
        self.assertIn("after", material.html_content)
        self.assertEqual(material.material_type, EduMaterial.MaterialType.QUIZ)
        self.assertEqual(material.metadata_status, EduMaterial.MetadataStatus.DONE)
        self.assertIn("복습", material.search_text)

    def test_delete_material(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="삭제할 자료",
            html_content="<html><body>delete</body></html>",
        )

        response = self.client.post(reverse("edu_materials:delete", args=[material.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EduMaterial.objects.filter(id=material.id).exists())

    def test_main_view_separates_my_materials_and_shared_materials(self):
        other_user = self._create_other_user()

        my_private = EduMaterial.objects.create(
            teacher=self.user,
            title="내 비공개 자료",
            html_content="<html><body>mine</body></html>",
            is_published=False,
        )
        my_public = EduMaterial.objects.create(
            teacher=self.user,
            title="내 공개 자료",
            html_content="<html><body>mine-public</body></html>",
            is_published=True,
        )
        other_public = EduMaterial.objects.create(
            teacher=other_user,
            title="다른 교사 자료",
            html_content="<html><body>other</body></html>",
            is_published=True,
        )

        response = self.client.get(reverse("edu_materials:main"), data={"tab": "my"})

        self.assertEqual(response.status_code, 200)
        my_titles = {item.title for item in response.context["my_page_obj"].object_list}
        self.assertEqual(my_titles, {my_private.title, my_public.title})
        self.assertEqual(response.context["shared_material_count"], 2)
        self.assertEqual(response.context["active_tab"], "my")

    def test_main_view_allows_anonymous_public_browse_only(self):
        other_user = self._create_other_user()
        EduMaterial.objects.create(
            teacher=self.user,
            title="내 비공개 자료",
            html_content="<html><body>mine</body></html>",
            is_published=False,
        )
        public_material = EduMaterial.objects.create(
            teacher=other_user,
            title="공개 둘러보기 자료",
            html_content="<html><body>shared</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
            tags=["화산"],
            summary="로그인 없이 볼 수 있는 공개 자료",
            search_text="화산 공개 자료",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = Client().get(reverse("edu_materials:main"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "shared")
        self.assertIsNone(response.context["my_page_obj"])
        self.assertEqual(response.context["shared_material_count"], 1)
        self.assertEqual(response.context["featured_public_material"].title, public_material.title)
        self.assertContains(response, "AI 수업자료 메이커")
        self.assertNotContains(response, reverse("edu_materials:create"))
        self.assertNotContains(response, "새 자료 만들기")
        self.assertContains(response, reverse("edu_materials:detail", args=[public_material.id]))
        self.assertContains(response, "수업 시작판")

    def test_main_view_filters_by_subject(self):
        other_user = self._create_other_user()
        EduMaterial.objects.create(
            teacher=self.user,
            title="과학 자료",
            html_content="<html><body>science</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
            grade="4학년 1학기",
            tags=["화산"],
            summary="과학 요약",
            search_text="과학 화산 요약",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )
        EduMaterial.objects.create(
            teacher=other_user,
            title="사회 자료",
            html_content="<html><body>social</body></html>",
            is_published=True,
            subject="SOCIAL",
            material_type=EduMaterial.MaterialType.REFERENCE,
            grade="4학년 1학기",
            tags=["정책"],
            summary="사회 요약",
            search_text="사회 정책 요약",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.get(reverse("edu_materials:main"), data={"subject": "SCIENCE", "tab": "my"})

        self.assertEqual(response.status_code, 200)
        my_titles = {item.title for item in response.context["my_page_obj"].object_list}
        self.assertEqual(my_titles, {"과학 자료"})
        self.assertEqual(response.context["shared_material_count"], 1)

    def test_main_view_filters_by_query_material_type_grade_and_tag(self):
        other_user = self._create_other_user()
        matching = EduMaterial.objects.create(
            teacher=other_user,
            title="화산 실험 퀴즈",
            html_content="<html><body>volcano</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.QUIZ,
            grade="4학년 1학기",
            unit_title="화산과 지진",
            tags=["화산", "퀴즈"],
            summary="핵심 개념을 바로 확인하는 퀴즈",
            search_text="화산과 지진 화산 퀴즈 핵심 개념",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )
        EduMaterial.objects.create(
            teacher=other_user,
            title="정책 안내",
            html_content="<html><body>policy</body></html>",
            is_published=True,
            subject="SOCIAL",
            material_type=EduMaterial.MaterialType.REFERENCE,
            grade="5학년 1학기",
            unit_title="정책과 제도",
            tags=["정책"],
            summary="정책 자료",
            search_text="정책 제도",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.get(
            reverse("edu_materials:main"),
            data={
                "q": "핵심 개념",
                "material_type": EduMaterial.MaterialType.QUIZ,
                "grade": "4학년 1학기",
                "tag": "화산",
                "tab": "shared",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["featured_public_material"].title, matching.title)
        self.assertEqual(list(response.context["shared_page_obj"].object_list), [])
        self.assertNotContains(response, "조건에 맞는 공개 자료가 없습니다.")
        self.assertContains(response, "조건 적용 중")

    def test_main_view_shared_tab_shows_thumbnail_preview_for_catalog_cards(self):
        other_user = self._create_other_user()
        featured = EduMaterial.objects.create(
            teacher=other_user,
            title="대표 공개 자료",
            html_content="<html><body>featured</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.REFERENCE,
            summary="대표로 보여줄 공개 자료",
            search_text="대표 공개 자료",
            metadata_status=EduMaterial.MetadataStatus.DONE,
            view_count=10,
        )
        browse = EduMaterial.objects.create(
            teacher=other_user,
            title="공개 자료 카드",
            html_content="<html><body>shared</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.REFERENCE,
            summary="가벼운 카드로 보여줄 공개 자료",
            search_text="공개 자료 카드",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.get(reverse("edu_materials:main"), data={"tab": "shared"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "shared")
        self.assertEqual(response.context["featured_public_material"].id, featured.id)
        self.assertContains(response, browse.title)
        self.assertContains(response, reverse("edu_materials:render", args=[featured.id]))
        self.assertContains(response, reverse("edu_materials:detail", args=[featured.id]))
        self.assertContains(response, reverse("edu_materials:detail", args=[browse.id]))
        self.assertContains(response, reverse("edu_materials:render", args=[browse.id]))
        self.assertNotContains(response, "추천 자료")
        self.assertNotContains(response, "썸네일로 바로 고르기.")
        self.assertNotContains(response, "화면을 보면서 바로 찾기.")

    def test_main_view_uses_compact_public_toolbar_and_filter_copy(self):
        other_user = self._create_other_user()
        EduMaterial.objects.create(
            teacher=other_user,
            title="공개 자료 한 장",
            html_content="<html><body>shared</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.REFERENCE,
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = Client().get(reverse("edu_materials:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "공개 자료")
        self.assertContains(response, "필터")
        self.assertNotContains(response, "로그인 후 편집 가능")
        self.assertNotContains(response, "조건 선택")
        self.assertNotContains(response, "공개 자료실")
        self.assertNotContains(response, "썸네일로 바로 고르기.")
        self.assertNotContains(response, "화면을 보면서 바로 찾기.")

    def test_main_view_renders_summary_and_tags(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="태그 보이는 자료",
            html_content="<html><body>tag</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.GAME,
            tags=["게임", "협동"],
            summary="팀별 활동으로 개념을 익히는 게임형 자료",
            search_text="게임 협동",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.get(reverse("edu_materials:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "팀별 활동으로 개념을 익히는 게임형 자료")
        self.assertContains(response, "#게임")
        self.assertContains(response, "자료 유형")
        self.assertContains(response, 'data-board-preview-root')
        self.assertContains(response, reverse("edu_materials:render", args=[material.id]))
        self.assertNotContains(response, "크게 보기")
        self.assertNotContains(response, "미리보기 확인 중")
        self.assertNotContains(response, "다시 보기")

    def test_main_view_omits_long_fallback_copy_when_public_card_has_no_summary(self):
        other_user = self._create_other_user()
        EduMaterial.objects.create(
            teacher=other_user,
            title="요약 없는 공개 자료",
            html_content="<html><body>plain</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.REFERENCE,
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.get(reverse("edu_materials:main"), data={"tab": "shared"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "수업 흐름을 빠르게 비교해보고, 마음에 들면 바로 열거나 내 자료로 복사해 수정할 수 있는 공개 자료입니다.")

    def test_main_view_my_and_create_tabs_omit_auxiliary_copy(self):
        EduMaterial.objects.create(
            teacher=self.user,
            title="내 자료 카드",
            html_content="<html><body>mine</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        my_response = self.client.get(reverse("edu_materials:main"), data={"tab": "my"})
        create_response = self.client.get(reverse("edu_materials:main"), data={"tab": "create"})

        self.assertEqual(my_response.status_code, 200)
        self.assertEqual(create_response.status_code, 200)
        self.assertNotContains(my_response, "미리보기, 수정, 공유판.")
        self.assertNotContains(create_response, "직접 만들기")
        self.assertNotContains(create_response, "저장 후 공개")
        self.assertNotContains(create_response, "다음 확인")

    def test_clone_material_creates_published_copy_for_teacher(self):
        other_user = self._create_other_user()
        source = EduMaterial.objects.create(
            teacher=other_user,
            title="공개 원본 자료",
            html_content="<html><body>clone me</body></html>",
            is_published=True,
            subject="SCIENCE",
            grade="4학년 1학기",
            unit_title="화산과 지진",
            material_type=EduMaterial.MaterialType.PRACTICE,
            tags=["화산", "실험"],
            summary="복제 테스트용 자료",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.post(reverse("edu_materials:clone", args=[source.id]))

        self.assertEqual(response.status_code, 302)
        clone = EduMaterial.objects.exclude(id=source.id).get(teacher=self.user)
        self.assertEqual(clone.title, "공개 원본 자료 (내 자료)")
        self.assertTrue(clone.is_published)
        self.assertEqual(clone.source_material, source)
        self.assertEqual(clone.subject, source.subject)
        self.assertEqual(clone.material_type, source.material_type)
        self.assertEqual(clone.metadata_source, EduMaterial.MetadataSource.MANUAL)

    def test_clone_material_redirects_to_existing_copy_for_same_source(self):
        other_user = self._create_other_user()
        source = EduMaterial.objects.create(
            teacher=other_user,
            title="이미 가져온 공개 자료",
            html_content="<html><body>same source</body></html>",
            is_published=True,
        )
        existing_clone = EduMaterial.objects.create(
            teacher=self.user,
            source_material=source,
            title="이미 가져온 공개 자료 (내 자료)",
            html_content=source.html_content,
            is_published=True,
        )

        response = self.client.post(reverse("edu_materials:clone", args=[source.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(EduMaterial.objects.filter(teacher=self.user, source_material=source).count(), 1)
        self.assertContains(response, "이미 내 자료실에 있어 그 자료를 바로 열었습니다")
        self.assertEqual(response.request["PATH_INFO"], reverse("edu_materials:detail", args=[existing_clone.id]))

    def test_run_view_requires_published_material(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="비공개 자료",
            html_content="<html><body>private</body></html>",
            is_published=False,
        )
        response = self.client.get(reverse("edu_materials:run", args=[material.id]))
        self.assertEqual(response.status_code, 404)

    def test_run_view_renders_runtime_data_iframe_and_tracks_views(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="공개 자료",
            html_content="<html><body><script>window.lesson=true;</script></body></html>",
            is_published=True,
        )
        response = self.client.get(reverse("edu_materials:run", args=[material.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'src="data:text/html;charset=utf-8;base64,')
        self.assertNotContains(response, 'sandbox="')
        self.assertContains(
            response,
            f'data-material-render-url="{reverse("edu_materials:render", args=[material.id])}"',
        )
        self.assertIn("frame-src", response._csp_update)
        self.assertIn("data:", response._csp_update["frame-src"])
        self.assertContains(response, "data-frame-mode=\"runtime\"")
        self.assertContains(response, "data-material-frame-shell")
        self.assertContains(response, "data-frame-status")
        self.assertNotContains(response, "자료 실행 확인 중")
        material.refresh_from_db()
        self.assertEqual(material.view_count, 1)

    def test_detail_view_renders_preview_toggle_and_metadata_form(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="미리보기 자료",
            html_content="<html><body>preview</body></html>",
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
            tags=["태그1", "태그2"],
            summary="요약 텍스트",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.get(reverse("edu_materials:detail", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("frame-src", response._csp_update)
        self.assertIn("data:", response._csp_update["frame-src"])
        self.assertContains(response, reverse("edu_materials:render", args=[material.id]))
        self.assertNotContains(response, "srcdoc=")
        self.assertContains(response, "data-frame-mode=\"preview\"")
        self.assertContains(response, "Desktop")
        self.assertContains(response, "Mobile")
        self.assertContains(response, material.access_code)
        self.assertContains(response, "전체화면 공유판 열기")
        self.assertContains(response, "학생 화면 열기")
        self.assertNotContains(response, "자료 실행 확인 중")
        self.assertContains(response, "자료 정보 바꾸기")
        self.assertContains(response, "현재 내용으로 다시 자동 분류")
        self.assertEqual(response.context["preview_default_viewport"]["id"], "desktop")

    def test_detail_view_for_published_owner_shows_share_board_actions(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="공개 수업 자료",
            html_content="<html><body>published owner</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
        )

        response = self.client.get(reverse("edu_materials:detail", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "전체화면 공유판 열기")
        self.assertContains(response, "edu-materials-primary-action")
        self.assertContains(response, reverse("edu_materials:share_board", args=[material.id]))
        self.assertContains(response, material.access_code)
        self.assertContains(response, reverse("edu_materials:join_short"))

    def test_detail_view_allows_anonymous_public_startboard(self):
        other_user = self._create_other_user()
        material = EduMaterial.objects.create(
            teacher=other_user,
            title="비회원 공개 시작판 자료",
            html_content="<html><body>public anon</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
        )

        response = Client().get(reverse("edu_materials:detail", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "로그인 없이도 바로 수업에 쓰기")
        self.assertContains(response, "전체화면 공유판 열기")
        self.assertContains(response, "edu-materials-primary-action")
        self.assertContains(response, reverse("edu_materials:share_board", args=[material.id]))
        self.assertContains(response, reverse("edu_materials:run", args=[material.id]))
        self.assertContains(response, material.access_code)

    def test_detail_view_allows_logged_in_teacher_to_open_other_published_material(self):
        other_user = self._create_other_user()
        material = EduMaterial.objects.create(
            teacher=other_user,
            title="다른 교사 공개 자료",
            html_content="<html><body>public other</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
        )

        response = self.client.get(reverse("edu_materials:detail", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내 자료로 복사해 수정하기")
        self.assertContains(response, "전체화면 공유판 열기")
        self.assertContains(response, reverse("edu_materials:share_board", args=[material.id]))
        self.assertNotContains(response, "자료 삭제하기")

    def test_detail_view_links_existing_copy_for_logged_in_teacher(self):
        other_user = self._create_other_user()
        material = EduMaterial.objects.create(
            teacher=other_user,
            title="이미 가져온 자료 원본",
            html_content="<html><body>public other</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
        )
        existing_clone = EduMaterial.objects.create(
            teacher=self.user,
            source_material=material,
            title="이미 가져온 자료 원본 (내 자료)",
            html_content=material.html_content,
            is_published=True,
        )

        response = self.client.get(reverse("edu_materials:detail", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내 자료 열기")
        self.assertContains(response, reverse("edu_materials:detail", args=[existing_clone.id]))
        self.assertNotContains(response, "내 자료로 복사해 수정하기")
        self.assertContains(response, "이미 내 자료실로 가져왔습니다")

    def test_main_view_shows_open_existing_copy_for_already_cloned_material(self):
        other_user = self._create_other_user()
        material = EduMaterial.objects.create(
            teacher=other_user,
            title="공개 참고 자료",
            html_content="<html><body>public reference</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
        )
        existing_clone = EduMaterial.objects.create(
            teacher=self.user,
            source_material=material,
            title="공개 참고 자료 (내 자료)",
            html_content=material.html_content,
            is_published=True,
        )

        response = self.client.get(reverse("edu_materials:main"), data={"tab": "shared", "q": "공개 참고"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내 자료 열기")
        self.assertContains(response, reverse("edu_materials:detail", args=[existing_clone.id]))
        self.assertNotContains(response, "내 자료로 복사해 수정하기")

    def test_main_view_public_catalog_excludes_cloned_copies(self):
        other_user = self._create_other_user()
        material = EduMaterial.objects.create(
            teacher=other_user,
            title="공개 참고 자료",
            html_content="<html><body>public reference</body></html>",
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
        )
        existing_clone = EduMaterial.objects.create(
            teacher=self.user,
            source_material=material,
            title="공개 참고 자료 (내 자료)",
            html_content=material.html_content,
            is_published=True,
            subject="SCIENCE",
            material_type=EduMaterial.MaterialType.PRACTICE,
        )

        response = self.client.get(reverse("edu_materials:main"), data={"tab": "shared", "q": "공개 참고"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["shared_material_count"], 1)
        self.assertEqual(response.context["featured_public_material"].id, material.id)
        self.assertEqual(response.context["featured_public_material"].existing_clone_id, existing_clone.id)
        self.assertEqual(len(response.context["shared_page_obj"].object_list), 0)
        self.assertContains(response, "내 자료 열기")

    def test_anonymous_public_catalog_excludes_cloned_copies(self):
        original_teacher = self._create_other_user()
        clone_teacher = User.objects.create_user(
            username="clone-teacher",
            email="clone@example.com",
            password="pw123456",
        )
        material = EduMaterial.objects.create(
            teacher=original_teacher,
            title="공개 자료 원본",
            html_content="<html><body>original public</body></html>",
            is_published=True,
        )
        clone = EduMaterial.objects.create(
            teacher=clone_teacher,
            source_material=material,
            title="공개 자료 원본 (내 자료)",
            html_content=material.html_content,
            is_published=True,
        )

        response = Client().get(reverse("edu_materials:main"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["shared_material_count"], 1)
        self.assertEqual(response.context["featured_public_material"].id, material.id)
        self.assertNotContains(response, reverse("edu_materials:detail", args=[clone.id]))

    def test_cloned_copy_remains_directly_accessible_even_if_hidden_from_public_catalog(self):
        other_user = self._create_other_user()
        source = EduMaterial.objects.create(
            teacher=other_user,
            title="공개 원본 자료",
            html_content="<html><body>public source</body></html>",
            is_published=True,
        )
        clone = EduMaterial.objects.create(
            teacher=self.user,
            source_material=source,
            title="공개 원본 자료 (내 자료)",
            html_content=source.html_content,
            is_published=True,
        )

        detail_response = Client().get(reverse("edu_materials:detail", args=[clone.id]))
        share_board_response = Client().get(reverse("edu_materials:share_board", args=[clone.id]))
        run_response = Client().get(reverse("edu_materials:run", args=[clone.id]))

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(share_board_response.status_code, 200)
        self.assertEqual(run_response.status_code, 200)

    def test_detail_view_keeps_private_material_hidden_from_anonymous_users(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="비회원 비공개 자료",
            html_content="<html><body>private anon</body></html>",
            is_published=False,
        )

        response = Client().get(reverse("edu_materials:detail", args=[material.id]))

        self.assertEqual(response.status_code, 404)

    def test_join_views_redirect_to_run_for_valid_code(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="코드 입장 자료",
            html_content="<html><body>join me</body></html>",
            is_published=True,
        )

        join_response = Client().get(reverse("edu_materials:join"), data={"code": material.access_code})
        short_response = Client().get(reverse("edu_materials:join_short"), data={"code": material.access_code})

        self.assertEqual(join_response.status_code, 302)
        self.assertEqual(join_response.url, reverse("edu_materials:run", args=[material.id]))
        self.assertEqual(short_response.status_code, 302)
        self.assertEqual(short_response.url, reverse("edu_materials:run", args=[material.id]))

    def test_join_view_shows_friendly_error_for_private_or_missing_code(self):
        private_material = EduMaterial.objects.create(
            teacher=self.user,
            title="비공개 코드 자료",
            html_content="<html><body>private join</body></html>",
            is_published=False,
        )
        missing_code = "999999" if private_material.access_code != "999999" else "000000"
        client = Client()

        private_response = client.get(reverse("edu_materials:join"), data={"code": private_material.access_code})
        missing_response = client.get(reverse("edu_materials:join_short"), data={"code": missing_code})

        self.assertEqual(private_response.status_code, 200)
        self.assertContains(private_response, "아직 학생 공유가 열리지 않았습니다")
        self.assertEqual(missing_response.status_code, 200)
        self.assertContains(missing_response, "입력한 공유 코드를 찾지 못했습니다")

    def test_share_board_allows_public_access_and_blocks_private_non_owners(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="공유판 자료",
            html_content="<html><body>share board</body></html>",
            is_published=True,
        )
        other_user = self._create_other_user()

        owner_response = self.client.get(reverse("edu_materials:share_board", args=[material.id]))
        other_client = Client()
        other_client.force_login(other_user)
        other_response = other_client.get(reverse("edu_materials:share_board", args=[material.id]))
        anonymous_response = Client().get(reverse("edu_materials:share_board", args=[material.id]))

        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(anonymous_response.status_code, 200)
        self.assertContains(owner_response, material.access_code)
        self.assertContains(owner_response, reverse("edu_materials:join_short"))
        self.assertContains(owner_response, "학생 자료 입장")
        self.assertContains(other_response, material.access_code)
        self.assertContains(anonymous_response, material.access_code)

        private_material = EduMaterial.objects.create(
            teacher=self.user,
            title="비공개 공유판 자료",
            html_content="<html><body>private share board</body></html>",
            is_published=False,
        )

        private_anonymous_response = Client().get(reverse("edu_materials:share_board", args=[private_material.id]))
        private_other_response = other_client.get(reverse("edu_materials:share_board", args=[private_material.id]))
        private_owner_response = self.client.get(reverse("edu_materials:share_board", args=[private_material.id]))

        self.assertEqual(private_anonymous_response.status_code, 404)
        self.assertEqual(private_other_response.status_code, 404)
        self.assertEqual(private_owner_response.status_code, 200)

    def test_update_material_metadata_marks_manual_source(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="수정 전",
            html_content="<html><body>manual</body></html>",
            metadata_status=EduMaterial.MetadataStatus.FAILED,
        )

        response = self.client.post(
            reverse("edu_materials:update_metadata", args=[material.id]),
            {
                "subject": "MATH",
                "grade": "3학년 2학기",
                "unit_title": "분수와 소수",
                "material_type": EduMaterial.MaterialType.PRACTICE,
                "tags": "분수, 연습, 계산",
                "summary": "분수 계산을 반복해보는 자료",
            },
        )

        self.assertEqual(response.status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.subject, "MATH")
        self.assertEqual(material.metadata_source, EduMaterial.MetadataSource.MANUAL)
        self.assertEqual(material.metadata_status, EduMaterial.MetadataStatus.DONE)
        self.assertEqual(material.tags, ["분수", "연습", "계산"])
        self.assertIn("분수 계산", material.search_text)

    @patch("edu_materials.classification._call_json_response")
    def test_reclassify_material_overwrites_manual_metadata(self, mock_call_json_response):
        mock_call_json_response.return_value = self._mock_classification_payload(
            subject="SOCIAL",
            material_type="reference",
            tags=["정책", "제도", "안내"],
            summary="정책과 제도를 빠르게 확인하는 참고 자료",
        )
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="재분류 전",
            html_content="<html><body>policy text</body></html>",
            subject="MATH",
            material_type=EduMaterial.MaterialType.PRACTICE,
            tags=["수동"],
            summary="직접 수정한 요약",
            metadata_source=EduMaterial.MetadataSource.MANUAL,
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        response = self.client.post(reverse("edu_materials:reclassify", args=[material.id]))

        self.assertEqual(response.status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.subject, "SOCIAL")
        self.assertEqual(material.material_type, EduMaterial.MaterialType.REFERENCE)
        self.assertEqual(material.tags, ["정책", "제도", "안내"])
        self.assertEqual(material.metadata_source, EduMaterial.MetadataSource.AUTO)
        self.assertEqual(material.metadata_status, EduMaterial.MetadataStatus.DONE)

    def test_render_view_allows_teacher_preview_before_publish(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="원본 렌더",
            html_content="<html><body><button>play</button></body></html>",
            is_published=False,
        )

        response = self.client.get(reverse("edu_materials:render", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<button>play</button>", html=True)
        self.assertContains(response, "edu-materials-runtime-guard")
        self.assertIn("sandbox allow-downloads", response["Content-Security-Policy"])

    def test_render_view_requires_publish_for_public_access(self):
        other_user = self._create_other_user()
        material = EduMaterial.objects.create(
            teacher=other_user,
            title="비공개 렌더",
            html_content="<html><body>private</body></html>",
            is_published=False,
        )
        self.client.logout()

        response = self.client.get(reverse("edu_materials:render", args=[material.id]))

        self.assertEqual(response.status_code, 404)


class EduMaterialClassificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="classification-teacher",
            email="classification@example.com",
            password="pw123456",
        )

    @patch("edu_materials.classification._call_json_response")
    def test_apply_auto_metadata_extracts_visible_text_and_updates_search_text(self, mock_call_json_response):
        mock_call_json_response.return_value = {
            "subject": "SCIENCE",
            "grade": "4학년 1학기",
            "unit_title": "화산과 지진",
            "material_type": "practice",
            "tags": ["화산", "시뮬레이션", "실험"],
            "summary": "화산 실험을 단계별로 연습하는 자료",
            "confidence": 0.7,
        }
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="화산 자료",
            html_content="<html><head><style>.x{color:red;}</style></head><body><script>alert(1)</script><h1>화산 실험</h1><p>단계별 학습</p></body></html>",
        )

        metadata = apply_auto_metadata(material, save=True)
        material.refresh_from_db()

        self.assertIsNotNone(metadata)
        self.assertEqual(extract_visible_text(material.html_content), "화산 실험 단계별 학습")
        self.assertEqual(material.metadata_status, EduMaterial.MetadataStatus.DONE)
        self.assertIn("화산 실험 단계별 학습", material.search_text)

    @patch("edu_materials.classification._call_json_response", side_effect=EduMaterialClassificationError("bad json"))
    def test_apply_auto_metadata_marks_failed_when_llm_fails(self, _mock_call_json_response):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="실패 자료",
            html_content="<html><body><p>실패 테스트</p></body></html>",
        )

        metadata = apply_auto_metadata(material, save=True)
        material.refresh_from_db()

        self.assertIsNone(metadata)
        self.assertEqual(material.metadata_status, EduMaterial.MetadataStatus.FAILED)
        self.assertIn("실패 테스트", material.search_text)


class EduMaterialRuntimeTests(TestCase):
    def test_build_runtime_html_injects_guard_after_head(self):
        html = "<!DOCTYPE html><html><head><title>demo</title></head><body><h1>ok</h1></body></html>"

        rendered = build_runtime_html(html)

        self.assertIn("edu-materials-runtime-guard", rendered)
        self.assertIn("<title>demo</title>", rendered)
        self.assertIn("<script>", rendered)
        self.assertIn("<body><h1>ok</h1></body>", rendered)

    def test_build_runtime_html_injects_guard_for_fragment(self):
        rendered = build_runtime_html("<div>fragment</div>")

        self.assertIn("edu-materials-runtime-guard", rendered)
        self.assertTrue(rendered.endswith("<div>fragment</div>"))


class EduMaterialBackfillCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="command-teacher",
            email="command@example.com",
            password="pw123456",
        )

    @patch("edu_materials.management.commands.backfill_edu_material_metadata.apply_auto_metadata")
    def test_backfill_only_processes_non_done_without_force(self, mock_apply_auto_metadata):
        pending_material = EduMaterial.objects.create(
            teacher=self.user,
            title="대기 자료",
            html_content="<html><body>pending</body></html>",
            metadata_status=EduMaterial.MetadataStatus.PENDING,
        )
        EduMaterial.objects.create(
            teacher=self.user,
            title="완료 자료",
            html_content="<html><body>done</body></html>",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )

        out = StringIO()
        call_command("backfill_edu_material_metadata", stdout=out)

        self.assertEqual(mock_apply_auto_metadata.call_count, 1)
        self.assertEqual(mock_apply_auto_metadata.call_args.args[0].id, pending_material.id)

    @patch("edu_materials.management.commands.backfill_edu_material_metadata.apply_auto_metadata")
    def test_backfill_force_reprocesses_done_rows(self, mock_apply_auto_metadata):
        first = EduMaterial.objects.create(
            teacher=self.user,
            title="첫 자료",
            html_content="<html><body>first</body></html>",
            metadata_status=EduMaterial.MetadataStatus.DONE,
        )
        second = EduMaterial.objects.create(
            teacher=self.user,
            title="둘째 자료",
            html_content="<html><body>second</body></html>",
            metadata_status=EduMaterial.MetadataStatus.PENDING,
        )

        out = StringIO()
        call_command("backfill_edu_material_metadata", "--force", stdout=out)

        processed_ids = {call.args[0].id for call in mock_apply_auto_metadata.call_args_list}
        self.assertEqual(processed_ids, {first.id, second.id})


class EduMaterialMigrationHelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="migration-teacher",
            email="migration-teacher@example.com",
            password="pw123456",
        )
        self.module = importlib.import_module("edu_materials.migrations.0002_import_from_textbooks")
        self.temp_tables = []

    def tearDown(self):
        with connection.cursor() as cursor:
            for table_name in self.temp_tables:
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        super().tearDown()

    def _create_temp_table(self, schema_sql):
        table_name = f"tmp_textbooks_{uuid.uuid4().hex[:8]}"
        self.temp_tables.append(table_name)
        with connection.cursor() as cursor:
            cursor.execute(schema_sql.format(table=table_name))
        return table_name

    def test_legacy_schema_without_source_type_moves_all_rows(self):
        table_name = self._create_temp_table(
            """
            CREATE TABLE "{table}" (
                "id" char(32) NOT NULL PRIMARY KEY,
                "subject" varchar(20) NOT NULL,
                "grade" varchar(50) NULL,
                "unit_title" varchar(200) NOT NULL,
                "title" varchar(200) NOT NULL,
                "content" text NOT NULL,
                "is_published" bool NOT NULL,
                "created_at" datetime NOT NULL,
                "updated_at" datetime NOT NULL,
                "teacher_id" integer NOT NULL,
                "view_count" integer NOT NULL,
                "is_shared" bool NOT NULL
            )
            """
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f'INSERT INTO "{table_name}" (id, subject, grade, unit_title, title, content, is_published, created_at, updated_at, teacher_id, view_count, is_shared) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                [
                    uuid.uuid4().hex,
                    "SCIENCE",
                    "4학년 1학기",
                    "화산과 지진",
                    "레거시 HTML 자료",
                    "<html><body>legacy</body></html>",
                    0,
                    "2026-03-01 09:00:00",
                    "2026-03-01 09:30:00",
                    self.user.id,
                    7,
                    1,
                ],
            )

        schema_editor = SimpleNamespace(connection=connection)
        created = self.module.migrate_legacy_rows(schema_editor, EduMaterial, source_table=table_name)

        self.assertEqual(created, 1)
        material = EduMaterial.objects.get(title="레거시 HTML 자료")
        self.assertEqual(material.teacher_id, self.user.id)
        self.assertEqual(material.input_mode, EduMaterial.INPUT_PASTE)
        self.assertTrue(material.is_published)
        self.assertEqual(material.view_count, 7)

    def test_mixed_schema_skips_pdf_and_moves_html_markdown_rows(self):
        table_name = self._create_temp_table(
            """
            CREATE TABLE "{table}" (
                "id" char(32) NOT NULL PRIMARY KEY,
                "subject" varchar(20) NOT NULL,
                "grade" varchar(50) NULL,
                "unit_title" varchar(200) NOT NULL,
                "title" varchar(200) NOT NULL,
                "content" text NOT NULL,
                "source_type" varchar(20) NOT NULL,
                "pdf_file" varchar(100) NULL,
                "original_filename" varchar(255) NULL,
                "is_published" bool NOT NULL,
                "created_at" datetime NOT NULL,
                "updated_at" datetime NOT NULL,
                "teacher_id" integer NOT NULL,
                "view_count" integer NOT NULL,
                "is_shared" bool NOT NULL
            )
            """
        )
        rows = [
            [uuid.uuid4().hex, "SCIENCE", "4학년 1학기", "화산과 지진", "PDF 자료", "", "pdf", "textbooks/pdf/sample.pdf", "sample.pdf", 1, "2026-03-01 09:00:00", "2026-03-01 09:10:00", self.user.id, 3, 0],
            [uuid.uuid4().hex, "SCIENCE", "4학년 1학기", "화산과 지진", "HTML 자료", "<html><body>html</body></html>", "html", "", "activity.html", 1, "2026-03-01 09:00:00", "2026-03-01 09:10:00", self.user.id, 5, 0],
            [uuid.uuid4().hex, "SCIENCE", "4학년 1학기", "화산과 지진", "Markdown 자료", "# markdown", "markdown", "", "", 0, "2026-03-01 09:00:00", "2026-03-01 09:10:00", self.user.id, 2, 0],
        ]
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    f'INSERT INTO "{table_name}" (id, subject, grade, unit_title, title, content, source_type, pdf_file, original_filename, is_published, created_at, updated_at, teacher_id, view_count, is_shared) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                    row,
                )

        schema_editor = SimpleNamespace(connection=connection)
        created = self.module.migrate_legacy_rows(schema_editor, EduMaterial, source_table=table_name)

        self.assertEqual(created, 2)
        titles = set(EduMaterial.objects.values_list("title", flat=True))
        self.assertIn("HTML 자료", titles)
        self.assertIn("Markdown 자료", titles)
        self.assertNotIn("PDF 자료", titles)
