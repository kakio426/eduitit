import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from classcalendar.models import CalendarEvent
from core.home_agent_service_bridge import generate_service_preview
from reservations.models import GradeRecurringLock, Reservation, School, SchoolConfig, SpecialRoom
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

    def test_reservation_preview_room_only_does_not_make_up_date_or_period(self):
        school = School.objects.create(name="우리학교", owner=self.user)
        SchoolConfig.objects.get_or_create(school=school)
        room = SpecialRoom.objects.create(school=school, name="미술실")

        result = generate_service_preview(
            request=self._request(),
            mode_key="reservation",
            mode_spec={"badge": "특별실 예약", "default_title": "예약 요청 후보"},
            text="미술실",
        )

        self.assertEqual(result["provider"], "reservations")
        self.assertEqual(result["execution"]["kind"], "reservation")
        self.assertEqual(result["execution"]["draft"]["school_slug"], school.slug)
        self.assertEqual(result["execution"]["draft"]["room_id"], str(room.id))
        self.assertEqual(result["execution"]["draft"]["date"], "")
        self.assertEqual(result["execution"]["draft"]["period"], "")
        self.assertIn("날짜를 확인해 주세요.", result["execution"]["warnings"])
        self.assertIn("교시를 선택해 주세요.", result["execution"]["warnings"])

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

    def test_home_agent_execute_allows_matching_grade_locked_slot(self):
        target_date = date(2026, 4, 22)
        school = School.objects.create(name="미래초", owner=self.user)
        SchoolConfig.objects.get_or_create(school=school)
        room = SpecialRoom.objects.create(school=school, name="과학실")
        GradeRecurringLock.objects.create(
            room=room,
            day_of_week=target_date.weekday(),
            period=3,
            grade=4,
        )

        response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "reservation",
                    "data": {
                        "school_slug": school.slug,
                        "room_id": str(room.id),
                        "date": target_date.strftime("%Y-%m-%d"),
                        "period": "3",
                        "owner_type": "class",
                        "grade": "4",
                        "class_no": "2",
                        "name": "담임",
                        "edit_code": "1234",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(Reservation.objects.filter(room=room, date=target_date, period=3).exists())

    def test_home_agent_execute_returns_grade_lock_override_warning(self):
        target_date = date(2026, 4, 22)
        school = School.objects.create(name="미래초", owner=self.user)
        SchoolConfig.objects.get_or_create(school=school)
        room = SpecialRoom.objects.create(school=school, name="과학실")
        GradeRecurringLock.objects.create(
            room=room,
            day_of_week=target_date.weekday(),
            period=3,
            grade=4,
        )

        response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "reservation",
                    "data": {
                        "school_slug": school.slug,
                        "room_id": str(room.id),
                        "date": target_date.strftime("%Y-%m-%d"),
                        "period": "3",
                        "owner_type": "class",
                        "grade": "5",
                        "class_no": "2",
                        "name": "담임",
                        "edit_code": "1234",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("override_grade_lock", response.json()["field_errors"])
        self.assertEqual(Reservation.objects.count(), 0)

        override_response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "reservation",
                    "data": {
                        "school_slug": school.slug,
                        "room_id": str(room.id),
                        "date": target_date.strftime("%Y-%m-%d"),
                        "period": "3",
                        "owner_type": "class",
                        "grade": "5",
                        "class_no": "2",
                        "name": "담임",
                        "edit_code": "1234",
                        "override_grade_lock": True,
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(override_response.status_code, 200)
        self.assertEqual(override_response.json()["status"], "ok")
        self.assertTrue(Reservation.objects.filter(room=room, date=target_date, period=3).exists())

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
                "reasoning_summary": "영상 제공은 개인정보와 학생 초상 관련 동의 범위를 함께 확인해야 하므로 학교 절차가 먼저입니다.",
                "action_items": ["학교 관리자와 먼저 공유합니다."],
                "citations": [
                    {
                        "source_type": "law",
                        "law_name": "개인정보 보호법",
                        "reference_label": "제15조",
                        "article_label": "제15조",
                    },
                    {
                        "source_type": "case",
                        "law_name": "대법원 2024다12345",
                        "case_number": "2024다12345",
                    },
                ],
                "representative_case": {
                    "title": "대법원 2024다12345",
                    "case_number": "2024다12345",
                },
                "representative_case_confidence": "high",
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
        preview_items = response.json()["preview"]["sections"][0]["items"]
        self.assertIn("판단 기준 · 영상 제공은 개인정보와 학생 초상 관련 동의 범위를 함께 확인해야 하므로 학교 절차가 먼저입니다.", preview_items)
        self.assertIn("법령 근거 · 개인정보 보호법 제15조", preview_items)
        self.assertIn("판례 참고 · 대법원 2024다12345 (연관성 높음)", preview_items)
        self.assertEqual(LegalChatMessage.objects.count(), 2)
        self.assertEqual(LegalChatMessage.objects.filter(role=LegalChatMessage.Role.USER).count(), 1)
        self.assertEqual(LegalChatMessage.objects.filter(role=LegalChatMessage.Role.ASSISTANT).count(), 1)

        from teacher_law.views import _build_page_context

        page_request = self.factory.get("/teacher-law/")
        page_request.user = self.user
        page_request.session = self.client.session
        page_context = _build_page_context(page_request)
        self.assertEqual(
            page_context["latest_pair"]["user_message"]["body"],
            "학부모가 수업 중 촬영 영상을 요구합니다.",
        )
        self.assertEqual(
            page_context["latest_pair"]["assistant_message"]["summary"],
            "제공 범위와 보관 기록을 먼저 확인해야 합니다.",
        )

    @patch(
        "teacher_law.views.answer_legal_question",
        return_value={
            "status": "ok",
            "profile": {
                "original_question": "이전 질문: 학부모가 사진을 올렸습니다.\n추가 질문: 내릴 수 있게 요청해도 되나요?",
                "normalized_question": "사진 게시 중단 요청",
                "topic": "privacy_photo",
                "scope_supported": True,
                "risk_flags": [],
                "candidate_queries": ["사진 게시 중단"],
                "quick_question_key": "",
            },
            "payload": {
                "summary": "게시 범위와 동의 여부를 확인한 뒤 요청하세요.",
                "action_items": [],
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
    def test_home_agent_execute_uses_teacher_law_context_but_stores_followup_question(self, mock_answer_legal_question):
        response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "teacher-law",
                    "data": {
                        "question": "내릴 수 있게 요청해도 되나요?",
                        "context_turns": [
                            {
                                "question": "학부모가 사진을 올렸습니다.",
                                "summary": "공개 범위와 동의 여부를 먼저 봅니다.",
                            },
                            {
                                "question": "바로 삭제 요청을 해도 되나요?",
                                "summary": "사실관계를 확인하고 요청 주체를 정리합니다.",
                            },
                        ],
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
        self.assertEqual(response.json()["preview"]["title"], "법률 답변")
        self.assertEqual(response.json()["message"], "법률 대화에 남겼습니다.")
        called_question = mock_answer_legal_question.call_args.kwargs["question"]
        self.assertIn("이전 대화", called_question)
        self.assertIn("1. 질문: 학부모가 사진을 올렸습니다.", called_question)
        self.assertIn("2. 질문: 바로 삭제 요청을 해도 되나요?", called_question)
        self.assertIn("추가 질문: 내릴 수 있게 요청해도 되나요?", called_question)
        self.assertEqual(
            LegalChatMessage.objects.get(role=LegalChatMessage.Role.USER).body,
            "내릴 수 있게 요청해도 되나요?",
        )

    def test_home_agent_execute_returns_teacher_law_field_errors(self):
        response = self.client.post(
            reverse("home_agent_execute"),
            data=json.dumps(
                {
                    "mode_key": "teacher-law",
                    "data": {
                        "question": "학부모가 수업 중에 녹음을 요구합니다. 어디까지 응해야하나요",
                        "incident_type": "recording_defamation",
                        "legal_goal": "",
                        "scene": "",
                        "counterpart": "",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "필수 항목을 먼저 선택해 주세요.")
        self.assertEqual(response.json()["field_errors"]["legal_goal"], "지금 궁금한 것을 먼저 골라 주세요.")
        self.assertEqual(response.json()["field_errors"]["counterpart"], "상대를 하나 골라 주세요.")
