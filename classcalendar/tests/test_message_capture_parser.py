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

    def test_parse_ignores_farewell_today_phrase_and_keeps_explicit_dates(self):
        now = timezone.make_aware(datetime(2026, 3, 16, 9, 0))
        result = parse_message_capture_draft(
            "선생님 안녕하세요.\n"
            "학부모총회와 관련하여 계획서를 다시한번 보내드립니다.\n"
            "\n"
            "1) 의자배치는 18일(수) 15시 45분\n"
            ": 담임교사, 주무관님 협조\n"
            "2) 의자 뒷정리는 19일(목) 15시 10분\n"
            ": 전담, 비교과, 주무관님 협조\n"
            "3) 내빈석 셋팅 및 청소담당 확인\n"
            "\n"
            "4) 등록부 출력하여 배치\n"
            "5) 총회 전 교실정리\n"
            "-------------------\n"
            "\n"
            "그리고 또 하나,\n"
            "4월 2일(목)에 보정동에 벚꽃이 핀다는 정보를\n"
            "친목 회장님께 들었습니다.\n"
            "직원연수를 계획하고 있으니 오후 시간을 비워두셔요. (함께 움직이지 않습니다. 학년별로 자유롭게...)\n"
            "\n"
            "이번주 총회 끝나고 조금 여유로워지기를 바라며\n"
            "오늘도 즐퇴하세요.",
            now=now,
            has_files=False,
        )

        self.assertEqual(
            [candidate["start_time"].date().isoformat() for candidate in result["candidates"]],
            ["2026-03-18", "2026-03-19", "2026-04-02"],
        )

    def test_parse_llm_refinement_matches_candidate_ids_even_when_response_is_reordered(self):
        now = timezone.make_aware(datetime(2026, 3, 10, 9, 0))

        def reordered_refiner(*, candidates, **kwargs):
            return [
                {
                    "candidate_id": candidates[1]["refinement_id"],
                    "kind": "event",
                    "title": "학부모총회",
                    "summary": "학부모총회가 실시됩니다.",
                    "is_recommended": True,
                    "evidence_text": "3월 19일 학부모총회 실시",
                },
                {
                    "candidate_id": candidates[0]["refinement_id"],
                    "kind": "deadline",
                    "title": "연수물 수정 마감",
                    "summary": "12일까지 연수물을 수정해 주세요.",
                    "is_recommended": True,
                    "evidence_text": "12일(목)까지 연수물 수정 부탁드립니다.",
                },
            ]

        result = parse_message_capture_draft(
            "3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
            now=now,
            has_files=False,
            llm_refiner=reordered_refiner,
        )

        self.assertEqual(
            {
                candidate["start_time"].date().isoformat(): candidate["title"]
                for candidate in result["candidates"]
            },
            {
                "2026-03-12": "연수물 수정 마감",
                "2026-03-19": "학부모총회",
            },
        )
