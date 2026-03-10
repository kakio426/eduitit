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
                "source_type": "pdf",
                "content": "교사용 메모",
                "pdf_file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        return TextbookMaterial.objects.get(title="지층과 화석 PDF")

    def _create_html_material(self):
        response = self.client.post(
            reverse("textbooks:create"),
            {
                "subject": "SCIENCE",
                "grade": "5학년 1학기",
                "unit_title": "태양계 탐험",
                "title": "태양계 HTML 자료",
                "source_type": "html",
                "content": "<!doctype html><html><body><button>시작</button></body></html>",
            },
        )
        self.assertEqual(response.status_code, 302)
        return TextbookMaterial.objects.get(title="태양계 HTML 자료")

    def _create_markdown_material(self):
        response = self.client.post(
            reverse("textbooks:create"),
            {
                "subject": "KOREAN",
                "grade": "4학년 2학기",
                "unit_title": "이야기 읽기",
                "title": "국어 텍스트 자료",
                "source_type": "markdown",
                "content": "첫째 문단\n둘째 문단",
            },
        )
        self.assertEqual(response.status_code, 302)
        return TextbookMaterial.objects.get(title="국어 텍스트 자료")

    def test_create_pdf_material_stores_metadata(self):
        material = self._create_pdf_material()
        self.assertEqual(material.source_type, TextbookMaterial.SOURCE_PDF)
        self.assertEqual(material.page_count, 2)
        self.assertTrue(material.pdf_sha256)
        self.assertEqual(material.original_filename, "science.pdf")

    def test_create_html_material_persists_source_type_and_content(self):
        material = self._create_html_material()
        self.assertEqual(material.source_type, TextbookMaterial.SOURCE_HTML)
        self.assertIn("<button>시작</button>", material.content)
        self.assertEqual(material.page_count, 0)

    def test_create_html_material_requires_content(self):
        response = self.client.post(
            reverse("textbooks:create"),
            {
                "subject": "SCIENCE",
                "grade": "5학년 1학기",
                "unit_title": "태양계 탐험",
                "title": "빈 HTML 자료",
                "source_type": "html",
                "content": "   ",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TextbookMaterial.objects.filter(title="빈 HTML 자료").exists())

    def test_create_markdown_material_is_still_supported(self):
        material = self._create_markdown_material()
        self.assertEqual(material.source_type, TextbookMaterial.SOURCE_MARKDOWN)
        self.assertEqual(material.page_count, 0)

    def test_non_pdf_upload_is_rejected(self):
        upload = SimpleUploadedFile("lesson.html", b"<html></html>", content_type="text/html")
        response = self.client.post(
            reverse("textbooks:create"),
            {
                "subject": "SCIENCE",
                "grade": "5학년 1학기",
                "unit_title": "지층과 화석",
                "title": "잘못된 업로드",
                "source_type": "pdf",
                "pdf_file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TextbookMaterial.objects.filter(title="잘못된 업로드").exists())

    def test_main_view_lists_html_pdf_and_markdown_materials(self):
        html_material = self._create_html_material()
        pdf_material = self._create_pdf_material()
        markdown_material = self._create_markdown_material()

        response = self.client.get(reverse("textbooks:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, html_material.title)
        self.assertContains(response, pdf_material.title)
        self.assertContains(response, markdown_material.title)
        self.assertContains(response, "Sandbox Preview")

    def test_html_detail_view_uses_preview_shell(self):
        material = self._create_html_material()

        response = self.client.get(reverse("textbooks:detail", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sandbox Preview")
        self.assertContains(response, "textbooks-preview-html-json")
        self.assertContains(response, "allow-scripts allow-forms allow-downloads")

    def test_html_preview_window_is_teacher_only(self):
        material = self._create_html_material()
        other = User.objects.create_user(username="other", email="other@example.com", password="pw123456")
        other_client = Client()
        other_client.force_login(other)

        response = other_client.get(reverse("textbooks:html_preview_window", args=[material.id]))

        self.assertIn(response.status_code, [302, 404])

    def test_html_preview_window_renders_saved_material(self):
        material = self._create_html_material()

        response = self.client.get(reverse("textbooks:html_preview_window", args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "새 창 미리보기")
        self.assertContains(response, "textbooks-preview-window-json")

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

    def test_detail_view_renders_embedded_join_qr_for_pdf(self):
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
