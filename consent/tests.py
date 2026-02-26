from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import DataError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from consent.models import SignatureDocument, SignatureRecipient, SignatureRequest
from handoff.models import HandoffRosterGroup, HandoffRosterMember


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
        self.assertRedirects(
            response,
            reverse("consent:sign", kwargs={"token": self.recipient.access_token}),
            fetch_redirect_response=False,
        )

    def test_send_marks_request_as_sent(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, SignatureRequest.STATUS_SENT)
        self.assertIsNotNone(self.request_obj.sent_at)

    def test_send_blocks_when_source_document_missing(self):
        self.document.original_file.name = "signatures/consent/originals/missing-file.pdf"
        self.document.save(update_fields=["original_file"])

        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:send", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "안내문 파일을 찾을 수 없어 발송 링크를 생성할 수 없습니다.")
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, SignatureRequest.STATUS_DRAFT)

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

    def test_sign_link_blocked_before_send_start(self):
        url = reverse("consent:sign", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "아직 발송이 시작되지 않았습니다.", status_code=403)

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

    @patch("django.db.models.fields.files.FieldFile.save", side_effect=RuntimeError("storage down"))
    def test_summary_pdf_download_falls_back_when_storage_save_fails(self, mocked_save):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:download_summary_pdf", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response["Content-Type"])
        self.assertIn("attachment;", response.get("Content-Disposition", ""))

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
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("attachment;", response.get("Content-Disposition", ""))

    def test_public_document_blocked_before_send_start(self):
        url = reverse("consent:public_document", kwargs={"token": self.recipient.access_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "아직 발송이 시작되지 않았습니다.", status_code=403)

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
        self.assertIn("attachment;", response.get("Content-Disposition", ""))

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
        self.request_obj.status = SignatureRequest.STATUS_SENT
        self.request_obj.sent_at = timezone.now()
        self.request_obj.save(update_fields=["status", "sent_at"])
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "안내문+링크 복사")
        self.assertContains(response, "data:image/png;base64,")

    def test_detail_hides_links_before_send_start(self):
        self.client.login(username="teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "제출 링크가 숨김 상태")
        self.assertContains(response, "발송 시작 후 수신자 링크가 표시됩니다.")

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
                "recipients_text": "김하늘,김하늘 보호자",
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
        self.assertEqual(self.recipient.phone_number, "010-1234-5678")

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


class ConsentSharedRosterTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="roster_teacher", password="pw123456")
        self.teacher.email = "roster_teacher@example.com"
        self.teacher.save(update_fields=["email"])
        self.teacher.userprofile.nickname = "교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])

        self.other_teacher = User.objects.create_user(username="roster_other_teacher", password="pw123456")
        self.other_teacher.email = "roster_other_teacher@example.com"
        self.other_teacher.save(update_fields=["email"])
        self.other_teacher.userprofile.nickname = "외부교사"
        self.other_teacher.userprofile.role = "school"
        self.other_teacher.userprofile.save(update_fields=["nickname", "role"])

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

        self.group = HandoffRosterGroup.objects.create(owner=self.teacher, name="2학년 담임")
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="김하늘",
            sort_order=1,
            is_active=True,
        )
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="박나래",
            sort_order=2,
            is_active=True,
        )
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="비활성",
            sort_order=3,
            is_active=False,
        )
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="",
            sort_order=4,
            is_active=True,
        )

        self.other_group = HandoffRosterGroup.objects.create(owner=self.other_teacher, name="외부 명단")
        HandoffRosterMember.objects.create(
            group=self.other_group,
            display_name="외부학생",
            sort_order=1,
            is_active=True,
        )

    def test_recipients_imports_from_shared_roster_and_links_request(self):
        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            url,
            {
                "shared_roster_group": str(self.group.id),
                "recipients_text": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.shared_roster_group_id, self.group.id)
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=self.request_obj,
                student_name="김하늘",
                parent_name="김하늘 보호자",
            ).exists()
        )
        self.assertTrue(
            SignatureRecipient.objects.filter(
                request=self.request_obj,
                student_name="박나래",
                parent_name="박나래 보호자",
            ).exists()
        )
        self.assertFalse(
            SignatureRecipient.objects.filter(
                request=self.request_obj,
                student_name="비활성",
            ).exists()
        )

    def test_recipients_rejects_other_users_shared_roster_group(self):
        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.post(
            url,
            {
                "shared_roster_group": str(self.other_group.id),
                "recipients_text": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("shared_roster_group", response.context["form"].errors)
        self.request_obj.refresh_from_db()
        self.assertIsNone(self.request_obj.shared_roster_group_id)
        self.assertEqual(self.request_obj.recipients.count(), 0)

    def test_recipients_get_prefills_linked_shared_roster(self):
        self.request_obj.shared_roster_group = self.group
        self.request_obj.save(update_fields=["shared_roster_group"])

        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:recipients", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial.get("shared_roster_group"), self.group.id)

    def test_detail_shows_linked_shared_roster_name(self):
        self.request_obj.shared_roster_group = self.group
        self.request_obj.save(update_fields=["shared_roster_group"])

        self.client.login(username="roster_teacher", password="pw123456")
        url = reverse("consent:detail", kwargs={"request_id": self.request_obj.request_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "연결된 공유 명단")
        self.assertContains(response, self.group.name)
