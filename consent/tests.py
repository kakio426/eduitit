from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from consent.models import SignatureDocument, SignatureRecipient, SignatureRequest


class ConsentFlowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="pw123456")
        self.teacher.email = "teacher@example.com"
        self.teacher.save(update_fields=["email"])
        self.teacher.userprofile.nickname = "교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])

        file_obj = SimpleUploadedFile("sample.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        self.document = SignatureDocument.objects.create(
            created_by=self.teacher,
            title="sample",
            original_file=file_obj,
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        self.request_obj = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=self.document,
            title="req",
            consent_text_version="v1",
        )
        self.recipient = SignatureRecipient.objects.create(
            request=self.request_obj,
            student_name="가나다",
            parent_name="홍길동",
            phone_number="",
        )

    def test_access_token_generated(self):
        self.assertTrue(self.recipient.access_token)
        self.assertGreaterEqual(len(self.recipient.access_token), 20)

    def test_verify_redirects_to_sign(self):
        url = reverse("consent:verify", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertRedirects(response, reverse("consent:sign", kwargs={"token": self.recipient.access_token}))

    def test_send_marks_request_as_sent(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, SignatureRequest.STATUS_SENT)

    def test_sign_submission_updates_status(self):
        sign_url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.post(
            sign_url,
            {
                "decision": "agree",
                "decline_reason": "",
                "signature_data": "data:image/png;base64,AAA",
            },
        )

        self.assertRedirects(response, reverse("consent:complete", kwargs={"token": self.recipient.access_token}))
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, SignatureRecipient.STATUS_SIGNED)
        self.assertEqual(self.recipient.decision, SignatureRecipient.DECISION_AGREE)
        self.assertTrue(bool(self.recipient.signature_data))

    def test_csv_download(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_csv", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("학생명", response.content.decode("utf-8-sig"))

    def test_summary_pdf_download(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_summary_pdf", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response["Content-Type"])

    def test_sign_link_expired(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now() - timezone.timedelta(days=20)
        self.request_obj.link_expire_days = 7
        self.request_obj.save(update_fields=["status", "sent_at", "link_expire_days"])

        url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "응답 링크가 만료되었습니다.", status_code=410)

    def test_public_document_returns_file(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        url = reverse("consent:public_document", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_document_source_returns_file(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:document_source", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")

    @patch("consent.views.get_consent_schema_status", return_value=(False, ["signatures_signaturedocument"], "missing"))
    def test_schema_guard_returns_503(self, mocked_schema):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:create_step1")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "동의서 서비스 점검 안내", status_code=503)
