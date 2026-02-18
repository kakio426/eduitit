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
