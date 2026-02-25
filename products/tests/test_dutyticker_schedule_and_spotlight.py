import json
from datetime import time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom
from products.models import DTRole, DTRoleAssignment, DTSchedule, DTStudent, DTTimeSlot

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
        payload = {
            "slot_p1_start": "08:55",
            "slot_p1_end": "09:35",
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

        DTStudent.objects.create(user=self.user, classroom=self.classroom, name="학생A", number=1)
        DTRole.objects.create(user=self.user, classroom=self.classroom, name="칠판 지우기", time_slot="쉬는시간")
        api_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(api_response.status_code, 200)
        weekly = api_response.json()["schedule"]
        monday_rows = weekly.get("1", [])
        self.assertTrue(any(row.get("slot_type") == "lunch" for row in monday_rows))

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

