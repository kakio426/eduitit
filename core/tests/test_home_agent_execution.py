import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from classcalendar.models import CalendarEvent
from core.home_agent_service_bridge import generate_service_preview
from reservations.models import Reservation, School, SchoolConfig, SpecialRoom
from teacher_law.models import LegalChatMessage


User = get_user_model()


class HomeAgentExecutionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="agentexec",
            password="pw12345!",
        )
        self.client.force_login(self.user)

    def _request(self):
        request = self.factory.post("/api/home-agent/preview/")
        request.user = self.user
        request.session = self.client.session
        request.COOKIES = {}
        request.META = {}
        return request

    def test_reservation_preview_includes_execution_payload(self):
        school = School.objects.create(name="우리학교", owner=self.user)
        config, _ = SchoolConfig.objects.get_or_create(school=school)
        config.period_times = "09:00-09:40,09:50-10:30,10:40-11:20"
        config.save(update_fields=["period_times"])
        room = SpecialRoom.objects.create(school=school, name="과학실")

        result = generate_service_preview(
            request=self._request(),
            mode_key="reservation",
            mode_spec={"badge": "특별실 예약", "default_title": "예약 요청 후보"},
            text="4월 22일 3교시 과학실 예약",
        )

        self.assertEqual(result["provider"], "reservations")
        self.assertEqual(result["execution"]["kind"], "reservation")
        self.assertEqual(result["execution"]["draft"]["school_slug"], school.slug)
        self.assertEqual(result["execution"]["draft"]["room_id"], str(room.id))
        self.assertEqual(result["execution"]["draft"]["period"], "3")

    def test_home_agent_execute_creates_calendar_event(self):
        response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "schedule",
                    "data": {
                        "title": "학부모총회",
                        "note": "준비물 확인",
                        "start_time": "2026-04-18T15:30",
                        "end_time": "2026-04-18T16:30",
                        "is_all_day": False,
                        "color": "indigo",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(CalendarEvent.objects.count(), 1)
        event = CalendarEvent.objects.get()
        self.assertEqual(event.title, "학부모총회")
        self.assertEqual(event.author, self.user)

    def test_home_agent_execute_creates_reservation(self):
        school = School.objects.create(name="미래초", owner=self.user)
        SchoolConfig.objects.get_or_create(school=school)
        room = SpecialRoom.objects.create(school=school, name="과학실")

        response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "reservation",
                    "data": {
                        "school_slug": school.slug,
                        "room_id": str(room.id),
                        "date": "2026-04-22",
                        "period": "3",
                        "owner_type": "class",
                        "grade": "3",
                        "class_no": "2",
                        "name": "담임",
                        "memo": "실험 수업",
                        "edit_code": "1234",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(Reservation.objects.count(), 1)
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.room, room)
        self.assertEqual(reservation.date, date(2026, 4, 22))
        self.assertEqual(reservation.period, 3)
        self.assertEqual(reservation.grade, 3)
        self.assertEqual(reservation.class_no, 2)
        self.assertEqual(reservation.name, "담임")

    @patch(
        "teacher_law.views.answer_legal_question",
        return_value={
            "status": "ok",
            "profile": {
                "original_question": "학부모가 수업 중 촬영 영상을 요구합니다.",
                "normalized_question": "학부모가 수업 중 촬영 영상을 요구합니다.",
                "topic": "privacy_photo",
                "scope_supported": True,
                "risk_flags": [],
                "candidate_queries": ["학부모 촬영 영상 제공"],
                "quick_question_key": "",
            },
            "payload": {
                "summary": "제공 범위와 보관 기록을 먼저 확인해야 합니다.",
                "action_items": ["학교 관리자와 먼저 공유합니다."],
                "citations": [],
                "risk_level": "medium",
                "needs_human_help": False,
                "disclaimer": "일반 정보 안내입니다.",
                "scope_supported": True,
            },
            "audit": {
                "cache_hit": False,
                "search_attempt_count": 1,
                "search_result_count": 1,
                "detail_fetch_count": 1,
                "selected_laws_json": [],
                "failure_reason": "",
                "error_message": "",
                "elapsed_ms": 200,
            },
        },
    )
    def test_home_agent_execute_creates_teacher_law_messages(self, _mock_answer_legal_question):
        response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "teacher-law",
                    "data": {
                        "question": "학부모가 수업 중 촬영 영상을 요구합니다.",
                        "incident_type": "privacy_photo",
                        "legal_goal": "posting_allowed",
                        "scene": "",
                        "counterpart": "parent",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(LegalChatMessage.objects.count(), 2)
        self.assertEqual(LegalChatMessage.objects.filter(role=LegalChatMessage.Role.USER).count(), 1)
        self.assertEqual(LegalChatMessage.objects.filter(role=LegalChatMessage.Role.ASSISTANT).count(), 1)
