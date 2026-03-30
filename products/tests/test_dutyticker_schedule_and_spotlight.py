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
            "slot_morning_start": "08:00",
            "slot_morning_end": "09:00",
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

        morning_slot = DTTimeSlot.objects.get(user=self.user, classroom=self.classroom, slot_code="morning")
        self.assertEqual(morning_slot.slot_kind, "morning")
        self.assertEqual(morning_slot.start_time, time(8, 0))
        self.assertEqual(morning_slot.end_time, time(9, 0))

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
        payload = api_response.json()
        weekly = payload["schedule"]
        time_slots = payload["timeSlots"]
        monday_rows = weekly.get("1", [])
        morning_row = next(row for row in monday_rows if row.get("slot_code") == "morning")
        slot_34_row = next(row for row in monday_rows if row.get("slot_code") == "b3")
        lunch_row = next(row for row in monday_rows if row.get("slot_code") == "lunch")
        slot_56_row = next(row for row in monday_rows if row.get("slot_code") == "b5")
        morning_slot_row = next(row for row in time_slots if row.get("slotCode") == "morning")
        self.assertEqual(morning_row["slot_type"], "morning")
        self.assertEqual(morning_row["slot_label"], "아침시간")
        self.assertEqual(morning_slot_row["slotType"], "morning")
        self.assertEqual(morning_slot_row["startTime"], "08:00")
        self.assertEqual(morning_slot_row["endTime"], "09:00")
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

    def test_mission_automation_api_persists_slot_linked_automations(self):
        DTTimeSlot.objects.create(
            user=self.user,
            classroom=self.classroom,
            slot_code="morning",
            slot_kind="morning",
            slot_order=1,
            slot_label="아침시간",
            period_number=None,
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        DTTimeSlot.objects.create(
            user=self.user,
            classroom=self.classroom,
            slot_code="lunch",
            slot_kind="lunch",
            slot_order=9,
            slot_label="점심시간 (4-5)",
            period_number=None,
            start_time=time(12, 10),
            end_time=time(13, 0),
        )
        payload = {
            "automations": [
                {
                    "slotCode": "morning",
                    "enabled": True,
                    "phrase": {
                        "label": "아침 조회 준비",
                        "title": "아침 조회 준비",
                        "desc": "출석부와 전달사항 확인",
                    },
                },
                {
                    "slotCode": "lunch",
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
        self.assertEqual(automations[0].slot_code, "morning")
        self.assertEqual(automations[0].mission_title, "아침 조회 준비")
        self.assertEqual(automations[0].mission_desc, "출석부와 전달사항 확인")
        self.assertEqual(automations[0].start_time, time(8, 0))
        self.assertEqual(automations[0].end_time, time(9, 0))
        self.assertEqual(automations[0].timer_minutes, 60)
        self.assertTrue(automations[0].is_enabled)
        self.assertFalse(automations[1].is_enabled)

        api_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(api_response.status_code, 200)
        rows = api_response.json()["automations"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["slotCode"], "morning")
        self.assertEqual(rows[0]["name"], "아침시간")
        self.assertEqual(rows[0]["startTime"], "08:00")
        self.assertEqual(rows[0]["endTime"], "09:00")
        self.assertEqual(rows[0]["phrase"]["label"], "아침 조회 준비")

        self.client.post(
            reverse("dt_admin_update_schedule_settings"),
            data={
                "slot_morning_start": "08:10",
                "slot_morning_end": "09:00",
                "slot_p1_start": "09:00",
                "slot_p1_end": "09:40",
                "slot_b1_start": "09:40",
                "slot_b1_end": "09:50",
                "slot_p2_start": "09:50",
                "slot_p2_end": "10:30",
                "slot_b2_start": "10:30",
                "slot_b2_end": "10:40",
                "slot_p3_start": "10:40",
                "slot_p3_end": "11:20",
                "slot_b3_start": "11:20",
                "slot_b3_end": "11:30",
                "slot_b3_kind": "break",
                "slot_p4_start": "11:30",
                "slot_p4_end": "12:10",
                "slot_lunch_start": "12:10",
                "slot_lunch_end": "13:10",
                "slot_lunch_kind": "lunch",
                "slot_p5_start": "13:10",
                "slot_p5_end": "13:50",
                "slot_b5_start": "13:50",
                "slot_b5_end": "14:00",
                "slot_b5_kind": "break",
                "slot_p6_start": "14:00",
                "slot_p6_end": "14:40",
            },
        )
        refreshed_rows = self.client.get(reverse("dt_api_data")).json()["automations"]
        self.assertEqual(refreshed_rows[0]["slotCode"], "morning")
        self.assertEqual(refreshed_rows[0]["startTime"], "08:10")
        self.assertEqual(refreshed_rows[0]["endTime"], "09:00")

    def test_weekly_schedule_payload_leaves_empty_period_name_blank(self):
        response = self.client.post(
            reverse("dt_admin_update_schedule_settings"),
            data={
                "slot_morning_start": "08:00",
                "slot_morning_end": "09:00",
                "slot_p1_start": "09:00",
                "slot_p1_end": "09:40",
                "slot_b1_start": "09:40",
                "slot_b1_end": "09:50",
                "slot_p2_start": "09:50",
                "slot_p2_end": "10:30",
                "slot_b2_start": "10:30",
                "slot_b2_end": "10:40",
                "slot_p3_start": "10:40",
                "slot_p3_end": "11:20",
                "slot_b3_start": "11:20",
                "slot_b3_end": "11:30",
                "slot_b3_kind": "break",
                "slot_p4_start": "11:30",
                "slot_p4_end": "12:10",
                "slot_lunch_start": "12:10",
                "slot_lunch_end": "13:00",
                "slot_lunch_kind": "lunch",
                "slot_p5_start": "13:00",
                "slot_p5_end": "13:40",
                "slot_b5_start": "13:40",
                "slot_b5_end": "13:50",
                "slot_b5_kind": "break",
                "slot_p6_start": "13:50",
                "slot_p6_end": "14:30",
                "subject_1_1": "국어",
                "subject_1_2": "수학",
            },
        )
        self.assertEqual(response.status_code, 302)

        weekly = self.client.get(reverse("dt_api_data")).json()["schedule"]
        monday_rows = weekly["1"]
        sixth_row = next(row for row in monday_rows if row.get("slot_code") == "p6")
        self.assertEqual(sixth_row["name"], "")

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
