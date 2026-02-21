import io
import zipfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


def _build_sample_hwpx_file(name="sample.hwpx"):
    section_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>Sample document</hp:t></hp:run></hp:p>
</hp:section>
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contents/section0.xml", section_xml)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/octet-stream")


class HwpxChatViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hwpxchat_tester",
            password="pw123456",
            email="hwpxchat_tester@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "hwpxchat_tester"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_hwp_upload_is_blocked_server_side(self):
        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file(name="sample.hwp")},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HWP 파일은 지원하지 않습니다.")

    def test_main_wireframe_has_back_link_and_fallback_form_attrs(self):
        response = self.client.get(reverse("hwpxchat:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "서비스 목록으로 돌아가기")
        self.assertContains(response, "action=\"/hwpx-chat/process/\"")
        self.assertContains(response, "action=\"/hwpx-chat/reset/\"")
        self.assertContains(response, "method=\"post\"")

    def test_missing_file_returns_error(self):
        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HWPX 파일을 업로드해 주세요.")

    def test_hwpx_convert_success(self):
        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "변환 완료.")
        self.assertContains(response, "id=\"hwpx-markdown-output\"")
        self.assertContains(response, "Sample document")

    def test_download_markdown_after_convert(self):
        self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        response = self.client.get(reverse("hwpxchat:download_markdown"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=\"hwpx_markdown.md\"", response["Content-Disposition"])
        self.assertIn("Sample document", response.content.decode("utf-8"))

    def test_download_markdown_without_output_returns_400(self):
        response = self.client.get(reverse("hwpxchat:download_markdown"))

        self.assertEqual(response.status_code, 400)

    def test_result_contains_llm_quick_links(self):
        response = self.client.get(reverse("hwpxchat:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://chatgpt.com/")
        self.assertContains(response, "https://gemini.google.com/")
        self.assertContains(response, "https://claude.ai/")
        self.assertContains(response, "https://www.perplexity.ai/")
