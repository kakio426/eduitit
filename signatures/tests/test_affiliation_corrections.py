from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from signatures.models import AffiliationCorrectionLog, ExpectedParticipant, Signature, TrainingSession


User = get_user_model()


class SignatureAffiliationCorrectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="signature_affiliation_owner",
            password="pw12345",
            email="signature_affiliation_owner@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "signature_affiliation_owner", "role": "school"},
        )
        self.session = TrainingSession.objects.create(
            title="직위 정정 테스트 연수",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="시청각실",
            created_by=self.user,
            is_active=True,
        )
        self.client.force_login(self.user)

    def test_sign_view_includes_affiliation_suggestions(self):
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="홍길동",
            affiliation="교사 /3-3",
        )
        response = self.client.get(reverse("signatures:sign", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'datalist id="affiliationSuggestions"')
        self.assertContains(response, 'value="교사/3-3"')
        self.assertContains(response, 'value="교사"')

    def test_correct_signature_affiliation_preserves_original(self):
        signature = Signature.objects.create(
            training_session=self.session,
            participant_name="임상은",
            participant_affiliation="교사 /3-3",
            signature_data="data:image/png;base64,SIG",
        )

        response = self.client.post(
            reverse(
                "signatures:correct_signature_affiliation",
                kwargs={"uuid": self.session.uuid, "signature_id": signature.id},
            ),
            data='{"corrected_affiliation":"교사/3-3","reason":"표기 통일"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        signature.refresh_from_db()
        self.assertEqual(signature.participant_affiliation, "교사 /3-3")
        self.assertEqual(signature.corrected_affiliation, "교사/3-3")
        self.assertEqual(signature.display_affiliation, "교사/3-3")
        self.assertEqual(signature.affiliation_correction_reason, "표기 통일")
        self.assertEqual(signature.affiliation_corrected_by_id, self.user.id)
        self.assertIsNotNone(signature.affiliation_corrected_at)
        log = AffiliationCorrectionLog.objects.get(signature=signature)
        self.assertEqual(log.target_type, AffiliationCorrectionLog.TARGET_SIGNATURE)
        self.assertEqual(log.mode, AffiliationCorrectionLog.MODE_SINGLE)
        self.assertEqual(log.before_affiliation, "교사/3-3")
        self.assertEqual(log.after_affiliation, "교사/3-3")
        self.assertEqual(log.reason, "표기 통일")
        self.assertEqual(log.corrected_by_id, self.user.id)

    def test_bulk_correct_affiliation_updates_signatures_and_participants(self):
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="고서영",
            affiliation="교사 /3-3",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="고서영",
            participant_affiliation="교사 /3-3",
            signature_data="data:image/png;base64,SIG1",
        )

        response = self.client.post(
            reverse("signatures:bulk_correct_affiliation", kwargs={"uuid": self.session.uuid}),
            data='{"source_affiliation":"교사 /3-3","corrected_affiliation":"교사/3-3","target":"all","reason":"일괄 정리"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["updated_total"], 2)
        self.assertEqual(body["updated_signatures"], 1)
        self.assertEqual(body["updated_participants"], 1)

        participant = self.session.expected_participants.get(name="고서영")
        signature = self.session.signatures.get(participant_name="고서영")
        self.assertEqual(participant.display_affiliation, "교사/3-3")
        self.assertEqual(signature.display_affiliation, "교사/3-3")
        self.assertEqual(
            AffiliationCorrectionLog.objects.filter(
                training_session=self.session,
                mode=AffiliationCorrectionLog.MODE_BULK,
            ).count(),
            2,
        )

    def test_print_view_uses_corrected_affiliation(self):
        signature = Signature.objects.create(
            training_session=self.session,
            participant_name="조은아",
            participant_affiliation="영어회화전문강사/ 영어46",
            corrected_affiliation="영어회화전문강사/영어46",
            signature_data="data:image/png;base64,SIG2",
        )
        participant = ExpectedParticipant.objects.create(
            training_session=self.session,
            name="조은아",
            affiliation="영어회화전문강사/ 영어46",
            corrected_affiliation="영어회화전문강사/영어46",
            matched_signature=signature,
        )
        self.assertEqual(participant.display_affiliation, "영어회화전문강사/영어46")

        response = self.client.get(reverse("signatures:print", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "영어회화전문강사/영어46")
        self.assertNotContains(response, "영어회화전문강사/ 영어46")
