from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from core.home_agent_service_bridge import generate_service_preview


class HomeAgentServiceBridgeTests(SimpleTestCase):
    def _request(self):
        request = RequestFactory().post("/api/home-agent/preview/")
        request.user = SimpleNamespace(is_authenticated=True)
        request.session = {}
        request.COOKIES = {}
        request.META = {}
        return request

    @patch("noticegen.views._generate_notice_payload", return_value=(200, {"result_text": "내일 우산을 챙겨 주세요."}))
    def test_notice_mode_uses_noticegen_payload(self, _mock_generate_notice_payload):
        result = generate_service_preview(
            request=self._request(),
            mode_key="notice",
            mode_spec={"badge": "알림장", "default_title": "알림장 초안"},
            text="내일 비가 와요. 우산을 챙겨 주세요.",
        )

        self.assertEqual(result["provider"], "noticegen")
        self.assertEqual(result["preview"]["title"], "알림장 결과")
        self.assertEqual(result["preview"]["sections"][0]["items"], ["내일 우산을 챙겨 주세요."])

    @patch(
        "teacher_law.services.answer_legal_question",
        return_value={
            "status": "ok",
            "payload": {
                "summary": "기록을 먼저 남기고 관리자와 공유하세요.",
                "action_items": [
                    "통화 내용과 시간을 남기세요.",
                    "학교 관리자에게 바로 공유하세요.",
                ],
            },
        },
    )
    def test_teacher_law_mode_uses_teacher_law_payload(self, _mock_answer_legal_question):
        result = generate_service_preview(
            request=self._request(),
            mode_key="teacher-law",
            mode_spec={"badge": "교사 법률", "default_title": "법률 검토 메모"},
            text="학부모가 반복적으로 항의 전화를 합니다.",
        )

        self.assertEqual(result["provider"], "teacher_law")
        self.assertEqual(result["preview"]["title"], "법률 답변")
        self.assertIn("기록을 먼저 남기고 관리자와 공유하세요.", result["preview"]["sections"][0]["items"])
        self.assertIn("통화 내용과 시간을 남기세요.", result["preview"]["sections"][0]["items"])

    def test_schedule_mode_uses_classcalendar_parser_candidates(self):
        result = generate_service_preview(
            request=self._request(),
            mode_key="schedule",
            mode_spec={"badge": "일정", "default_title": "캘린더 등록 후보"},
            text="3월 19일 학부모총회 실시",
        )

        self.assertEqual(result["provider"], "classcalendar")
        self.assertEqual(result["preview"]["title"], "캘린더 후보")
        self.assertIn("3월 19일", result["preview"]["sections"][0]["items"][0])
        self.assertIn("학부모총회", result["preview"]["sections"][0]["items"][0])
