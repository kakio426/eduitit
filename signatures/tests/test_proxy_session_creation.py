from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent, UserProfile
from handoff.models import HandoffRosterGroup, HandoffRosterMember
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from signatures.models import TrainingSession


User = get_user_model()


class SignatureProxySessionCreationTests(TestCase):
    def setUp(self):
        self.kakio = User.objects.create_superuser(
            username="kakio",
            email="kakio@example.com",
            password="pw12345",
        )
        self.other_admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pw12345",
        )
        self.teacher = User.objects.create_user(
            username="teacher_alpha",
            email="teacher_alpha@example.com",
            password="pw12345",
        )
        UserProfile.objects.update_or_create(
            user=self.kakio,
            defaults={"nickname": "카키오", "role": "school"},
        )
        UserProfile.objects.update_or_create(
            user=self.other_admin,
            defaults={"nickname": "관리자", "role": "school"},
        )
        UserProfile.objects.update_or_create(
            user=self.teacher,
            defaults={"nickname": "김선생", "role": "school"},
        )
        UserPolicyConsent.objects.create(
            user=self.kakio,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
        )
        UserPolicyConsent.objects.create(
            user=self.other_admin,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
        )

    def _session_payload(self, **extra):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        payload = {
            "title": "대행 생성 요청",
            "print_title": "",
            "instructor": "담당 강사",
            "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
            "location": "시청각실",
            "description": "",
            "expected_count": "2",
            "is_active": "on",
        }
        payload.update(extra)
        return payload

    def test_only_kakio_sees_proxy_create_entrypoints(self):
        self.client.force_login(self.kakio)

        response = self.client.get(reverse("signatures:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교사 대신 만들기")

        response = self.client.get(reverse("signatures:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교사가 부탁한 요청을 대신 준비할 수 있습니다.")
        html = response.content.decode("utf-8")
        self.assertLess(html.find('<form method="post"'), html.find('name="acting_for_user"'))
        self.assertLess(html.find('<form method="post"'), html.find('name="proxy_participants_text"'))

        self.client.force_login(self.other_admin)

        response = self.client.get(reverse("signatures:list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "교사 대신 만들기")

        response = self.client.get(reverse("signatures:create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "교사가 부탁한 요청을 대신 준비할 수 있습니다.")

    def test_kakio_can_create_session_for_teacher_with_pasted_participants(self):
        self.client.force_login(self.kakio)

        response = self.client.post(
            reverse("signatures:create"),
            data=self._session_payload(
                acting_for_user=str(self.teacher.id),
                proxy_participants_text="김교사, 1-1\n이교사, 1-2",
                shared_roster_group="",
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        session = TrainingSession.objects.get(title="대행 생성 요청", created_by=self.teacher)
        self.assertEqual(session.proxy_created_by, self.kakio)
        participants = list(
            session.expected_participants.values_list("name", "affiliation").order_by("name")
        )
        self.assertEqual(
            participants,
            [("김교사", "1-1"), ("이교사", "1-2")],
        )
        self.assertContains(response, "김선생 선생님 대신 요청을 만들었습니다.")

        detail_response = self.client.get(reverse("signatures:detail", kwargs={"uuid": session.uuid}))
        self.assertEqual(detail_response.status_code, 200)

    def test_kakio_can_link_teacher_roster_group_when_creating_on_behalf(self):
        group = HandoffRosterGroup.objects.create(owner=self.teacher, name="1학년 담임")
        HandoffRosterMember.objects.create(
            group=group,
            display_name="강교사",
            note="1-3",
            sort_order=1,
            is_active=True,
        )

        self.client.force_login(self.kakio)
        response = self.client.post(
            reverse("signatures:create"),
            data=self._session_payload(
                title="명단 연결 대행 요청",
                acting_for_user=str(self.teacher.id),
                shared_roster_group=str(group.id),
                proxy_participants_text="",
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        session = TrainingSession.objects.get(title="명단 연결 대행 요청", created_by=self.teacher)
        self.assertEqual(session.proxy_created_by, self.kakio)
        self.assertEqual(session.shared_roster_group_id, group.id)
        self.assertEqual(
            list(session.expected_participants.values_list("name", "affiliation")),
            [("강교사", "1-3")],
        )

    def test_other_admin_cannot_create_session_for_teacher(self):
        self.client.force_login(self.other_admin)

        response = self.client.post(
            reverse("signatures:create"),
            data=self._session_payload(
                acting_for_user=str(self.teacher.id),
                proxy_participants_text="김교사, 1-1",
                shared_roster_group="",
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        session = TrainingSession.objects.get(title="대행 생성 요청", created_by=self.other_admin)
        self.assertIsNone(session.proxy_created_by)
        self.assertFalse(
            TrainingSession.objects.filter(title="대행 생성 요청", created_by=self.teacher).exists()
        )
        self.assertEqual(session.expected_participants.count(), 0)
