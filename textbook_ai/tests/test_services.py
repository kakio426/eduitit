import io
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from reportlab.pdfgen import canvas

from textbook_ai.models import TextbookDocument
from textbook_ai.services import (
    _ensure_java_runtime_on_path,
    build_scan_review_reason,
    discover_java_bin_dir,
    get_parser_readiness,
    normalize_opendataloader_payload,
    search_document_chunks,
)


User = get_user_model()


def build_pdf_bytes(texts):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for text in texts:
        pdf.drawString(72, 750, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


class TextbookAiServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="textbook-ai-tester",
            email="textbook-ai@example.com",
            password="pw123456",
        )
        self.user.userprofile.nickname = "테스트교사"
        self.user.userprofile.role = "school"
        self.user.userprofile.save(update_fields=["nickname", "role"])

    def test_normalize_payload_builds_headings_tables_and_chunks(self):
        payload = {
            "file name": "sample.pdf",
            "number of pages": 2,
            "title": "광합성",
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
                    "content": (
                        "광합성은 식물이 빛에너지를 이용해 양분을 만드는 과정입니다. "
                        "빛, 물, 이산화탄소가 함께 작용해 포도당과 산소를 만듭니다. "
                        "잎의 기공과 엽록체 역할을 함께 이해하면 단원 구조를 파악하기 쉽습니다."
                    ),
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
        }

        normalized = normalize_opendataloader_payload(payload, "# 광합성")

        self.assertEqual(normalized["page_count"], 2)
        self.assertEqual(normalized["heading_count"], 1)
        self.assertEqual(normalized["table_count"], 1)
        self.assertFalse(normalized["needs_review"])
        self.assertTrue(normalized["chunks"])
        self.assertEqual(normalized["chunks"][0]["heading_path"], "1. 광합성")
        self.assertIn("잎", normalized["summary_json"]["table_previews"][0]["text"])

    def test_scan_like_payload_marks_needs_review(self):
        payload = {
            "file name": "scan.pdf",
            "number of pages": 4,
            "kids": [
                {
                    "type": "image",
                    "page number": 1,
                    "bounding box": [0, 0, 600, 800],
                }
            ],
        }

        normalized = normalize_opendataloader_payload(payload, "")

        self.assertTrue(normalized["needs_review"])
        self.assertIn("스캔본", build_scan_review_reason(page_count=4, text_char_count=0, text_chunk_count=0))

    def test_search_results_include_page_source(self):
        document = TextbookDocument.objects.create(
            owner=self.user,
            title="광합성 PDF",
            subject=TextbookDocument.Subject.SCIENCE,
            source_pdf=SimpleUploadedFile("science.pdf", build_pdf_bytes(["광합성", "기공"]), content_type="application/pdf"),
            original_filename="science.pdf",
            file_sha256="a" * 64,
            file_size_bytes=100,
            page_count=2,
            license_confirmed=True,
            parse_status=TextbookDocument.ParseStatus.READY,
        )
        document.chunks.create(
            chunk_type="text",
            heading_path="1. 광합성",
            text="광합성은 빛을 이용해 양분을 만드는 과정입니다.",
            search_text="1. 광합성 광합성은 빛을 이용해 양분을 만드는 과정입니다.",
            page_from=2,
            page_to=2,
            sort_order=1,
        )

        results = search_document_chunks(document, "광합성")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_label"], "2쪽")

    def test_discover_java_bin_dir_uses_java_home_bin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir) / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            (bin_dir / ("java.exe" if os.name == "nt" else "java")).write_text("", encoding="utf-8")

            with mock.patch("textbook_ai.services.shutil.which", return_value=None):
                with mock.patch.dict(os.environ, {"JAVA_HOME": temp_dir}, clear=False):
                    detected = discover_java_bin_dir()

        self.assertEqual(Path(detected), bin_dir.resolve())

    def test_ensure_java_runtime_on_path_prepends_override_bin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir) / "java-bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            (bin_dir / ("java.exe" if os.name == "nt" else "java")).write_text("", encoding="utf-8")

            with mock.patch("textbook_ai.services.shutil.which", return_value=None):
                with mock.patch.dict(
                    os.environ,
                    {"PATH": "", "TEXTBOOK_AI_JAVA_BIN": str(bin_dir)},
                    clear=False,
                ):
                    detected = _ensure_java_runtime_on_path()
                    path_head = os.environ["PATH"].split(os.pathsep)[0]

        self.assertEqual(Path(detected), bin_dir.resolve())
        self.assertEqual(Path(path_head), bin_dir.resolve())

    def test_parser_readiness_accepts_discovered_java_bin(self):
        fake_java_bin = str(Path("C:/fake-java/bin"))
        with mock.patch("textbook_ai.services.discover_java_bin_dir", return_value=fake_java_bin):
            with mock.patch("textbook_ai.services._ensure_java_runtime_on_path", return_value=fake_java_bin):
                with mock.patch.dict(sys.modules, {"opendataloader_pdf": mock.Mock()}):
                    readiness = get_parser_readiness()

        self.assertTrue(readiness["is_ready"])
        self.assertTrue(readiness["java_available"])
        self.assertEqual(readiness["java_bin_dir"], fake_java_bin)
