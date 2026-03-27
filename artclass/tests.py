import json
import os
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent, UserProfile
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from .classification import apply_auto_metadata
from .launcher_release import (
    LauncherReleaseValidationError,
    parse_latest_yml_text,
    upload_launcher_release_bundle,
)
from .manual_pipeline import ManualPipelineError, parse_manual_pipeline_result
from .models import ArtClass, ArtClassAttachment, ArtStep

User = get_user_model()


def make_test_gif_upload(name="step.gif"):
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
            b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
            b"\x00\x02\x02L\x01\x00;"
        ),
        content_type="image/gif",
    )


def make_test_material_upload(name="activity.pdf", content_type="application/pdf", size_bytes=None):
    if size_bytes is None:
        payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    else:
        payload = b"a" * size_bytes
    return SimpleUploadedFile(name, payload, content_type=content_type)


def make_test_launcher_manifest(version="0.2.0", installer_name=None):
    installer_name = installer_name or f"Eduitit Teacher Launcher Setup {version}.exe"
    return (
        f"version: {version}\n"
        "files:\n"
        f"  - url: {installer_name}\n"
        "    sha512: testsha512\n"
        "    size: 123456\n"
        f"path: {installer_name}\n"
        "sha512: testsha512\n"
        "releaseDate: '2026-03-24T00:00:00.000Z'\n"
    )


def make_test_launcher_release_uploads(version="0.2.0", installer_name=None):
    installer_name = installer_name or f"Eduitit Teacher Launcher Setup {version}.exe"
    blockmap_name = f"{installer_name}.blockmap"
    latest_yml = SimpleUploadedFile(
        "latest.yml",
        make_test_launcher_manifest(version=version, installer_name=installer_name).encode("utf-8"),
        content_type="text/yaml",
    )
    installer_file = SimpleUploadedFile(
        installer_name,
        b"launcher-binary",
        content_type="application/octet-stream",
    )
    blockmap_file = SimpleUploadedFile(
        blockmap_name,
        b"{}",
        content_type="application/octet-stream",
    )
    return latest_yml, installer_file, blockmap_file


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


