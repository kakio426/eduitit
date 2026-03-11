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

    def test_print_view_without_roster_sorts_by_corrected_affiliation_naturally(self):
        Signature.objects.create(
            training_session=self.session,
            participant_name="둘반",
            participant_affiliation="2-1",
            signature_data="data:image/png;base64,SIG21",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="열반",
            participant_affiliation="1-10",
            signature_data="data:image/png;base64,SIG110",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="정정반",
            participant_affiliation="1 / 2",
            corrected_affiliation="1-2",
            signature_data="data:image/png;base64,SIG12",
        )

        response = self.client.get(reverse("signatures:print", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(response.status_code, 200)

        ordered_names = [item["name"] for item in response.context["pages"][0]["left_items"]]
        self.assertEqual(ordered_names[:3], ["정정반", "열반", "둘반"])

    def test_print_view_with_roster_defaults_to_roster_input_order(self):
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="둘반",
            affiliation="2-1",
        )
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="열반",
            affiliation="1-10",
        )
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="정정반",
            affiliation="1 / 2",
            corrected_affiliation="1-2",
        )

        response = self.client.get(reverse("signatures:print", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["session"].participant_sort_mode, TrainingSession.SIGNATURE_SORT_SUBMITTED)

        ordered_names = [item["name"] for item in response.context["pages"][0]["left_items"]]
        self.assertEqual(ordered_names[:3], ["둘반", "열반", "정정반"])

    def test_detail_view_without_roster_uses_sorted_signature_rows(self):
        Signature.objects.create(
            training_session=self.session,
            participant_name="마지막",
            participant_affiliation="2-3",
            signature_data="data:image/png;base64,SIG23",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="첫번째",
            participant_affiliation="1-1",
            signature_data="data:image/png;base64,SIG11",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="두번째",
            participant_affiliation="1-2",
            signature_data="data:image/png;base64,SIG12B",
        )

        response = self.client.get(reverse("signatures:detail", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(response.status_code, 200)

        ordered_names = [sig.participant_name for sig in response.context["signature_rows"]]
        self.assertEqual(ordered_names[:3], ["첫번째", "두번째", "마지막"])

    def test_signature_sort_mode_can_switch_to_submitted_order(self):
        Signature.objects.create(
            training_session=self.session,
            participant_name="먼저사인",
            participant_affiliation="2-1",
            signature_data="data:image/png;base64,SIGA",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="나중사인",
            participant_affiliation="1-1",
            signature_data="data:image/png;base64,SIGB",
        )

        response = self.client.post(
            reverse("signatures:update_signature_sort_mode", kwargs={"uuid": self.session.uuid}),
            data='{"sort_mode":"submitted"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.signature_sort_mode, TrainingSession.SIGNATURE_SORT_SUBMITTED)

        detail_response = self.client.get(reverse("signatures:detail", kwargs={"uuid": self.session.uuid}))
        ordered_names = [sig.participant_name for sig in detail_response.context["signature_rows"]]
        self.assertEqual(ordered_names[:2], ["먼저사인", "나중사인"])

    def test_manual_signature_order_updates_detail_and_print(self):
        Signature.objects.create(
            training_session=self.session,
            participant_name="첫줄",
            participant_affiliation="1-1",
            signature_data="data:image/png;base64,SIGM1",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="둘째줄",
            participant_affiliation="1-2",
            signature_data="data:image/png;base64,SIGM2",
        )
        third = Signature.objects.create(
            training_session=self.session,
            participant_name="셋째줄",
            participant_affiliation="2-1",
            signature_data="data:image/png;base64,SIGM3",
        )

        response = self.client.post(
            reverse(
                "signatures:update_signature_manual_order",
                kwargs={"uuid": self.session.uuid, "signature_id": third.id},
            ),
            data='{"position":1}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.signature_sort_mode, TrainingSession.SIGNATURE_SORT_MANUAL)

        ordered_manual = list(self.session.signatures.order_by("manual_sort_order", "id"))
        self.assertEqual([sig.participant_name for sig in ordered_manual], ["셋째줄", "첫줄", "둘째줄"])
        self.assertEqual([sig.manual_sort_order for sig in ordered_manual], [1, 2, 3])

        detail_response = self.client.get(reverse("signatures:detail", kwargs={"uuid": self.session.uuid}))
        ordered_names = [sig.participant_name for sig in detail_response.context["signature_rows"]]
        self.assertEqual(ordered_names[:3], ["셋째줄", "첫줄", "둘째줄"])

        print_response = self.client.get(reverse("signatures:print", kwargs={"uuid": self.session.uuid}))
        print_names = [item["name"] for item in print_response.context["pages"][0]["left_items"]]
        self.assertEqual(print_names[:3], ["셋째줄", "첫줄", "둘째줄"])

    def test_roster_sort_mode_can_switch_to_affiliation_order_for_list_and_print(self):
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="둘반",
            affiliation="2-1",
        )
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="열반",
            affiliation="1-10",
        )
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="정정반",
            affiliation="1 / 2",
            corrected_affiliation="1-2",
        )

        response = self.client.post(
            reverse("signatures:update_signature_sort_mode", kwargs={"uuid": self.session.uuid}),
            data='{"sort_mode":"affiliation"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["uses_participants"])

        self.session.refresh_from_db()
        self.assertEqual(self.session.participant_sort_mode, TrainingSession.SIGNATURE_SORT_AFFILIATION)

        list_response = self.client.get(reverse("signatures:get_participants", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [item["name"] for item in list_response.json()["participants"]],
            ["정정반", "열반", "둘반"],
        )

        print_response = self.client.get(reverse("signatures:print", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(print_response.status_code, 200)
        print_names = [item["name"] for item in print_response.context["pages"][0]["left_items"]]
        self.assertEqual(print_names[:3], ["정정반", "열반", "둘반"])

    def test_manual_participant_order_updates_list_and_print(self):
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="첫줄",
            affiliation="1-1",
        )
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="둘째줄",
            affiliation="1-2",
        )
        third = ExpectedParticipant.objects.create(
            training_session=self.session,
            name="셋째줄",
            affiliation="2-1",
        )

        response = self.client.post(
            reverse(
                "signatures:update_participant_manual_order",
                kwargs={"uuid": self.session.uuid, "participant_id": third.id},
            ),
            data='{"position":1}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        self.session.refresh_from_db()
        self.assertEqual(self.session.participant_sort_mode, TrainingSession.SIGNATURE_SORT_MANUAL)

        ordered_manual = list(self.session.expected_participants.order_by("manual_sort_order", "id"))
        self.assertEqual([participant.name for participant in ordered_manual], ["셋째줄", "첫줄", "둘째줄"])
        self.assertEqual([participant.manual_sort_order for participant in ordered_manual], [1, 2, 3])

        list_response = self.client.get(reverse("signatures:get_participants", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(
            [item["name"] for item in list_response.json()["participants"]],
            ["셋째줄", "첫줄", "둘째줄"],
        )

        print_response = self.client.get(reverse("signatures:print", kwargs={"uuid": self.session.uuid}))
        print_names = [item["name"] for item in print_response.context["pages"][0]["left_items"]]
        self.assertEqual(print_names[:3], ["셋째줄", "첫줄", "둘째줄"])

    def test_detail_view_with_roster_shows_match_picker_for_unmatched_signature(self):
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="김연결",
            affiliation="1-1",
        )
        ExpectedParticipant.objects.create(
            training_session=self.session,
            name="박찾기",
            affiliation="2-3",
        )
        Signature.objects.create(
            training_session=self.session,
            participant_name="누군지모름",
            participant_affiliation="1학년",
            signature_data="data:image/png;base64,SIGPICK",
        )

        response = self.client.get(reverse("signatures:detail", kwargs={"uuid": self.session.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "명단에서 찾아 연결")
        self.assertContains(response, "김연결")
        self.assertContains(response, "박찾기")
