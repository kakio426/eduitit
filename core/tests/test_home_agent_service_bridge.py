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
        self.assertEqual(result["execution"]["kind"], "teacher-law")
        self.assertTrue(result["execution"]["incident_options"])

    @patch(
        "teacher_law.services.answer_legal_question",
        return_value={
            "status": "ok",
            "payload": {
                "summary": "관리자 공유와 게시 중단 요청을 먼저 검토하세요.",
                "action_items": [],
            },
            "profile": {
                "incident_type": "privacy_photo",
                "legal_goal": "posting_allowed",
            },
        },
    )
    def test_teacher_law_followup_context_is_used_without_replacing_draft_question(self, mock_answer_legal_question):
        result = generate_service_preview(
            request=self._request(),
            mode_key="teacher-law",
            mode_spec={"badge": "교사 법률", "default_title": "법률 검토 메모"},
            text="그럼 학교가 바로 요청할 조치는요?",
            context={
                "teacher_law_followup": {
                    "turns": [
                        {
                            "question": "학부모가 아이들 사진을 인터넷에 올렸습니다.",
                            "summary": "공개 범위와 동의 여부를 먼저 확인해야 합니다.",
                        },
                        {
                            "question": "게시 중단 요청은 누가 해야 하나요?",
                            "summary": "학교가 사실관계를 확인해 보호자에게 요청합니다.",
                        },
                    ],
                }
            },
        )

        called_question = mock_answer_legal_question.call_args.kwargs["question"]
        self.assertIn("이전 대화", called_question)
        self.assertIn("1. 질문: 학부모가 아이들 사진을 인터넷에 올렸습니다.", called_question)
        self.assertIn("2. 질문: 게시 중단 요청은 누가 해야 하나요?", called_question)
        self.assertIn("추가 질문: 그럼 학교가 바로 요청할 조치는요?", called_question)
        self.assertEqual(result["execution"]["draft"]["question"], "그럼 학교가 바로 요청할 조치는요?")
        self.assertEqual(len(result["execution"]["draft"]["context_turns"]), 2)
        self.assertEqual(result["execution"]["draft"]["context_question"], "게시 중단 요청은 누가 해야 하나요?")

    @patch(
        "teacher_law.services.answer_legal_question",
        return_value={
            "status": "ok",
            "payload": {
                "summary": "쉬는시간 사고로 보고 당시 위치와 조치 기록을 먼저 정리하세요.",
                "action_items": [],
            },
            "profile": {
                "incident_type": "school_safety",
                "legal_goal": "teacher_liability",
                "scene_value": "break_time",
            },
        },
    )
    def test_teacher_law_short_scene_followup_completes_pending_draft(self, mock_answer_legal_question):
        result = generate_service_preview(
            request=self._request(),
            mode_key="teacher-law",
            mode_spec={"badge": "교사 법률", "default_title": "법률 검토 메모"},
            text="쉬는시간",
            context={
                "teacher_law_followup": {
                    "summary": "수업 중인지, 쉬는시간인지, 체험학습인지 먼저 골라 주세요.",
                    "draft": {
                        "question": "학생이 다쳤는데 그때 교사실에 가 있었습니다. 제 책임이 있나요?",
                        "incident_type": "school_safety",
                        "legal_goal": "teacher_liability",
                        "scene": "",
                        "counterpart": "",
                    },
                }
            },
        )

        called_kwargs = mock_answer_legal_question.call_args.kwargs
        self.assertEqual(called_kwargs["scene"], "break_time")
        self.assertEqual(called_kwargs["incident_type"], "school_safety")
        self.assertEqual(called_kwargs["legal_goal"], "teacher_liability")
        self.assertIn("이전 대화", called_kwargs["question"])
        self.assertIn("학생이 다쳤는데 그때 교사실에 가 있었습니다.", called_kwargs["question"])
        self.assertIn("추가 질문: 쉬는시간", called_kwargs["question"])
        self.assertEqual(result["preview"]["title"], "법률 답변")
        self.assertEqual(result["execution"]["draft"]["question"], "학생이 다쳤는데 그때 교사실에 가 있었습니다. 제 책임이 있나요?")
        self.assertEqual(result["execution"]["draft"]["scene"], "break_time")

    def test_schedule_mode_uses_classcalendar_parser_candidates(self):
        result = generate_service_preview(
            request=self._request(),
            mode_key="schedule",
            mode_spec={"badge": "일정", "default_title": "캘린더 등록 후보"},
            text="3월 19일 학부모총회 실시",
        )

        self.assertEqual(result["provider"], "classcalendar")
        self.assertEqual(result["preview"]["title"], "캘린더 확인")
        self.assertIn("3월 19일", result["preview"]["sections"][0]["items"][0])
        self.assertIn("학부모총회", result["preview"]["sections"][0]["items"][0])
        self.assertEqual(result["execution"]["kind"], "schedule")
        self.assertTrue(result["execution"]["choices"])
