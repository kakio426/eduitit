from datetime import datetime

from django.test import SimpleTestCase
from django.utils import timezone

from classcalendar.message_capture import parse_message_capture_draft


class MessageCaptureParserTests(SimpleTestCase):
    def test_parse_with_absolute_date_and_range_time(self):
        now = timezone.make_aware(datetime(2026, 3, 4, 9, 0))
        result = parse_message_capture_draft(
            "과학 실험 안내\n2026-03-15 14:00-15:20 과학실 수업\n준비물: 실험 노트",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["parse_status"], "parsed")
        self.assertEqual(result["confidence_label"], "high")
        self.assertEqual(result["extracted_title"], "과학 실험 안내")
        self.assertEqual(result["extracted_start_time"].date().isoformat(), "2026-03-15")
        self.assertEqual(result["extracted_start_time"].hour, 14)
        self.assertEqual(result["extracted_end_time"].hour, 15)

    def test_parse_marks_needs_review_when_date_missing(self):
        result = parse_message_capture_draft(
            "준비물 공지\n실험 노트와 필기구 챙기기",
            has_files=False,
        )

        self.assertEqual(result["parse_status"], "needs_review")
        self.assertEqual(result["confidence_label"], "low")
        self.assertTrue(any("날짜" in warning for warning in result["warnings"]))

    def test_parse_relative_date_and_single_time(self):
        now = timezone.make_aware(datetime(2026, 3, 4, 9, 0))
        result = parse_message_capture_draft(
            "학부모 상담\n내일 오후 3시 상담실 방문",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["parse_status"], "needs_review")
        self.assertEqual(result["extracted_start_time"].date().isoformat(), "2026-03-05")
        self.assertEqual(result["extracted_start_time"].hour, 15)

    def test_parse_failed_when_text_and_files_are_empty(self):
        result = parse_message_capture_draft("", has_files=False)

        self.assertEqual(result["parse_status"], "failed")
        self.assertEqual(result["confidence_label"], "low")
