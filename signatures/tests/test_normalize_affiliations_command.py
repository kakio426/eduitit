from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import UserProfile
from signatures.models import AffiliationCorrectionLog, ExpectedParticipant, Signature, TrainingSession


User = get_user_model()


class NormalizeAffiliationsCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="normalize_affiliations_owner",
            password="pw12345",
            email="normalize_affiliations_owner@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "normalize_affiliations_owner", "role": "school"},
        )
        self.session = TrainingSession.objects.create(
            title="정규화 테스트 연수",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="시청각실",
            created_by=self.user,
            is_active=True,
        )
        self.signature = Signature.objects.create(
            training_session=self.session,
            participant_name="홍길동",
            participant_affiliation="교사 /3-3",
            signature_data="data:image/png;base64,SIG",
        )
        self.participant = ExpectedParticipant.objects.create(
            training_session=self.session,
            name="홍길동",
            affiliation="교사 /3-3",
        )

    def test_dry_run_does_not_modify_data(self):
        output = StringIO()
        call_command("normalize_affiliations", stdout=output)

        self.signature.refresh_from_db()
        self.participant.refresh_from_db()
        self.assertEqual(self.signature.participant_affiliation, "교사 /3-3")
        self.assertEqual(self.participant.affiliation, "교사 /3-3")
        self.assertEqual(AffiliationCorrectionLog.objects.count(), 0)

    def test_apply_updates_data_and_creates_logs(self):
        output = StringIO()
        call_command("normalize_affiliations", "--apply", stdout=output)

        self.signature.refresh_from_db()
        self.participant.refresh_from_db()
        self.assertEqual(self.signature.participant_affiliation, "교사/3-3")
        self.assertEqual(self.participant.affiliation, "교사/3-3")
        self.assertEqual(
            AffiliationCorrectionLog.objects.filter(mode=AffiliationCorrectionLog.MODE_SCRIPT).count(),
            2,
        )
