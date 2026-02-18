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

    def test_public_document_korean_filename_returns_file(self):
        file_obj = SimpleUploadedFile("안내문.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        document = SignatureDocument.objects.create(
            created_by=self.teacher,
            title="korean-file",
            original_file=file_obj,
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        req = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=document,
            title="korean-filename-request",
            consent_text_version="v1",
            status=SignatureRequest.STATUS_SENT,
            sent_at=timezone.now(),
        )
        rec = SignatureRecipient.objects.create(
            request=req,
            student_name="학생A",
            parent_name="학부모A",
            phone_number="",
        )
        url = reverse("consent:public_document", kwargs={"token": rec.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_document_source_returns_file(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:document_source", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_recipients_csv_template_download(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients_csv_template")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("학생명", response.content.decode("utf-8-sig"))

    def test_recipients_csv_upload(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        csv_content = "학생명,학부모명\n김하늘,김하늘 보호자\n박나래,박나래 보호자\n"
        csv_file = SimpleUploadedFile(
            "recipients.csv",
            csv_content.encode("utf-8-sig"),
            content_type="text/csv",
        )
        response = self.client.post(
            url,
            {
                "recipients_text": "",
                "recipients_csv": csv_file,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=self.request_obj,
                student_name="김하늘",
                parent_name="김하늘 보호자",
            ).exists()
        )

    def test_detail_includes_copy_buttons_and_qr(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "문구+링크 복사")
        self.assertContains(response, "data:image/png;base64,")

    @patch("consent.models.SignatureDocument.save", side_effect=RuntimeError("storage failure"))
    def test_create_step1_handles_upload_exception_without_500(self, mocked_save):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:create_step1")
        file_obj = SimpleUploadedFile("sample.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        response = self.client.post(
            url,
            {
                "title": "테스트 동의서",
                "message": "안내",
                "legal_notice": "",
                "link_expire_days": 14,
                "original_file": file_obj,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "문서 업로드 처리 중 오류가 발생했습니다.")

    @patch("consent.views.SignatureRecipient.objects.get_or_create", side_effect=RuntimeError("db failure"))
    def test_recipients_handles_save_exception_without_500(self, mocked_get_or_create):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            url,
            {
                "recipients_text": "김하늘,김하늘 보호자",
                "recipients_csv": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "수신자 저장 중 오류가 발생했습니다.")

    def test_public_document_missing_file_returns_404_page(self):
        self.document.original_file.name = "signatures/consent/originals/missing-file.pdf"
        self.document.save(update_fields=["original_file"])
        url = reverse("consent:public_document", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "첨부 문서를 불러오지 못했습니다.", status_code=404)

    @patch("consent.views.get_consent_schema_status", return_value=(False, ["signatures_signaturedocument"], "missing"))
    def test_schema_guard_returns_503(self, mocked_schema):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:create_step1")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "동의서 서비스 점검 안내", status_code=503)
