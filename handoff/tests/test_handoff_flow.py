from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from handoff.models import HandoffReceipt, HandoffRosterGroup, HandoffRosterMember, HandoffSession


class HandoffFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", email="teacher@example.com", password="pw123456")
        profile = self.user.userprofile
        profile.nickname = "담임선생님"
        profile.save(update_fields=["nickname"])
        self.client.force_login(self.user)

    def _create_group_with_members(self):
        group = HandoffRosterGroup.objects.create(owner=self.user, name="전교무")
        member1 = HandoffRosterMember.objects.create(group=group, display_name="김민수", sort_order=1, is_active=True)
        member2 = HandoffRosterMember.objects.create(group=group, display_name="이서연", sort_order=2, is_active=True)
        member3 = HandoffRosterMember.objects.create(group=group, display_name="박지훈", sort_order=3, is_active=False)
        return group, [member1, member2, member3]

    def _create_session(self, group, members):
        session = HandoffSession.objects.create(
            owner=self.user,
            roster_group=group,
            roster_group_name=group.name,
            title="교무실 전달 자료",
        )
        HandoffReceipt.objects.bulk_create(
            [
                HandoffReceipt(
                    session=session,
                    member=member,
                    member_name_snapshot=member.display_name,
                    member_order_snapshot=member.sort_order,
                )
                for member in members
                if member.is_active
            ]
        )
        return session

    def test_group_and_member_crud(self):
        create_response = self.client.post(
            reverse("handoff:group_create"),
            data={
                "name": "1학년 담임",
                "description": "배부 체크용",
                "is_favorite": "on",
            },
        )
        group = HandoffRosterGroup.objects.get(owner=self.user, name="1학년 담임")
        self.assertRedirects(create_response, reverse("handoff:group_detail", args=[group.id]))

        add_response = self.client.post(
            reverse("handoff:group_members_add", args=[group.id]),
            data={"names_text": "김민수, 3-1\n이서연, 교감\n이서연, 교감\n"},
        )
        self.assertRedirects(add_response, reverse("handoff:group_detail", args=[group.id]))
        self.assertEqual(group.members.count(), 2)
        self.assertEqual(group.members.get(display_name="김민수").affiliation, "3-1")
        self.assertEqual(group.members.get(display_name="이서연").affiliation, "교감")

        member = group.members.first()
        update_response = self.client.post(
            reverse("handoff:group_member_update", args=[group.id, member.id]),
            data={
                "display_name": "김민수A",
                "note": "대리 수령 잦음",
            },
        )
        self.assertRedirects(update_response, reverse("handoff:group_detail", args=[group.id]))
        member.refresh_from_db()
        self.assertEqual(member.display_name, "김민수A")
        self.assertEqual(member.note, "대리 수령 잦음")
        self.assertFalse(member.is_active)

        delete_response = self.client.post(reverse("handoff:group_member_delete", args=[group.id, member.id]))
        self.assertRedirects(delete_response, reverse("handoff:group_detail", args=[group.id]))
        self.assertEqual(group.members.count(), 1)

    def test_bulk_add_allows_same_name_when_affiliation_differs(self):
        group = HandoffRosterGroup.objects.create(owner=self.user, name="중복 이름 명단")

        response = self.client.post(
            reverse("handoff:group_members_add", args=[group.id]),
            data={
                "names_text": "김민수, 1-1\n김민수, 1-2\n김민수, 1-1\n",
            },
        )

        self.assertRedirects(response, reverse("handoff:group_detail", args=[group.id]))
        members = list(group.members.order_by("sort_order").values_list("display_name", "affiliation"))
        self.assertEqual(
            members,
            [("김민수", "1-1"), ("김민수", "1-2")],
        )

    def test_group_members_upload_csv_supports_header_and_cp949(self):
        group = HandoffRosterGroup.objects.create(owner=self.user, name="CSV 명단")
        csv_content = (
            "이름,직위/학년반,작성 예시\n"
            ",,왼쪽 두 칸만 채우세요\n"
            ",,예: 김민수 / 3-1\n"
            "김민수,3-1,\n"
            "이서연,교감,\n"
            "김민수,3-1,\n"
            "김민수,3-2,\n"
        )
        upload = SimpleUploadedFile(
            "members.csv",
            csv_content.encode("cp949"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("handoff:group_members_upload", args=[group.id]),
            data={"csv_file": upload},
        )

        self.assertRedirects(response, reverse("handoff:group_detail", args=[group.id]))
        members = list(group.members.order_by("sort_order").values_list("display_name", "affiliation"))
        self.assertEqual(
            members,
            [("김민수", "3-1"), ("이서연", "교감"), ("김민수", "3-2")],
        )

        second_upload = SimpleUploadedFile(
            "members.csv",
            csv_content.encode("utf-8-sig"),
            content_type="text/csv",
        )
        second_response = self.client.post(
            reverse("handoff:group_members_upload", args=[group.id]),
            data={"csv_file": second_upload},
        )
        self.assertRedirects(second_response, reverse("handoff:group_detail", args=[group.id]))
        self.assertEqual(group.members.count(), 3)

    def test_group_members_template_download_includes_examples(self):
        group = HandoffRosterGroup.objects.create(owner=self.user, name="양식 명단")

        response = self.client.get(reverse("handoff:group_members_template_download", args=[group.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("이름,소속/학년반,보호자명,연락처 뒤 4자리,번호,메모", content)
        self.assertIn("김민수,3-1,김민수 보호자,5678,1,동의서/행복씨앗 같이 사용", content)
        self.assertIn("박지훈,교감,,,,사인/배부 체크용", content)

    def test_return_to_is_preserved_for_group_creation_and_member_updates(self):
        return_to = "/signatures/create/?draft_token=testdraft"
        create_response = self.client.post(
            reverse("handoff:group_create"),
            data={
                "name": "서명 복귀 명단",
                "description": "",
                "return_to": return_to,
            },
        )

        group = HandoffRosterGroup.objects.get(owner=self.user, name="서명 복귀 명단")
        self.assertRedirects(
            create_response,
            f"{reverse('handoff:group_detail', args=[group.id])}?return_to=%2Fsignatures%2Fcreate%2F%3Fdraft_token%3Dtestdraft",
        )

        detail_response = self.client.get(
            reverse("handoff:group_detail", args=[group.id]),
            data={"return_to": return_to},
        )
        self.assertContains(detail_response, "활성 멤버를 먼저 넣어야 연결할 수 있습니다")
        self.assertNotContains(
            detail_response,
            f"{return_to}&amp;shared_roster_group={group.id}",
            html=False,
        )
        dashboard_response = self.client.get(reverse("handoff:dashboard"), data={"return_to": return_to})
        self.assertNotContains(dashboard_response, f"{return_to}&amp;shared_roster_group={group.id}", html=False)

        add_response = self.client.post(
            reverse("handoff:group_members_add", args=[group.id]),
            data={
                "names_text": "김민수",
                "return_to": return_to,
            },
        )
        self.assertRedirects(
            add_response,
            f"{reverse('handoff:group_detail', args=[group.id])}?return_to=%2Fsignatures%2Fcreate%2F%3Fdraft_token%3Dtestdraft",
        )

        detail_response = self.client.get(
            reverse("handoff:group_detail", args=[group.id]),
            data={"return_to": return_to},
        )
        self.assertContains(
            detail_response,
            f"{return_to}&amp;shared_roster_group={group.id}",
            html=False,
        )
        dashboard_response = self.client.get(reverse("handoff:dashboard"), data={"return_to": return_to})
        self.assertContains(
            dashboard_response,
            f"{return_to}&amp;shared_roster_group={group.id}",
            html=False,
        )

    def test_external_return_to_is_ignored(self):
        response = self.client.post(
            reverse("handoff:group_create"),
            data={
                "name": "외부 복귀 차단 명단",
                "description": "",
                "return_to": "https://evil.example.com/phish",
            },
        )

        group = HandoffRosterGroup.objects.get(owner=self.user, name="외부 복귀 차단 명단")
        self.assertRedirects(response, reverse("handoff:group_detail", args=[group.id]))

    def test_session_create_generates_receipts_for_active_members(self):
        group, _ = self._create_group_with_members()
        response = self.client.post(
            reverse("handoff:session_create"),
            data={
                "title": "3월 회의자료",
                "roster_group": str(group.id),
                "note": "",
            },
        )

        session = HandoffSession.objects.get(owner=self.user, title="3월 회의자료")
        self.assertRedirects(response, reverse("handoff:session_detail", args=[session.id]))
        self.assertEqual(session.receipts.count(), 2)
        self.assertEqual(session.receipts.filter(state="pending").count(), 2)

    def test_landing_shows_open_session_instead_of_redirecting(self):
        group, members = self._create_group_with_members()
        session = self._create_session(group, members)

        response = self.client.get(reverse("handoff:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내 명부 선택")
        self.assertContains(response, session.title)
        self.assertContains(response, reverse("handoff:session_detail", args=[session.id]))
        self.assertContains(response, f"{reverse('handoff:group_detail', args=[group.id])}#start-session", html=False)

    def test_landing_shows_roster_selection_cards_when_no_open_session(self):
        group, members = self._create_group_with_members()
        second_group = HandoffRosterGroup.objects.create(
            owner=self.user,
            name="학년부 명부",
            is_favorite=True,
        )
        HandoffRosterMember.objects.create(
            group=second_group,
            display_name="최지원",
            sort_order=1,
            is_active=True,
        )
        closed_session = self._create_session(group, members)
        closed_session.status = "closed"
        closed_session.save(update_fields=["status"])

        response = self.client.get(reverse("handoff:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내 명부 선택")
        self.assertContains(response, "이 명부로 배부 시작")
        self.assertContains(response, group.name)
        self.assertContains(response, second_group.name)
        self.assertContains(response, f"{reverse('handoff:group_detail', args=[group.id])}#start-session", html=False)
        self.assertContains(
            response,
            f"{reverse('handoff:group_detail', args=[second_group.id])}#start-session",
            html=False,
        )
        self.assertNotContains(response, "명부에서 바로 시작")

    def test_dashboard_is_roster_first_and_group_detail_owns_sessions(self):
        group, members = self._create_group_with_members()
        session = self._create_session(group, members)

        dashboard_response = self.client.get(reverse("handoff:dashboard"))
        self.assertContains(dashboard_response, "공용 명부 목록")
        self.assertNotContains(dashboard_response, "최근 배부 세션")
        self.assertNotContains(dashboard_response, "배부 세션 시작")
        self.assertContains(dashboard_response, "진행 중 세션 이어하기")

        detail_response = self.client.get(reverse("handoff:group_detail", args=[group.id]))
        self.assertContains(detail_response, "이 명부로 배부 체크 시작")
        self.assertContains(detail_response, "이 명부의 최근 배부 세션")
        self.assertContains(detail_response, session.title)

    def test_invalid_session_create_returns_to_group_detail(self):
        group, _ = self._create_group_with_members()

        response = self.client.post(
            reverse("handoff:session_create"),
            data={
                "title": "",
                "roster_group": str(group.id),
                "note": "",
            },
        )

        self.assertRedirects(response, reverse("handoff:group_detail", args=[group.id]))

    def test_receipt_state_update_json(self):
        group, members = self._create_group_with_members()
        session = self._create_session(group, members)
        receipt = session.receipts.first()

        response = self.client.post(
            reverse("handoff:receipt_set_state", args=[session.id, receipt.id]),
            data={"state": "received"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["receipt"]["state"], "received")
        self.assertEqual(payload["counts"]["received"], 1)

        receipt.refresh_from_db()
        self.assertEqual(receipt.state, "received")

        revert_response = self.client.post(
            reverse("handoff:receipt_set_state", args=[session.id, receipt.id]),
            data={"state": "pending"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(revert_response.status_code, 200)
        receipt.refresh_from_db()
        self.assertEqual(receipt.state, "pending")

    def test_group_delete_keeps_session_snapshot(self):
        group, members = self._create_group_with_members()
        session = self._create_session(group, members)

        response = self.client.post(reverse("handoff:group_delete", args=[group.id]))
        self.assertRedirects(response, reverse("handoff:dashboard"))
        self.assertFalse(HandoffRosterGroup.objects.filter(id=group.id).exists())

        session.refresh_from_db()
        self.assertIsNone(session.roster_group)
        self.assertEqual(session.roster_group_name, "전교무")

    def test_closed_session_blocks_receipt_update(self):
        group, members = self._create_group_with_members()
        session = self._create_session(group, members)
        session.status = "closed"
        session.save(update_fields=["status"])
        receipt = session.receipts.first()

        response = self.client.post(
            reverse("handoff:receipt_set_state", args=[session.id, receipt.id]),
            data={"state": "received"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_session_edit_and_delete(self):
        group, members = self._create_group_with_members()
        session = self._create_session(group, members)

        edit_response = self.client.post(
            reverse("handoff:session_edit", args=[session.id]),
            data={
                "title": "수정된 제목",
                "due_at": "",
                "note": "수정 메모",
            },
        )
        self.assertRedirects(edit_response, reverse("handoff:session_detail", args=[session.id]))
        session.refresh_from_db()
        self.assertEqual(session.title, "수정된 제목")

        delete_response = self.client.post(reverse("handoff:session_delete", args=[session.id]))
        self.assertRedirects(delete_response, reverse("handoff:dashboard"))
        self.assertFalse(HandoffSession.objects.filter(id=session.id).exists())


class HandoffProxyRosterTests(TestCase):
    def setUp(self):
        self.kakio = User.objects.create_superuser(
            username="kakio",
            email="kakio@example.com",
            password="pw123456",
        )
        self.other_admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pw123456",
        )
        self.teacher = User.objects.create_user(
            username="teacher_proxy",
            email="teacher_proxy@example.com",
            password="pw123456",
        )
        for user, nickname in (
            (self.kakio, "카키오"),
            (self.other_admin, "다른관리자"),
            (self.teacher, "김선생"),
        ):
            profile = user.userprofile
            profile.nickname = nickname
            profile.role = "school"
            profile.save(update_fields=["nickname", "role"])
        for user in (self.kakio, self.other_admin):
            UserPolicyConsent.objects.create(
                user=user,
                provider="direct",
                terms_version=TERMS_VERSION,
                privacy_version=PRIVACY_VERSION,
                agreed_at=user.date_joined,
                agreement_source="required_gate",
            )

    def test_only_kakio_sees_proxy_roster_controls(self):
        self.client.force_login(self.kakio)

        response = self.client.get(reverse("handoff:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교사 대신 공용 명부를 만들어 넣을 수 있습니다.")
        self.assertContains(response, 'name="acting_for_user"', html=False)

        self.client.force_login(self.other_admin)

        response = self.client.get(reverse("handoff:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "교사 대신 공용 명부를 만들어 넣을 수 있습니다.")
        self.assertNotContains(response, 'name="acting_for_user"', html=False)

    def test_only_kakio_sees_proxy_roster_controls_on_landing(self):
        self.client.force_login(self.kakio)

        response = self.client.get(reverse("handoff:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "다른 선생님 명부 넣어주기")
        self.assertContains(response, 'name="acting_for_user"', html=False)

        self.client.force_login(self.other_admin)

        response = self.client.get(reverse("handoff:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "다른 선생님 명부 넣어주기")
        self.assertNotContains(response, 'name="acting_for_user"', html=False)

    def test_kakio_can_create_teacher_owned_roster_and_teacher_can_use_it(self):
        self.client.force_login(self.kakio)

        create_response = self.client.post(
            reverse("handoff:group_create"),
            data={
                "name": "3학년 2반 공용 명부",
                "description": "운영자가 대신 준비",
                "acting_for_user": str(self.teacher.id),
            },
            follow=True,
        )

        self.assertEqual(create_response.status_code, 200)
        group = HandoffRosterGroup.objects.get(owner=self.teacher, name="3학년 2반 공용 명부")
        self.assertContains(create_response, "김선생 선생님 계정에 만들었습니다.")

        add_response = self.client.post(
            reverse("handoff:group_members_add", args=[group.id]),
            data={"names_text": "김민수, 3-2\n이서연, 3-2\n"},
            follow=True,
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(group.members.count(), 2)
        self.assertEqual(
            list(group.members.order_by("sort_order").values_list("display_name", "affiliation")),
            [("김민수", "3-2"), ("이서연", "3-2")],
        )

        self.client.force_login(self.teacher)

        dashboard_response = self.client.get(reverse("handoff:dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "3학년 2반 공용 명부")

        session_response = self.client.post(
            reverse("handoff:session_create"),
            data={
                "title": "교사 본인 사용 세션",
                "roster_group": str(group.id),
                "note": "",
            },
            follow=True,
        )

        self.assertEqual(session_response.status_code, 200)
        session = HandoffSession.objects.get(owner=self.teacher, title="교사 본인 사용 세션")
        self.assertEqual(session.roster_group_id, group.id)
        self.assertEqual(session.receipts.count(), 2)

    def test_other_admin_cannot_force_teacher_owned_roster_creation(self):
        self.client.force_login(self.other_admin)

        response = self.client.post(
            reverse("handoff:group_create"),
            data={
                "name": "운영자 개인 명부",
                "description": "",
                "acting_for_user": str(self.teacher.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        group = HandoffRosterGroup.objects.get(name="운영자 개인 명부")
        self.assertEqual(group.owner, self.other_admin)
        self.assertFalse(
            HandoffRosterGroup.objects.filter(owner=self.teacher, name="운영자 개인 명부").exists()
        )
