from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from collect.models import CollectionRequest
from handoff.models import HandoffRosterGroup, HandoffRosterMember


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

    def test_creator_can_edit_request(self):
        self.client.force_login(self.teacher)
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="before-title",
            description="before-desc",
            allow_file=True,
            allow_link=False,
            allow_text=False,
            status="active",
        )

        response = self.client.post(
            reverse("collect:request_edit", args=[req.id]),
            data={
                "title": "after-title",
                "description": "after-desc",
                "expected_submitters": "학생1\n학생2",
                "allow_file": "on",
                "allow_text": "on",
                "choice_mode": "single",
                "choice_min_selections": "1",
                "choice_max_selections": "",
                "choice_options_text": "",
                "deadline": "",
                "max_submissions": "75",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("collect:request_detail", args=[req.id]))

        req.refresh_from_db()
        self.assertEqual(req.title, "after-title")
        self.assertEqual(req.description, "after-desc")
        self.assertTrue(req.allow_file)
        self.assertFalse(req.allow_link)
        self.assertTrue(req.allow_text)
        self.assertEqual(req.max_submissions, 75)
        self.assertEqual(req.expected_submitters_list, ["학생1", "학생2"])

    def test_only_creator_can_access_edit_page(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="owner-only-edit",
            status="active",
        )
        self.client.force_login(self.other_teacher)

        response = self.client.get(reverse("collect:request_edit", args=[req.id]))
        self.assertEqual(response.status_code, 404)

    def test_dashboard_renders_edit_link(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="dashboard-edit-link",
            status="active",
        )
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("collect:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("collect:request_edit", args=[req.id]))

    def test_expected_submitters_list_merges_shared_roster_and_manual_names(self):
        group = HandoffRosterGroup.objects.create(owner=self.teacher, name="교무부")
        HandoffRosterMember.objects.create(group=group, display_name="이서연", sort_order=1, is_active=True)
        HandoffRosterMember.objects.create(group=group, display_name="김민수", sort_order=2, is_active=True)
        HandoffRosterMember.objects.create(group=group, display_name="박지훈", sort_order=3, is_active=False)
        HandoffRosterMember.objects.create(group=group, display_name="김민수", sort_order=4, is_active=True)

        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="shared-roster-list",
            status="active",
            shared_roster_group=group,
            expected_submitters="추가A\n김민수\n추가B",
        )

        self.assertEqual(req.expected_submitters_list, ["이서연", "김민수", "추가A", "추가B"])

    def test_request_create_can_link_shared_handoff_roster(self):
        self.client.force_login(self.teacher)
        group = HandoffRosterGroup.objects.create(owner=self.teacher, name="2학년")
        HandoffRosterMember.objects.create(group=group, display_name="김교사", sort_order=1, is_active=True)
        HandoffRosterMember.objects.create(group=group, display_name="이교사", sort_order=2, is_active=True)

        response = self.client.post(
            reverse("collect:request_create"),
            data={
                "title": "공유 명단 연동 수합",
                "description": "",
                "shared_roster_group": str(group.id),
                "expected_submitters": "",
                "allow_file": "on",
                "allow_link": "on",
                "allow_text": "on",
                "choice_mode": "single",
                "choice_min_selections": "1",
                "choice_max_selections": "",
                "choice_options_text": "",
                "deadline": "",
                "max_submissions": "30",
            },
        )

        self.assertEqual(response.status_code, 302)
        req = CollectionRequest.objects.get(creator=self.teacher, title="공유 명단 연동 수합")
        self.assertEqual(req.shared_roster_group_id, group.id)
        self.assertEqual(req.expected_submitters_list, ["김교사", "이교사"])

    def test_request_create_rejects_other_users_handoff_roster(self):
        self.client.force_login(self.teacher)
        other_group = HandoffRosterGroup.objects.create(owner=self.other_teacher, name="다른교사 명단")
        HandoffRosterMember.objects.create(group=other_group, display_name="외부교사", sort_order=1, is_active=True)

        response = self.client.post(
            reverse("collect:request_create"),
            data={
                "title": "잘못된 공유 명단",
                "description": "",
                "shared_roster_group": str(other_group.id),
                "expected_submitters": "",
                "allow_file": "on",
                "deadline": "",
                "max_submissions": "30",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CollectionRequest.objects.filter(creator=self.teacher, title="잘못된 공유 명단").exists())
        self.assertIn("shared_roster_group", response.context["form"].errors)
