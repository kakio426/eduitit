from datetime import datetime

from django.test import SimpleTestCase
from django.utils import timezone

from classcalendar.message_capture import parse_message_capture_draft


class MessageCaptureParserTests(SimpleTestCase):
    def test_parse_date_only_event_as_all_day_candidate(self):
        now = timezone.make_aware(datetime(2026, 3, 10, 9, 0))
        result = parse_message_capture_draft(
            "3월 19일 학부모총회 실시",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["parse_status"], "parsed")
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["kind"], "event")
        self.assertEqual(candidate["title"], "학부모총회")
        self.assertTrue(candidate["is_all_day"])
        self.assertEqual(candidate["start_time"].date().isoformat(), "2026-03-19")
        self.assertFalse(any("시간" in warning for warning in result["warnings"]))

    def test_parse_mixed_message_returns_deadline_and_event_candidates(self):
        now = timezone.make_aware(datetime(2026, 3, 10, 9, 0))
        result = parse_message_capture_draft(
            "선생님 안녕하세요.\n"
            "3월 19일(목)에 학부모총회가 실시됩니다.\n"
            "이에 학부모를 대상으로 하는 연수물을 작성하여 이알리미로 안내하고자 합니다.\n"
            "작년 연수물 파일에 담당자를 지정해두었으니 수정해주시면 됩니다.\n"
            "12일(목)까지 부탁드릴게요.",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["parse_status"], "parsed")
        self.assertEqual(result["predicted_item_type"], "task")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["candidates"][0]["kind"], "deadline")
        self.assertEqual(result["candidates"][0]["start_time"].date().isoformat(), "2026-03-12")
        self.assertEqual(result["candidates"][1]["kind"], "event")
        self.assertEqual(result["candidates"][1]["title"], "학부모총회")
        self.assertNotIn("선생님 안녕하세요", result["candidates"][0]["title"])
        self.assertNotIn("선생님 안녕하세요", result["candidates"][1]["title"])

    def test_parse_reads_day_only_date_using_previous_month_context(self):
        now = timezone.make_aware(datetime(2026, 3, 10, 9, 0))
        result = parse_message_capture_draft(
            "3월 19일 학부모총회 실시\n12일(목)까지 자료 제출 부탁드립니다.",
            now=now,
            has_files=False,
        )

        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["candidates"][0]["start_time"].date().isoformat(), "2026-03-12")
        self.assertEqual(result["candidates"][1]["start_time"].date().isoformat(), "2026-03-19")

    def test_parse_with_absolute_date_and_time_keeps_location_and_materials(self):
        now = timezone.make_aware(datetime(2026, 3, 4, 9, 0))
        result = parse_message_capture_draft(
            "2026-03-15 14:00-15:20 학부모총회\n준비물: 실험 노트\n과학실 수업",
            now=now,
            has_files=False,
        )

        self.assertEqual(result["parse_status"], "parsed")
        self.assertEqual(result["location"], "과학실")
        self.assertEqual(result["materials"], "실험 노트")
        candidate = result["candidates"][0]
        self.assertEqual(candidate["kind"], "event")
        self.assertEqual(candidate["start_time"].hour, 14)
        self.assertEqual(candidate["end_time"].hour, 15)
        self.assertFalse(candidate["is_all_day"])

    def test_parse_failed_when_no_date_is_present(self):
        result = parse_message_capture_draft("학급 안내\n추후 다시 알려드리겠습니다.", has_files=False)

        self.assertEqual(result["parse_status"], "failed")
        self.assertEqual(result["confidence_label"], "low")
        self.assertEqual(result["candidates"], [])
