import uuid
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from happy_seed.models import HSClassroom, HSStudent

from products.models import DTRole, DTRoleAssignment, DTStudent


class DutyTickerStudentSyncApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dt_sync_teacher",
            password="test-pass-1234",
        )
        self.classroom = HSClassroom.objects.create(
            teacher=self.user,
            name="6-1",
            school_name="테스트초",
            slug=f"sync-{uuid.uuid4().hex[:10]}",
        )

        self.client.force_login(self.user)
        session = self.client.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

    def test_sync_students_from_hs_updates_creates_and_deactivates(self):
        HSStudent.objects.create(classroom=self.classroom, name="김민수", number=1, is_active=True)
        HSStudent.objects.create(classroom=self.classroom, name="이서연", number=2, is_active=True)

        matched = DTStudent.objects.create(
            user=self.user,
            classroom=self.classroom,
            name="옛이름",
            number=1,
            is_active=False,
        )
        stale = DTStudent.objects.create(
            user=self.user,
            classroom=self.classroom,
            name="삭제대상",
            number=9,
            is_active=True,
        )

        role = DTRole.objects.create(
            user=self.user,
            classroom=self.classroom,
            name="칠판 지우기",
            time_slot="쉬는시간",
            description="",
        )
        assignment = DTRoleAssignment.objects.create(
            user=self.user,
            classroom=self.classroom,
            role=role,
            student=stale,
        )

        response = self.client.post(reverse("dt_api_sync_students_from_hs"))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["summary"]["created_count"], 1)
        self.assertEqual(payload["summary"]["updated_count"], 1)
        self.assertEqual(payload["summary"]["deactivated_count"], 1)
        self.assertEqual(payload["summary"]["active_count"], 2)

        matched.refresh_from_db()
        stale.refresh_from_db()
        assignment.refresh_from_db()

        self.assertEqual(matched.name, "김민수")
        self.assertTrue(matched.is_active)

        created = DTStudent.objects.get(user=self.user, classroom=self.classroom, number=2)
        self.assertEqual(created.name, "이서연")
        self.assertTrue(created.is_active)

        self.assertFalse(stale.is_active)
        self.assertIsNone(assignment.student)

    def test_sync_students_from_hs_requires_active_classroom(self):
        session = self.client.session
        session.pop("active_classroom_source", None)
        session.pop("active_classroom_id", None)
        session.save()

        response = self.client.post(reverse("dt_api_sync_students_from_hs"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])


class DutyTickerMissionEmptyValueTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dt_mission_teacher",
            password="test-pass-1234",
        )
        self.classroom = HSClassroom.objects.create(
            teacher=self.user,
            name="5-2",
            school_name="테스트초",
            slug=f"mission-{uuid.uuid4().hex[:10]}",
        )

        self.client.force_login(self.user)
        session = self.client.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

    def test_mission_update_accepts_empty_text(self):
        response = self.client.post(
            reverse("dt_api_mission_update"),
            data=json.dumps({"title": "", "description": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        data_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(data_response.status_code, 200)
        payload = data_response.json()
        self.assertEqual(payload["settings"]["mission_title"], "")
        self.assertEqual(payload["settings"]["mission_desc"], "")
