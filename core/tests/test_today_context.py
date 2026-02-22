from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse

from consent.models import SignatureDocument, SignatureRecipient, SignatureRequest
from core.views import _build_today_context


class TodayContextTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="teacher", password="password123")

    def _build_request(self):
        request = self.factory.get("/")
        request.user = self.user
        return request

    def _create_sent_request(self):
        document = SignatureDocument.objects.create(
            created_by=self.user,
            title="가정통신문 동의서",
            original_file=SimpleUploadedFile(
                "consent.pdf",
                b"%PDF-1.4\n%test\n",
                content_type="application/pdf",
            ),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        return SignatureRequest.objects.create(
            created_by=self.user,
            document=document,
            title="3학년 2반 보호자 동의서",
            status=SignatureRequest.STATUS_SENT,
        )

    def test_today_context_includes_unsigned_consent_item(self):
        consent_request = self._create_sent_request()
        SignatureRecipient.objects.create(
            request=consent_request,
            student_name="김학생",
            parent_name="김보호자",
            phone_number="010-1111-1111",
            status=SignatureRecipient.STATUS_PENDING,
        )
        SignatureRecipient.objects.create(
            request=consent_request,
            student_name="이학생",
            parent_name="이보호자",
            phone_number="010-2222-2222",
            status=SignatureRecipient.STATUS_VERIFIED,
        )
        SignatureRecipient.objects.create(
            request=consent_request,
            student_name="박학생",
            parent_name="박보호자",
            phone_number="010-3333-3333",
            status=SignatureRecipient.STATUS_SIGNED,
        )

        context = _build_today_context(self._build_request())
        consent_item = next((item for item in context["today_items"] if item["href"] == reverse("consent:dashboard")), None)

        self.assertIsNotNone(consent_item)
        self.assertEqual(consent_item["count_text"], "2건")

    def test_today_context_omits_consent_item_when_no_unsigned(self):
        consent_request = self._create_sent_request()
        SignatureRecipient.objects.create(
            request=consent_request,
            student_name="한학생",
            parent_name="한보호자",
            phone_number="010-4444-4444",
            status=SignatureRecipient.STATUS_SIGNED,
        )

        context = _build_today_context(self._build_request())
        has_consent_item = any(item["href"] == reverse("consent:dashboard") for item in context["today_items"])

        self.assertFalse(has_consent_item)
