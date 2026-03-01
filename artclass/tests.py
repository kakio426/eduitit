import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
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

    def test_rejects_heavily_duplicated_steps(self):
        payload = {"steps": [{"summary": "같은 문장이 반복됩니다"} for _ in range(5)]}
        with self.assertRaises(ManualPipelineError) as exc:
            parse_manual_pipeline_result(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(exc.exception.code, "DUPLICATED_STEPS")

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

    def test_parse_gemini_steps_api_rejects_empty_input(self):
        url = reverse("artclass:parse_gemini_steps_api")
        response = self.client.post(
            url,
            data=json.dumps({"rawText": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "EMPTY_INPUT")

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

        self.assertRedirects(response, reverse("artclass:classroom", kwargs={"pk": self.art_class.pk}))
        new_step = self.art_class.steps.get(step_number=1)
        self.assertEqual(new_step.description, "수정된 단계 설명")
        self.assertEqual(new_step.image.name, old_image_name)
