from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from collect.models import CollectionRequest, Submission


class CollectFlowTest(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="pw123456",
        )
        self.teacher.userprofile.nickname = "teacher"
        self.teacher.userprofile.save(update_fields=["nickname"])

    def test_join_by_access_code_redirects_to_submit(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="가정통신문 수합",
            description="파일로 제출해주세요.",
            allow_file=True,
            allow_link=True,
            allow_text=True,
            status="active",
        )

        response = self.client.get(reverse("collect:join"), data={"code": req.access_code})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("collect:submit", args=[req.id]))

    def test_public_landing_prioritizes_guest_join_before_teacher_login(self):
        response = self.client.get(reverse("collect:landing"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("제출 참여는 비로그인", content)
        self.assertIn("요청 만들기는 로그인 후", content)
        self.assertIn("로그인 후 만들기", content)
        self.assertLess(content.index("제출 참여"), content.index("요청 만들기"))

    def test_guest_submit_file_and_teacher_download(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="과제물 수합",
            description="파일 제출만 허용",
            allow_file=True,
            allow_link=False,
            allow_text=False,
            status="active",
        )

        upload = SimpleUploadedFile(
            "sample.txt",
            b"hello collect",
            content_type="text/plain",
        )
        submit_response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "학생1",
                "contributor_affiliation": "1-1",
                "submission_type": "file",
                "file": upload,
                "file_description": "제출합니다.",
            },
        )
        self.assertEqual(submit_response.status_code, 302)

        sub = Submission.objects.get(collection_request=req, contributor_name="학생1")
        self.assertRedirects(
            submit_response,
            reverse("collect:submission_manage", args=[sub.management_id]),
        )

        self.client.force_login(self.teacher)
        download_response = self.client.get(reverse("collect:submission_download", args=[sub.id]))
        self.assertIn(download_response.status_code, (200, 302))
        if download_response.status_code == 200:
            self.assertIn("attachment;", download_response["Content-Disposition"])
            self.assertEqual(download_response["Cache-Control"], "no-store, private")

    def test_template_download_is_proxied_with_sensitive_cache_headers(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="양식 있는 수합",
            description="양식을 내려받아 제출",
            allow_file=True,
            allow_link=False,
            allow_text=False,
            status="active",
            template_file=SimpleUploadedFile(
                "guide.txt",
                b"collect template",
                content_type="text/plain",
            ),
            template_file_name="제출양식.txt",
        )

        response = self.client.get(reverse("collect:template_download", args=[req.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store, private")

    def test_request_detail_uses_inline_feedback_for_copy_download_and_delete(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="학급 파일 수합",
            description="파일 제출",
            allow_file=True,
            allow_link=False,
            allow_text=False,
            status="active",
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생1",
            contributor_affiliation="1반",
            submission_type="file",
            file=SimpleUploadedFile("report.txt", b"hello", content_type="text/plain"),
            original_filename="report.txt",
            file_size=5,
        )
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("collect:request_detail", args=[req.id]))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("collect-action-status", content)
        self.assertIn("data-download-all-button", content)
        self.assertIn("data-confirm-submit", content)
        self.assertNotIn("alert(", content)

    def test_reference_image_is_visible_on_submit_page_and_served_inline(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="이미지 참고 자료 수합",
            description="이미지를 보고 제출",
            allow_file=False,
            allow_link=False,
            allow_text=True,
            status="active",
            template_file=SimpleUploadedFile(
                "guide.png",
                b"\x89PNG\r\n\x1a\n",
                content_type="image/png",
            ),
            template_file_name="참고이미지.png",
        )

        submit_response = self.client.get(reverse("collect:submit", args=[req.id]))

        self.assertEqual(submit_response.status_code, 200)
        self.assertContains(submit_response, "참고 자료")
        self.assertContains(submit_response, "다운로드")
        self.assertContains(submit_response, "참고이미지.png")
        self.assertContains(submit_response, "data-consent-document-preview")
        self.assertContains(submit_response, "data-preview-image")
        self.assertContains(submit_response, "<img", html=False)

        image_response = self.client.get(reverse("collect:template_download", args=[req.id]))

        self.assertEqual(image_response.status_code, 200)
        self.assertIn("inline;", image_response["Content-Disposition"])
        self.assertEqual(image_response["Cache-Control"], "no-store, private")

        download_response = self.client.get(reverse("collect:template_download", args=[req.id]), data={"download": "1"})

        self.assertEqual(download_response.status_code, 200)
        self.assertIn("attachment;", download_response["Content-Disposition"])

    def test_reference_pdf_is_previewed_inline_and_still_downloadable(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="PDF 참고 자료 수합",
            description="PDF를 보고 제출",
            allow_file=False,
            allow_link=False,
            allow_text=True,
            status="active",
            template_file=SimpleUploadedFile(
                "guide.pdf",
                b"%PDF-1.4\n% collect reference\n",
                content_type="application/pdf",
            ),
            template_file_name="참고자료.pdf",
        )

        submit_response = self.client.get(reverse("collect:submit", args=[req.id]))

        self.assertEqual(submit_response.status_code, 200)
        self.assertContains(submit_response, "참고 자료")
        self.assertContains(submit_response, "참고자료.pdf")
        self.assertContains(submit_response, "다운로드")
        self.assertContains(submit_response, "data-consent-document-preview")
        self.assertContains(submit_response, "data-file-type=\"pdf\"")
        self.assertContains(submit_response, "data-preview-pagination")
        self.assertContains(submit_response, "consent/pdf_preview.js")
        self.assertContains(submit_response, f"{reverse('collect:template_download', args=[req.id])}?download=1")

        preview_response = self.client.get(reverse("collect:template_download", args=[req.id]))

        self.assertEqual(preview_response.status_code, 200)
        self.assertIn("inline;", preview_response["Content-Disposition"])
        self.assertEqual(preview_response["Cache-Control"], "no-store, private")

        download_response = self.client.get(reverse("collect:template_download", args=[req.id]), data={"download": "1"})

        self.assertEqual(download_response.status_code, 200)
        self.assertIn("attachment;", download_response["Content-Disposition"])

    def test_public_submit_page_uses_sensitive_cache_headers(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="공개 수합",
            description="설문 제출",
            allow_file=False,
            allow_link=True,
            allow_text=True,
            status="active",
        )

        response = self.client.get(reverse("collect:submit", args=[req.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        content = response.content.decode("utf-8")
        self.assertIn("<details", content)
        self.assertIn("보안 및 책임 안내", content)
        self.assertNotIn("<details open", content)
        self.assertLess(content.index('type="submit"'), content.index("보안 및 책임 안내"))

    def test_creator_can_reach_title_edit_from_submit_page(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="아이디 비밀번호 수합",
            description="",
            allow_file=False,
            allow_link=True,
            allow_text=False,
            status="active",
        )

        guest_response = self.client.get(reverse("collect:submit", args=[req.id]))
        self.assertNotContains(guest_response, "제목 수정")

        self.client.force_login(self.teacher)
        submit_response = self.client.get(reverse("collect:submit", args=[req.id]))
        edit_response = self.client.get(reverse("collect:request_edit", args=[req.id]))

        self.assertContains(submit_response, "제목 수정")
        self.assertContains(submit_response, reverse("collect:request_edit", args=[req.id]))
        self.assertContains(edit_response, "부제목")
