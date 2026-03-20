import io
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from reportlab.pdfgen import canvas

from core.context_processors import search_products
from products.models import ManualSection, Product, ServiceManual
from textbook_ai.models import TextbookDocument


User = get_user_model()


def build_pdf_bytes(texts):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for text in texts:
        pdf.drawString(72, 750, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def build_parser_payload(*, low_text=False):
    paragraph_text = (
        "짧음"
        if low_text
        else (
            "광합성은 식물이 빛을 이용해 양분을 만드는 과정입니다. "
            "빛, 물, 이산화탄소가 함께 작용해 포도당과 산소를 만듭니다. "
            "잎의 구조와 기공, 엽록체 역할을 함께 보면 핵심을 빠르게 파악할 수 있습니다."
        )
    )
    markdown = paragraph_text
    return {
        "json_payload": {
            "file name": "sample.pdf",
            "number of pages": 2,
            "title": "샘플 PDF",
            "kids": [
                {
                    "type": "heading",
                    "page number": 1,
                    "bounding box": [72, 700, 300, 720],
                    "heading level": 1,
                    "content": "1. 광합성",
                },
                {
                    "type": "paragraph",
                    "page number": 1,
                    "bounding box": [72, 620, 520, 680],
                    "content": paragraph_text,
                },
                {
                    "type": "table",
                    "page number": 2,
                    "bounding box": [70, 420, 540, 620],
                    "rows": [
                        {
                            "type": "table row",
                            "cells": [
                                {"type": "paragraph", "page number": 2, "content": "잎"},
                                {"type": "paragraph", "page number": 2, "content": "빛 흡수"},
                            ],
                        }
                    ],
                },
            ],
        },
        "json_text": "{}",
        "markdown_text": markdown,
    }


class TextbookAiViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="pw123456",
        )
        self.user.userprofile.nickname = "테스트교사"
        self.user.userprofile.role = "school"
        self.user.userprofile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def _upload_payload(self, title="과학 PDF"):
        return {
            "title": title,
            "subject": TextbookDocument.Subject.SCIENCE,
            "grade": "5학년 1학기",
            "unit_title": "광합성",
            "license_confirmed": "on",
            "source_pdf": SimpleUploadedFile(
                "science.pdf",
                build_pdf_bytes(["광합성", "기공"]),
                content_type="application/pdf",
            ),
        }

    def test_main_page_renders_teacher_focused_copy(self):
        response = self.client.get(reverse("textbook_ai:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF 분석 도우미")
        self.assertContains(response, "PDF 읽기 시작")

    @patch("textbook_ai.views.parse_document")
    def test_upload_requires_license_checkbox(self, mock_parse_document):
        payload = self._upload_payload()
        payload.pop("license_confirmed")

        response = self.client.post(reverse("textbook_ai:upload"), data=payload)

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "PDF 사용 허가를 확인해 주세요.", status_code=400)
        self.assertFalse(mock_parse_document.called)

    @patch("textbook_ai.views.parse_document")
    def test_duplicate_upload_redirects_existing_document(self, mock_parse_document):
        existing = TextbookDocument.objects.create(
            owner=self.user,
            title="기존 PDF",
            subject=TextbookDocument.Subject.SCIENCE,
            grade="5학년 1학기",
            unit_title="광합성",
            source_pdf=SimpleUploadedFile("science.pdf", build_pdf_bytes(["광합성"]), content_type="application/pdf"),
            original_filename="science.pdf",
            file_sha256="b" * 64,
            file_size_bytes=100,
            page_count=1,
            license_confirmed=True,
            parse_status=TextbookDocument.ParseStatus.READY,
        )

        with patch(
            "textbook_ai.views.inspect_pdf_upload",
            return_value={
                "sha256": "b" * 64,
                "page_count": 2,
                "file_size_bytes": 123,
                "original_filename": "science.pdf",
            },
        ):
            response = self.client.post(reverse("textbook_ai:upload"), data=self._upload_payload())

        self.assertRedirects(response, reverse("textbook_ai:detail", args=[existing.id]))
        self.assertFalse(mock_parse_document.called)
        self.assertEqual(TextbookDocument.objects.count(), 1)

    @patch("textbook_ai.services.convert_pdf_with_opendataloader", return_value=build_parser_payload())
    def test_upload_creates_ready_document_and_chunks(self, mock_parser):
        response = self.client.post(reverse("textbook_ai:upload"), data=self._upload_payload())

        self.assertEqual(response.status_code, 302)
        document = TextbookDocument.objects.get(title="과학 PDF")
        self.assertEqual(document.parse_status, TextbookDocument.ParseStatus.READY)
        self.assertEqual(document.chunks.count(), 2)
        self.assertEqual(document.artifact.table_count, 1)
        self.assertEqual(mock_parser.call_count, 1)

    @patch("textbook_ai.services.convert_pdf_with_opendataloader", return_value=build_parser_payload(low_text=True))
    def test_low_text_parse_marks_document_needs_review(self, mock_parser):
        response = self.client.post(reverse("textbook_ai:upload"), data=self._upload_payload(title="저텍스트 PDF"))

        self.assertEqual(response.status_code, 302)
        document = TextbookDocument.objects.get(title="저텍스트 PDF")
        self.assertEqual(document.parse_status, TextbookDocument.ParseStatus.NEEDS_REVIEW)
        self.assertTrue(document.artifact.summary_json["needs_review"])
        self.assertEqual(mock_parser.call_count, 1)

    @patch("textbook_ai.services.convert_pdf_with_opendataloader", side_effect=RuntimeError("boom"))
    def test_parse_failure_is_shown_on_detail(self, mock_parser):
        response = self.client.post(reverse("textbook_ai:upload"), data=self._upload_payload(title="실패 PDF"))

        self.assertEqual(response.status_code, 302)
        document = TextbookDocument.objects.get(title="실패 PDF")
        self.assertEqual(document.parse_status, TextbookDocument.ParseStatus.FAILED)

        detail = self.client.get(reverse("textbook_ai:detail", args=[document.id]))
        self.assertContains(detail, "실패")

    @patch("textbook_ai.services.convert_pdf_with_opendataloader", return_value=build_parser_payload())
    def test_search_view_shows_page_source_and_pdf_link(self, mock_parser):
        self.client.post(reverse("textbook_ai:upload"), data=self._upload_payload(title="검색 PDF"))
        document = TextbookDocument.objects.get(title="검색 PDF")

        response = self.client.get(reverse("textbook_ai:search", args=[document.id]), {"q": "광합성"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1쪽")
        self.assertContains(response, "원본 보기")
        self.assertContains(response, "광합성")


class TextbookAiEnsureCommandTests(TestCase):
    def test_ensure_command_creates_product_and_manual(self):
        from django.core.management import call_command

        call_command("ensure_textbook_ai")

        product = Product.objects.get(launch_route_name="textbook_ai:main")
        self.assertEqual(product.title, "PDF 분석 도우미")
        manual = ServiceManual.objects.get(product=product)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(ManualSection.objects.filter(manual=manual).count(), 3)

    def test_ensure_command_exposes_product_in_service_launcher(self):
        from django.core.management import call_command

        call_command("ensure_textbook_ai")
        user = User.objects.create_user(
            username="launcher-teacher",
            email="launcher@example.com",
            password="pw123456",
        )
        request = RequestFactory().get("/")
        request.user = user

        payload = json.loads(search_products(request)["service_launcher_json"])

        textbook_ai_item = next(item for item in payload if item["title"] == "PDF 분석 도우미")
        self.assertEqual(textbook_ai_item["href"], reverse("textbook_ai:main"))

    def test_ensure_command_preserves_admin_managed_menu_fields(self):
        from django.core.management import call_command

        product = Product.objects.create(
            title="PDF 분석 도우미",
            lead_text="기존 안내",
            description="기존 설명",
            price=0,
            is_active=True,
            is_featured=False,
            is_guest_allowed=False,
            icon="📘",
            color_theme="blue",
            card_size="small",
            display_order=77,
            service_type="work",
            external_url="",
            launch_route_name="",
            solve_text="",
            result_text="",
            time_text="",
        )

        call_command("ensure_textbook_ai")
        product.refresh_from_db()

        self.assertEqual(product.display_order, 77)
        self.assertEqual(product.color_theme, "blue")
        self.assertEqual(product.launch_route_name, "textbook_ai:main")
        self.assertEqual(product.solve_text, "PDF를 AI가 읽기 좋게 정리하고 싶어요")
