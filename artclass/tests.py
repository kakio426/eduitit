import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from .classification import apply_auto_metadata
from .manual_pipeline import ManualPipelineError, parse_manual_pipeline_result
from .models import ArtClass, ArtStep

User = get_user_model()


class ManualPipelineParserTest(TestCase):
    def test_parse_json_with_time_materials_and_tip(self):
        payload = {
            "video_title": "테스트 수업",
            "steps": [
                {
                    "start": "00:35",
                    "end": "01:20",
                    "summary": "도화지 중앙에 큰 원을 그린다.",
                    "materials": ["도화지", "연필"],
                    "teacher_tip": "선을 약하게 시작하세요.",
                },
                {
                    "summary": "배경 색을 칠하고 명암을 넣는다.",
                },
            ],
        }

        result = parse_manual_pipeline_result(json.dumps(payload, ensure_ascii=False))

        self.assertEqual(result["meta"]["mode"], "json")
        self.assertEqual(result["meta"]["step_count"], 2)
        self.assertIn("[00:35-01:20]", result["steps"][0]["text"])
        self.assertIn("준비물:", result["steps"][0]["text"])
        self.assertIn("교사 팁:", result["steps"][0]["text"])

    def test_parse_fenced_json(self):
        raw_text = """```json
{
  "steps": [
    {"summary": "재료를 준비한다."},
    {"summary": "색을 섞어 바탕을 칠한다."}
  ]
}
```"""
        result = parse_manual_pipeline_result(raw_text)
        self.assertEqual(result["meta"]["mode"], "json")
        self.assertEqual(len(result["steps"]), 2)

    def test_parse_plain_text_list(self):
        raw_text = """
1. [00:10] 연필로 스케치를 시작한다.
2. [00:45] 스케치 선을 정리한다.
3. 색연필로 주요 부분에 색을 넣는다.
"""
        result = parse_manual_pipeline_result(raw_text)
        self.assertEqual(result["meta"]["mode"], "plain_text")
        self.assertEqual(len(result["steps"]), 3)
        self.assertIn("[00:10]", result["steps"][0]["text"])

    def test_deduplicates_heavily_duplicated_steps_with_warning(self):
        payload = {"steps": [{"summary": "같은 문장이 반복됩니다"} for _ in range(5)]}
        result = parse_manual_pipeline_result(json.dumps(payload, ensure_ascii=False))

        self.assertEqual(result["meta"]["step_count"], 1)
        self.assertEqual(len(result["steps"]), 1)
        self.assertTrue(any("중복" in warning for warning in result["warnings"]))

    def test_parse_broken_json_falls_back_to_loose_extraction(self):
        raw_text = """
{
  "steps": [
    {"summary": "도화지 중앙에 큰 원을 그린다.",
     "materials": ["도화지", "연필"]},
    {"summary": "배경 색을 칠한다."
     "teacher_tip": "밝은 색부터 칠하세요."}
  ]
}
"""
        result = parse_manual_pipeline_result(raw_text)

        self.assertEqual(result["meta"]["mode"], "plain_text")
        self.assertEqual(result["meta"]["step_count"], 2)
        self.assertTrue(any("읽을 수 있는 내용만 반영" in warning for warning in result["warnings"]))
        self.assertIn("준비물:", result["steps"][0]["text"])
        self.assertIn("교사 팁:", result["steps"][1]["text"])

    def test_skips_short_and_low_info_steps_when_valid_step_exists(self):
        payload = {
            "steps": [
                {"summary": "짧다"},
                {"summary": "요약할 수 있는 충분한 정보가 없습니다"},
                {"summary": "도화지에 연필로 윤곽을 그린다."},
            ]
        }
        result = parse_manual_pipeline_result(json.dumps(payload, ensure_ascii=False))

        self.assertEqual(result["meta"]["step_count"], 1)
        self.assertIn("윤곽", result["steps"][0]["text"])
        self.assertTrue(any("짧아 제외" in warning for warning in result["warnings"]))
        self.assertTrue(any("정보 부족" in warning for warning in result["warnings"]))

    def test_trims_steps_over_max_with_warning(self):
        payload = {
            "steps": [
                {"summary": f"{idx}단계에서 도형을 그리고 색을 채운다."}
                for idx in range(1, 31)
            ]
        }
        result = parse_manual_pipeline_result(json.dumps(payload, ensure_ascii=False))

        self.assertEqual(result["meta"]["step_count"], 24)
        self.assertEqual(len(result["steps"]), 24)
        self.assertTrue(any("앞 24개만 반영" in warning for warning in result["warnings"]))


class ManualPipelineApiTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="api_owner",
            password="pw123456",
            email="api_owner@example.com",
        )
        self.other = User.objects.create_user(
            username="api_other",
            password="pw123456",
            email="api_other@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"nickname": "소유교사", "role": "school"},
        )
        UserProfile.objects.update_or_create(
            user=self.other,
            defaults={"nickname": "외부교사", "role": "school"},
        )

    def test_parse_gemini_steps_api_success(self):
        url = reverse("artclass:parse_gemini_steps_api")
        raw = json.dumps(
            {
                "steps": [
                    {"start": "00:12", "summary": "주요 도형을 크게 잡는다."},
                    {"summary": "윤곽선을 정리하고 색을 넣는다."},
                ]
            },
            ensure_ascii=False,
        )

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                    "rawText": raw,
                },
                ensure_ascii=False,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["meta"]["step_count"], 2)
        self.assertIn("https://www.youtube.com/watch?v=2bBhnfh4StU", data["promptTemplate"])

    def test_parse_gemini_steps_api_recovers_partial_json_with_warnings(self):
        url = reverse("artclass:parse_gemini_steps_api")
        raw = """
{
  "steps": [
    {"summary": "도화지 중앙에 큰 원을 그린다.",
     "materials": ["도화지", "연필"]},
    {"summary": "배경 색을 칠한다."
     "teacher_tip": "밝은 색부터 칠하세요."}
  ]
}
"""

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                    "rawText": raw,
                },
                ensure_ascii=False,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["meta"]["mode"], "plain_text")
        self.assertEqual(data["meta"]["step_count"], 2)
        self.assertTrue(data["warnings"])

    def test_parse_gemini_steps_api_rejects_empty_input(self):
        url = reverse("artclass:parse_gemini_steps_api")
        response = self.client.post(
            url,
            data=json.dumps({"rawText": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "EMPTY_INPUT")
        self.assertEqual(response.json()["message"], "답변을 붙여넣어 주세요.")

    def test_parse_gemini_steps_api_method_not_allowed(self):
        url = reverse("artclass:parse_gemini_steps_api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_update_playback_mode_api_success(self):
        art_class = ArtClass.objects.create(
            title="테스트 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EMBED,
            created_by=self.owner,
        )
        url = reverse("artclass:update_playback_mode_api", kwargs={"pk": art_class.pk})
        self.client.force_login(self.owner)

        response = self.client.post(
            url,
            data=json.dumps({"mode": ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        art_class.refresh_from_db()
        self.assertEqual(art_class.playback_mode, ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW)
        self.assertTrue(response.json()["success"])

    def test_update_playback_mode_api_invalid_mode(self):
        art_class = ArtClass.objects.create(
            title="테스트 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        url = reverse("artclass:update_playback_mode_api", kwargs={"pk": art_class.pk})
        self.client.force_login(self.owner)

        response = self.client.post(
            url,
            data=json.dumps({"mode": "unsupported_mode"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "INVALID_MODE")

    def test_update_playback_mode_api_requires_authentication(self):
        art_class = ArtClass.objects.create(
            title="테스트 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        url = reverse("artclass:update_playback_mode_api", kwargs={"pk": art_class.pk})

        response = self.client.post(
            url,
            data=json.dumps({"mode": ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "AUTH_REQUIRED")

    def test_update_playback_mode_api_forbidden_for_non_owner(self):
        art_class = ArtClass.objects.create(
            title="테스트 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EMBED,
            created_by=self.owner,
        )
        url = reverse("artclass:update_playback_mode_api", kwargs={"pk": art_class.pk})
        self.client.force_login(self.other)

        response = self.client.post(
            url,
            data=json.dumps({"mode": ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "FORBIDDEN")
        art_class.refresh_from_db()
        self.assertEqual(art_class.playback_mode, ArtClass.PLAYBACK_MODE_EMBED)

    def test_start_launcher_session_api_success(self):
        art_class = ArtClass.objects.create(
            title="런처 테스트 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EMBED,
            created_by=self.owner,
        )
        url = reverse("artclass:start_launcher_session_api", kwargs={"pk": art_class.pk})
        self.client.force_login(self.owner)

        response = self.client.post(
            url,
            data=json.dumps({"source": "test"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn("eduitit-launcher://launch?payload=", payload["launcherUrl"])
        self.assertIn("display=dashboard", payload["fallback"]["dashboardUrl"])
        self.assertIn("runtime=launcher", payload["fallback"]["dashboardUrl"])
        self.assertIn("playlist=2bBhnfh4StU", payload["fallback"]["youtubeUrl"])
        art_class.refresh_from_db()
        self.assertEqual(art_class.playback_mode, ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW)

    def test_start_launcher_session_api_requires_authentication(self):
        art_class = ArtClass.objects.create(
            title="런처 인증 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        url = reverse("artclass:start_launcher_session_api", kwargs={"pk": art_class.pk})

        response = self.client.post(
            url,
            data=json.dumps({"source": "test"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "AUTH_REQUIRED")

    def test_start_launcher_session_api_forbidden_for_non_owner(self):
        art_class = ArtClass.objects.create(
            title="런처 권한 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        url = reverse("artclass:start_launcher_session_api", kwargs={"pk": art_class.pk})
        self.client.force_login(self.other)

        response = self.client.post(
            url,
            data=json.dumps({"source": "test"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "FORBIDDEN")

    @patch("artclass.views._fetch_youtube_title")
    def test_video_advice_api_returns_launcher_recommended_for_valid_youtube_video(self, mock_fetch_title):
        mock_fetch_title.return_value = "봄 꽃병 꾸미기"
        url = reverse("artclass:video_advice_api")

        response = self.client.post(
            url,
            data=json.dumps({"videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "launcher_recommended")
        self.assertEqual(payload["recommendedMode"], ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW)
        self.assertEqual(payload["headline"], "런처로 바로 시작하면 됩니다")
        self.assertEqual(payload["title"], "봄 꽃병 꾸미기")

    @patch("artclass.views._fetch_youtube_title")
    def test_video_advice_api_returns_launcher_recommended_when_title_fetch_fails(self, mock_fetch_title):
        mock_fetch_title.return_value = ""
        url = reverse("artclass:video_advice_api")

        response = self.client.post(
            url,
            data=json.dumps({"videoUrl": "https://www.youtube.com/watch?v=UFQT5Wtamw0"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "launcher_recommended")
        self.assertEqual(payload["recommendedMode"], ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW)

    def test_video_advice_api_returns_unknown_for_invalid_url(self):
        url = reverse("artclass:video_advice_api")

        response = self.client.post(
            url,
            data=json.dumps({"videoUrl": "not-a-youtube-url"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "unknown")
        self.assertEqual(payload["recommendedMode"], ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW)

    @patch("artclass.views._fetch_youtube_title")
    def test_video_advice_api_does_not_fetch_for_localhost_url(self, mock_fetch_title):
        url = reverse("artclass:video_advice_api")

        response = self.client.post(
            url,
            data=json.dumps({"videoUrl": "http://127.0.0.1:8000/private"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unknown")
        mock_fetch_title.assert_not_called()

    def test_video_advice_api_rejects_invalid_json(self):
        url = reverse("artclass:video_advice_api")

        response = self.client.post(url, data="{", content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "INVALID_JSON")

    def test_update_step_text_api_success(self):
        art_class = ArtClass.objects.create(
            title="단계 저장 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        step = ArtStep.objects.create(
            art_class=art_class,
            step_number=1,
            description="기존 설명",
        )
        url = reverse("artclass:update_step_text_api", kwargs={"pk": art_class.pk, "step_id": step.pk})
        self.client.force_login(self.owner)

        response = self.client.post(
            url,
            data=json.dumps({"text": "새 설명\n준비물: 도화지, 연필\n교사 팁: 흐름을 천천히 안내"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        step.refresh_from_db()
        self.assertEqual(step.description, payload["text"])
        self.assertIn("준비물:", step.description)

    def test_update_step_text_api_requires_authentication(self):
        art_class = ArtClass.objects.create(
            title="단계 인증 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        step = ArtStep.objects.create(art_class=art_class, step_number=1, description="기존 설명")
        url = reverse("artclass:update_step_text_api", kwargs={"pk": art_class.pk, "step_id": step.pk})

        response = self.client.post(
            url,
            data=json.dumps({"text": "수정 시도"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "AUTH_REQUIRED")

    def test_update_step_text_api_forbidden_for_non_owner(self):
        art_class = ArtClass.objects.create(
            title="단계 권한 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        step = ArtStep.objects.create(art_class=art_class, step_number=1, description="기존 설명")
        url = reverse("artclass:update_step_text_api", kwargs={"pk": art_class.pk, "step_id": step.pk})
        self.client.force_login(self.other)

        response = self.client.post(
            url,
            data=json.dumps({"text": "권한 없는 수정"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "FORBIDDEN")

    def test_update_step_text_api_rejects_invalid_json(self):
        art_class = ArtClass.objects.create(
            title="단계 JSON 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        step = ArtStep.objects.create(art_class=art_class, step_number=1, description="기존 설명")
        url = reverse("artclass:update_step_text_api", kwargs={"pk": art_class.pk, "step_id": step.pk})
        self.client.force_login(self.owner)

        response = self.client.post(
            url,
            data="{bad json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "INVALID_JSON")

    def test_update_step_text_api_rejects_empty_text(self):
        art_class = ArtClass.objects.create(
            title="단계 빈값 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        step = ArtStep.objects.create(art_class=art_class, step_number=1, description="기존 설명")
        url = reverse("artclass:update_step_text_api", kwargs={"pk": art_class.pk, "step_id": step.pk})
        self.client.force_login(self.owner)

        response = self.client.post(
            url,
            data=json.dumps({"text": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "EMPTY_TEXT")


class ArtClassDeleteTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="art_owner",
            password="pw123456",
            email="art_owner@example.com",
        )
        self.other = User.objects.create_user(
            username="art_other",
            password="pw123456",
            email="art_other@example.com",
        )
        self.staff = User.objects.create_user(
            username="art_staff",
            password="pw123456",
            email="art_staff@example.com",
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"nickname": "미술교사", "role": "school"},
        )
        UserProfile.objects.update_or_create(
            user=self.other,
            defaults={"nickname": "다른교사", "role": "school"},
        )
        UserProfile.objects.update_or_create(
            user=self.staff,
            defaults={"nickname": "관리교사", "role": "school"},
        )
        self.art_class = ArtClass.objects.create(
            title="삭제 테스트 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )

    def test_owner_can_delete_class(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("artclass:delete", kwargs={"pk": self.art_class.pk}))
        self.assertRedirects(response, reverse("artclass:library"))
        self.assertFalse(ArtClass.objects.filter(pk=self.art_class.pk).exists())

    def test_staff_can_delete_class(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("artclass:delete", kwargs={"pk": self.art_class.pk}))
        self.assertRedirects(response, reverse("artclass:library"))
        self.assertFalse(ArtClass.objects.filter(pk=self.art_class.pk).exists())

    def test_non_owner_cannot_delete_class(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("artclass:delete", kwargs={"pk": self.art_class.pk}))
        self.assertRedirects(response, reverse("artclass:library"))
        self.assertTrue(ArtClass.objects.filter(pk=self.art_class.pk).exists())

    def test_delete_requires_login(self):
        response = self.client.post(reverse("artclass:delete", kwargs={"pk": self.art_class.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ArtClass.objects.filter(pk=self.art_class.pk).exists())


class ArtClassSetupEditTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="setup_owner",
            password="pw123456",
            email="setup_owner@example.com",
        )
        self.other = User.objects.create_user(
            username="setup_other",
            password="pw123456",
            email="setup_other@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"nickname": "수정교사", "role": "school"},
        )
        UserProfile.objects.update_or_create(
            user=self.other,
            defaults={"nickname": "외부교사", "role": "school"},
        )
        self.art_class = ArtClass.objects.create(
            title="수정 테스트 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        image_file = SimpleUploadedFile(
            "step.gif",
            (
                b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
                b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
                b"\x00\x02\x02L\x01\x00;"
            ),
            content_type="image/gif",
        )
        self.existing_step = ArtStep.objects.create(
            art_class=self.art_class,
            step_number=1,
            description="기존 단계",
            image=image_file,
        )

    def test_setup_edit_forbidden_for_non_owner(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("artclass:setup_edit", kwargs={"pk": self.art_class.pk}))
        self.assertEqual(response.status_code, 403)

    def test_setup_edit_renders_initial_steps_via_safe_json_script(self):
        self.existing_step.description = '</script><script>alert(1)</script>'
        self.existing_step.save(update_fields=["description"])
        self.client.force_login(self.owner)

        response = self.client.get(reverse("artclass:setup_edit", kwargs={"pk": self.art_class.pk}))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn('id="artclassInitialSteps"', body)
        self.assertIn(r'\u003C/script\u003E\u003Cscript\u003Ealert(1)\u003C/script\u003E', body)

    def test_setup_page_uses_beginner_friendly_gemini_copy(self):
        response = self.client.get(reverse("artclass:setup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "오늘 바로 시작하는 미술 수업")
        self.assertContains(response, "런처로 수업 시작")
        self.assertContains(response, "응답 예시 보기")
        self.assertContains(response, "ArtClass는 이제 런처 한 가지 방식으로 시작합니다.")
        self.assertNotContains(response, "브라우저로 시작")
        self.assertNotContains(response, "샘플 영상으로 체험하기")

    def test_setup_page_uses_gemini_example_without_sample_shortcut(self):
        response = self.client.get(reverse("artclass:setup"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("gemini_example_result", response.context)
        self.assertIn('"video_title": "봄 꽃병 꾸미기"', response.context["gemini_example_result"])
        self.assertNotContains(response, 'artclassSampleLesson')

    def test_setup_edit_preserves_existing_image_if_not_reuploaded(self):
        self.client.force_login(self.owner)
        old_image_name = self.existing_step.image.name

        response = self.client.post(
            reverse("artclass:setup_edit", kwargs={"pk": self.art_class.pk}),
            data={
                "title": "수정된 수업",
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "15",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_count": "1",
                "step_text_0": "수정된 단계 설명",
                "step_existing_id_0": str(self.existing_step.pk),
            },
        )

        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': self.art_class.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        new_step = self.art_class.steps.get(step_number=1)
        self.assertEqual(new_step.description, "수정된 단계 설명")
        self.assertEqual(new_step.image.name, old_image_name)

    def test_setup_edit_external_mode_redirects_with_launcher_autostart(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("artclass:setup_edit", kwargs={"pk": self.art_class.pk}),
            data={
                "title": "런처 자동 시작 수업",
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "15",
                "playbackMode": ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
                "step_count": "1",
                "step_text_0": "외부 모드 단계 설명",
                "step_existing_id_0": str(self.existing_step.pk),
            },
        )

        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': self.art_class.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)

    def test_setup_clone_creates_copy_for_non_owner(self):
        self.client.force_login(self.other)
        original_count = ArtClass.objects.count()
        original_step_count = self.art_class.steps.count()

        response = self.client.get(reverse("artclass:setup_clone", kwargs={"pk": self.art_class.pk}))

        self.assertEqual(ArtClass.objects.count(), original_count + 1)
        cloned = ArtClass.objects.exclude(pk=self.art_class.pk).latest("id")
        self.assertRedirects(response, reverse("artclass:setup_edit", kwargs={"pk": cloned.pk}))
        self.assertEqual(cloned.created_by, self.other)
        self.assertEqual(cloned.youtube_url, self.art_class.youtube_url)
        self.assertEqual(cloned.default_interval, self.art_class.default_interval)
        self.assertEqual(cloned.steps.count(), original_step_count)
        self.assertEqual(cloned.steps.get(step_number=1).description, self.existing_step.description)

    def test_setup_clone_redirects_owner_to_existing_edit(self):
        self.client.force_login(self.owner)
        original_count = ArtClass.objects.count()

        response = self.client.get(reverse("artclass:setup_clone", kwargs={"pk": self.art_class.pk}))

        self.assertRedirects(response, reverse("artclass:setup_edit", kwargs={"pk": self.art_class.pk}))
        self.assertEqual(ArtClass.objects.count(), original_count)

    def test_setup_clone_forbidden_for_non_shared_class(self):
        self.art_class.is_shared = False
        self.art_class.save(update_fields=["is_shared"])
        self.client.force_login(self.other)

        response = self.client.get(reverse("artclass:setup_clone", kwargs={"pk": self.art_class.pk}))

        self.assertEqual(response.status_code, 403)


class ArtClassAutoMetadataTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="meta_owner",
            password="pw123456",
            email="meta_owner@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"nickname": "자동분류교사", "role": "school"},
        )

    def test_setup_rejects_non_youtube_url_and_preserves_posted_steps(self):
        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "http://127.0.0.1:8000/private",
                "stepInterval": "12",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_count": "1",
                "step_text_0": "도화지에 연필로 큰 원을 그린다.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ArtClass.objects.count(), 0)
        self.assertContains(response, "유효한 유튜브 주소만 사용할 수 있어요.")
        self.assertEqual(response.context["initial_steps"][0]["text"], "도화지에 연필로 큰 원을 그린다.")

    def test_setup_rejects_invalid_step_image_type(self):
        upload = SimpleUploadedFile("step.txt", b"hello", content_type="text/plain")

        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "12",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_count": "1",
                "step_text_0": "도화지에 연필로 큰 원을 그린다.",
                "step_image_0": upload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ArtClass.objects.count(), 0)
        self.assertContains(response, "단계 이미지는 JPG, PNG, GIF, WEBP 파일만 사용할 수 있어요.")

    def test_setup_page_shows_input_guardrails(self):
        response = self.client.get(reverse("artclass:setup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "유튜브가 아닌 링크, 내부망 주소, localhost 주소는 사용할 수 없습니다.")
        self.assertContains(response, "외부 AI 서비스로 전송될 수 있습니다.")
        self.assertContains(response, "JPG, PNG, GIF, WEBP 파일만 가능하며 5MB 이하")

    def test_setup_generates_auto_metadata_without_manual_title(self):
        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "12",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_count": "2",
                "step_text_0": "3학년 학생이 수채 물감으로 봄 풍경을 채색한다.",
                "step_text_1": "벚꽃 표현을 위해 붓 터치를 연습한다.",
            },
        )

        created = ArtClass.objects.latest("id")
        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': created.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        self.assertTrue(created.is_auto_classified)
        self.assertEqual(created.auto_category, "회화")
        self.assertEqual(created.auto_grade_band, "중학년")
        self.assertIn("물감", created.auto_tags)
        self.assertTrue(created.title)

    def test_setup_accepts_invalid_step_interval_with_default(self):
        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "abc",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_count": "1",
                "step_text_0": "3학년 학생이 수채 물감으로 봄 풍경을 채색한다.",
            },
        )

        created = ArtClass.objects.latest("id")
        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': created.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        self.assertEqual(created.default_interval, 10)

    def test_setup_recovers_steps_without_step_count(self):
        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "12",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_text_0": "도화지에 연필로 큰 원을 그린다.",
                "step_text_2": "색연필로 바탕을 채색한다.",
            },
        )

        created = ArtClass.objects.latest("id")
        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': created.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        self.assertEqual(created.steps.count(), 2)
        self.assertEqual(
            list(created.steps.values_list("description", flat=True)),
            ["도화지에 연필로 큰 원을 그린다.", "색연필로 바탕을 채색한다."],
        )

    def test_setup_recovers_steps_when_step_count_is_invalid(self):
        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=UFQT5Wtamw0",
                "stepInterval": "12",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_count": "abc",
                "step_text_0": "새학기 삼각 이름표 밑그림을 연필로 잡는다.",
                "step_text_1": "색연필로 이름표를 채색하고 꾸민다.",
            },
        )

        created = ArtClass.objects.latest("id")
        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': created.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        self.assertEqual(created.steps.count(), 2)

    @patch("artclass.views._fetch_youtube_title")
    def test_setup_does_not_fetch_youtube_title_during_save(self, mock_fetch_title):
        mock_fetch_title.return_value = "삼각 이름표 만들기"

        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=UFQT5Wtamw0",
                "stepInterval": "12",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "step_count": "2",
                "step_text_0": "새학기 삼각 이름표 밑그림을 연필로 잡는다.",
                "step_text_1": "색연필로 이름표를 채색하고 꾸민다.",
            },
        )

        created = ArtClass.objects.latest("id")
        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': created.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        mock_fetch_title.assert_not_called()
        self.assertNotEqual(created.title, "삼각 이름표 만들기")

    def test_library_query_matches_step_text_and_auto_tags(self):
        art_class = ArtClass.objects.create(
            title="",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
        )
        ArtStep.objects.create(
            art_class=art_class,
            step_number=1,
            description="재활용품으로 협동 콜라주 작품을 만든다.",
        )
        apply_auto_metadata(art_class)
        art_class.refresh_from_db()

        response = self.client.get(reverse("artclass:library"), data={"q": "재활용"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, art_class.display_title)

    def test_library_filters_category_and_grade(self):
        drawing = ArtClass.objects.create(
            title="",
            youtube_url="https://www.youtube.com/watch?v=abc123",
            default_interval=10,
            created_by=self.owner,
        )
        ArtStep.objects.create(
            art_class=drawing,
            step_number=1,
            description="1학년 학생이 색연필로 선 그리기 드로잉을 연습한다.",
        )
        apply_auto_metadata(drawing)

        sculpture = ArtClass.objects.create(
            title="",
            youtube_url="https://www.youtube.com/watch?v=def456",
            default_interval=10,
            created_by=self.owner,
        )
        ArtStep.objects.create(
            art_class=sculpture,
            step_number=1,
            description="5학년 학생이 점토로 입체 조형 작품을 만든다.",
        )
        apply_auto_metadata(sculpture)

        drawing.refresh_from_db()
        sculpture.refresh_from_db()

        response = self.client.get(
            reverse("artclass:library"),
            data={"category": "조형", "grade": "고학년"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, sculpture.display_title)
        self.assertNotContains(response, drawing.display_title)

    def test_library_shows_creator_nickname(self):
        art_class = ArtClass.objects.create(
            title="닉네임 표시 테스트",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            created_by=self.owner,
            is_shared=True,
        )

        response = self.client.get(reverse("artclass:library"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, art_class.display_title)
        self.assertContains(response, "자동분류교사")

    def test_library_hides_generated_username_when_nickname_missing(self):
        generated_user = User.objects.create_user(
            username="user694",
            password="pw123456",
            email="generated@example.com",
        )
        UserProfile.objects.update_or_create(
            user=generated_user,
            defaults={"nickname": "", "role": "school"},
        )
        art_class = ArtClass.objects.create(
            title="아이디 마스킹 테스트",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            created_by=generated_user,
            is_shared=True,
        )

        response = self.client.get(reverse("artclass:library"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, art_class.display_title)
        self.assertContains(response, "익명의 선생님")
        self.assertNotContains(response, "user694")

    def test_library_separates_my_classes_and_shared_classes_for_logged_in_teacher(self):
        self.client.force_login(self.owner)
        other_user = User.objects.create_user(
            username="other_owner",
            password="pw123456",
            email="other_owner@example.com",
        )

        my_private = ArtClass.objects.create(
            title="내 비공개 수업",
            youtube_url="https://www.youtube.com/watch?v=private01",
            default_interval=10,
            created_by=self.owner,
            is_shared=False,
        )
        my_shared = ArtClass.objects.create(
            title="내 공개 수업",
            youtube_url="https://www.youtube.com/watch?v=shared01",
            default_interval=10,
            created_by=self.owner,
            is_shared=True,
        )
        other_shared = ArtClass.objects.create(
            title="다른 선생님 공개 수업",
            youtube_url="https://www.youtube.com/watch?v=shared02",
            default_interval=10,
            created_by=other_user,
            is_shared=True,
        )

        response = self.client.get(reverse("artclass:library"))

        self.assertEqual(response.status_code, 200)
        my_titles = {item.display_title for item in response.context["my_classes"]}
        shared_titles = {item.display_title for item in response.context["shared_classes"]}
        self.assertEqual(my_titles, {my_private.display_title, my_shared.display_title})
        self.assertEqual(shared_titles, {my_shared.display_title, other_shared.display_title})

    def test_library_shows_start_mode_badge_and_reason(self):
        art_class = ArtClass.objects.create(
            title="런처 권장 공개 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
            created_by=self.owner,
            is_shared=True,
        )

        response = self.client.get(reverse("artclass:library"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, art_class.display_title)
        self.assertContains(response, "런처 시작")
        self.assertContains(response, "이 수업은 런처로 시작합니다.")


class ArtClassPresentationUxTest(TestCase):
    def test_classroom_shows_launcher_recommended_state_for_external_mode(self):
        art_class = ArtClass.objects.create(
            title="런처 상태 안내 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
        )
        ArtStep.objects.create(art_class=art_class, step_number=1, description="기본 단계")

        response = self.client.get(reverse("artclass:classroom", kwargs={"pk": art_class.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "런처 시작")
        self.assertContains(response, "이 수업은 런처로 시작합니다.")

    def test_classroom_normalizes_legacy_embed_mode_to_launcher_flow(self):
        art_class = ArtClass.objects.create(
            title="브라우저 상태 안내 수업",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EMBED,
        )
        ArtStep.objects.create(art_class=art_class, step_number=1, description="기본 단계")

        response = self.client.get(reverse("artclass:classroom", kwargs={"pk": art_class.pk}))

        self.assertEqual(response.status_code, 200)
        art_class.refresh_from_db()
        self.assertEqual(art_class.playback_mode, ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW)
        self.assertContains(response, "런처 시작")
        self.assertContains(response, "초록 버튼을 누르면 영상과 수업 안내가 나뉘어 열립니다.")


class ArtClassYoutubeTitleBackfillCommandTest(TestCase):
    @patch("artclass.management.commands.backfill_artclass_youtube_titles._fetch_youtube_title")
    def test_command_updates_titles_from_youtube(self, mock_fetch_title):
        target = ArtClass.objects.create(
            title="동물 회화 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
        )
        untouched = ArtClass.objects.create(
            title="기존 제목 유지",
            youtube_url="https://www.youtube.com/watch?v=unknown_id",
            default_interval=10,
        )

        def fake_fetch(url):
            if "UFQT5Wtamw0" in url:
                return "삼각 이름표 만들기"
            return ""

        mock_fetch_title.side_effect = fake_fetch

        stdout = StringIO()
        call_command("backfill_artclass_youtube_titles", sleep_ms=0, stdout=stdout)

        target.refresh_from_db()
        untouched.refresh_from_db()

        self.assertEqual(target.title, "삼각 이름표 만들기")
        self.assertEqual(untouched.title, "기존 제목 유지")
