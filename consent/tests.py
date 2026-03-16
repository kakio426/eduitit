import csv
import io
from unittest.mock import patch
from io import StringIO
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import DataError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from consent.models import (
    ConsentAuditLog,
    ConsentRoster,
    ConsentRosterEntry,
    SignatureDocument,
    SignatureRecipient,
    SignatureRequest,
)
from consent.services import PdfRuntimeUnavailable, generate_recipient_evidence_pdf, generate_summary_pdf
from consent.views import DEFAULT_LEGAL_NOTICE
from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION


def seed_current_policy_consent(user):
    return UserPolicyConsent.objects.create(
        user=user,
        provider="direct",
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        agreed_at=timezone.now(),
        agreement_source="required_gate",
    )


class ConsentFlowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="pw123456")
        self.teacher.email = "teacher@example.com"
        self.teacher.save(update_fields=["email"])
        self.teacher.userprofile.nickname = "교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])
        seed_current_policy_consent(self.teacher)

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
        self.assertRedirects(
            response,
            reverse("consent:sign", kwargs={"token": self.recipient.access_token}),
            fetch_redirect_response=False,
        )

    def test_send_marks_request_as_sent(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, SignatureRequest.STATUS_SENT)
        self.assertIsNotNone(self.request_obj.sent_at)

    def test_send_blocks_when_source_document_missing(self):
        self.document.original_file.name = "signatures/consent/originals/missing-file.pdf"
        self.document.save(update_fields=["original_file"])

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "안내문 파일을 찾을 수 없어 발송 링크를 생성할 수 없습니다.")
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, SignatureRequest.STATUS_DRAFT)

    def test_detail_shows_locked_shared_lookup_banner_before_send(self):
        self.client.login(username="teacher", password="pw123456")

        response = self.client.get(
            reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학부모 전체 링크")
        self.assertContains(response, "발송 시작 후 공개")

    def test_detail_shows_shared_lookup_banner_after_send(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
        self.client.login(username="teacher", password="pw123456")

        response = self.client.get(
            reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학부모 전체 링크")
        self.assertContains(
            response,
            reverse("consent:shared_lookup", kwargs={"shared_lookup_token": self.request_obj.shared_lookup_token}),
        )
        self.assertContains(response, "전체 링크 복사")
        self.assertContains(response, "안내문+전체 링크 복사")

    def test_sign_submission_updates_status(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
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

    def test_sign_page_shows_policy_links_and_updated_legal_notice(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.legal_notice = DEFAULT_LEGAL_NOTICE
        self.request_obj.save(update_fields=["status", "sent_at", "legal_notice"])

        response = self.client.get(
            reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("policy"))
        self.assertContains(response, "개인정보처리방침")
        self.assertContains(response, "운영정책")
        self.assertContains(response, "접속 기록")


    def test_sign_submission_with_phone_requires_last4(self):
        self.recipient.phone_number = "010-1234-5678"
        self.recipient.save(update_fields=["phone_number"])
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        sign_url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.post(
            sign_url,
            {
                "decision": "agree",
                "decline_reason": "",
                "signature_data": "data:image/png;base64,AAA",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, SignatureRecipient.STATUS_PENDING)
        self.assertContains(response, "전화번호 끝 4자리를 확인해 주세요.")
        self.assertTrue(
            ConsentAuditLog.objects.filter(
                request=self.request_obj,
                recipient=self.recipient,
                event_type=ConsentAuditLog.EVENT_VERIFY_FAIL,
            ).exists()
        )

    def test_sign_submission_with_phone_stores_verified_evidence(self):
        self.recipient.phone_number = "010-1234-5678"
        self.recipient.save(update_fields=["phone_number"])
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        sign_url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.post(
            sign_url,
            {
                "decision": "agree",
                "decline_reason": "",
                "phone_last4": "5678",
                "signature_data": "data:image/png;base64,AAA",
            },
            HTTP_X_FORWARDED_FOR="203.0.113.10",
            HTTP_USER_AGENT="ConsentTestAgent/1.0",
        )

        self.assertRedirects(response, reverse("consent:complete", kwargs={"token": self.recipient.access_token}))
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.identity_assurance, SignatureRecipient.IDENTITY_PHONE_LAST4)
        self.assertIsNotNone(self.recipient.verified_at)
        self.assertEqual(self.recipient.verified_ip_address, "203.0.113.10")
        self.assertEqual(self.recipient.verified_user_agent, "ConsentTestAgent/1.0")
        self.assertEqual(self.recipient.ip_address, "203.0.113.10")
        self.assertEqual(self.recipient.user_agent, "ConsentTestAgent/1.0")
        self.assertTrue(
            ConsentAuditLog.objects.filter(
                request=self.request_obj,
                recipient=self.recipient,
                event_type=ConsentAuditLog.EVENT_VERIFY_SUCCESS,
            ).exists()
        )

    def test_sign_submission_without_phone_uses_token_only_assurance(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
        sign_url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.post(
            sign_url,
            {
                "decision": "agree",
                "decline_reason": "",
                "signature_data": "data:image/png;base64,AAA",
            },
            HTTP_X_FORWARDED_FOR="203.0.113.11",
            HTTP_USER_AGENT="ConsentNoPhone/1.0",
        )

        self.assertRedirects(response, reverse("consent:complete", kwargs={"token": self.recipient.access_token}))
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.identity_assurance, SignatureRecipient.IDENTITY_TOKEN_ONLY)
        self.assertIsNone(self.recipient.verified_at)
        self.assertEqual(self.recipient.ip_address, "203.0.113.11")
        self.assertEqual(self.recipient.user_agent, "ConsentNoPhone/1.0")

    def test_sign_link_blocked_before_send_start(self):
        url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "아직 발송이 시작되지 않았습니다.", status_code=403)

    def test_shared_lookup_blocked_before_send_start(self):
        url = reverse(
            "consent:shared_lookup",
            kwargs={"shared_lookup_token": self.request_obj.shared_lookup_token},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "아직 발송이 시작되지 않았습니다.", status_code=403)

    def test_shared_lookup_redirects_to_recipient_sign_page(self):
        self.recipient.phone_number = "010-1234-5678"
        self.recipient.save(update_fields=["phone_number"])
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        url = reverse(
            "consent:shared_lookup",
            kwargs={"shared_lookup_token": self.request_obj.shared_lookup_token},
        )
        response = self.client.post(
            url,
            {
                "student_name": "가나다",
                "phone_last4": "5678",
            },
        )

        self.assertRedirects(
            response,
            reverse("consent:sign", kwargs={"token": self.recipient.access_token}),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            ConsentAuditLog.objects.filter(
                request=self.request_obj,
                recipient=self.recipient,
                event_type=ConsentAuditLog.EVENT_LOOKUP_SUCCESS,
            ).exists()
        )

    def test_shared_lookup_shows_generic_error_on_no_match(self):
        self.recipient.phone_number = "010-1234-5678"
        self.recipient.save(update_fields=["phone_number"])
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        url = reverse(
            "consent:shared_lookup",
            kwargs={"shared_lookup_token": self.request_obj.shared_lookup_token},
        )
        response = self.client.post(
            url,
            {
                "student_name": "가나다",
                "phone_last4": "0000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "입력한 정보로 제출 대상을 확인하지 못했습니다. 다시 확인해 주세요.")
        self.assertNotContains(response, "전화번호 끝 4자리를 확인해 주세요.")
        log = ConsentAuditLog.objects.filter(
            request=self.request_obj,
            event_type=ConsentAuditLog.EVENT_LOOKUP_FAIL,
        ).latest("created_at")
        self.assertEqual(log.event_meta.get("reason"), "no_match")

    def test_shared_lookup_fails_when_multiple_candidates_match(self):
        self.recipient.phone_number = "010-1234-5678"
        self.recipient.save(update_fields=["phone_number"])
        SignatureRecipient.objects.create(
            request=self.request_obj,
            student_name="가나다",
            parent_name="다른 보호자",
            phone_number="010-9999-5678",
        )
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        url = reverse(
            "consent:shared_lookup",
            kwargs={"shared_lookup_token": self.request_obj.shared_lookup_token},
        )
        response = self.client.post(
            url,
            {
                "student_name": "가나다",
                "phone_last4": "5678",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "입력한 정보로 제출 대상을 확인하지 못했습니다. 다시 확인해 주세요.")
        log = ConsentAuditLog.objects.filter(
            request=self.request_obj,
            event_type=ConsentAuditLog.EVENT_LOOKUP_FAIL,
        ).latest("created_at")
        self.assertEqual(log.event_meta.get("reason"), "multiple_match")

    def test_csv_download(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_csv", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertGreaterEqual(len(rows), 2)
        header = rows[0]
        self.assertIn("학생명", header)
        self.assertIn("요청ID", header)
        self.assertIn("안내문SHA256", header)
        self.assertIn("증빙수준", header)
        self.assertIn("본인확인IP", header)
        self.assertIn("제출IP", header)
        first = dict(zip(header, rows[1]))
        self.assertEqual(first["요청ID"], str(self.request_obj.request_id))
        self.assertEqual(first["동의서제목"], self.request_obj.title)
        self.assertEqual(first["안내문제목"], self.document.title)
        self.assertTrue(first["안내문SHA256"])

    @patch("consent.views.generate_summary_pdf")
    def test_summary_pdf_download(self, mocked_generate_summary_pdf):
        mocked_generate_summary_pdf.return_value = ContentFile(
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            name="summary.pdf",
        )
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_summary_pdf", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response["Content-Type"])
        disposition = response.get("Content-Disposition", "")
        self.assertIn("attachment;", disposition)
        self.assertNotIn("untitled", disposition.lower())

    def test_summary_pdf_download_includes_source_document_pages_when_pdf_valid(self):
        try:
            from pypdf import PdfReader
            from reportlab.pdfgen import canvas
        except ModuleNotFoundError:
            self.skipTest("pypdf/reportlab unavailable")

        packet = io.BytesIO()
        c = canvas.Canvas(packet)
        c.drawString(72, 720, "source-document-page")
        c.showPage()
        c.save()
        packet.seek(0)

        document = SignatureDocument.objects.create(
            created_by=self.teacher,
            title="valid-source-doc",
            original_file=SimpleUploadedFile(
                "valid_source.pdf",
                packet.getvalue(),
                content_type="application/pdf",
            ),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        request_obj = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=document,
            title="valid-summary-test",
            consent_text_version="v1",
        )
        SignatureRecipient.objects.create(
            request=request_obj,
            student_name="학생A",
            parent_name="보호자A",
            phone_number="",
        )

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_summary_pdf", kwargs={"request_id": request_obj.request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response["Content-Type"])

        reader = PdfReader(io.BytesIO(response.content))
        self.assertGreaterEqual(len(reader.pages), 2)

    def test_summary_pdf_download_limits_source_pdf_to_first_page(self):
        try:
            from pypdf import PdfReader
            from reportlab.pdfgen import canvas
        except ModuleNotFoundError:
            self.skipTest("pypdf/reportlab unavailable")

        packet = io.BytesIO()
        c = canvas.Canvas(packet)
        for label in ("source-page-1", "source-page-2", "source-page-3"):
            c.drawString(72, 720, label)
            c.showPage()
        c.save()
        packet.seek(0)

        document = SignatureDocument.objects.create(
            created_by=self.teacher,
            title="multi-source-doc",
            original_file=SimpleUploadedFile(
                "multi_source.pdf",
                packet.getvalue(),
                content_type="application/pdf",
            ),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        request_obj = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=document,
            title="multi-summary-test",
            consent_text_version="v1",
        )
        SignatureRecipient.objects.create(
            request=request_obj,
            student_name="학생B",
            parent_name="보호자B",
            phone_number="",
        )

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_summary_pdf", kwargs={"request_id": request_obj.request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        reader = PdfReader(io.BytesIO(response.content))
        self.assertGreaterEqual(len(reader.pages), 2)
        combined_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        self.assertIn("source-page-1", combined_text)
        self.assertNotIn("source-page-2", combined_text)
        self.assertNotIn("source-page-3", combined_text)

    @patch("consent.views.generate_summary_pdf")
    @patch("django.db.models.fields.files.FieldFile.save", side_effect=RuntimeError("storage down"))
    def test_summary_pdf_download_falls_back_when_storage_save_fails(self, mocked_save, mocked_generate_summary_pdf):
        mocked_generate_summary_pdf.return_value = ContentFile(
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            name="summary.pdf",
        )
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_summary_pdf", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response["Content-Type"])
        self.assertIn("attachment;", response.get("Content-Disposition", ""))

    @patch("consent.views.generate_summary_pdf", side_effect=PdfRuntimeUnavailable("missing reportlab, pypdf"))
    def test_summary_pdf_download_shows_error_when_pdf_runtime_missing(self, mocked_generate_summary_pdf):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_summary_pdf", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF 엔진(reportlab, pypdf)이 준비되지 않아 요약 PDF를 생성할 수 없습니다.")

    def test_sign_link_expired(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now() - timezone.timedelta(days=20)
        self.request_obj.link_expire_days = 7
        self.request_obj.save(update_fields=["status", "sent_at", "link_expire_days"])

        url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "이 제출 링크는 만료되었습니다.", status_code=410)

    def test_public_document_returns_file(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        url = reverse("consent:public_document", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertIn("attachment;", response.get("Content-Disposition", ""))
        log = ConsentAuditLog.objects.filter(
            request=self.request_obj,
            recipient=self.recipient,
            event_type=ConsentAuditLog.EVENT_DOCUMENT_VIEWED,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.event_meta.get("mode"), "download")

    def test_public_document_blocked_before_send_start(self):
        url = reverse("consent:public_document", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "아직 발송이 시작되지 않았습니다.", status_code=403)

    def test_send_rotates_shared_lookup_token_on_resend(self):
        self.recipient.phone_number = "010-1234-5678"
        self.recipient.save(update_fields=["phone_number"])
        self.client.login(username="teacher", password="pw123456")

        first_response = self.client.post(
            reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        )
        self.assertEqual(first_response.status_code, 302)
        self.request_obj.refresh_from_db()
        first_token = self.request_obj.shared_lookup_token

        second_response = self.client.post(
            reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        )
        self.assertEqual(second_response.status_code, 302)
        self.request_obj.refresh_from_db()
        self.assertNotEqual(self.request_obj.shared_lookup_token, first_token)

        old_lookup_response = self.client.get(
            reverse("consent:shared_lookup", kwargs={"shared_lookup_token": first_token})
        )
        self.assertEqual(old_lookup_response.status_code, 404)

        new_lookup_response = self.client.get(
            reverse("consent:shared_lookup", kwargs={"shared_lookup_token": self.request_obj.shared_lookup_token})
        )
        self.assertEqual(new_lookup_response.status_code, 200)

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
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertIn("attachment;", response.get("Content-Disposition", ""))

    def test_public_document_inline_logs_document_view(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        url = reverse("consent:public_document_inline", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        log = ConsentAuditLog.objects.filter(
            request=self.request_obj,
            recipient=self.recipient,
            event_type=ConsentAuditLog.EVENT_DOCUMENT_VIEWED,
        ).latest("created_at")
        self.assertEqual(log.event_meta.get("mode"), "inline")

    def test_document_source_returns_file(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:document_source", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.request_obj.refresh_from_db()
        self.assertIsNotNone(self.request_obj.preview_checked_at)

    def test_recipients_csv_template_download(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients_csv_template")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("학생명", response.content.decode("utf-8-sig"))
        self.assertIn("연락처(뒤4자리)", response.content.decode("utf-8-sig"))

    def test_recipients_csv_upload(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        csv_content = "학생명,학부모명,연락처(뒤4자리)\n김하늘,김하늘 보호자,5678\n박나래,,1234\n"
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
                phone_number="5678",
            ).exists()
        )
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=self.request_obj,
                student_name="박나래",
                parent_name="박나래 보호자",
                phone_number="1234",
            ).exists()
        )

    def test_general_recipients_csv_template_download(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients_csv_template") + "?audience_type=general"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn("이름", content)
        self.assertNotIn("연락처(뒤4자리)", content)

    def test_general_recipients_accept_name_only(self):
        general_request = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=self.document,
            title="general-req",
            consent_text_version="v1",
            audience_type=SignatureRequest.AUDIENCE_GENERAL,
        )
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": general_request.request_id})
        response = self.client.post(
            url,
            {
                "recipients_text": "김교사\n박강사",
                "recipients_csv": "",
                "saved_roster": "",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=general_request,
                student_name="김교사",
                parent_name="",
                phone_number="",
            ).exists()
        )
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=general_request,
                student_name="박강사",
                parent_name="",
                phone_number="",
            ).exists()
        )

    def test_general_detail_hides_shared_lookup_banner(self):
        general_request = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=self.document,
            title="general-detail",
            consent_text_version="v1",
            audience_type=SignatureRequest.AUDIENCE_GENERAL,
            status=SignatureRequest.STATUS_SENT,
            sent_at=timezone.now(),
        )
        SignatureRecipient.objects.create(
            request=general_request,
            student_name="김교사",
            parent_name="",
            phone_number="",
        )
        self.client.login(username="teacher", password="pw123456")

        response = self.client.get(
            reverse("consent:detail", kwargs={"request_id": general_request.request_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "일반 서명형은 수신자별 개별 링크만 사용합니다.")
        self.assertNotContains(response, "학부모 전체 링크")

    def test_detail_includes_copy_buttons_and_qr(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "안내문+링크 복사")
        self.assertContains(response, "data:image/png;base64,")

    def test_detail_shows_inline_document_preview_panel(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-consent-document-preview")
        self.assertContains(response, "data-preview-pagination")
        self.assertContains(response, reverse("consent:document_source", kwargs={"request_id": self.request_obj.request_id}))

    def test_sign_page_shows_document_preview_pagination_controls(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])

        url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-preview-pagination")
        self.assertContains(response, "data-preview-prev")
        self.assertContains(response, "data-preview-next")

    def test_detail_hides_links_before_send_start(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "제출 링크가 숨김 상태")
        self.assertContains(response, "발송 시작 후 수신자 링크가 표시됩니다.")


    def test_download_recipient_pdf_returns_file_when_available(self):
        self.recipient.status = SignatureRecipient.STATUS_SIGNED
        self.recipient.decision = SignatureRecipient.DECISION_AGREE
        self.recipient.signature_data = "data:image/png;base64,AAA"
        self.recipient.signed_at = timezone.now()
        self.recipient.signed_pdf.save(
            "recipient-proof.pdf",
            ContentFile(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"),
            save=True,
        )

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_recipient_pdf", kwargs={"recipient_id": self.recipient.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response["Content-Type"])
        self.assertIn("attachment;", response.get("Content-Disposition", ""))

    def test_regenerate_link_clears_evidence_fields(self):
        old_token = self.recipient.access_token
        self.recipient.identity_assurance = SignatureRecipient.IDENTITY_PHONE_LAST4
        self.recipient.verified_at = timezone.now()
        self.recipient.verified_ip_address = "203.0.113.20"
        self.recipient.verified_user_agent = "VerifyAgent/1.0"
        self.recipient.decision = SignatureRecipient.DECISION_AGREE
        self.recipient.decline_reason = ""
        self.recipient.signature_data = "data:image/png;base64,AAA"
        self.recipient.signed_at = timezone.now()
        self.recipient.ip_address = "203.0.113.21"
        self.recipient.user_agent = "SubmitAgent/1.0"
        self.recipient.signed_pdf.save(
            "signed.pdf",
            ContentFile(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"),
            save=False,
        )
        self.recipient.status = SignatureRecipient.STATUS_PENDING
        self.recipient.save(
            update_fields=[
                "identity_assurance",
                "verified_at",
                "verified_ip_address",
                "verified_user_agent",
                "decision",
                "decline_reason",
                "signature_data",
                "signed_at",
                "ip_address",
                "user_agent",
                "signed_pdf",
                "status",
            ]
        )

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:regenerate_link", kwargs={"recipient_id": self.recipient.id})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.recipient.refresh_from_db()
        self.assertNotEqual(self.recipient.access_token, old_token)
        self.assertEqual(self.recipient.identity_assurance, SignatureRecipient.IDENTITY_TOKEN_ONLY)
        self.assertIsNone(self.recipient.verified_at)
        self.assertIsNone(self.recipient.verified_ip_address)
        self.assertEqual(self.recipient.verified_user_agent, "")
        self.assertEqual(self.recipient.decision, "")
        self.assertEqual(self.recipient.signature_data, "")
        self.assertIsNone(self.recipient.signed_at)
        self.assertIsNone(self.recipient.ip_address)
        self.assertEqual(self.recipient.user_agent, "")

    def test_resend_rotates_pending_recipient_token_and_invalidates_old_link(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now() - timezone.timedelta(days=1)
        self.request_obj.save(update_fields=["status", "sent_at"])
        old_token = self.recipient.access_token

        self.client.login(username="teacher", password="pw123456")
        resend_url = reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(resend_url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.recipient.refresh_from_db()
        self.assertNotEqual(self.recipient.access_token, old_token)
        old_link_response = self.client.get(reverse("consent:sign", kwargs={"token": old_token}))
        self.assertEqual(old_link_response.status_code, 404)

    def test_detail_shows_progress_dashboard_counts(self):
        self.recipient.status = SignatureRecipient.STATUS_SIGNED
        self.recipient.decision = SignatureRecipient.DECISION_AGREE
        self.recipient.signed_at = timezone.now()
        self.recipient.save(update_fields=["status", "decision", "signed_at"])
        SignatureRecipient.objects.create(
            request=self.request_obj,
            student_name="학생B",
            parent_name="학부모B",
            phone_number="",
        )

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "전체 수신자")
        self.assertContains(response, "응답 완료")
        self.assertContains(response, "완료율")
        self.assertContains(response, "50%")

    def test_delete_request_allows_when_submitted_response_exists(self):
        self.recipient.status = SignatureRecipient.STATUS_SIGNED
        self.recipient.decision = SignatureRecipient.DECISION_AGREE
        self.recipient.signature_data = "data:image/png;base64,AAA"
        self.recipient.signed_at = timezone.now()
        self.recipient.save(update_fields=["status", "decision", "signature_data", "signed_at"])

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:delete_request", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(url, {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SignatureRequest.objects.filter(id=self.request_obj.id).exists())

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

    def test_create_step1_prefills_from_sheetbook_seed(self):
        self.client.login(username="teacher", password="pw123456")
        session = self.client.session
        session["sheetbook_action_seeds"] = {
            "seed-token": {
                "action": "consent",
                "data": {
                    "title": "교무수첩 동의서",
                    "message": "교무수첩에서 가져온 안내문입니다.",
                    "document_title": "체험학습 안내문",
                },
            }
        }
        session.save()

        response = self.client.get(f"{reverse('consent:create_step1')}?sb_seed=seed-token")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교무수첩에서 가져온 내용으로")
        self.assertContains(response, "교무수첩 동의서")
        self.assertContains(response, "교무수첩에서 가져온 안내문입니다.")
        self.assertContains(response, 'name="sheetbook_seed_token"')

    def test_create_step1_shows_upload_preview_shell(self):
        self.client.login(username="teacher", password="pw123456")
        response = self.client.get(reverse("consent:create_step1"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-consent-upload-preview")
        self.assertContains(response, "consent/pdf_preview.js")
        self.assertContains(response, "선택한 안내문 미리보기")
        self.assertContains(response, "교사용 체크")

    def test_create_step1_seed_auto_adds_recipients(self):
        self.client.login(username="teacher", password="pw123456")
        session = self.client.session
        session["sheetbook_action_seeds"] = {
            "seed-token-2": {
                "action": "consent",
                "data": {
                    "recipients_text": "김하늘,김하늘 보호자,01012345678\n박나래,박나래 보호자,01099887766",
                },
            }
        }
        session.save()

        url = reverse("consent:create_step1")
        file_obj = SimpleUploadedFile("seed.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        response = self.client.post(
            url,
            {
                "sheetbook_seed_token": "seed-token-2",
                "title": "교무수첩 연동 동의서",
                "message": "안내",
                "legal_notice": "",
                "link_expire_days": 14,
                "original_file": file_obj,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교무수첩에서 가져온 수신자 2명을 미리 넣어두었어요.")
        created_request = SignatureRequest.objects.filter(
            created_by=self.teacher,
            title="교무수첩 연동 동의서",
        ).latest("created_at")
        self.assertEqual(created_request.recipients.count(), 2)
        self.assertTrue(created_request.recipients.filter(student_name="김하늘", phone_number="5678").exists())

    @patch("consent.views.SignatureRecipient.objects.get_or_create", side_effect=RuntimeError("db failure"))
    def test_create_step1_seed_auto_add_handles_exception_without_500(self, mocked_get_or_create):
        self.client.login(username="teacher", password="pw123456")
        session = self.client.session
        session["sheetbook_action_seeds"] = {
            "seed-token-2b": {
                "action": "consent",
                "data": {
                    "recipients_text": "김하늘,김하늘 보호자,01012345678\n박나래,박나래 보호자,01099887766",
                },
            }
        }
        session.save()
        before_request_count = SignatureRequest.objects.filter(created_by=self.teacher).count()
        before_document_count = SignatureDocument.objects.filter(created_by=self.teacher).count()

        url = reverse("consent:create_step1")
        file_obj = SimpleUploadedFile("seed-error.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        response = self.client.post(
            url,
            {
                "sheetbook_seed_token": "seed-token-2b",
                "title": "교무수첩 연동 동의서 실패",
                "message": "안내",
                "legal_notice": "",
                "link_expire_days": 14,
                "original_file": file_obj,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "수신자 자동 넣기 중 오류가 발생했습니다.")
        self.assertEqual(SignatureRequest.objects.filter(created_by=self.teacher).count(), before_request_count)
        self.assertEqual(SignatureDocument.objects.filter(created_by=self.teacher).count(), before_document_count)

    def test_create_step1_seed_can_skip_auto_add_recipients(self):
        self.client.login(username="teacher", password="pw123456")
        session = self.client.session
        session["sheetbook_action_seeds"] = {
            "seed-token-3": {
                "action": "consent",
                "data": {
                    "title": "교무수첩 수신자 선택 테스트",
                    "recipients_text": "한지민,한지민 보호자,1111\n윤서준,윤서준 보호자,2222",
                },
            }
        }
        session.save()

        get_response = self.client.get(f"{reverse('consent:create_step1')}?sb_seed=seed-token-3")
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "미리보기")
        self.assertContains(get_response, "다음 단계에 이 수신자 후보 넣기")

        file_obj = SimpleUploadedFile("seed_skip.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        post_response = self.client.post(
            reverse("consent:create_step1"),
            {
                "sheetbook_seed_token": "seed-token-3",
                "apply_seed_recipients": "0",
                "title": "교무수첩 수신자 선택 테스트",
                "message": "안내",
                "legal_notice": "",
                "link_expire_days": 14,
                "original_file": file_obj,
            },
            follow=True,
        )
        self.assertEqual(post_response.status_code, 200)
        self.assertContains(post_response, "교무수첩 수신자 자동 넣기는 꺼두었어요.")

        created_request = SignatureRequest.objects.filter(
            created_by=self.teacher,
            title="교무수첩 수신자 선택 테스트",
        ).latest("created_at")
        self.assertEqual(created_request.recipients.count(), 0)

    @patch("consent.models.SignatureDocument.save", side_effect=DataError("value too long for type character varying(100)"))
    def test_create_step1_handles_path_length_data_error_without_500(self, mocked_save):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:create_step1")
        file_obj = SimpleUploadedFile("sample.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
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
        self.assertContains(response, "파일 경로가 너무 길어 저장할 수 없습니다.")

    @patch("consent.views.SignatureRecipient.objects.get_or_create", side_effect=RuntimeError("db failure"))
    def test_recipients_handles_save_exception_without_500(self, mocked_get_or_create):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            url,
            {
                "recipients_text": "김하늘,김하늘 보호자,5678",
                "recipients_csv": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "수신자 저장 중 오류가 발생했습니다.")

    def test_public_document_missing_file_returns_404_page(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
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

class ConsentRecipientManageTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="manage_teacher", password="pw123456")
        self.teacher.email = "manage_teacher@example.com"
        self.teacher.save(update_fields=["email"])
        self.teacher.userprofile.nickname = "교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])
        seed_current_policy_consent(self.teacher)

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
            student_name="학생A",
            parent_name="학부모A",
            phone_number="",
        )

    def test_update_recipient_changes_fields(self):
        self.client.login(username="manage_teacher", password="pw123456")
        url = reverse("consent:update_recipient", kwargs={"recipient_id": self.recipient.id})
        response = self.client.post(
            url,
            {
                "student_name": "수정학생",
                "parent_name": "수정학부모",
                "phone_number": "010-1234-5678",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.student_name, "수정학생")
        self.assertEqual(self.recipient.parent_name, "수정학부모")
        self.assertEqual(self.recipient.phone_number, "5678")

    def test_update_recipient_defaults_blank_parent_name(self):
        self.client.login(username="manage_teacher", password="pw123456")
        url = reverse("consent:update_recipient", kwargs={"recipient_id": self.recipient.id})
        response = self.client.post(
            url,
            {
                "student_name": "수정학생",
                "parent_name": "",
                "phone_number": "1234",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.parent_name, "수정학생 보호자")
        self.assertEqual(self.recipient.phone_number, "1234")

    def test_update_recipient_blocks_when_signed(self):
        self.recipient.status = SignatureRecipient.STATUS_SIGNED
        self.recipient.save(update_fields=["status"])

        self.client.login(username="manage_teacher", password="pw123456")
        url = reverse("consent:update_recipient", kwargs={"recipient_id": self.recipient.id})
        response = self.client.post(
            url,
            {
                "student_name": "변경시도",
                "parent_name": "변경시도",
                "phone_number": "",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.recipient.refresh_from_db()
        self.assertNotEqual(self.recipient.student_name, "변경시도")

    def test_delete_recipient_removes_pending_recipient(self):
        self.client.login(username="manage_teacher", password="pw123456")
        url = reverse("consent:delete_recipient", kwargs={"recipient_id": self.recipient.id})
        response = self.client.post(url, {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SignatureRecipient.objects.filter(id=self.recipient.id).exists())

class ConsentEvidenceTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="evidence_teacher", password="pw123456")
        self.teacher.email = "evidence_teacher@example.com"
        self.teacher.save(update_fields=["email"])
        self.teacher.userprofile.nickname = "교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])
        seed_current_policy_consent(self.teacher)

        file_obj = SimpleUploadedFile("sample.pdf", b"%PDF-1.4\nproof\n%%EOF", content_type="application/pdf")
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
            document_name_snapshot="sample.pdf",
            document_size_snapshot=17,
            document_sha256_snapshot="abc123",
        )
        self.recipient = SignatureRecipient.objects.create(
            request=self.request_obj,
            student_name="학생A",
            parent_name="학부모A",
            phone_number="",
        )

    def test_sign_page_shows_document_evidence_block(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
        url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SHA-256")
        self.assertContains(response, "abc123")
        self.assertContains(response, "data-consent-document-preview")
        self.assertContains(response, "consent/pdf_preview.js")
        self.assertContains(response, "첨부 문서 미리보기")
        self.assertContains(response, "법적 고지")

    def test_sign_audit_log_contains_document_evidence(self):
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
        url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.post(
            url,
            {
                "decision": "agree",
                "decline_reason": "",
                "signature_data": "data:image/png;base64,AAA",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        log = self.request_obj.audit_logs.filter(event_type="sign_submitted").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.event_meta.get("document_sha256"), "abc123")


    def test_summary_pdf_generation_handles_long_recipient_cards(self):
        try:
            from pypdf import PdfReader
            from reportlab.pdfgen import canvas
        except ModuleNotFoundError:
            self.skipTest("pypdf/reportlab unavailable")

        packet = io.BytesIO()
        c = canvas.Canvas(packet)
        c.drawString(72, 720, "source-document-page")
        c.showPage()
        c.save()
        packet.seek(0)

        document = SignatureDocument.objects.create(
            created_by=self.teacher,
            title="layout-source",
            original_file=SimpleUploadedFile(
                "layout_source.pdf",
                packet.getvalue(),
                content_type="application/pdf",
            ),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        request_obj = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=document,
            title="layout-summary-test",
            consent_text_version="v1",
            document_name_snapshot="layout_source.pdf",
            document_size_snapshot=len(packet.getvalue()),
            document_sha256_snapshot="layoutsha256",
        )
        SignatureRecipient.objects.create(
            request=request_obj,
            student_name="아주긴이름학생" * 4,
            parent_name="매우긴보호자이름" * 4,
            phone_number="010-1111-2222",
            status=SignatureRecipient.STATUS_DECLINED,
            decision=SignatureRecipient.DECISION_DISAGREE,
            decline_reason="비동의 사유가 길게 이어질 때 카드 안에서 줄바꿈과 높이 계산이 안정적으로 동작하는지 확인합니다. " * 5,
            signature_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE/wH+G14J3QAAAABJRU5ErkJggg==",
            signed_at=timezone.now(),
            identity_assurance=SignatureRecipient.IDENTITY_PHONE_LAST4,
            verified_at=timezone.now(),
            verified_ip_address="203.0.113.30",
            ip_address="203.0.113.31",
            user_agent="LayoutAgent/1.0" * 10,
        )

        summary_file = generate_summary_pdf(request_obj)
        pdf_bytes = summary_file.read()
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreaterEqual(len(reader.pages), 2)

    def test_recipient_evidence_pdf_generation_handles_long_text_and_signature(self):
        try:
            from pypdf import PdfReader
            from reportlab.pdfgen import canvas
        except ModuleNotFoundError:
            self.skipTest("pypdf/reportlab unavailable")

        packet = io.BytesIO()
        c = canvas.Canvas(packet)
        c.drawString(72, 720, "recipient-evidence-source")
        c.showPage()
        c.save()
        packet.seek(0)

        document = SignatureDocument.objects.create(
            created_by=self.teacher,
            title="evidence-source",
            original_file=SimpleUploadedFile(
                "evidence_source.pdf",
                packet.getvalue(),
                content_type="application/pdf",
            ),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        request_obj = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=document,
            title="layout-evidence-test",
            consent_text_version="v1",
        )
        recipient = SignatureRecipient.objects.create(
            request=request_obj,
            student_name="학생" * 12,
            parent_name="보호자" * 12,
            phone_number="010-2222-3333",
            status=SignatureRecipient.STATUS_DECLINED,
            decision=SignatureRecipient.DECISION_DISAGREE,
            decline_reason="긴 비동의 사유가 개별 증빙 페이지에서 서명 영역과 겹치지 않는지 확인합니다. " * 6,
            signature_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE/wH+G14J3QAAAABJRU5ErkJggg==",
            signed_at=timezone.now(),
            identity_assurance=SignatureRecipient.IDENTITY_PHONE_LAST4,
            verified_at=timezone.now(),
            verified_ip_address="203.0.113.40",
            ip_address="203.0.113.41",
            user_agent="EvidenceAgent/1.0 " * 20,
        )

        evidence_file = generate_recipient_evidence_pdf(recipient)
        pdf_bytes = evidence_file.read()
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreaterEqual(len(reader.pages), 2)

    def test_recipient_evidence_pdf_limits_source_pdf_to_first_page(self):
        try:
            from pypdf import PdfReader
            from reportlab.pdfgen import canvas
        except ModuleNotFoundError:
            self.skipTest("pypdf/reportlab unavailable")

        packet = io.BytesIO()
        c = canvas.Canvas(packet)
        for label in ("evidence-source-page-1", "evidence-source-page-2"):
            c.drawString(72, 720, label)
            c.showPage()
        c.save()
        packet.seek(0)

        document = SignatureDocument.objects.create(
            created_by=self.teacher,
            title="evidence-preview-source",
            original_file=SimpleUploadedFile(
                "evidence_preview_source.pdf",
                packet.getvalue(),
                content_type="application/pdf",
            ),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        request_obj = SignatureRequest.objects.create(
            created_by=self.teacher,
            document=document,
            title="preview-evidence-test",
            consent_text_version="v1",
        )
        recipient = SignatureRecipient.objects.create(
            request=request_obj,
            student_name="학생A",
            parent_name="보호자A",
            phone_number="010-3333-4444",
            status=SignatureRecipient.STATUS_SIGNED,
            decision=SignatureRecipient.DECISION_AGREE,
            signature_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE/wH+G14J3QAAAABJRU5ErkJggg==",
            signed_at=timezone.now(),
            identity_assurance=SignatureRecipient.IDENTITY_PHONE_LAST4,
            verified_at=timezone.now(),
            verified_ip_address="203.0.113.50",
            ip_address="203.0.113.51",
            user_agent="EvidencePreviewAgent/1.0",
        )

        evidence_file = generate_recipient_evidence_pdf(recipient)
        pdf_bytes = evidence_file.read()
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreaterEqual(len(reader.pages), 2)
        combined_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        self.assertIn("evidence-source-page-1", combined_text)
        self.assertNotIn("evidence-source-page-2", combined_text)


class ConsentRosterTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="roster_teacher", password="pw123456")
        self.teacher.email = "roster_teacher@example.com"
        self.teacher.save(update_fields=["email"])
        self.teacher.userprofile.nickname = "교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])
        seed_current_policy_consent(self.teacher)

        self.other_teacher = User.objects.create_user(username="roster_other_teacher", password="pw123456")
        self.other_teacher.email = "roster_other_teacher@example.com"
        self.other_teacher.save(update_fields=["email"])
        self.other_teacher.userprofile.nickname = "외부교사"
        self.other_teacher.userprofile.role = "school"
        self.other_teacher.userprofile.save(update_fields=["nickname", "role"])
        seed_current_policy_consent(self.other_teacher)

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
            title="shared-roster-req",
            consent_text_version="v1",
        )

        self.roster = ConsentRoster.objects.create(
            owner=self.teacher,
            audience_type=SignatureRequest.AUDIENCE_GUARDIAN,
            name="2학년 학부모 명단",
        )
        ConsentRosterEntry.objects.create(
            roster=self.roster,
            student_name="김하늘",
            parent_name="김하늘 보호자",
            phone_number="5678",
            sort_order=1,
        )
        ConsentRosterEntry.objects.create(
            roster=self.roster,
            student_name="박나래",
            parent_name="박나래 보호자",
            phone_number="1234",
            sort_order=2,
        )

        self.other_roster = ConsentRoster.objects.create(
            owner=self.other_teacher,
            audience_type=SignatureRequest.AUDIENCE_GUARDIAN,
            name="외부 명단",
        )
        ConsentRosterEntry.objects.create(
            roster=self.other_roster,
            student_name="외부학생",
            parent_name="외부학생 보호자",
            phone_number="9999",
            sort_order=1,
        )

    def test_recipients_loads_saved_roster_and_manual_entries_together(self):
        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            url,
            {
                "saved_roster": str(self.roster.id),
                "recipients_text": "최민서,,4321",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.roster_id, self.roster.id)
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=self.request_obj,
                student_name="김하늘",
                parent_name="김하늘 보호자",
                phone_number="5678",
            ).exists()
        )
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=self.request_obj,
                student_name="최민서",
                parent_name="최민서 보호자",
                phone_number="4321",
            ).exists()
        )

    def test_recipients_allows_saved_roster_without_manual_input(self):
        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            url,
            {
                "saved_roster": str(self.roster.id),
                "recipients_text": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.roster_id, self.roster.id)
        self.assertEqual(self.request_obj.recipients.count(), 2)

    def test_recipients_rejects_other_users_saved_roster(self):
        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            url,
            {
                "saved_roster": str(self.other_roster.id),
                "recipients_text": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("saved_roster", response.context["form"].errors)
        self.request_obj.refresh_from_db()
        self.assertIsNone(self.request_obj.roster_id)
        self.assertEqual(self.request_obj.recipients.count(), 0)

    def test_recipients_get_prefills_linked_roster(self):
        self.request_obj.roster = self.roster
        self.request_obj.save(update_fields=["roster"])

        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial.get("saved_roster"), self.roster.id)

    def test_recipients_page_exposes_roster_manage_link_with_return_to(self):
        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        manage_rosters_url = response.context["manage_rosters_url"]
        split_result = urlsplit(manage_rosters_url)
        query = parse_qs(split_result.query)
        self.assertEqual(split_result.path, reverse("consent:rosters"))
        self.assertEqual(query.get("audience_type"), [SignatureRequest.AUDIENCE_GUARDIAN])
        self.assertEqual(query.get("return_to"), [url])

    def test_roster_create_returns_to_recipients_with_saved_roster_prefilled(self):
        self.client.login(username="roster_teacher", password="pw123456")
        return_to = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            reverse("consent:rosters"),
            {
                "audience_type": SignatureRequest.AUDIENCE_GUARDIAN,
                "return_to": return_to,
                "name": "새 학부모 명단",
                "description": "복귀 테스트",
                "entries_text": "최민서,,4321",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], return_to)
        created_roster = ConsentRoster.objects.get(owner=self.teacher, name="새 학부모 명단")
        self.assertEqual(response.context["form"].initial.get("saved_roster"), created_roster.id)
        self.assertEqual(response.context["saved_roster_count"], 2)

    def test_detail_shows_linked_saved_roster_name(self):
        self.request_obj.roster = self.roster
        self.request_obj.save(update_fields=["roster"])

        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "연결된 저장 명단")
        self.assertContains(response, self.roster.name)
