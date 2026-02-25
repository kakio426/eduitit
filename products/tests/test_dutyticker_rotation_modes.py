from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
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

    def test_admin_dashboard_shows_compact_rotation_controls(self):
        response = self.client.get(reverse("dt_admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="rotationMode"')
        self.assertContains(response, "지금 1칸 순환")
        self.assertNotContains(response, "지금 순환하기")
