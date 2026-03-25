from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from products.models import DTRole, DTRoleAssignment, DTSettings, DTStudent


class DutyTickerRotationModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rotation_teacher",
            email="rotation_teacher@example.com",
            password="pw123456",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "rotation-teacher"
        profile.save(update_fields=["nickname"])
        self.client.login(username="rotation_teacher", password="pw123456")

    def test_update_rotation_settings_persists_mode(self):
        settings, _ = DTSettings.objects.get_or_create(user=self.user)
        settings.last_rotation_date = timezone.localdate()
        settings.save(update_fields=["last_rotation_date"])

        response = self.client.post(
            reverse("dt_admin_update_rotation_settings"),
            data={"rotation_mode": "auto_random"},
        )
        self.assertEqual(response.status_code, 302)

        settings.refresh_from_db()
        self.assertEqual(settings.rotation_mode, "auto_random")
        self.assertTrue(settings.auto_rotation)
        self.assertEqual(settings.rotation_frequency, "daily")

        response = self.client.post(
            reverse("dt_admin_update_rotation_settings"),
            data={"rotation_mode": "manual_random"},
        )
        self.assertEqual(response.status_code, 302)

        settings.refresh_from_db()
        self.assertEqual(settings.rotation_mode, "manual_random")
        self.assertFalse(settings.auto_rotation)
        self.assertIsNone(settings.last_rotation_date)

    def test_update_display_settings_persists_theme_and_role_view_mode(self):
        response = self.client.post(
            reverse("dt_admin_update_display_settings"),
            data={"theme": "sunny", "role_view_mode": "readable"},
        )
        self.assertEqual(response.status_code, 302)

        settings = DTSettings.objects.get(user=self.user)
        self.assertEqual(settings.theme, "sunny")
        self.assertEqual(settings.role_view_mode, "readable")

    def test_get_data_applies_auto_rotation_once_per_day(self):
        s1 = DTStudent.objects.create(user=self.user, name="학생1", number=1)
        s2 = DTStudent.objects.create(user=self.user, name="학생2", number=2)
        role = DTRole.objects.create(user=self.user, name="칠판", time_slot="쉬는시간")
        assignment = DTRoleAssignment.objects.create(user=self.user, role=role, student=s1)

        settings, _ = DTSettings.objects.get_or_create(user=self.user)
        settings.rotation_mode = "auto_sequential"
        settings.auto_rotation = False
        settings.last_rotation_date = timezone.localdate() - timedelta(days=1)
        settings.save(update_fields=["rotation_mode", "auto_rotation", "last_rotation_date"])

        response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        settings.refresh_from_db()
        self.assertEqual(assignment.student_id, s2.id)
        self.assertEqual(settings.last_rotation_date, timezone.localdate())

        second_response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(second_response.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.student_id, s2.id)

    def test_api_data_includes_role_view_mode(self):
        settings, _ = DTSettings.objects.get_or_create(user=self.user)
        settings.role_view_mode = "readable"
        settings.save(update_fields=["role_view_mode"])

        response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["settings"]["role_view_mode"], "readable")

    def test_rotation_trigger_random_behavior(self):
        s1 = DTStudent.objects.create(user=self.user, name="학생1", number=1)
        s2 = DTStudent.objects.create(user=self.user, name="학생2", number=2)
        s3 = DTStudent.objects.create(user=self.user, name="학생3", number=3)

        role1 = DTRole.objects.create(user=self.user, name="역할1", time_slot="아침")
        role2 = DTRole.objects.create(user=self.user, name="역할2", time_slot="쉬는")
        role3 = DTRole.objects.create(user=self.user, name="역할3", time_slot="종례")

        DTRoleAssignment.objects.create(user=self.user, role=role1, student=s1)
        DTRoleAssignment.objects.create(user=self.user, role=role2, student=s2)
        DTRoleAssignment.objects.create(user=self.user, role=role3, student=s3)

        def reverse_shuffle(values):
            values.reverse()

        with patch("products.dutyticker_api.random.shuffle", side_effect=reverse_shuffle):
            response = self.client.post(
                reverse("dt_api_rotate"),
                data='{"behavior":"random"}',
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("behavior"), "random")

        assignments = list(DTRoleAssignment.objects.filter(user=self.user).order_by("role_id"))
        self.assertEqual(assignments[0].student_id, s3.id)
        self.assertEqual(assignments[1].student_id, s2.id)
        self.assertEqual(assignments[2].student_id, s1.id)

    def test_rotation_trigger_random_behavior_rotates_with_single_assignment(self):
        s1 = DTStudent.objects.create(user=self.user, name="학생1", number=1)
        s2 = DTStudent.objects.create(user=self.user, name="학생2", number=2)
        role = DTRole.objects.create(user=self.user, name="역할1", time_slot="아침")
        assignment = DTRoleAssignment.objects.create(user=self.user, role=role, student=s1)

        response = self.client.post(
            reverse("dt_api_rotate"),
            data='{"behavior":"random"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("behavior"), "random")
        self.assertTrue(payload.get("rotated"))

        assignment.refresh_from_db()
        self.assertEqual(assignment.student_id, s2.id)

    def test_admin_dashboard_groups_settings_before_data_management(self):
        response = self.client.get(reverse("dt_admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "알림판 설정")
        self.assertContains(response, "학급 데이터 관리")
        self.assertContains(response, "화면 표시 저장")
        self.assertContains(response, 'id="rotationMode"')
        self.assertContains(response, "지금 1칸 순환")
        self.assertContains(response, "방송 저장")
        self.assertContains(response, 'id="slotKind_b3"')
        self.assertContains(response, 'name="slot_b3_kind"')
        self.assertContains(response, 'id="slotKind_lunch"')
        self.assertContains(response, 'name="slot_lunch_kind"')
        self.assertContains(response, 'id="slotKind_b5"')
        self.assertContains(response, 'name="slot_b5_kind"')
        self.assertNotContains(response, "시간표와 방송 저장")


class DutyTickerRotationCsrfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rotation_csrf_teacher",
            email="rotation_csrf_teacher@example.com",
            password="pw123456",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "rotation-csrf-teacher"
        profile.save(update_fields=["nickname"])

        self.client = Client(enforce_csrf_checks=True)
        self.client.login(username="rotation_csrf_teacher", password="pw123456")

    def _csrf_token(self):
        self.client.get(reverse("dt_admin_dashboard"))
        return self.client.cookies["csrftoken"].value

    def test_rotation_trigger_rejects_missing_csrf(self):
        response = self.client.post(
            reverse("dt_api_rotate"),
            data='{"behavior":"random"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_rotation_trigger_accepts_valid_csrf(self):
        s1 = DTStudent.objects.create(user=self.user, name="학생1", number=1)
        role1 = DTRole.objects.create(user=self.user, name="역할1", time_slot="아침")
        DTRoleAssignment.objects.create(user=self.user, role=role1, student=s1)

        token = self._csrf_token()
        response = self.client.post(
            reverse("dt_api_rotate"),
            data='{"behavior":"sequential"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))

    def test_reset_data_rejects_missing_csrf(self):
        response = self.client.post(reverse("dt_api_reset"))
        self.assertEqual(response.status_code, 403)

    def test_reset_data_accepts_valid_csrf(self):
        DTStudent.objects.create(user=self.user, name="학생1", number=1)
        DTRole.objects.create(user=self.user, name="역할1", time_slot="아침")
        token = self._csrf_token()
        response = self.client.post(
            reverse("dt_api_reset"),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        self.assertFalse(DTStudent.objects.filter(user=self.user).exists())
        self.assertFalse(DTRole.objects.filter(user=self.user).exists())

    def test_reset_assignments_only_rejects_missing_csrf(self):
        response = self.client.post(reverse("dt_api_reset_assignments"))
        self.assertEqual(response.status_code, 403)

    def test_reset_assignments_only_accepts_valid_csrf_and_clears_students(self):
        student = DTStudent.objects.create(user=self.user, name="학생1", number=1)
        role = DTRole.objects.create(user=self.user, name="역할1", time_slot="아침")
        assignment = DTRoleAssignment.objects.create(
            user=self.user,
            role=role,
            student=student,
            is_completed=True,
        )

        token = self._csrf_token()
        response = self.client.post(
            reverse("dt_api_reset_assignments"),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))

        assignment.refresh_from_db()
        self.assertIsNone(assignment.student)
        self.assertFalse(assignment.is_completed)

class DutyTickerMainResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="main_reset_teacher",
            email="main_reset_teacher@example.com",
            password="pw123456",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "main-reset-teacher"
        profile.save(update_fields=["nickname"])

        self.client = Client(enforce_csrf_checks=True)
        self.client.login(username="main_reset_teacher", password="pw123456")

    def test_main_view_sets_csrf_cookie_for_reset_actions_even_without_students(self):
        response = self.client.get(reverse("dutyticker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", self.client.cookies)

        assignment_response = self.client.post(
            reverse("dt_api_reset_assignments"),
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(assignment_response.status_code, 200)
        self.assertTrue(assignment_response.json().get("success"))
        self.assertEqual(assignment_response.json().get("updated_count"), 0)

        mission_response = self.client.post(
            reverse("dt_api_reset_student_missions"),
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(mission_response.status_code, 200)
        self.assertTrue(mission_response.json().get("success"))
        self.assertEqual(mission_response.json().get("updated_count"), 0)

    def test_reset_student_missions_accepts_valid_csrf_and_clears_progress(self):
        student = DTStudent.objects.create(user=self.user, name="학생1", number=1, is_mission_completed=True)
        DTStudent.objects.create(user=self.user, name="학생2", number=2, is_mission_completed=True)
        settings, _ = DTSettings.objects.get_or_create(user=self.user)
        settings.spotlight_student = student
        settings.save(update_fields=["spotlight_student"])

        self.client.get(reverse("dutyticker"))
        response = self.client.post(
            reverse("dt_api_reset_student_missions"),
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("updated_count"), 2)
        self.assertFalse(DTStudent.objects.filter(user=self.user, is_mission_completed=True).exists())

        settings.refresh_from_db()
        self.assertIsNone(settings.spotlight_student)
