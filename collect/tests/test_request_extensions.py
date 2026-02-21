from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from collect.models import CollectionRequest


class RequestExtensionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="extension_teacher",
            email="extension_teacher@example.com",
            password="pw123456",
        )
        self.other_teacher = User.objects.create_user(
            username="other_teacher",
            email="other_teacher@example.com",
            password="pw123456",
        )
        self.teacher.userprofile.nickname = "extension-teacher"
        self.teacher.userprofile.save(update_fields=["nickname"])
        self.other_teacher.userprofile.nickname = "other-teacher"
        self.other_teacher.userprofile.save(update_fields=["nickname"])

    def test_extend_deadline_uses_existing_deadline_as_base(self):
        self.client.force_login(self.teacher)
        original_deadline = timezone.now() + timedelta(days=2)
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="deadline-test",
            deadline=original_deadline,
            status="active",
        )

        response = self.client.post(
            reverse("collect:request_extend_deadline", args=[req.id]),
            data={"days": "3"},
        )

        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertAlmostEqual(
            req.deadline,
            original_deadline + timedelta(days=3),
            delta=timedelta(seconds=3),
        )
        self.assertIsNone(req.retention_until)

    def test_extend_deadline_without_existing_deadline_starts_from_now(self):
        self.client.force_login(self.teacher)
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="deadline-empty",
            status="active",
        )
        before = timezone.now()

        response = self.client.post(
            reverse("collect:request_extend_deadline", args=[req.id]),
            data={"days": "1"},
        )
        after = timezone.now()

        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertGreaterEqual(req.deadline, before + timedelta(days=1))
        self.assertLessEqual(req.deadline, after + timedelta(days=1, seconds=3))

    def test_extend_retention_uses_existing_retention_as_base(self):
        self.client.force_login(self.teacher)
        original_retention = timezone.now() + timedelta(days=7)
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="retention-test",
            retention_until=original_retention,
            status="closed",
        )

        response = self.client.post(
            reverse("collect:request_extend_retention", args=[req.id]),
            data={"days": "7"},
        )

        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertAlmostEqual(
            req.retention_until,
            original_retention + timedelta(days=7),
            delta=timedelta(seconds=3),
        )

    def test_only_creator_can_extend(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="owner-only",
            status="active",
        )
        self.client.force_login(self.other_teacher)

        response = self.client.post(
            reverse("collect:request_extend_retention", args=[req.id]),
            data={"days": "7"},
        )
        self.assertEqual(response.status_code, 404)

    def test_toggle_updates_closed_at(self):
        self.client.force_login(self.teacher)
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="toggle-test",
            status="active",
        )

        close_response = self.client.post(reverse("collect:request_toggle", args=[req.id]))
        self.assertEqual(close_response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, "closed")
        self.assertIsNotNone(req.closed_at)

        reopen_response = self.client.post(reverse("collect:request_toggle", args=[req.id]))
        self.assertEqual(reopen_response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, "active")
        self.assertIsNone(req.closed_at)