class LauncherReleaseStorageTest(TestCase):
    def test_parse_latest_yml_text_reads_version_and_installer_name(self):
        manifest = parse_latest_yml_text(make_test_launcher_manifest(version="0.2.0"))

        self.assertEqual(manifest["version"], "0.2.0")
        self.assertEqual(manifest["installer_filename"], "Eduitit Teacher Launcher Setup 0.2.0.exe")
        self.assertEqual(
            manifest["blockmap_filename"],
            "Eduitit Teacher Launcher Setup 0.2.0.exe.blockmap",
        )

    def test_upload_launcher_release_bundle_rejects_mismatched_installer_name(self):
        latest_yml, installer_file, blockmap_file = make_test_launcher_release_uploads(
            version="0.2.0",
            installer_name="Expected Setup 0.2.0.exe",
        )
        installer_file.name = "Different Setup 0.2.0.exe"
        blockmap_file.name = "Different Setup 0.2.0.exe.blockmap"

        with patch("artclass.launcher_release.is_launcher_bucket_configured", return_value=True):
            with self.assertRaises(LauncherReleaseValidationError):
                upload_launcher_release_bundle(
                    latest_yml_file=latest_yml,
                    installer_file=installer_file,
                    blockmap_file=blockmap_file,
                )

    def test_upload_launcher_release_bundle_uploads_three_files(self):
        latest_yml, installer_file, blockmap_file = make_test_launcher_release_uploads(version="0.2.0")
        mock_client = Mock()

        with patch("artclass.launcher_release.is_launcher_bucket_configured", return_value=True), patch(
            "artclass.launcher_release._load_s3_client",
            return_value=mock_client,
        ), patch(
            "artclass.launcher_release.get_launcher_bucket_settings",
            return_value={"bucket_name": "launcher-bucket"},
        ):
            manifest = upload_launcher_release_bundle(
                latest_yml_file=latest_yml,
                installer_file=installer_file,
                blockmap_file=blockmap_file,
            )

        self.assertEqual(manifest["version"], "0.2.0")
        self.assertEqual(mock_client.upload_fileobj.call_count, 3)


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
        self.staff = User.objects.create_user(
            username="api_staff",
            password="pw123456",
            email="api_staff@example.com",
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.staff,
            defaults={"nickname": "운영교사", "role": "school"},
        )
        UserPolicyConsent.objects.create(
            user=self.staff,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
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

    def test_launcher_release_config_api_returns_env_values(self):
        with patch.dict(
            os.environ,
            {
                "ARTCLASS_LAUNCHER_DOWNLOAD_URL": "https://downloads.eduitit.com/launcher/Eduitit-Teacher-Launcher-Setup-0.2.0.exe",
                "ARTCLASS_LAUNCHER_UPDATE_BASE_URL": "https://downloads.eduitit.com/launcher/windows",
                "ARTCLASS_LAUNCHER_BRIDGE_VERSION": "0.2.0",
                "ARTCLASS_LAUNCHER_MINIMUM_REQUIRED_VERSION": "",
                "ARTCLASS_LAUNCHER_BRIDGE_NOTICE": "이미 설치했다면 이번 한 번만 다시 설치해 주세요.",
            },
            clear=False,
        ):
            response = self.client.get(reverse("artclass:launcher_release_config_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["downloadUrl"],
            "https://downloads.eduitit.com/launcher/Eduitit-Teacher-Launcher-Setup-0.2.0.exe",
        )
        self.assertEqual(payload["updateBaseUrl"], "https://downloads.eduitit.com/launcher/windows/")
        self.assertEqual(payload["bridgeVersion"], "0.2.0")
        self.assertEqual(payload["latestVersion"], "0.2.0")
        self.assertEqual(payload["minimumRequiredVersion"], "0.2.0")
        self.assertEqual(payload["bridgeNotice"], "이미 설치했다면 이번 한 번만 다시 설치해 주세요.")

    def test_launcher_release_config_api_allows_minimum_required_version_override(self):
        with patch.dict(
            os.environ,
            {
                "ARTCLASS_LAUNCHER_DOWNLOAD_URL": "https://downloads.eduitit.com/launcher/Eduitit-Teacher-Launcher-Setup-0.2.0.exe",
                "ARTCLASS_LAUNCHER_UPDATE_BASE_URL": "https://downloads.eduitit.com/launcher/windows",
                "ARTCLASS_LAUNCHER_BRIDGE_VERSION": "0.2.0",
                "ARTCLASS_LAUNCHER_MINIMUM_REQUIRED_VERSION": "0.2.4",
            },
            clear=False,
        ):
            response = self.client.get(reverse("artclass:launcher_release_config_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["latestVersion"], "0.2.0")
        self.assertEqual(payload["minimumRequiredVersion"], "0.2.4")

    def test_launcher_release_config_api_prefers_bucket_release_urls_over_env_values(self):
        current_release = {
            "version": "0.2.0",
            "installer_filename": "Eduitit Teacher Launcher Setup 0.2.0.exe",
            "blockmap_filename": "Eduitit Teacher Launcher Setup 0.2.0.exe.blockmap",
            "latest_filename": "latest.yml",
        }

        with patch.dict(
            os.environ,
            {
                "ARTCLASS_LAUNCHER_DOWNLOAD_URL": "https://drive.google.com/file/d/example/view?usp=sharing",
                "ARTCLASS_LAUNCHER_UPDATE_BASE_URL": "https://downloads.eduitit.com/launcher/windows",
                "ARTCLASS_LAUNCHER_BRIDGE_VERSION": "0.2.0",
            },
            clear=False,
        ), patch("artclass.views.get_current_launcher_release", return_value=current_release):
            response = self.client.get(reverse("artclass:launcher_release_config_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["downloadUrl"],
            "http://testserver/artclass/launcher-updates/windows/Eduitit%20Teacher%20Launcher%20Setup%200.2.0.exe",
        )
        self.assertEqual(payload["updateBaseUrl"], "http://testserver/artclass/launcher-updates/windows/")
        self.assertEqual(payload["latestVersion"], "0.2.0")
        self.assertEqual(payload["minimumRequiredVersion"], "0.2.0")

    def test_launcher_release_config_api_uses_bucket_release_urls_when_env_missing(self):
        current_release = {
            "version": "0.2.0",
            "installer_filename": "Eduitit Teacher Launcher Setup 0.2.0.exe",
            "blockmap_filename": "Eduitit Teacher Launcher Setup 0.2.0.exe.blockmap",
            "latest_filename": "latest.yml",
        }

        with patch.dict(
            os.environ,
            {
                "ARTCLASS_LAUNCHER_DOWNLOAD_URL": "",
                "ARTCLASS_LAUNCHER_UPDATE_BASE_URL": "",
                "ARTCLASS_LAUNCHER_BRIDGE_VERSION": "",
            },
            clear=False,
        ), patch("artclass.views.get_current_launcher_release", return_value=current_release):
            response = self.client.get(reverse("artclass:launcher_release_config_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["downloadUrl"],
            "http://testserver/artclass/launcher-updates/windows/Eduitit%20Teacher%20Launcher%20Setup%200.2.0.exe",
        )
        self.assertEqual(
            payload["updateBaseUrl"],
            "http://testserver/artclass/launcher-updates/windows/",
        )
        self.assertEqual(payload["bridgeVersion"], "0.2.0")
        self.assertEqual(payload["latestVersion"], "0.2.0")
        self.assertEqual(payload["minimumRequiredVersion"], "0.2.0")

    def test_launcher_update_index_view_returns_current_release_urls(self):
        current_release = {
            "version": "0.2.0",
            "installer_filename": "Eduitit Teacher Launcher Setup 0.2.0.exe",
            "blockmap_filename": "Eduitit Teacher Launcher Setup 0.2.0.exe.blockmap",
            "latest_filename": "latest.yml",
        }

        with patch("artclass.views.get_current_launcher_release", return_value=current_release):
            response = self.client.get(reverse("artclass:launcher_update_index"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["version"], "0.2.0")
        self.assertEqual(payload["latestVersion"], "0.2.0")
        self.assertEqual(payload["minimumRequiredVersion"], "0.2.0")
        self.assertEqual(
            payload["latestYmlUrl"],
            "http://testserver/artclass/launcher-updates/windows/latest.yml",
        )

    def test_launcher_update_asset_view_redirects_to_presigned_bucket_url(self):
        with patch(
            "artclass.views.get_launcher_asset_download_url",
            return_value="https://storage.railway.app/signed-download",
        ):
            response = self.client.get(
                reverse("artclass:launcher_update_asset", kwargs={"filename": "latest.yml"})
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://storage.railway.app/signed-download")

    def test_launcher_release_manager_requires_staff(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("artclass:launcher_release_manager"))

        self.assertEqual(response.status_code, 403)

    def test_launcher_release_manager_page_uses_operator_only_copy(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("artclass:launcher_release_manager"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "운영자 전용 런처 배포")
        self.assertContains(response, "교사는 이 화면을 사용할 필요가 없습니다.")
        self.assertContains(response, "교사용 설치 링크")
        self.assertNotContains(response, "desktop/teacher-launcher/dist")

    def test_launcher_install_guide_page_uses_download_url_and_next_link(self):
        with patch.dict(
            os.environ,
            {
                "ARTCLASS_LAUNCHER_DOWNLOAD_URL": "https://downloads.eduitit.com/launcher/Eduitit-Teacher-Launcher-Setup-0.2.0.exe",
                "ARTCLASS_LAUNCHER_BRIDGE_VERSION": "0.2.0",
            },
            clear=False,
        ):
            response = self.client.get(
                reverse("artclass:launcher_install_guide"),
                data={
                    "next": "/artclass/classroom/14/?autostart_launcher=1",
                    "label": "설치 후 이 수업 시작",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "런처 설치 / 다시 설치")
        self.assertContains(response, "설치파일 받기")
        self.assertContains(response, "설치 후 이 수업 시작")
        self.assertContains(response, "Bridge 0.2.0")
        self.assertContains(response, "이미 런처를 설치했다면 이번 한 번은 새 설치파일로 다시 설치해 주세요. 이후부터는 자동 업데이트됩니다.")
        self.assertContains(response, "수업 시작 전에 런처가 자동으로 업데이트를 마치고 같은 수업으로 다시 이어집니다.")
        self.assertContains(response, "Windows 보호 화면이 나오면")
        self.assertContains(response, "추가 정보")
        self.assertContains(response, "학교 PC 정책으로 실행이 막히면 관리자에게 런처 설치 허용을 요청하면 됩니다.")
        self.assertContains(response, "/artclass/classroom/14/?autostart_launcher=1")

    def test_launcher_release_manager_uploads_release_bundle_for_staff(self):
        self.client.force_login(self.staff)
        latest_yml, installer_file, blockmap_file = make_test_launcher_release_uploads(version="0.2.0")

        with patch(
            "artclass.views.upload_launcher_release_bundle",
            return_value={
                "version": "0.2.0",
                "installer_filename": installer_file.name,
                "blockmap_filename": blockmap_file.name,
                "latest_filename": "latest.yml",
            },
        ) as mock_upload:
            response = self.client.post(
                reverse("artclass:launcher_release_manager"),
                data={
                    "latest_yml": latest_yml,
                    "installer_exe": installer_file,
                    "installer_blockmap": blockmap_file,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("artclass:launcher_release_manager"))
        mock_upload.assert_called_once()

    def test_teacher_facing_pages_hide_release_manager_link_even_for_staff(self):
        art_class = ArtClass.objects.create(
            title="운영자 링크 숨김 확인",
            youtube_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
            created_by=self.staff,
        )
        ArtStep.objects.create(art_class=art_class, step_number=1, description="기본 단계")
        self.client.force_login(self.staff)

        setup_response = self.client.get(reverse("artclass:setup"))
        library_response = self.client.get(reverse("artclass:library"))
        classroom_response = self.client.get(reverse("artclass:classroom", kwargs={"pk": art_class.pk}))

        self.assertNotContains(setup_response, "운영자용 런처 버전 올리기")
        self.assertNotContains(library_response, "운영자용 런처 버전 올리기")
        self.assertNotContains(classroom_response, "운영자용 런처 버전 올리기")

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
        self.assertEqual(
            payload["payload"]["updateConfigUrl"],
            f"http://testserver{reverse('artclass:launcher_release_config_api')}",
        )
        self.assertEqual(payload["fallback"]["updateConfigUrl"], payload["payload"]["updateConfigUrl"])
        self.assertIn("watch?v=2bBhnfh4StU", payload["fallback"]["youtubeUrl"])
        self.assertIn("autoplay=1", payload["fallback"]["youtubeUrl"])
        self.assertNotIn("playlist=", payload["fallback"]["youtubeUrl"])
        self.assertNotIn("loop=1", payload["fallback"]["youtubeUrl"])
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
        self.assertContains(response, "저장하면 다음 화면에서 초록 버튼으로 바로 시작할 수 있어요.")
        self.assertContains(response, "저장 후 런처로 수업 시작")
        self.assertContains(response, "실행이 안 되면 같은 안내 화면에서 설치와 다시 설치를 한 번에 진행할 수 있어요.")
        self.assertContains(response, "런처 설치 안내 보기")
        self.assertContains(response, "수업 준비 팁")
        self.assertNotContains(response, "브라우저로 시작")
        self.assertNotContains(response, "ArtClass는 이제 런처 한 가지 방식으로 시작합니다.")
        self.assertNotContains(response, "저장 후 이렇게 시작됩니다")
        self.assertNotContains(response, "처음이라면 이렇게 시작해 보세요")
        self.assertNotContains(response, "설치가 필요한 경우 보기")
        self.assertContains(response, "프롬프트 복사하고 제미나이 열기")
        self.assertContains(response, "추천: 아래 파란 버튼 한 번이면 프롬프트를 복사하고 제미나이를 바로 엽니다.")
        self.assertContains(response, "프롬프트만 복사")
        self.assertContains(response, "수업 준비를 저장하고 있어요")
        self.assertContains(response, "이미지나 자료 파일이 있으면 업로드 때문에 조금 더 걸릴 수 있어요.")
        self.assertNotContains(response, "샘플 영상으로 체험하기")
        self.assertNotContains(response, "이번 한 번은 새 설치파일로 다시 설치해 주세요")

    def test_setup_page_keeps_install_notice_off_main_flow_even_when_download_available(self):
        with patch.dict(
            os.environ,
            {
                "ARTCLASS_LAUNCHER_DOWNLOAD_URL": "https://downloads.eduitit.com/launcher/Eduitit-Teacher-Launcher-Setup-0.2.0.exe",
                "ARTCLASS_LAUNCHER_BRIDGE_VERSION": "0.2.0",
            },
            clear=False,
        ):
            response = self.client.get(reverse("artclass:setup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "런처 설치 안내 보기")
        self.assertNotContains(response, "Bridge 0.2.0")
        self.assertNotContains(response, "이미 런처를 설치했다면 이번 한 번은 새 설치파일로 다시 설치해 주세요. 이후부터는 자동 업데이트됩니다.")
        self.assertNotContains(response, "런처 설치파일 다운로드")

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

    def test_setup_edit_shows_existing_materials_and_note(self):
        self.art_class.teacher_material_note = "자료를 먼저 나눠 준 뒤 색칠 단계에서 다시 보여 주세요."
        self.art_class.save(update_fields=["teacher_material_note"])
        attachment = ArtClassAttachment.objects.create(
            art_class=self.art_class,
            file=make_test_material_upload("guide.pdf"),
            original_name="guide.pdf",
            sort_order=1,
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("artclass:setup_edit", kwargs={"pk": self.art_class.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, attachment.original_name)
        self.assertContains(response, "자료를 먼저 나눠 준 뒤 색칠 단계에서 다시 보여 주세요.")
        self.assertContains(response, "PDF, HWP, HWPX / 최대 5개 / 파일당 20MB")

    def test_setup_edit_can_replace_material_attachments(self):
        old_attachment = ArtClassAttachment.objects.create(
            art_class=self.art_class,
            file=make_test_material_upload("old.pdf"),
            original_name="old.pdf",
            sort_order=1,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("artclass:setup_edit", kwargs={"pk": self.art_class.pk}),
            data={
                "title": "자료 수정 수업",
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "15",
                "playbackMode": ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
                "teacherMaterialNote": "새 활동지는 색칠 전에 먼저 배부합니다.",
                "delete_attachment_ids": str(old_attachment.pk),
                "class_material_files": make_test_material_upload("new.hwpx", content_type="application/octet-stream"),
                "step_count": "1",
                "step_text_0": "외부 모드 단계 설명",
                "step_existing_id_0": str(self.existing_step.pk),
            },
        )

        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': self.art_class.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        self.art_class.refresh_from_db()
        self.assertEqual(self.art_class.teacher_material_note, "새 활동지는 색칠 전에 먼저 배부합니다.")
        attachments = list(self.art_class.attachments.all())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].original_name, "new.hwpx")
        self.assertFalse(ArtClassAttachment.objects.filter(pk=old_attachment.pk).exists())

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

    def test_setup_clone_copies_materials_and_note(self):
        self.art_class.teacher_material_note = "도입에서 먼저 질문을 던진 뒤 활동지를 나눠 주세요."
        self.art_class.save(update_fields=["teacher_material_note"])
        ArtClassAttachment.objects.create(
            art_class=self.art_class,
            file=make_test_material_upload("worksheet.hwp", content_type="application/octet-stream"),
            original_name="worksheet.hwp",
            sort_order=1,
        )
        self.client.force_login(self.other)

        response = self.client.get(reverse("artclass:setup_clone", kwargs={"pk": self.art_class.pk}))

        cloned = ArtClass.objects.exclude(pk=self.art_class.pk).latest("id")
        self.assertRedirects(response, reverse("artclass:setup_edit", kwargs={"pk": cloned.pk}))
        self.assertEqual(cloned.teacher_material_note, self.art_class.teacher_material_note)
        self.assertEqual(cloned.attachments.count(), 1)
        self.assertEqual(cloned.attachments.first().original_name, "worksheet.hwp")

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

    def test_setup_rejects_invalid_material_attachment_type(self):
        upload = make_test_material_upload("guide.txt", content_type="text/plain")

        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "12",
                "playbackMode": ArtClass.PLAYBACK_MODE_EMBED,
                "teacherMaterialNote": "자료 설명",
                "class_material_files": upload,
                "step_count": "1",
                "step_text_0": "도화지에 연필로 큰 원을 그린다.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ArtClass.objects.count(), 0)
        self.assertContains(response, "수업 자료는 PDF, HWP, HWPX 파일만 사용할 수 있어요.")

    def test_setup_rejects_too_many_material_attachments(self):
        uploads = [make_test_material_upload(f"sheet{index}.pdf") for index in range(6)]

        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "12",
                "teacherMaterialNote": "자료 설명",
                "class_material_files": uploads,
                "step_count": "1",
                "step_text_0": "도화지에 연필로 큰 원을 그린다.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ArtClass.objects.count(), 0)
        self.assertContains(response, "수업 자료는 한 수업에 최대 5개까지 올릴 수 있어요.")

    def test_setup_saves_material_attachments_and_note(self):
        response = self.client.post(
            reverse("artclass:setup"),
            data={
                "videoUrl": "https://www.youtube.com/watch?v=2bBhnfh4StU",
                "stepInterval": "12",
                "teacherMaterialNote": "첫 번째 멈춤 화면에서 활동지를 함께 보며 색을 고르게 합니다.",
                "class_material_files": [
                    make_test_material_upload("worksheet.pdf"),
                    make_test_material_upload("source.hwpx", content_type="application/octet-stream"),
                ],
                "step_count": "1",
                "step_text_0": "도화지에 연필로 큰 원을 그린다.",
            },
        )

        created = ArtClass.objects.latest("id")
        expected_url = f"{reverse('artclass:classroom', kwargs={'pk': created.pk})}?autostart_launcher=1"
        self.assertRedirects(response, expected_url)
        self.assertEqual(created.teacher_material_note, "첫 번째 멈춤 화면에서 활동지를 함께 보며 색을 고르게 합니다.")
        self.assertEqual(created.attachments.count(), 2)
        self.assertEqual(
            list(created.attachments.values_list("original_name", flat=True)),
            ["worksheet.pdf", "source.hwpx"],
        )

    def test_setup_page_shows_input_guardrails(self):
        response = self.client.get(reverse("artclass:setup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "영상 주소 안내: 유튜브 주소만 넣어 주세요.")
        self.assertContains(response, "외부 AI 서비스로 전송될 수 있습니다.")
        self.assertContains(response, "JPG, PNG, GIF, WEBP 파일만 가능하며 7MB 이하")
        self.assertContains(response, "PDF, HWP, HWPX / 최대 5개 / 파일당 20MB")

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
        ArtClassAttachment.objects.create(
            art_class=art_class,
            file=make_test_material_upload("guide.pdf"),
            original_name="guide.pdf",
            sort_order=1,
        )

        response = self.client.get(reverse("artclass:library"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, art_class.display_title)
        self.assertContains(response, "런처 시작")
        self.assertContains(response, "초록 버튼을 누르면 영상과 수업 안내가 나뉘어 열립니다.")
        self.assertContains(response, "자료 1개")

    def test_library_uses_single_install_guide_link(self):
        response = self.client.get(reverse("artclass:library"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "실행이 안 되면 보기")
        self.assertContains(response, "설치 / 다시 설치 안내 열기")
        self.assertContains(response, reverse("artclass:launcher_install_guide"))
        self.assertNotContains(response, "설치파일 받기")
        self.assertNotContains(response, "Bridge 0.2.0")
        self.assertNotContains(response, "운영자용 런처 버전 올리기")


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
        self.assertContains(response, "초록 버튼을 누르면 영상과 수업 안내가 나뉘어 열립니다.")
        self.assertNotContains(response, "이번 한 번은 새 설치파일로 다시 설치해 주세요")

    def test_classroom_uses_single_install_guide_link(self):
        art_class = ArtClass.objects.create(
            title="런처 안내 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
        )
        ArtStep.objects.create(art_class=art_class, step_number=1, description="기본 단계")

        response = self.client.get(reverse("artclass:classroom", kwargs={"pk": art_class.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "실행이 안 되면 보기")
        self.assertContains(response, "설치 / 다시 설치 안내 열기")
        self.assertContains(response, "안내 화면에서 설치를 마친 뒤 초록 버튼으로 다시 돌아오면 됩니다.")
        self.assertContains(response, reverse("artclass:launcher_install_guide"))
        self.assertNotContains(response, "설치파일 받기")
        self.assertNotContains(response, "Bridge 0.2.0")
        self.assertNotContains(response, "운영자용 런처 버전 올리기")

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

    def test_launcher_runtime_inlines_step_images_as_data_urls(self):
        art_class = ArtClass.objects.create(
            title="런처 이미지 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
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
        ArtStep.objects.create(
            art_class=art_class,
            step_number=1,
            description="이미지 있는 단계",
            image=image_file,
        )

        response = self.client.get(
            reverse("artclass:classroom", kwargs={"pk": art_class.pk}),
            data={"display": "dashboard", "runtime": "launcher"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["data"]["steps"][0]["image_url"].startswith("data:image/gif;base64,"))

    def test_classroom_web_shows_teacher_materials_but_hides_loop_button(self):
        art_class = ArtClass.objects.create(
            title="자료 있는 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
            teacher_material_note="도입 3분 전쯤 활동지를 먼저 보여 주세요.",
        )
        ArtStep.objects.create(art_class=art_class, step_number=1, description="기본 단계")
        ArtClassAttachment.objects.create(
            art_class=art_class,
            file=make_test_material_upload("worksheet.pdf"),
            original_name="worksheet.pdf",
            sort_order=1,
        )

        response = self.client.get(reverse("artclass:classroom", kwargs={"pk": art_class.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "수업 자료 보기")
        self.assertContains(response, "worksheet.pdf")
        self.assertContains(response, "도입 3분 전쯤 활동지를 먼저 보여 주세요.")
        self.assertNotContains(response, 'id="btnLoop"')

    def test_launcher_dashboard_hides_teacher_materials_card(self):
        art_class = ArtClass.objects.create(
            title="자료 숨김 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
            teacher_material_note="교사용 메모",
        )
        ArtStep.objects.create(art_class=art_class, step_number=1, description="기본 단계")
        ArtClassAttachment.objects.create(
            art_class=art_class,
            file=make_test_material_upload("worksheet.pdf"),
            original_name="worksheet.pdf",
            sort_order=1,
        )

        response = self.client.get(
            reverse("artclass:classroom", kwargs={"pk": art_class.pk}),
            data={"display": "dashboard", "runtime": "launcher"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "수업 자료 보기")

    def test_launcher_dashboard_shows_manual_video_controls(self):
        art_class = ArtClass.objects.create(
            title="런처 제어 수업",
            youtube_url="https://www.youtube.com/watch?v=UFQT5Wtamw0",
            default_interval=10,
            playback_mode=ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW,
        )
        ArtStep.objects.create(art_class=art_class, step_number=1, description="기본 단계")

        response = self.client.get(
            reverse("artclass:classroom", kwargs={"pk": art_class.pk}),
            data={"display": "dashboard", "runtime": "launcher"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "수업 제어")
        self.assertContains(response, 'eduitit-launcher://action?name=replay_video')
        self.assertContains(response, "영상 다시 재생")
        self.assertContains(response, 'eduitit-launcher://quit')
        self.assertContains(response, "수업 종료")


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
