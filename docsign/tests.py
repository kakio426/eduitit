from __future__ import annotations

import io
import tempfile
import unittest
import base64
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import OperationalError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from docsign.models import DocumentSignJob
from docsign.services import build_signed_storage_name


def build_test_pdf_bytes(label: str = "docsign-source", *, page_size=(612, 792)) -> bytes:
    try:
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest("reportlab unavailable") from exc

    packet = io.BytesIO()
    pdf = canvas.Canvas(packet, pagesize=page_size)
    pdf.drawString(72, page_size[1] - 80, label)
    pdf.showPage()
    pdf.save()
    packet.seek(0)
    return packet.getvalue()


def build_signature_data_url() -> str:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest("Pillow unavailable") from exc

    image = Image.new("RGBA", (48, 24), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line((4, 18, 16, 8, 28, 16, 42, 6), fill=(15, 23, 42, 255), width=3)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def build_rotated_pdf_bytes(label: str = "rotated-doc", *, page_size=(400, 200), rotation: int = 90) -> bytes:
    try:
        from pypdf import PdfReader, PdfWriter
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest("pypdf unavailable") from exc

    reader = PdfReader(io.BytesIO(build_test_pdf_bytes(label, page_size=page_size)))
    writer = PdfWriter()
    page = reader.pages[0]
    page.rotate(rotation)
    writer.add_page(page)
    payload = io.BytesIO()
    writer.write(payload)
    return payload.getvalue()


def seed_current_policy_consent(user):
    return UserPolicyConsent.objects.create(
        user=user,
        provider="direct",
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        agreed_at=timezone.now(),
        agreement_source="required_gate",
    )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="docsign-tests-"))
class DocumentSignFlowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="pw123456")
        self.other = User.objects.create_user(username="other", password="pw123456")
        for index, user in enumerate((self.teacher, self.other), start=1):
            user.email = f"user{index}@example.com"
            user.save(update_fields=["email"])
            user.userprofile.nickname = f"교사{index}"
            user.userprofile.role = "school"
            user.userprofile.save(update_fields=["nickname", "role"])
            seed_current_policy_consent(user)

    def test_upload_creates_job(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("docsign:create"),
            {
                "title": "가정통신문",
                "source_file": SimpleUploadedFile(
                    "sample.pdf",
                    build_test_pdf_bytes("upload-check"),
                    content_type="application/pdf",
                ),
            },
        )

        job = DocumentSignJob.objects.get(owner=self.teacher)
        self.assertRedirects(response, reverse("docsign:position", kwargs={"job_id": job.id}))
        self.assertEqual(job.title, "가정통신문")
        self.assertEqual(job.file_type, "pdf")
        self.assertEqual(job.source_file_name_snapshot, "sample.pdf")
        self.assertTrue(job.source_file_sha256_snapshot)

    def test_non_pdf_upload_fails(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("docsign:create"),
            {
                "title": "이미지",
                "source_file": SimpleUploadedFile(
                    "sample.png",
                    b"not-pdf",
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF만 올릴 수 있습니다.")
        self.assertFalse(DocumentSignJob.objects.exists())

    def test_position_and_sign_generates_signed_pdf(self):
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError:
            self.skipTest("pypdf unavailable")

        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="사인 테스트",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes(page_size=(400, 400)),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="source.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
        )

        position_response = self.client.post(
            reverse("docsign:position", kwargs={"job_id": job.id}),
            {
                "position_json": '{"page":1,"x_ratio":0.5,"y_ratio":0.1,"w_ratio":0.3,"h_ratio":0.12}',
            },
        )
        self.assertRedirects(position_response, reverse("docsign:sign", kwargs={"job_id": job.id}))

        sign_response = self.client.post(
            reverse("docsign:sign", kwargs={"job_id": job.id}),
            {"signature_data": build_signature_data_url()},
        )

        self.assertRedirects(sign_response, f'{reverse("docsign:detail", kwargs={"job_id": job.id})}?download=1')
        job.refresh_from_db()
        self.assertTrue(job.is_signed)
        self.assertIsNotNone(job.signed_at)

        with job.signed_pdf.open("rb") as handle:
            reader = PdfReader(handle)
            self.assertEqual(len(reader.pages), 1)
            raw_stream = reader.pages[0].get_contents().get_data().decode("latin-1", errors="ignore")
        self.assertRegex(raw_stream, r"204(?:\.0+)? 44(?:\.0+)? 112(?:\.0+)? 40(?:\.0+)? re")
        self.assertRegex(raw_stream, r"80(?:\.0+)? 0 0 40(?:\.0+)? 220(?:\.0+)? 44(?:\.0+)? cm")

    def test_position_step_can_store_checkmark_mode(self):
        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="체크 위치",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes(page_size=(400, 400)),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="source.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
        )

        response = self.client.post(
            reverse("docsign:position", kwargs={"job_id": job.id}),
            {
                "position_json": '{"page":1,"x_ratio":0.4,"y_ratio":0.2,"w_ratio":0.2,"h_ratio":0.2,"mark_type":"checkmark"}',
            },
        )

        self.assertRedirects(response, reverse("docsign:sign", kwargs={"job_id": job.id}))
        job.refresh_from_db()
        self.assertEqual(job.mark_type, DocumentSignJob.MARK_TYPE_CHECKMARK)
        self.assertEqual(job.signature_page, 1)
        self.assertEqual(job.x, 160)
        self.assertEqual(job.y, 80)
        self.assertEqual(job.width, 80)
        self.assertEqual(job.height, 80)

    def test_checkmark_sign_generates_dark_overlay_at_expected_position(self):
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError:
            self.skipTest("pypdf unavailable")

        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="체크 테스트",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes(page_size=(400, 400)),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="source.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
            mark_type=DocumentSignJob.MARK_TYPE_CHECKMARK,
            signature_page=1,
            x=160,
            y=80,
            width=80,
            height=80,
        )

        response = self.client.post(
            reverse("docsign:sign", kwargs={"job_id": job.id}),
            {"signature_data": ""},
        )

        self.assertRedirects(response, f'{reverse("docsign:detail", kwargs={"job_id": job.id})}?download=1')
        job.refresh_from_db()
        self.assertTrue(job.is_signed)

        with job.signed_pdf.open("rb") as handle:
            reader = PdfReader(handle)
            raw_stream = reader.pages[0].get_contents().get_data().decode("latin-1", errors="ignore")

        self.assertRegex(raw_stream, r"0 0 0 RG")
        self.assertRegex(raw_stream, r"10(?:\.0+)? w")
        self.assertRegex(
            raw_stream,
            r"180(?:\.0+)? 116(?:\.0+)? m\s+196(?:\.0+)? 96(?:\.0+)? l\s+224(?:\.0+)? 140(?:\.0+)? l",
        )

    def test_checkmark_sign_page_uses_preview_instead_of_canvas(self):
        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="체크 미리보기",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes(page_size=(400, 400)),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="source.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
            mark_type=DocumentSignJob.MARK_TYPE_CHECKMARK,
            signature_page=1,
            x=160,
            y=80,
            width=80,
            height=80,
        )

        response = self.client.get(reverse("docsign:sign", kwargs={"job_id": job.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "진한 체크")
        self.assertContains(response, "문서 위에 진하게 올립니다.")
        self.assertNotContains(response, 'id="signaturePad"', html=False)

    def test_only_owner_can_access_job(self):
        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="비공개 문서",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes("private-doc"),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="source.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
        )

        self.client.force_login(self.other)
        response = self.client.get(reverse("docsign:detail", kwargs={"job_id": job.id}))
        self.assertEqual(response.status_code, 404)

    def test_list_shows_only_my_jobs(self):
        own_job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="내 문서",
            source_file=SimpleUploadedFile("my.pdf", build_test_pdf_bytes("my-doc"), content_type="application/pdf"),
            source_file_name_snapshot="my.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="a",
            file_type="pdf",
        )
        DocumentSignJob.objects.create(
            owner=self.other,
            title="다른 문서",
            source_file=SimpleUploadedFile("other.pdf", build_test_pdf_bytes("other-doc"), content_type="application/pdf"),
            source_file_name_snapshot="other.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="b",
            file_type="pdf",
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("docsign:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_job.title)
        self.assertNotContains(response, "다른 문서")

    def test_list_returns_503_when_schema_not_ready(self):
        self.client.force_login(self.teacher)

        with patch(
            "docsign.views.DocumentSignJob.objects.filter",
            side_effect=OperationalError("no such table: docsign_documentsignjob"),
        ):
            response = self.client.get(reverse("docsign:list"))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "잠시만요", status_code=503)

    def test_source_document_uses_pdf_helper_for_response(self):
        self.client.force_login(self.teacher)
        helper_payload = build_test_pdf_bytes("from-helper")
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="기존 문서",
            source_file=SimpleUploadedFile(
                "source.pdf",
                helper_payload,
                content_type="application/pdf",
            ),
            source_file_name_snapshot="기존문서.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
        )

        response = self.client.get(reverse("docsign:source_document", kwargs={"job_id": job.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline;", response["Content-Disposition"])
        self.assertEqual(response.content, helper_payload)

    def test_signed_storage_name_is_ascii_only(self):
        job = DocumentSignJob(
            id=17,
            owner=self.teacher,
            title="한글 제목",
            source_file_name_snapshot="학교 안내문.pdf",
            source_file_sha256_snapshot="abc123",
        )

        filename = build_signed_storage_name(job)

        self.assertEqual(filename, "docsign-signed-17-6367c48dd193d56e.pdf")
        self.assertRegex(filename, r"^[A-Za-z0-9._-]+$")

    @patch("docsign.views.get_file_field_bytes", return_value=b"%PDF-1.4 signed-helper")
    def test_download_signed_uses_file_bytes_helper_for_response(self, file_bytes_mock):
        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="완료 문서",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes("download-doc"),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="완료문서.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
            signed_pdf="docsign/signed/missing-cloudinary-id",
            signed_at=timezone.now(),
        )

        response = self.client.get(reverse("docsign:download", kwargs={"job_id": job.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-1.4 signed-helper")
        file_bytes_mock.assert_called_once_with(
            job.signed_pdf,
            file_type="pdf",
            filename_hint="완료문서-signed.pdf",
        )

    def test_detail_uses_signed_preview_url_after_completion(self):
        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="완료 문서",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes("detail-doc"),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="완료문서.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
            signed_pdf="docsign/signed/ready.pdf",
            signed_at=timezone.now(),
        )

        response = self.client.get(reverse("docsign:detail", kwargs={"job_id": job.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("docsign:signed_document", kwargs={"job_id": job.id}))
        self.assertNotContains(response, reverse("docsign:source_document", kwargs={"job_id": job.id}))

    @patch("docsign.views.get_file_field_bytes", return_value=b"%PDF-1.4 signed-preview")
    def test_signed_document_uses_signed_pdf_bytes_for_inline_preview(self, file_bytes_mock):
        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="완료 문서",
            source_file=SimpleUploadedFile(
                "source.pdf",
                build_test_pdf_bytes("preview-doc"),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="완료문서.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
            signed_pdf="docsign/signed/ready.pdf",
            signed_at=timezone.now(),
        )

        response = self.client.get(reverse("docsign:signed_document", kwargs={"job_id": job.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline;", response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-1.4 signed-preview")
        file_bytes_mock.assert_called_once_with(
            job.signed_pdf,
            file_type="pdf",
            filename_hint="완료문서-signed.pdf",
        )

    def test_source_document_flattens_rotated_pdf_for_preview_alignment(self):
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError:
            self.skipTest("pypdf unavailable")

        self.client.force_login(self.teacher)
        job = DocumentSignJob.objects.create(
            owner=self.teacher,
            title="회전 문서",
            source_file=SimpleUploadedFile(
                "rotated.pdf",
                build_rotated_pdf_bytes(),
                content_type="application/pdf",
            ),
            source_file_name_snapshot="rotated.pdf",
            source_file_size_snapshot=0,
            source_file_sha256_snapshot="abc",
            file_type="pdf",
        )

        response = self.client.get(reverse("docsign:source_document", kwargs={"job_id": job.id}))

        self.assertEqual(response.status_code, 200)
        reader = PdfReader(io.BytesIO(response.content))
        page = reader.pages[0]
        self.assertEqual(int(getattr(page, "rotation", 0) or 0) % 360, 0)
        self.assertEqual(round(float(page.mediabox.width)), 200)
        self.assertEqual(round(float(page.mediabox.height)), 400)
