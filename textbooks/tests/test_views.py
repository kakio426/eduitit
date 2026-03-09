import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from reportlab.pdfgen import canvas

from happy_seed.models import HSClassroom
from textbooks.models import TextbookLiveSession, TextbookMaterial
from textbooks.services import ACCESS_COOKIE_NAME


User = get_user_model()


def build_pdf_bytes(pages=2):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for page in range(pages):
        pdf.drawString(120, 750, f"page {page + 1}")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


class TextbookViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="pw123456",
        )
        self.user.userprofile.nickname = "테스트교사"
        self.user.userprofile.save(update_fields=["nickname"])
        self.client = Client()
        self.client.force_login(self.user)
        self.classroom = HSClassroom.objects.create(teacher=self.user, name="5학년 2반")
        session = self.client.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

    def _create_pdf_material(self):
        upload = SimpleUploadedFile("science.pdf", build_pdf_bytes(), content_type="application/pdf")
        response = self.client.post(
            reverse("textbooks:create"),
            {
                "subject": "SCIENCE",
                "grade": "5학년 1학기",
                "unit_title": "지층과 화석",
                "title": "지층과 화석 PDF",
                "content": "교사용 메모",
                "pdf_file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        return TextbookMaterial.objects.get(title="지층과 화석 PDF")

    def test_create_pdf_material_stores_metadata(self):
        material = self._create_pdf_material()
        self.assertEqual(material.source_type, TextbookMaterial.SOURCE_PDF)
        self.assertEqual(material.page_count, 2)
        self.assertTrue(material.pdf_sha256)
        self.assertEqual(material.original_filename, "science.pdf")

    def test_non_pdf_upload_is_rejected(self):
        upload = SimpleUploadedFile("lesson.html", b"<html></html>", content_type="text/html")
        response = self.client.post(
            reverse("textbooks:create"),
            {
                "subject": "SCIENCE",
                "grade": "5학년 1학기",
                "unit_title": "지층과 화석",
                "title": "잘못된 업로드",
                "pdf_file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TextbookMaterial.objects.filter(title="잘못된 업로드").exists())

    def test_main_view_hides_non_pdf_legacy_material(self):
        TextbookMaterial.objects.create(
            teacher=self.user,
            subject="SCIENCE",
            grade="5학년 1학기",
            unit_title="텍스트 수업",
            title="숨겨져야 할 텍스트 자료",
            source_type=TextbookMaterial.SOURCE_MARKDOWN,
            content="# markdown",
        )
        material = self._create_pdf_material()

        response = self.client.get(reverse("textbooks:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, material.title)
        self.assertNotContains(response, "숨겨져야 할 텍스트 자료")

    def test_start_live_session_uses_active_classroom_and_publishes_material(self):
        material = self._create_pdf_material()
        response = self.client.post(reverse("textbooks:start_live", args=[material.id]))
        self.assertEqual(response.status_code, 302)
        session = TextbookLiveSession.objects.get(material=material)
        self.assertEqual(session.classroom_id, self.classroom.id)
        self.assertEqual(session.status, TextbookLiveSession.STATUS_LIVE)
        material.refresh_from_db()
        self.assertTrue(material.is_published)

    def test_join_verify_sets_cookie_and_bootstrap_allows_student(self):
        material = self._create_pdf_material()
        session = TextbookLiveSession.objects.create(
            material=material,
            teacher=self.user,
            classroom=self.classroom,
            status=TextbookLiveSession.STATUS_LIVE,
            join_code="123456",
            current_page=1,
            zoom_scale=1.0,
            viewport_json={},
        )
        anon = Client()
        response = anon.post(
            reverse("textbooks:verify_join", args=[session.id]),
            {"join_code": "123456", "display_name": "학생1"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(ACCESS_COOKIE_NAME, response.cookies)
        anon.cookies[ACCESS_COOKIE_NAME] = response.cookies[ACCESS_COOKIE_NAME].value
        bootstrap = anon.get(reverse("textbooks:bootstrap_session", args=[session.id]) + "?role=student")
        self.assertEqual(bootstrap.status_code, 200)
        self.assertEqual(bootstrap.json()["viewer_role"], "student")

    def test_pdf_requires_live_access_cookie_for_anonymous(self):
        material = self._create_pdf_material()
        session = TextbookLiveSession.objects.create(
            material=material,
            teacher=self.user,
            classroom=self.classroom,
            status=TextbookLiveSession.STATUS_LIVE,
            join_code="654321",
            current_page=1,
            zoom_scale=1.0,
            viewport_json={},
        )
        anon = Client()
        denied = anon.get(reverse("textbooks:material_pdf", args=[material.id]) + f"?session={session.id}")
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.get(reverse("textbooks:material_pdf", args=[material.id]) + f"?session={session.id}")
        self.assertEqual(allowed.status_code, 200)

    def test_detail_view_renders_embedded_join_qr(self):
        material = self._create_pdf_material()
        session = TextbookLiveSession.objects.create(
            material=material,
            teacher=self.user,
            classroom=self.classroom,
            status=TextbookLiveSession.STATUS_LIVE,
            join_code="777777",
            current_page=1,
            zoom_scale=1.0,
            viewport_json={},
        )
        response = self.client.get(reverse("textbooks:detail", args=[material.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data:image/png;base64,")
        self.assertContains(response, str(session.id))
