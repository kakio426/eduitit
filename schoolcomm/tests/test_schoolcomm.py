from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent
from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from schoolcomm.models import (
    CalendarSuggestion,
    CommunityRoom,
    RoomMessage,
    SchoolMembership,
    StoredAssetBlob,
    UserAssetCategory,
    WorkspaceInvite,
)
from schoolcomm.services import (
    accept_invite,
    create_room_message,
    create_workspace_for_user,
    ensure_user_asset_category,
    get_default_room,
    get_or_create_dm_room,
    update_user_asset_category,
)


User = get_user_model()


class SchoolcommTestCase(TestCase):
    def create_user(self, username):
        user = User.objects.create_user(username=username, email=f"{username}@test.com", password="pw123456")
        user.userprofile.nickname = f"{username}-teacher"
        user.userprofile.role = "school"
        user.userprofile.save(update_fields=["nickname", "role"])
        UserPolicyConsent.objects.create(
            user=user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
        )
        return user


class SchoolcommServiceTests(SchoolcommTestCase):
    def setUp(self):
        self.owner = self.create_user("owner")
        self.member = self.create_user("member")
        self.member_two = self.create_user("membertwo")
        self.workspace, self.owner_membership = create_workspace_for_user(self.owner, name="테스트초")
        self.shared_room = get_default_room(self.workspace, CommunityRoom.RoomKind.SHARED)
        self.notice_room = get_default_room(self.workspace, CommunityRoom.RoomKind.NOTICE)
        self.member_membership = SchoolMembership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=SchoolMembership.Role.MEMBER,
            status=SchoolMembership.Status.ACTIVE,
            joined_at=timezone.now(),
            approved_by=self.owner,
        )
        self.member_two_membership = SchoolMembership.objects.create(
            workspace=self.workspace,
            user=self.member_two,
            role=SchoolMembership.Role.MEMBER,
            status=SchoolMembership.Status.ACTIVE,
            joined_at=timezone.now(),
            approved_by=self.owner,
        )
        for room in (self.shared_room, self.notice_room):
            room.participants.get_or_create(membership=self.member_membership)
            room.participants.get_or_create(membership=self.member_two_membership)

    def test_workspace_creation_creates_default_rooms(self):
        self.assertEqual(self.notice_room.name, "공지")
        self.assertEqual(self.shared_room.name, "자료공유")
        self.assertEqual(self.owner_membership.role, SchoolMembership.Role.OWNER)

    def test_dm_reuses_same_participant_signature(self):
        room_a = get_or_create_dm_room(
            self.workspace,
            [self.owner_membership, self.member_membership],
            created_by=self.owner,
        )
        room_b = get_or_create_dm_room(
            self.workspace,
            [self.member_membership, self.owner_membership],
            created_by=self.owner,
        )
        group_room = get_or_create_dm_room(
            self.workspace,
            [self.owner_membership, self.member_membership, self.member_two_membership],
            created_by=self.owner,
        )
        self.assertEqual(room_a.id, room_b.id)
        self.assertEqual(room_a.room_kind, CommunityRoom.RoomKind.DM)
        self.assertEqual(group_room.room_kind, CommunityRoom.RoomKind.GROUP_DM)

    def test_asset_dedup_and_manual_category_protection(self):
        upload_a = SimpleUploadedFile("2026_1학기_중간_수학.hwp", b"same-bytes", content_type="application/octet-stream")
        upload_b = SimpleUploadedFile("2026_1학기_중간_수학_복사.hwp", b"same-bytes", content_type="application/octet-stream")

        message_one = create_room_message(self.shared_room, self.owner_membership, text="평가 자료 올립니다", uploads=[upload_a])
        message_two = create_room_message(self.shared_room, self.owner_membership, text="다시 올립니다", uploads=[upload_b])

        self.assertEqual(StoredAssetBlob.objects.count(), 1)
        asset = message_one.asset_links.select_related("asset__blob").first().asset
        manual_category = update_user_asset_category(self.owner, asset, "work")
        refreshed = ensure_user_asset_category(self.owner, asset, message_text="평가 자료", room_kind=self.shared_room.room_kind)
        self.assertEqual(manual_category.id, refreshed.id)
        self.assertEqual(refreshed.category, UserAssetCategory.Category.WORK)
        self.assertNotEqual(message_one.id, message_two.id)

    def test_thread_depth_is_single_level(self):
        parent = create_room_message(self.shared_room, self.owner_membership, text="상위 메시지")
        reply = create_room_message(self.shared_room, self.member_membership, text="답글", parent_message=parent)
        with self.assertRaises(Exception):
            create_room_message(self.shared_room, self.member_membership, text="중첩 답글", parent_message=reply)


