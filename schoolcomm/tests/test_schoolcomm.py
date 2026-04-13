import re
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from classcalendar.models import CalendarEvent
from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from schoolcomm.models import (
    CalendarSuggestion,
    CommunityRoom,
    RoomMessage,
    SchoolMembership,
    SharedCalendarEvent,
    SharedCalendarEventCopy,
    StoredAssetBlob,
    UserAssetCategory,
    WorkspaceInvite,
)
from schoolcomm.services import (
    create_room_message,
    create_shared_calendar_event,
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

    def test_auto_category_detects_social_assets_from_filename_and_message(self):
        upload = SimpleUploadedFile("친목_간식_정산.xlsx", b"social-bytes", content_type="application/octet-stream")

        message = create_room_message(self.shared_room, self.owner_membership, text="간식비 정리 파일", uploads=[upload])
        asset = message.asset_links.select_related("asset__blob").first().asset

        category = ensure_user_asset_category(
            self.member,
            asset,
            message_text=message.body,
            room_kind=self.shared_room.room_kind,
        )

        self.assertEqual(category.category, "social")


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

    def test_invite_accept_links_member_directly_into_workspace(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("schoolcomm:api_create_invite"),
            {"workspace_id": str(self.workspace.id), "role": "member"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        invite_url = response.json()["invite"]["url"]
        token = invite_url.rstrip("/").split("/")[-1]
        invite = WorkspaceInvite.objects.get(token=token)

        self.client.force_login(self.outsider)
        accept_response = self.client.post(reverse("schoolcomm:invite_accept", kwargs={"token": token}))
        self.assertEqual(accept_response.status_code, 302)
        self.assertEqual(accept_response["Location"], f"{reverse('schoolcomm:main')}?workspace={self.workspace.id}")

        membership = SchoolMembership.objects.get(workspace=self.workspace, user=self.outsider)
        invite.refresh_from_db()
        self.assertEqual(membership.status, SchoolMembership.Status.ACTIVE)
        self.assertEqual(invite.status, WorkspaceInvite.Status.ACCEPTED)
        self.assertTrue(self.notice_room.participants.filter(membership=membership).exists())
        self.assertTrue(self.shared_room.participants.filter(membership=membership).exists())

    def test_room_post_updates_notifications(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("schoolcomm:api_room_messages", kwargs={"room_id": self.shared_room.id}),
            {"text": "4월 10일 15:00 교무회의"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["message"]["body"], "4월 10일 15:00 교무회의")

        self.client.force_login(self.member)
        summary = self.client.get(reverse("schoolcomm:api_notifications_summary"))
        self.assertEqual(summary.status_code, 200)
        self.assertGreaterEqual(summary.json()["summary"]["total_unread"], 1)

    def test_chat_room_ajax_post_returns_json_without_redirect(self):
        dm_room = get_or_create_dm_room(
            self.workspace,
            [self.owner_membership, self.member_membership],
            created_by=self.owner,
        )

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("schoolcomm:api_room_messages", kwargs={"room_id": dm_room.id}),
            {"text": "채팅 바로 보내기"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["message"]["body"], "채팅 바로 보내기")
        self.assertEqual(payload["message"]["room_id"], str(dm_room.id))

    def test_room_fragment_refresh_returns_partial_content(self):
        create_room_message(self.shared_room, self.owner_membership, text="자료 확인 부탁드립니다")

        self.client.force_login(self.member)
        response = self.client.get(
            reverse("schoolcomm:room_detail", kwargs={"room_id": self.shared_room.id}),
            {"fragment": "content"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "schoolcomm/partials/room_content.html")
        self.assertContains(response, 'data-schoolcomm-shared-board="true"')
        self.assertContains(response, 'data-schoolcomm-thread-panel="')
        self.assertNotContains(response, "<html", html=False)

    def test_shared_room_detail_prioritizes_info_board_over_thread_feed(self):
        lesson_upload = SimpleUploadedFile("3학년_수업_활동지.hwp", b"lesson", content_type="application/octet-stream")
        social_upload = SimpleUploadedFile("친목_간식_공지.xlsx", b"social", content_type="application/octet-stream")
        parent = create_room_message(self.shared_room, self.owner_membership, text="수업 자료 올립니다", uploads=[lesson_upload])
        create_room_message(self.shared_room, self.member_membership, text="간식비 정리입니다", parent_message=parent, uploads=[social_upload])

        self.client.force_login(self.owner)
        response = self.client.get(reverse("schoolcomm:room_detail", kwargs={"room_id": self.shared_room.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-schoolcomm-shared-board="true"')
        self.assertContains(response, "자료 올리기")
        self.assertContains(response, "수업")
        self.assertContains(response, "친목")
        self.assertContains(response, "대화")
        self.assertContains(response, "자료 1개 보기")
        self.assertNotContains(response, "확인 0")
        self.assertNotContains(response, "이 글 아래에서만 이어집니다.")
        self.assertNotContains(response, "올라온 자료")

    def test_shared_room_filter_keeps_category_during_fragment_refresh(self):
        social_upload = SimpleUploadedFile("친목_다과_목록.xlsx", b"social", content_type="application/octet-stream")
        create_room_message(self.shared_room, self.owner_membership, text="다과 목록", uploads=[social_upload])

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:room_detail", kwargs={"room_id": self.shared_room.id}),
            {"category": "social"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "category=social&amp;fragment=content")

    def test_dm_room_renders_chat_style_stream_and_reply_composer(self):
        dm_room = get_or_create_dm_room(
            self.workspace,
            [self.owner_membership, self.member_membership],
            created_by=self.owner,
        )
        parent = create_room_message(dm_room, self.owner_membership, text="안녕하세요")
        create_room_message(dm_room, self.member_membership, text="네 확인했어요", parent_message=parent)

        self.client.force_login(self.owner)
        response = self.client.get(reverse("schoolcomm:room_detail", kwargs={"room_id": dm_room.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-schoolcomm-chat-room="true"')
        self.assertContains(response, 'data-schoolcomm-chat-composer="true"')
        self.assertContains(response, 'data-schoolcomm-chat-reply-trigger="true"')
        self.assertContains(response, 'data-schoolcomm-chat-parent-input="true"')
        self.assertNotContains(response, "카카오톡처럼 이어지는 대화 흐름")
        self.assertNotContains(response, "확인 0")
        self.assertNotContains(response, 'data-schoolcomm-thread-panel="')

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

    def test_invite_accept_page_promises_direct_entry(self):
        invite = WorkspaceInvite.objects.create(
            workspace=self.workspace,
            invited_by=self.owner,
            role=SchoolMembership.Role.MEMBER,
            token="direct-invite-token",
        )

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("schoolcomm:invite_accept", kwargs={"token": invite.token}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "초대 링크를 받은 사람만 바로 들어올 수 있어요.")
        self.assertContains(response, "초대 수락 후 바로 입장")
        self.assertNotContains(response, "승인 기다리는 중입니다.")

    def test_main_empty_state_focuses_on_chat_room_name_and_direct_link_entry(self):
        starter = self.create_user("starter")
        self.client.force_login(starter)

        response = self.client.get(reverse("schoolcomm:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "채팅방 이름")
        self.assertContains(response, "시작 흐름")
        self.assertContains(response, "초대한 사람만 입장")
        self.assertNotContains(response, "학교 이름")
        self.assertNotContains(response, "학년도")
        self.assertNotContains(response, "승인 기다리는 학교")

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
        self.assertEqual(SharedCalendarEvent.objects.count(), 0)

        self.client.force_login(self.owner)
        response = self.client.post(reverse("schoolcomm:api_apply_calendar_suggestion", kwargs={"suggestion_id": suggestion.id}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CalendarEvent.objects.count(), 0)
        self.assertEqual(SharedCalendarEvent.objects.count(), 1)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, CalendarSuggestion.Status.APPLIED)

    def test_shared_calendar_copy_to_main_reuses_existing_personal_copy(self):
        shared_event = create_shared_calendar_event(
            self.workspace,
            self.owner_membership,
            title="학년 협의",
            note="자료 확인",
            start_time=timezone.make_aware(datetime(2026, 4, 10, 15, 0)),
            end_time=timezone.make_aware(datetime(2026, 4, 10, 16, 0)),
            color="emerald",
        )

        self.client.force_login(self.owner)
        first = self.client.post(
            reverse("schoolcomm:api_shared_calendar_event_copy_to_main", kwargs={"event_id": shared_event.id}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        second = self.client.post(
            reverse("schoolcomm:api_shared_calendar_event_copy_to_main", kwargs={"event_id": shared_event.id}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(CalendarEvent.objects.count(), 1)
        self.assertEqual(SharedCalendarEventCopy.objects.count(), 1)
        self.assertTrue(first.json()["created"])
        self.assertFalse(second.json()["created"])

    def test_shared_calendar_copy_can_recreate_after_personal_event_deleted(self):
        shared_event = create_shared_calendar_event(
            self.workspace,
            self.owner_membership,
            title="수업 공개",
            note="복사 테스트",
            start_time=timezone.make_aware(datetime(2026, 4, 12, 9, 0)),
            end_time=timezone.make_aware(datetime(2026, 4, 12, 10, 0)),
            color="sky",
        )

        self.client.force_login(self.owner)
        first = self.client.post(
            reverse("schoolcomm:api_shared_calendar_event_copy_to_main", kwargs={"event_id": shared_event.id}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        first_event_id = first.json()["event"]["id"]
        CalendarEvent.objects.get(id=first_event_id).delete()

        second = self.client.post(
            reverse("schoolcomm:api_shared_calendar_event_copy_to_main", kwargs={"event_id": shared_event.id}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["created"])
        self.assertEqual(CalendarEvent.objects.count(), 1)
        self.assertNotEqual(first_event_id, second.json()["event"]["id"])

    def test_shared_calendar_update_does_not_change_existing_personal_copy(self):
        shared_event = create_shared_calendar_event(
            self.workspace,
            self.owner_membership,
            title="원본 일정",
            note="원본 메모",
            start_time=timezone.make_aware(datetime(2026, 4, 14, 13, 0)),
            end_time=timezone.make_aware(datetime(2026, 4, 14, 14, 0)),
            color="amber",
        )

        self.client.force_login(self.owner)
        copy_response = self.client.post(
            reverse("schoolcomm:api_shared_calendar_event_copy_to_main", kwargs={"event_id": shared_event.id}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        copied_event = CalendarEvent.objects.get(id=copy_response.json()["event"]["id"])

        update_response = self.client.post(
            reverse("schoolcomm:api_shared_calendar_event_update", kwargs={"event_id": shared_event.id}),
            {
                "title": "바뀐 원본 일정",
                "note": "바뀐 메모",
                "start_time": "2026-04-14T15:00",
                "end_time": "2026-04-14T16:00",
                "color": "rose",
                "redirect_month": "2026-04",
                "redirect_date": "2026-04-14",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(update_response.status_code, 200)
        copied_event.refresh_from_db()
        self.assertEqual(copied_event.title, "원본 일정")
        self.assertEqual(copied_event.color, "amber")

    def test_main_falls_back_to_unavailable_state_when_database_error_occurs(self):
        self.client.force_login(self.owner)

        with patch("schoolcomm.views._resolve_workspace", side_effect=DatabaseError("db unavailable")):
            response = self.client.get(reverse("schoolcomm:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "끼리끼리 채팅방")
        self.assertContains(response, "지금은 채팅방을 준비하는 중입니다.")

    def test_notifications_api_returns_503_when_database_error_occurs(self):
        self.client.force_login(self.owner)

        with patch("schoolcomm.views._resolve_workspace", side_effect=DatabaseError("db unavailable")):
            response = self.client.get(reverse("schoolcomm:api_notifications_summary"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "service_unavailable")

    def test_main_renders_shared_calendar_tab_contents(self):
        create_shared_calendar_event(
            self.workspace,
            self.owner_membership,
            title="주간 협의",
            note="달력 노출",
            start_time=timezone.make_aware(datetime(2026, 4, 20, 14, 0)),
            end_time=timezone.make_aware(datetime(2026, 4, 20, 15, 0)),
            color="indigo",
        )

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:main"),
            {
                "workspace": str(self.workspace.id),
                "calendar_tab": "shared",
                "calendar_month": "2026-04",
                "calendar_date": "2026-04-20",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "끼리끼리 캘린더")
        self.assertContains(response, "내 메인 캘린더로 보내기")
        self.assertContains(response, "내 캘린더에서는 독립 일정으로 관리됩니다.")

    def test_calendar_panel_fragment_returns_partial_markup(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:main"),
            {
                "workspace": str(self.workspace.id),
                "calendar_tab": "shared",
                "calendar_month": "2026-05",
                "calendar_date": "2026-05-02",
                "fragment": "calendar_panel",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "schoolcomm/partials/calendar_panel.html")
        self.assertContains(response, 'data-schoolcomm-calendar-panel="true"')
        self.assertContains(response, 'data-schoolcomm-calendar-link="true"')
        self.assertNotContains(response, "<html", html=False)

    def test_shared_calendar_keeps_requested_date_inside_month(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:main"),
            {
                "workspace": str(self.workspace.id),
                "calendar_tab": "shared",
                "calendar_month": "2026-05",
                "calendar_date": "2026-05-02",
            },
        )

        self.assertEqual(response.context["shared_calendar"]["selected_date"], "2026-05-02")

    def test_shared_calendar_normalizes_out_of_month_date_to_first_day(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:main"),
            {
                "workspace": str(self.workspace.id),
                "calendar_tab": "shared",
                "calendar_month": "2026-05",
                "calendar_date": "2026-04-20",
            },
        )

        self.assertEqual(response.context["shared_calendar"]["selected_date"], "2026-05-01")

    def test_calendar_links_preserve_query_and_anchor(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:main"),
            {
                "workspace": str(self.workspace.id),
                "q": "meeting",
                "calendar_tab": "shared",
                "calendar_month": "2026-05",
                "calendar_date": "2026-05-02",
            },
        )

        content = response.content.decode("utf-8")
        match = re.search(r'<a[^>]*href="([^"]+)"[^>]*data-schoolcomm-calendar-key="tab-shared"', content)

        self.assertIsNotNone(match)
        self.assertIn(f"workspace={self.workspace.id}", match.group(1))
        self.assertIn("q=meeting", match.group(1))
        self.assertIn("calendar_tab=shared", match.group(1))
        self.assertTrue(match.group(1).endswith("#calendar-panel"))
        self.assertContains(response, 'name="redirect_query" value="meeting"')

    def test_calendar_async_link_contract_is_limited_to_tabs_months_and_days(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:main"),
            {
                "workspace": str(self.workspace.id),
                "calendar_tab": "shared",
                "calendar_month": "2026-05",
                "calendar_date": "2026-05-02",
            },
        )

        expected_count = len(response.context["shared_calendar"]["days"]) + 4
        self.assertEqual(response.content.decode("utf-8").count('data-schoolcomm-calendar-link="true"'), expected_count)

    def test_muted_calendar_day_link_targets_clicked_day_month(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schoolcomm:main"),
            {
                "workspace": str(self.workspace.id),
                "calendar_tab": "shared",
                "calendar_month": "2026-04",
                "calendar_date": "2026-04-20",
            },
        )

        muted_day = next(day for day in response.context["shared_calendar"]["days"] if not day["is_current_month"])
        content = response.content.decode("utf-8")
        match = re.search(
            rf'<a[^>]*href="([^"]+)"[^>]*data-schoolcomm-calendar-key="day-{re.escape(muted_day["date"])}"',
            content,
        )

        self.assertIsNotNone(match)
        self.assertIn(f'calendar_month={muted_day["date"][:7]}', match.group(1))
        self.assertIn(f'calendar_date={muted_day["date"]}', match.group(1))
        self.assertTrue(match.group(1).endswith("#calendar-panel"))

    def test_calendar_js_uses_fragment_refresh_contract(self):
        js_path = Path(settings.BASE_DIR) / "schoolcomm" / "static" / "schoolcomm" / "schoolcomm.js"
        source = js_path.read_text(encoding="utf-8")

        self.assertIn('[data-schoolcomm-calendar-link="true"]', source)
        self.assertIn("fragment', 'calendar_panel'", source)
        self.assertIn('data-schoolcomm-calendar-key', source)

    def test_chat_js_uses_reply_target_contract(self):
        js_path = Path(settings.BASE_DIR) / "schoolcomm" / "static" / "schoolcomm" / "schoolcomm.js"
        source = js_path.read_text(encoding="utf-8")

        self.assertIn('[data-schoolcomm-chat-reply-trigger="true"]', source)
        self.assertIn('[data-schoolcomm-chat-parent-input="true"]', source)
        self.assertIn('setChatReplyState', source)
