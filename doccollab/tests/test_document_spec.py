from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from django.test import SimpleTestCase

from doccollab.doc_hwp_builder import build_document_hwpx_bytes
from doccollab.document_spec import (
    DOCUMENT_SCHEMA_VERSION,
    normalize_document_spec,
    validate_document_spec,
)


class DocumentSpecTests(SimpleTestCase):
    def test_legacy_payload_becomes_school_document_spec(self):
        payload = {
            "title": "체험학습 안내문",
            "subtitle": "학부모 안내",
            "meta_lines": ["대상: 3학년", "일시: 2026.05.10"],
            "body_blocks": [
                {
                    "heading": "안내",
                    "paragraphs": ["5월 체험학습 운영 내용을 안내드립니다."],
                    "bullets": ["편한 복장", "개인 물통"],
                }
            ],
            "closing": "감사합니다.",
        }

        spec = normalize_document_spec(
            payload,
            document_type="home_letter",
            prompt="체험학습 안내 가정통신문을 작성해 주세요.",
            selected_blocks=[],
        )

        self.assertEqual(spec["schema_version"], DOCUMENT_SCHEMA_VERSION)
        self.assertEqual(spec["document_type"], "home_letter")
        self.assertIn("signature", spec["selected_blocks"])
        self.assertIn("meta_table", [block["type"] for block in spec["blocks"]])
        self.assertIn("bullet_list", [block["type"] for block in spec["blocks"]])
        self.assertEqual(validate_document_spec(spec), [])

    def test_unknown_blocks_and_wide_empty_tables_are_normalized(self):
        payload = {
            "schema_version": DOCUMENT_SCHEMA_VERSION,
            "title": "회의록",
            "blocks": [
                {"type": "unknown", "text": "제거"},
                {
                    "type": "decision_table",
                    "title": "결정",
                    "headers": ["안건", "결정", "담당", "기한", "비고", "초과"],
                    "rows": [],
                },
            ],
        }

        spec = normalize_document_spec(
            payload,
            document_type="minutes",
            prompt="체험학습 협의 회의록을 작성해 주세요.",
            selected_blocks=["signature"],
        )
        decision = next(block for block in spec["blocks"] if block["type"] == "decision_table")

        self.assertNotIn("unknown", [block["type"] for block in spec["blocks"]])
        self.assertLessEqual(len(decision["headers"]), 5)
        self.assertTrue(decision["rows"])
        self.assertEqual(validate_document_spec(spec), [])

    def test_build_document_hwpx_with_table_callout_and_signature(self):
        spec = normalize_document_spec(
            {
                "schema_version": DOCUMENT_SCHEMA_VERSION,
                "document_type": "notice",
                "title": "체험학습 안내",
                "subtitle": "학부모 안내",
                "summary_text": "체험학습 일정과 준비물 안내",
                "blocks": [
                    {"type": "masthead", "school_name": "○○초등학교", "contact": "교무실 000-0000-0000"},
                    {"type": "title", "text": "체험학습 안내", "subtitle": "학부모 안내"},
                    {
                        "type": "meta_table",
                        "title": "문서 정보",
                        "headers": ["항목", "내용"],
                        "rows": [["대상", "3학년"], ["일시", "2026.05.10"]],
                    },
                    {"type": "paragraph", "title": "안내", "text": "체험학습 운영 내용을 안내드립니다."},
                    {
                        "type": "info_table",
                        "title": "준비",
                        "headers": ["항목", "내용"],
                        "rows": [["준비물", "물통"], ["복장", "편한 복장"]],
                    },
                    {"type": "callout_box", "title": "문의", "text": "담임 선생님께 문의해 주세요."},
                    {"type": "signature_box", "date": "2026.05.02", "signer": "○○초등학교장"},
                ],
            },
            document_type="notice",
            prompt="체험학습 안내문",
            selected_blocks=["contact", "signature"],
        )

        result = build_document_hwpx_bytes(content=spec)

        self.assertGreaterEqual(result["page_count"], 1)
        self.assertTrue(result["file_name"].endswith(".hwpx"))
        self.assertTrue(result["hwpx_bytes"].startswith(b"PK"))
        with ZipFile(BytesIO(result["hwpx_bytes"])) as archive:
            section_xml = archive.read("Contents/section0.xml").decode("utf-8", errors="ignore")
            ET.fromstring(archive.read("Contents/header.xml"))
            ET.fromstring(section_xml)
        self.assertIn("<hp:tbl", section_xml)
        self.assertIn("준비물", section_xml)
        self.assertIn("물통", section_xml)
