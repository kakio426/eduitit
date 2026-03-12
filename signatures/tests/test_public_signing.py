from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from signatures.models import ExpectedParticipant, Signature, SignatureAuditLog, TrainingSession


User = get_user_model()


class SignaturePublicSigningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="signature_public_owner",
            password="pw12345",
            email="signature_public_owner@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "signature_public_owner", "role": "school"},
        )
        self.session = TrainingSession.objects.create(
            title="공개 서명 테스트 연수",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="시청각실",
            created_by=self.user,
            is_active=True,
        )

    def test_public_sign_submission_stores_request_meta_and_audit_log(self):
        response = self.client.post(
            reverse("signatures:sign", kwargs={"uuid": self.session.uuid}),
            data={
                "participant_affiliation": "교사",
                "participant_name": "홍길동",
                "signature_data": "data:image/png;base64,SIG",
            },
            HTTP_X_FORWARDED_FOR="198.51.100.10",
            HTTP_USER_AGENT="SignatureAgent/1.0",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertContains(response, "출석·참여 확인")
        signature = Signature.objects.get(training_session=self.session)
        self.assertEqual(signature.ip_address, "198.51.100.10")
        self.assertEqual(signature.user_agent, "SignatureAgent/1.0")
        self.assertEqual(signature.submission_mode, Signature.SUBMISSION_MODE_OPEN)
        self.assertEqual(signature.manual_sort_order, 1)

        log = SignatureAuditLog.objects.get(training_session=self.session, signature=signature)
        self.assertEqual(log.event_type, SignatureAuditLog.EVENT_SIGN_SUBMITTED)
        self.assertEqual(log.ip_address, "198.51.100.10")
        self.assertEqual(log.user_agent, "SignatureAgent/1.0")
        self.assertEqual(log.event_meta.get("participant_name"), "홍길동")
        self.assertEqual(log.event_meta.get("submission_mode"), Signature.SUBMISSION_MODE_OPEN)

    def test_public_sign_page_uses_roster_selection_when_expected_participants_exist(self):
        matched_signature = Signature.objects.create(
            training_session=self.session,
            participant_name="이미완료",
            participant_affiliation="교사",
            signature_data="data:image/png;base64,SIG0",
        )
        ExpectedParticipant.objects.create(training_session=self.session, name="김교사", affiliation="1-1")
        ExpectedParticipant.objects.create(training_session=self.session, name="김교사", affiliation="1-2")
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="이미완료",
            affiliation="교사",
            matched_signature=matched_signature,
        )

        response = self.client.get(reverse("signatures:sign", kwargs={"uuid": self.session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "이름 선택")
        self.assertContains(response, "김교사 (1-1)")
        self.assertContains(response, "김교사 (1-2)")
        self.assertContains(response, "이미완료 (교사) - 이미 완료")
        self.assertContains(response, "명단에 이름이 없어요")

    def test_roster_selection_submission_auto_matches_expected_participant(self):
        participant = ExpectedParticipant.objects.create(
            training_session=self.session,
            name="김교사",
            affiliation="1-1",
        )

        response = self.client.post(
            reverse("signatures:sign", kwargs={"uuid": self.session.uuid}),
            data={
                "expected_participant_id": str(participant.id),
                "participant_affiliation": "",
                "participant_name": "",
                "signature_data": "data:image/png;base64,SIG",
            },
            HTTP_X_FORWARDED_FOR="198.51.100.11",
            HTTP_USER_AGENT="SignatureAgent/2.0",
        )

        self.assertEqual(response.status_code, 200)
        signature = Signature.objects.get(training_session=self.session, participant_name="김교사")
        participant.refresh_from_db()
        self.assertEqual(participant.matched_signature_id, signature.id)
        self.assertTrue(participant.is_confirmed)
        self.assertEqual(signature.participant_affiliation, "1-1")

    def test_walk_in_submission_stays_unmatched_when_roster_exists(self):
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="명단교사",
            affiliation="1-1",
        )

        response = self.client.post(
            reverse("signatures:sign", kwargs={"uuid": self.session.uuid}),
            data={
                "walk_in_mode": "1",
                "expected_participant_id": "",
                "participant_affiliation": "외부강사",
                "participant_name": "현장참여",
                "signature_data": "data:image/png;base64,SIGWALKIN",
            },
        )

        self.assertEqual(response.status_code, 200)
        signature = Signature.objects.get(training_session=self.session, participant_name="현장참여")
        self.assertEqual(signature.participant_affiliation, "외부강사")
        self.assertFalse(
            ExpectedParticipant.objects.filter(training_session=self.session, matched_signature=signature).exists()
        )

    def test_roster_selection_blocks_already_signed_participant(self):
        existing_signature = Signature.objects.create(
            training_session=self.session,
            participant_name="김교사",
            participant_affiliation="1-1",
            signature_data="data:image/png;base64,OLD",
        )
        participant = ExpectedParticipant.objects.create(
            training_session=self.session,
            name="김교사",
            affiliation="1-1",
            matched_signature=existing_signature,
            is_confirmed=True,
        )

        response = self.client.post(
            reverse("signatures:sign", kwargs={"uuid": self.session.uuid}),
            data={
                "expected_participant_id": str(participant.id),
                "participant_affiliation": "",
                "participant_name": "",
                "signature_data": "data:image/png;base64,NEW",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "이미 서명이 완료된 이름입니다.")
        self.assertEqual(Signature.objects.filter(training_session=self.session).count(), 1)

    def test_session_detail_does_not_show_repeated_ip_warning(self):
        Signature.objects.create(
            training_session=self.session,
            participant_name="홍길동",
            participant_affiliation="교사",
            signature_data="data:image/png;base64,SIG1",
            submission_mode=Signature.SUBMISSION_MODE_OPEN,
            ip_address="198.51.100.20",
            user_agent="Agent/1.0",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="김영희",
            participant_affiliation="교사",
            signature_data="data:image/png;base64,SIG2",
            submission_mode=Signature.SUBMISSION_MODE_OPEN,
            ip_address="198.51.100.20",
            user_agent="Agent/1.0",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("signatures:detail", kwargs={"uuid": self.session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "반복 IP 제출")
        self.assertNotContains(response, "198.51.100.20")

    def test_print_view_uses_sensitive_cache_headers(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("signatures:print", kwargs={"uuid": self.session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
