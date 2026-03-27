import json
from datetime import time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom
from products.models import (
    DTRole,
    DTRoleAssignment,
    DTSchedule,
    DTSettings,
    DTStudent,
    DTTimeSlot,
    DTMissionAutomation,
)

User = get_user_model()


class DutyTickerScheduleAndSpotlightTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dt_schedule_user",
            password="pw12345",
            email="dt_schedule_user@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "dt-schedule"
        profile.save(update_fields=["nickname"])

        self.client = Client()
        self.client.force_login(self.user)

        self.classroom = HSClassroom.objects.create(
            teacher=self.user,
            name="4학년 2반",
            slug="dt-4-2",
        )
        session = self.client.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

    def test_admin_schedule_settings_updates_slots_and_subjects(self):
        role_34 = DTRole.objects.create(
            user=self.user,
            classroom=self.classroom,
            name="우리반 정리왕",
            time_slot="쉬는시간 (3-4)",
        )
        role_45 = DTRole.objects.create(
            user=self.user,
            classroom=self.classroom,
            name="우리반 정리왕",
            time_slot="점심시간 (4-5)",
        )
        role_56 = DTRole.objects.create(
            user=self.user,
            classroom=self.classroom,
            name="우리반 정리왕",
            time_slot="쉬는시간 (5-6)",
        )
        payload = {
            "slot_p1_start": "08:55",
            "slot_p1_end": "09:35",
            "slot_b3_start": "11:20",
            "slot_b3_end": "11:30",
            "slot_b3_kind": "lunch",
            "slot_lunch_start": "12:10",
            "slot_lunch_end": "13:00",
            "slot_lunch_kind": "break",
            "slot_b5_start": "13:40",
            "slot_b5_end": "13:50",
            "slot_b5_kind": "lunch",
            "subject_1_1": "국어",
            "subject_1_2": "수학",
            "subject_2_1": "과학",
        }
        response = self.client.post(reverse("dt_admin_update_schedule_settings"), data=payload)
        self.assertEqual(response.status_code, 302)

        slot = DTTimeSlot.objects.get(user=self.user, classroom=self.classroom, slot_code="p1")
        self.assertEqual(slot.start_time, time(8, 55))
        self.assertEqual(slot.end_time, time(9, 35))

        monday_first = DTSchedule.objects.get(user=self.user, classroom=self.classroom, day=1, period=1)
        self.assertEqual(monday_first.subject, "국어")
        self.assertEqual(monday_first.start_time, time(8, 55))
        self.assertEqual(monday_first.end_time, time(9, 35))

        slot_34 = DTTimeSlot.objects.get(user=self.user, classroom=self.classroom, slot_code="b3")
        self.assertEqual(slot_34.slot_kind, "lunch")
        self.assertEqual(slot_34.slot_label, "점심시간 (3-4)")

        lunch_slot = DTTimeSlot.objects.get(user=self.user, classroom=self.classroom, slot_code="lunch")
        self.assertEqual(lunch_slot.slot_kind, "break")
        self.assertEqual(lunch_slot.slot_label, "쉬는시간 (4-5)")

        slot_56 = DTTimeSlot.objects.get(user=self.user, classroom=self.classroom, slot_code="b5")
        self.assertEqual(slot_56.slot_kind, "lunch")
        self.assertEqual(slot_56.slot_label, "점심시간 (5-6)")

        role_34.refresh_from_db()
        role_45.refresh_from_db()
        role_56.refresh_from_db()
        self.assertEqual(role_34.time_slot, "점심시간 (3-4)")
        self.assertEqual(role_45.time_slot, "쉬는시간 (4-5)")
        self.assertEqual(role_56.time_slot, "점심시간 (5-6)")

        api_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(api_response.status_code, 200)
        weekly = api_response.json()["schedule"]
        monday_rows = weekly.get("1", [])
        slot_34_row = next(row for row in monday_rows if row.get("slot_code") == "b3")
        lunch_row = next(row for row in monday_rows if row.get("slot_code") == "lunch")
        slot_56_row = next(row for row in monday_rows if row.get("slot_code") == "b5")
        self.assertEqual(slot_34_row["slot_type"], "lunch")
        self.assertEqual(slot_34_row["slot_label"], "점심시간 (3-4)")
        self.assertEqual(lunch_row["slot_type"], "break")
        self.assertEqual(lunch_row["slot_label"], "쉬는시간 (4-5)")
        self.assertEqual(slot_56_row["slot_type"], "lunch")
        self.assertEqual(slot_56_row["slot_label"], "점심시간 (5-6)")

    def test_admin_tts_settings_updates_broadcast_preferences(self):
        payload = {
            "tts_enabled": "on",
            "tts_minutes_before": "5",
            "tts_voice_uri": "ko-KR-TestVoice",
            "tts_rate": "1.10",
            "tts_pitch": "0.95",
        }
        response = self.client.post(reverse("dt_admin_update_tts_settings"), data=payload)
        self.assertEqual(response.status_code, 302)

        settings = DTSettings.objects.get(user=self.user, classroom=self.classroom)
        self.assertTrue(settings.tts_enabled)
        self.assertEqual(settings.tts_minutes_before, 5)
        self.assertEqual(settings.tts_voice_uri, "ko-KR-TestVoice")
        self.assertAlmostEqual(settings.tts_rate, 1.10)
        self.assertAlmostEqual(settings.tts_pitch, 0.95)

        api_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(api_response.status_code, 200)
        api_settings = api_response.json()["settings"]
        self.assertTrue(api_settings["tts_enabled"])
        self.assertEqual(api_settings["tts_minutes_before"], 5)
        self.assertEqual(api_settings["tts_voice_uri"], "ko-KR-TestVoice")

    def test_mission_automation_api_persists_teacher_defined_windows(self):
        payload = {
            "automations": [
                {
                    "name": "아침시간",
                    "startTime": "08:30",
                    "endTime": "08:50",
                    "timerMinutes": 15,
                    "enabled": True,
                    "phrase": {
                        "label": "아침 조회 준비",
                        "title": "아침 조회 준비",
                        "desc": "출석부와 전달사항 확인",
                    },
                },
                {
                    "name": "점심 전 정리",
                    "startTime": "12:00",
                    "endTime": "12:10",
                    "timerMinutes": 8,
                    "enabled": False,
                    "phrase": {
                        "label": "점심 전 정리",
                        "title": "점심 전 정리",
                        "desc": "사물함과 책상 주변을 정리하기",
                    },
                },
            ]
        }
        response = self.client.post(
            reverse("dt_api_mission_automations_update"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        automations = list(
            DTMissionAutomation.objects.filter(user=self.user, classroom=self.classroom).order_by("sort_order", "id")
        )
        self.assertEqual(len(automations), 2)
        self.assertEqual(automations[0].name, "아침시간")
        self.assertEqual(automations[0].mission_title, "아침 조회 준비")
        self.assertEqual(automations[0].mission_desc, "출석부와 전달사항 확인")
        self.assertEqual(automations[0].timer_minutes, 15)
        self.assertTrue(automations[0].is_enabled)
        self.assertFalse(automations[1].is_enabled)

        api_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(api_response.status_code, 200)
        rows = api_response.json()["automations"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "아침시간")
        self.assertEqual(rows[0]["startTime"], "08:30")
        self.assertEqual(rows[0]["endTime"], "08:50")
        self.assertEqual(rows[0]["timerMinutes"], 15)
        self.assertEqual(rows[0]["phrase"]["label"], "아침 조회 준비")

    def test_spotlight_student_api_persists_setting(self):
        student = DTStudent.objects.create(user=self.user, classroom=self.classroom, name="김학생", number=1)
        role = DTRole.objects.create(user=self.user, classroom=self.classroom, name="칠판 지우기", time_slot="쉬는시간")
        DTRoleAssignment.objects.create(user=self.user, classroom=self.classroom, role=role, student=student)

        response = self.client.post(
            reverse("dt_api_spotlight_update"),
            data=json.dumps({"student_id": student.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["spotlight_student_id"], student.id)

        api_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["settings"]["spotlight_student_id"], student.id)

        clear_response = self.client.post(
            reverse("dt_api_spotlight_update"),
            data=json.dumps({"student_id": None}),
            content_type="application/json",
        )
        self.assertEqual(clear_response.status_code, 200)
        self.assertIsNone(clear_response.json()["spotlight_student_id"])

    def test_dutyticker_main_renders_broadcast_tts_controls(self):
        response = self.client.get(reverse("dutyticker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="openBroadcastModalBtn"', html=False)
        self.assertContains(response, 'id="broadcastUseScheduleBtn"', html=False)
        self.assertContains(response, 'id="broadcastSpeakNowBtn"', html=False)