class SchoolcommViewTests(SchoolcommTestCase):
    def setUp(self):
        self.owner = self.create_user("leader")
        self.member = self.create_user("teacher")
        self.outsider = self.create_user("outsider")
        self.workspace, self.owner_membership = create_workspace_for_user(self.owner, name="열린초")
        self.shared_room = get_default_room(self.workspace, CommunityRoom.RoomKind.SHARED)
        self.notice_room = get_default_room(self.workspace, CommunityRoom.RoomKind.NOTICE)
        self.member_membership = SchoolMembership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=SchoolMembership.Role.MEMBER,
            status=SchoolMembership.Status.ACTIVE,
            joined_at=timezone.now(),
            approved_by=self.owner,
        )
        for room in (self.shared_room, self.notice_room):
            room.participants.get_or_create(membership=self.member_membership)

    def test_invite_accept_and_approve_flow(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("schoolcomm:api_create_invite"),
            {"workspace_id": str(self.workspace.id), "role": "member"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        invite_url = response.json()["invite"]["url"]
        token = invite_url.rstrip("/").split("/")[-1]
        invite = WorkspaceInvite.objects.get(token=token)

        pending_membership = accept_invite(invite, self.outsider)
        self.assertEqual(pending_membership.status, SchoolMembership.Status.PENDING)

        self.client.force_login(self.owner)
        self.client.post(reverse("schoolcomm:api_approve_membership", kwargs={"membership_id": pending_membership.id}))
        pending_membership.refresh_from_db()
        invite.refresh_from_db()
        self.assertEqual(pending_membership.status, SchoolMembership.Status.ACTIVE)
        self.assertEqual(invite.status, WorkspaceInvite.Status.ACCEPTED)

    def test_room_post_updates_notifications(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("schoolcomm:api_room_messages", kwargs={"room_id": self.shared_room.id}),
            {"text": "4월 10일 15:00 교무회의"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        self.client.force_login(self.member)
        summary = self.client.get(reverse("schoolcomm:api_notifications_summary"))
        self.assertEqual(summary.status_code, 200)
        self.assertGreaterEqual(summary.json()["summary"]["total_unread"], 1)

    def test_room_fragment_refresh_returns_partial_content(self):
        create_room_message(self.shared_room, self.owner_membership, text="자료 확인 부탁드립니다")

        self.client.force_login(self.member)
        response = self.client.get(
            reverse("schoolcomm:room_detail", kwargs={"room_id": self.shared_room.id}),
            {"fragment": "content"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "schoolcomm/partials/room_content.html")
        self.assertContains(response, 'data-schoolcomm-thread-panel="')
        self.assertNotContains(response, "<html", html=False)

    def test_search_is_scoped_to_workspace(self):
        other_owner = self.create_user("otherowner")
        other_workspace, other_membership = create_workspace_for_user(other_owner, name="다른학교")
        other_shared_room = get_default_room(other_workspace, CommunityRoom.RoomKind.SHARED)
        create_room_message(other_shared_room, other_membership, text="숨겨야 하는 파일")
        create_room_message(self.shared_room, self.owner_membership, text="우리 학교 회의록")

        self.client.force_login(self.owner)
        response = self.client.get(reverse("schoolcomm:api_search"), {"workspace": str(self.workspace.id), "q": "회의록"})
        payload = response.json()
        message_bodies = [item["body"] for item in payload["messages"]]
        self.assertIn("우리 학교 회의록", message_bodies)
        self.assertNotIn("숨겨야 하는 파일", message_bodies)

    def test_invite_accept_page_shows_pending_state_message(self):
        invite = WorkspaceInvite.objects.create(
            workspace=self.workspace,
            invited_by=self.owner,
            role=SchoolMembership.Role.MEMBER,
            token="pending-invite-token",
        )
        accept_invite(invite, self.outsider)

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("schoolcomm:invite_accept", kwargs={"token": invite.token}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "승인 기다리는 중입니다.")
        self.assertContains(response, "대기 상태 확인")

    def test_calendar_suggestion_apply_creates_event_only_on_apply(self):
        message = RoomMessage.objects.create(
            room=self.shared_room,
            sender=self.owner,
            sender_membership=self.owner_membership,
            sender_name_snapshot=self.owner.username,
            sender_membership_snapshot=self.owner_membership.role,
            body="일정 추천 메시지",
        )
        suggestion = CalendarSuggestion.objects.create(
            user=self.owner,
            source_message=message,
            suggested_payload={
                "title": "교무회의",
                "start_time": "2026-04-10T15:00:00+09:00",
                "end_time": "2026-04-10T16:00:00+09:00",
                "is_all_day": False,
                "note": "회의실 A",
            },
        )
        self.assertEqual(CalendarEvent.objects.count(), 0)

        self.client.force_login(self.owner)
        response = self.client.post(reverse("schoolcomm:api_apply_calendar_suggestion", kwargs={"suggestion_id": suggestion.id}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CalendarEvent.objects.count(), 1)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, CalendarSuggestion.Status.APPLIED)
