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
