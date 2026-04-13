from __future__ import annotations

import io
import tempfile
import unittest
import base64

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from docsign.models import DocumentSignJob


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
