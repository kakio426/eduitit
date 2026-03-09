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
        self.assertEqual(result["predicted_item_type"], "event")
        self.assertEqual(result["extracted_title"], "과학 실험 안내")
        self.assertEqual(result["extracted_start_time"].date().isoformat(), "2026-03-15")
        self.assertEqual(result["extracted_start_time"].hour, 14)
        self.assertEqual(result["extracted_end_time"].hour, 15)
        self.assertEqual(result["location"], "과학실")
        self.assertEqual(result["materials"], "실험 노트")
        self.assertEqual(result["category"], "class")

    def test_parse_marks_task_for_deadline_message(self):
        now = timezone.make_aware(datetime(2026, 3, 4, 9, 0))
        result = parse_message_capture_draft(
            "2026-03-14까지 보고서 제출\n확인 후 출력본 제출",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["predicted_item_type"], "task")
        self.assertTrue(result["deadline_only"])
        self.assertEqual(result["parse_status"], "parsed")
        self.assertIsNotNone(result["task_due_at"])
        self.assertEqual(result["task_due_at"].date().isoformat(), "2026-03-14")

    def test_parse_marks_ignore_for_notice_message(self):
        now = timezone.make_aware(datetime(2026, 3, 4, 9, 0))
        result = parse_message_capture_draft(
            "학급 안내\n급식 시간은 추후 공지 예정입니다.",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["predicted_item_type"], "ignore")
        self.assertEqual(result["parse_status"], "needs_review")
        self.assertTrue(any("안내성" in warning for warning in result["warnings"]))

    def test_parse_relative_date_and_single_time(self):
        now = timezone.make_aware(datetime(2026, 3, 4, 9, 0))
        result = parse_message_capture_draft(
            "학부모 상담\n내일 오후 3시 상담실 방문",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["parse_status"], "needs_review")
        self.assertEqual(result["predicted_item_type"], "event")
        self.assertEqual(result["extracted_start_time"].date().isoformat(), "2026-03-05")
        self.assertEqual(result["extracted_start_time"].hour, 15)
        self.assertEqual(result["location"], "상담실")

    def test_parse_failed_when_text_and_files_are_empty(self):
        result = parse_message_capture_draft("", has_files=False)

        self.assertEqual(result["parse_status"], "failed")
        self.assertEqual(result["confidence_label"], "low")
