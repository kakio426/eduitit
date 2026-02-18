from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from signatures.consent_models import SignatureDocument, SignaturePosition, SignatureRecipient, SignatureRequest


class ConsentFlowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="pw123456")
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
        SignaturePosition.objects.create(request=self.request_obj, page=1, x=100, y=100, width=120, height=50)
        self.recipient = SignatureRecipient.objects.create(
            request=self.request_obj,
            student_name="가나다",
            parent_name="홍길순",
            phone_number="010-1234-5678",
        )

    def test_access_token_generated(self):
        self.assertTrue(self.recipient.access_token)
        self.assertGreaterEqual(len(self.recipient.access_token), 20)

    def test_verify_identity_success_and_redirect(self):
        url = reverse("consent:verify", kwargs={"token": self.recipient.access_token})
        response = self.client.post(url, {"parent_name": "홍길순", "phone_last4": "5678"})
        self.assertRedirects(response, reverse("consent:sign", kwargs={"token": self.recipient.access_token}))
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, SignatureRecipient.STATUS_VERIFIED)

    def test_send_requires_preview_check(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, SignatureRequest.STATUS_DRAFT)

    @patch("consent.views.generate_signed_pdf")
    def test_sign_submission_updates_status(self, mocked_generate):
        mocked_generate.return_value = ContentFile(b"%PDF-1.4\n%%EOF", name="signed.pdf")

        verify_url = reverse("consent:verify", kwargs={"token": self.recipient.access_token})
        self.client.post(verify_url, {"parent_name": "홍길순", "phone_last4": "5678"})

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
        self.assertTrue(bool(self.recipient.signed_pdf))
