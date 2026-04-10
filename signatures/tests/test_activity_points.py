from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import TeacherActivityEvent, TeacherActivityProfile, UserPolicyConsent, UserProfile
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from signatures.models import TrainingSession


def create_teacher(username: str) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pw123456",
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = username
    profile.role = "school"
    profile.save(update_fields=["nickname", "role"])
    UserPolicyConsent.objects.create(
        user=user,
        provider="direct",
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        agreed_at=timezone.now(),
        agreement_source="required_gate",
    )
    return user


class SignatureActivityPointTests(TestCase):
    def setUp(self):
        self.teacher = create_teacher("signature_teacher")
        self.client.force_login(self.teacher)
        self.session = TrainingSession.objects.create(
            title="활동 지수 테스트",
            print_title="활동 지수 테스트",
            instructor="담당 교사",
            datetime=timezone.now() + timezone.timedelta(days=1),
            location="강당",
            description="테스트용",
            created_by=self.teacher,
            is_active=False,
        )

    def test_toggle_active_awards_request_sent_activity(self):
        response = self.client.post(reverse("signatures:toggle", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(response.status_code, 200)

        profile = TeacherActivityProfile.objects.get(user=self.teacher)
        self.assertEqual(profile.total_score, 2)
        self.assertEqual(
            TeacherActivityEvent.objects.filter(
                user=self.teacher,
                category="request_sent",
            ).count(),
            1,
        )
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_shared_at)
