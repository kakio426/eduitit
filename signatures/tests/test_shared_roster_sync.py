from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from handoff.models import HandoffRosterGroup, HandoffRosterMember
from signatures.models import ExpectedParticipant, TrainingSession


User = get_user_model()


class SignatureSharedRosterSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="signature_roster_owner",
            password="pw12345",
            email="signature_roster_owner@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "signature_roster_owner", "role": "school"},
        )
        self.other_user = User.objects.create_user(
            username="signature_roster_other",
            password="pw12345",
            email="signature_roster_other@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.other_user,
            defaults={"nickname": "signature_roster_other", "role": "school"},
        )

        self.group = HandoffRosterGroup.objects.create(owner=self.user, name="1학년 담임")
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="김교사",
            note="1-1",
            sort_order=1,
            is_active=True,
        )
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="이교사",
            note="1-2",
            sort_order=2,
            is_active=True,
        )
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="",
            note="빈값",
            sort_order=3,
            is_active=True,
        )
        HandoffRosterMember.objects.create(
            group=self.group,
            display_name="박교사",
            note="1-3",
            sort_order=4,
            is_active=False,
        )

        self.other_group = HandoffRosterGroup.objects.create(owner=self.other_user, name="외부 명단")
        HandoffRosterMember.objects.create(
            group=self.other_group,
            display_name="외부교사",
            note="외부",
            sort_order=1,
            is_active=True,
        )

        self.client.force_login(self.user)

    def test_create_session_imports_expected_participants_from_shared_roster(self):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        response = self.client.post(
            reverse("signatures:create"),
            data={
                "title": "공유 명단 연동 연수",
                "print_title": "",
                "instructor": "강사",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "시청각실",
                "description": "",
                "shared_roster_group": str(self.group.id),
                "expected_count": "",
                "is_active": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        session = TrainingSession.objects.get(title="공유 명단 연동 연수", created_by=self.user)
        self.assertEqual(session.shared_roster_group_id, self.group.id)

        participants = list(
            session.expected_participants.values_list("name", "affiliation").order_by("name")
        )
        self.assertEqual(
            participants,
            [("김교사", "1-1"), ("이교사", "1-2")],
        )
        self.assertContains(response, "공유 명단")

    def test_create_session_rejects_other_users_roster_group(self):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        response = self.client.post(
            reverse("signatures:create"),
            data={
                "title": "잘못된 명단 선택",
                "print_title": "",
                "instructor": "강사",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "시청각실",
                "description": "",
                "shared_roster_group": str(self.other_group.id),
                "expected_count": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TrainingSession.objects.filter(title="잘못된 명단 선택", created_by=self.user).exists())
        self.assertIn("shared_roster_group", response.context["form"].errors)

    def test_edit_session_can_link_roster_and_import_members(self):
        session = TrainingSession.objects.create(
            title="초기 연수",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=2),
            location="강의실",
            created_by=self.user,
            is_active=True,
        )
        edit_dt = timezone.localtime(session.datetime).replace(second=0, microsecond=0)
        response = self.client.post(
            reverse("signatures:edit", kwargs={"uuid": session.uuid}),
            data={
                "title": "초기 연수",
                "print_title": "",
                "instructor": "강사",
                "datetime": edit_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "강의실",
                "description": "",
                "shared_roster_group": str(self.group.id),
                "expected_count": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        session.refresh_from_db()
        self.assertEqual(session.shared_roster_group_id, self.group.id)
        self.assertEqual(session.expected_participants.count(), 2)

    def test_manual_sync_roster_adds_only_missing_expected_participants(self):
        session = TrainingSession.objects.create(
            title="수동 동기화 연수",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=3),
            location="강의실",
            created_by=self.user,
            shared_roster_group=self.group,
            is_active=True,
        )
        ExpectedParticipant.objects.create(
            training_session=session,
            name="김교사",
            affiliation="1-1",
        )

        response = self.client.post(reverse("signatures:sync_roster", kwargs={"uuid": session.uuid}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.expected_participants.count(), 2)
        response = self.client.post(reverse("signatures:sync_roster", kwargs={"uuid": session.uuid}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.expected_participants.count(), 2)

    def test_create_session_prefills_from_sheetbook_seed(self):
        seed_token = "signature-seed-1"
        session = self.client.session
        session["sheetbook_action_seeds"] = {
            seed_token: {
                "action": "signature",
                "data": {
                    "title": "2학년 일정 서명 요청",
                    "print_title": "2학년 참석 서명",
                    "instructor": "김담임",
                    "location": "시청각실",
                    "datetime": "2026-03-15T14:00",
                    "description": "교무수첩에서 가져온 서명 요청입니다.",
                    "expected_count": 2,
                    "participants_text": "김하늘,2-1\n박나래,2-2",
                },
            }
        }
        session.save()

        response = self.client.get(reverse("signatures:create"), data={"sb_seed": seed_token})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교무수첩 선택 칸을 가져왔어요")
        self.assertContains(response, "참석자 후보 2명")
        self.assertEqual(response.context["form"]["title"].value(), "2학년 일정 서명 요청")
        self.assertEqual(response.context["form"]["print_title"].value(), "2학년 참석 서명")
        self.assertEqual(response.context["form"]["instructor"].value(), "김담임")
        self.assertEqual(response.context["form"]["location"].value(), "시청각실")
        self.assertEqual(response.context["form"]["datetime"].value(), "2026-03-15T14:00")
        self.assertEqual(str(response.context["form"]["expected_count"].value()), "2")

    def test_create_session_sheetbook_seed_auto_adds_expected_participants(self):
        seed_token = "signature-seed-2"
        session = self.client.session
        session["sheetbook_action_seeds"] = {
            seed_token: {
                "action": "signature",
                "data": {
                    "participants_text": "김하늘,2-1\n박나래,2-2\n김하늘,2-1",
                },
            }
        }
        session.save()

        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        response = self.client.post(
            reverse("signatures:create"),
            data={
                "sheetbook_seed_token": seed_token,
                "apply_sheetbook_participants": "1",
                "title": "교무수첩 연동 서명",
                "print_title": "",
                "instructor": "강사",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "시청각실",
                "description": "",
                "shared_roster_group": "",
                "expected_count": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        created_session = TrainingSession.objects.get(title="교무수첩 연동 서명", created_by=self.user)
        participants = list(
            created_session.expected_participants.values_list("name", "affiliation").order_by("name")
        )
        self.assertEqual(participants, [("김하늘", "2-1"), ("박나래", "2-2")])

        refreshed_session = self.client.session
        self.assertNotIn(seed_token, refreshed_session.get("sheetbook_action_seeds", {}))
