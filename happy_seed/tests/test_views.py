import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from consent.models import SignatureRecipient
from core.models import UserProfile
from happy_seed.models import HSBloomDraw, HSClassroom, HSClassroomConfig, HSGuardianConsent, HSPrize, HSStudent, HSStudentGroup


User = get_user_model()


class HappySeedViewTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher2", password="pw12345", email="teacher2@example.com")
        UserProfile.objects.update_or_create(
            user=self.teacher,
            defaults={"nickname": "교사2", "role": "school"},
        )
        self.classroom = HSClassroom.objects.create(teacher=self.teacher, name="5-2")
        HSClassroomConfig.objects.create(classroom=self.classroom)
        self.student = HSStudent.objects.create(classroom=self.classroom, name="하늘", number=1, ticket_count=1)
        HSGuardianConsent.objects.create(student=self.student, status="approved")

    def _create_consent_request(self, recipients_text):
        url = reverse("happy_seed:consent_request_via_sign_talk", kwargs={"classroom_id": self.classroom.id})
        return self.client.post(url, {"recipients_text": recipients_text})

    def test_landing_is_public(self):
        res = self.client.get(reverse("happy_seed:landing"))
        self.assertEqual(res.status_code, 200)

    def test_dashboard_legacy_url_redirects_to_canonical_root(self):
        res = self.client.get("/happy-seed/dashboard/")
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(
            res,
            reverse("happy_seed:dashboard"),
            fetch_redirect_response=False,
        )

    def test_dashboard_requires_login(self):
        res = self.client.get(reverse("happy_seed:dashboard"))
        self.assertEqual(res.status_code, 302)

    def test_dashboard_teacher_first_shell_prioritizes_classrooms(self):
        self.client.login(username="teacher2", password="pw12345")
        res = self.client.get(reverse("happy_seed:dashboard"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "내 교실 1개")
        self.assertContains(res, "새 교실 만들기")
        self.assertContains(res, "교실 열기")
        self.assertContains(res, "처음이면 사용 안내 보기")
        self.assertNotContains(res, "빠른 시작:")
        self.assertNotContains(res, "꽃밭 대시보드:")

    def test_classroom_detail_focuses_single_screen_operations(self):
        self.client.login(username="teacher2", password="pw12345")
        res = self.client.get(reverse("happy_seed:classroom_detail", kwargs={"classroom_id": self.classroom.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "처음이면 사용 안내 보기")
        self.assertContains(res, "오늘 바로 하는 일")
        self.assertContains(res, "학생 보드")
        self.assertContains(res, 'data-seed-amount-select')
        self.assertContains(res, 'data-action-mode-select')
        self.assertContains(res, 'data-student-primary-action')
        self.assertContains(res, "모둠 미션 보상")
        self.assertContains(res, "등록된 모둠이 없습니다.")
        self.assertContains(res, "꽃밭 보기")
        self.assertNotContains(res, 'data-draw-trigger')
        self.assertNotContains(res, "빠른 지급")

    def test_bloom_run_redirects_to_canonical_classroom_detail(self):
        self.client.login(username="teacher2", password="pw12345")
        res = self.client.get(reverse("happy_seed:bloom_run", kwargs={"classroom_id": self.classroom.id}))
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(
            res,
            reverse("happy_seed:classroom_detail", kwargs={"classroom_id": self.classroom.id}),
        )

    def test_celebration_requires_valid_token(self):
        draw = HSBloomDraw.objects.create(
            student=self.student,
            is_win=False,
            input_probability=5,
            balance_adjustment=0,
            effective_probability=5,
        )
        url = reverse("happy_seed:celebration", kwargs={"draw_id": draw.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

        res2 = self.client.get(f"{url}?token={draw.celebration_token}")
        self.assertEqual(res2.status_code, 200)

    def test_teacher_manual_requires_login(self):
        res = self.client.get(reverse("happy_seed:teacher_manual"))
        self.assertEqual(res.status_code, 302)

    def test_consent_request_via_sign_talk_sets_external_url(self):
        self.client.login(username="teacher2", password="pw12345")
        self.student.consent.status = "pending"
        self.student.consent.save(update_fields=["status"])
        url = reverse("happy_seed:consent_request_via_sign_talk", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            {"recipients_text": f"{self.student.name},하늘 보호자,01012345678"},
        )
        self.assertEqual(res.status_code, 302)
        consent = HSGuardianConsent.objects.get(student=self.student)
        self.assertTrue(consent.external_url)
        self.assertIn("/consent/public/", consent.external_url)
        self.assertIn("/sign/", consent.external_url)

    def test_consent_sync_from_sign_talk_applies_approved_status(self):
        self.client.login(username="teacher2", password="pw12345")
        self.student.consent.status = "pending"
        self.student.consent.save(update_fields=["status"])

        create_res = self._create_consent_request(f"{self.student.name},하늘 보호자,01012345678")
        self.assertEqual(create_res.status_code, 302)

        recipient = SignatureRecipient.objects.filter(student_name=self.student.name).latest("id")
        recipient.status = SignatureRecipient.STATUS_SIGNED
        recipient.decision = SignatureRecipient.DECISION_AGREE
        recipient.signed_at = timezone.now()
        recipient.save(update_fields=["status", "decision", "signed_at"])

        sync_url = reverse("happy_seed:consent_sync_from_sign_talk", kwargs={"classroom_id": self.classroom.id})
        sync_res = self.client.post(sync_url)
        self.assertEqual(sync_res.status_code, 302)

        self.student.refresh_from_db()
        self.assertEqual(self.student.consent.status, "approved")

    def test_consent_sync_uses_latest_linked_request_by_default(self):
        self.client.login(username="teacher2", password="pw12345")
        self.student.consent.status = "pending"
        self.student.consent.save(update_fields=["status"])

        student2 = HSStudent.objects.create(classroom=self.classroom, name="다온", number=2, ticket_count=0)
        HSGuardianConsent.objects.create(student=student2, status="pending")

        first_res = self._create_consent_request(f"{self.student.name},하늘 보호자,01012345678")
        self.assertEqual(first_res.status_code, 302)
        second_res = self._create_consent_request(f"{student2.name},다온 보호자,01000000000")
        self.assertEqual(second_res.status_code, 302)

        recipient = SignatureRecipient.objects.filter(student_name=student2.name).latest("id")
        recipient.status = SignatureRecipient.STATUS_SIGNED
        recipient.decision = SignatureRecipient.DECISION_AGREE
        recipient.signed_at = timezone.now()
        recipient.save(update_fields=["status", "decision", "signed_at"])

        sync_url = reverse("happy_seed:consent_sync_from_sign_talk", kwargs={"classroom_id": self.classroom.id})
        sync_res = self.client.post(sync_url)
        self.assertEqual(sync_res.status_code, 302)

        student2.refresh_from_db()
        self.assertEqual(student2.consent.status, "approved")

    def test_consent_sync_includes_inactive_student(self):
        self.client.login(username="teacher2", password="pw12345")
        self.student.consent.status = "pending"
        self.student.consent.save(update_fields=["status"])

        create_res = self._create_consent_request(f"{self.student.name},하늘 보호자,01012345678")
        self.assertEqual(create_res.status_code, 302)

        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        recipient = SignatureRecipient.objects.filter(student_name=self.student.name).latest("id")
        recipient.status = SignatureRecipient.STATUS_SIGNED
        recipient.decision = SignatureRecipient.DECISION_AGREE
        recipient.signed_at = timezone.now()
        recipient.save(update_fields=["status", "decision", "signed_at"])

        sync_url = reverse("happy_seed:consent_sync_from_sign_talk", kwargs={"classroom_id": self.classroom.id})
        sync_res = self.client.post(sync_url)
        self.assertEqual(sync_res.status_code, 302)

        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertEqual(self.student.consent.status, "approved")

    def test_group_mission_success_grants_ticket_to_random_member(self):
        self.client.login(username="teacher2", password="pw12345")
        student2 = HSStudent.objects.create(classroom=self.classroom, name="하랑", number=2, ticket_count=0)
        HSGuardianConsent.objects.create(student=student2, status="approved")
        group = HSStudentGroup.objects.create(classroom=self.classroom, name="1모둠")
        group.members.add(self.student, student2)
        url = reverse("happy_seed:group_mission_success", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(url, {"group_id": str(group.id), "draw_count": "1"})
        self.assertEqual(res.status_code, 302)
        self.student.refresh_from_db()
        student2.refresh_from_db()
        self.assertEqual(self.student.ticket_count + student2.ticket_count, 2)

    def test_group_manage_page_open(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:group_manage", kwargs={"classroom_id": self.classroom.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_student_manage_page_open(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:student_manage", kwargs={"classroom_id": self.classroom.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_student_manage_deactivate_restore_and_hard_delete(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:student_manage", kwargs={"classroom_id": self.classroom.id})

        deactivate_res = self.client.post(
            url,
            {
                "action": "deactivate_student",
                "student_id": str(self.student.id),
            },
        )
        self.assertEqual(deactivate_res.status_code, 302)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

        restore_res = self.client.post(
            url,
            {
                "action": "restore_student",
                "student_id": str(self.student.id),
            },
        )
        self.assertEqual(restore_res.status_code, 302)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

        delete_res = self.client.post(
            url,
            {
                "action": "hard_delete_student",
                "student_id": str(self.student.id),
            },
        )
        self.assertEqual(delete_res.status_code, 302)
        self.assertFalse(HSStudent.objects.filter(id=self.student.id).exists())

    def test_student_manage_bulk_add_in_same_page(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:student_manage", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            {
                "action": "bulk_add",
                "students_paste": "번호\t이름\n2\t민수\n3\t지수",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(HSStudent.objects.filter(classroom=self.classroom, number=2, name="민수").exists())
        self.assertTrue(HSStudent.objects.filter(classroom=self.classroom, number=3, name="지수").exists())

    def test_student_manage_bulk_edit_students_updates_multiple_rows(self):
        self.client.login(username="teacher2", password="pw12345")
        student2 = HSStudent.objects.create(classroom=self.classroom, name="다온", number=2, ticket_count=0)
        HSGuardianConsent.objects.create(student=student2, status="pending")
        url = reverse("happy_seed:student_manage", kwargs={"classroom_id": self.classroom.id})

        res = self.client.post(
            url,
            {
                "action": "bulk_edit_students",
                "edit_student_ids": [str(self.student.id), str(student2.id)],
                f"number_{self.student.id}": "11",
                f"name_{self.student.id}": "하늘이",
                f"number_{student2.id}": "12",
                f"name_{student2.id}": "다온이",
            },
        )

        self.assertEqual(res.status_code, 302)
        self.student.refresh_from_db()
        student2.refresh_from_db()
        self.assertEqual(self.student.number, 11)
        self.assertEqual(self.student.name, "하늘이")
        self.assertEqual(student2.number, 12)
        self.assertEqual(student2.name, "다온이")

    def test_student_manage_bulk_edit_students_blocks_duplicate_numbers(self):
        self.client.login(username="teacher2", password="pw12345")
        student2 = HSStudent.objects.create(classroom=self.classroom, name="다온", number=2, ticket_count=0)
        HSGuardianConsent.objects.create(student=student2, status="pending")
        url = reverse("happy_seed:student_manage", kwargs={"classroom_id": self.classroom.id})

        res = self.client.post(
            url,
            {
                "action": "bulk_edit_students",
                "edit_student_ids": [str(self.student.id), str(student2.id)],
                f"number_{self.student.id}": "9",
                f"name_{self.student.id}": "하늘A",
                f"number_{student2.id}": "9",
                f"name_{student2.id}": "다온A",
            },
        )

        self.assertEqual(res.status_code, 302)
        self.student.refresh_from_db()
        student2.refresh_from_db()
        self.assertEqual(self.student.number, 1)
        self.assertEqual(self.student.name, "하늘")
        self.assertEqual(student2.number, 2)
        self.assertEqual(student2.name, "다온")

    def test_student_bulk_add_with_excel_paste(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:student_bulk_add", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            {
                "students_paste": "번호\t이름\n2\t민수\n3\t지수",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(HSStudent.objects.filter(classroom=self.classroom, number=2, name="민수").exists())
        self.assertTrue(HSStudent.objects.filter(classroom=self.classroom, number=3, name="지수").exists())

    def test_student_bulk_add_get_redirects_to_student_manage(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:student_bulk_add", kwargs={"classroom_id": self.classroom.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(
            res,
            reverse("happy_seed:student_manage", kwargs={"classroom_id": self.classroom.id}),
        )

    def test_student_bulk_add_with_csv_file(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:student_bulk_add", kwargs={"classroom_id": self.classroom.id})
        csv_file = SimpleUploadedFile(
            "students.csv",
            "번호,이름\n4,다온\n5,서준\n".encode("utf-8"),
            content_type="text/csv",
        )
        res = self.client.post(
            url,
            {
                "students_paste": "",
                "students_csv": csv_file,
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(HSStudent.objects.filter(classroom=self.classroom, number=4, name="다온").exists())
        self.assertTrue(HSStudent.objects.filter(classroom=self.classroom, number=5, name="서준").exists())

    def test_student_delete_removes_student_and_group_membership(self):
        self.client.login(username="teacher2", password="pw12345")
        group = HSStudentGroup.objects.create(classroom=self.classroom, name="삭제테스트모둠")
        group.members.add(self.student)

        delete_url = reverse("happy_seed:student_delete", kwargs={"student_id": self.student.id})
        res = self.client.post(delete_url)
        self.assertEqual(res.status_code, 200)

        self.assertFalse(HSStudent.objects.filter(id=self.student.id).exists())
        self.assertFalse(group.members.filter(id=self.student.id).exists())

    def test_consent_manual_approve(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:consent_manual_approve", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(url, {"student_id": str(self.student.id), "signer_name": "보호자"})
        self.assertEqual(res.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.consent.status, "approved")

    def test_consent_manual_approve_creates_missing_consent(self):
        self.client.login(username="teacher2", password="pw12345")
        HSGuardianConsent.objects.filter(student=self.student).delete()
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        url = reverse("happy_seed:consent_manual_approve", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(url, {"student_id": str(self.student.id), "signer_name": "보호자"})
        self.assertEqual(res.status_code, 302)

        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertTrue(HSGuardianConsent.objects.filter(student=self.student, status="approved").exists())

    def test_consent_update_approved_reactivates_student(self):
        self.client.login(username="teacher2", password="pw12345")
        self.student.consent.status = "withdrawn"
        self.student.consent.save(update_fields=["status"])
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        url = reverse("happy_seed:consent_update", kwargs={"student_id": self.student.id})
        res = self.client.post(url, {"status": "approved"})
        self.assertEqual(res.status_code, 200)

        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertEqual(self.student.consent.status, "approved")

    def test_seed_grant_json_rejects_amount_outside_quick_amounts(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:seed_grant", kwargs={"student_id": self.student.id})
        res = self.client.post(
            url,
            {"amount": "2", "detail": "테스트"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(res.status_code, 400)
        payload = res.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "ERR_INVALID_SEED_GRANT_AMOUNT")

    def test_seed_grant_json_returns_updated_student_state(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:seed_grant", kwargs={"student_id": self.student.id})
        res = self.client.post(
            url,
            {"amount": "3", "detail": "테스트"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.student.refresh_from_db()
        self.assertEqual(payload["data"]["student_state"]["seeds_balance"], self.student.seed_count)
        self.assertEqual(self.student.seed_count, 3)

    def test_consent_regenerate_link_updates_token_and_reactivates(self):
        self.client.login(username="teacher2", password="pw12345")
        self.student.consent.status = "pending"
        self.student.consent.save(update_fields=["status"])

        create_res = self._create_consent_request(f"{self.student.name},하늘 보호자,01012345678")
        self.assertEqual(create_res.status_code, 302)

        self.student.refresh_from_db()
        old_url = self.student.consent.external_url
        old_token = old_url.rstrip("/").split("/")[-2]
        payload = json.loads(self.student.consent.note)
        recipient = SignatureRecipient.objects.get(id=payload["recipient_id"])

        self.student.is_active = False
        self.student.save(update_fields=["is_active"])
        self.student.consent.status = "withdrawn"
        self.student.consent.save(update_fields=["status"])

        regen_url = reverse("happy_seed:consent_regenerate_link", kwargs={"student_id": self.student.id})
        regen_res = self.client.post(regen_url)
        self.assertEqual(regen_res.status_code, 302)

        recipient.refresh_from_db()
        self.student.refresh_from_db()
        new_token = self.student.consent.external_url.rstrip("/").split("/")[-2]
        self.assertNotEqual(old_token, recipient.access_token)
        self.assertEqual(new_token, recipient.access_token)
        self.assertEqual(self.student.consent.status, "pending")
        self.assertTrue(self.student.is_active)

    def test_activity_manage_manual_bonus_grant_without_score(self):
        self.client.login(username="teacher2", password="pw12345")
        before = self.student.ticket_count
        url = reverse("happy_seed:activity_manage", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            {
                "title": "오프라인 확인 활동",
                "description": "",
                "threshold_score": "90",
                "extra_bloom_count": "1",
                f"bonus_manual_{self.student.id}": "on",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.ticket_count, before + 1)

    def test_api_execute_draw_returns_envelope_error_code(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:api_execute_draw", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            data='{"student_id":"%s"}' % self.student.id,
            content_type="application/json",
            **{"HTTP_X_REQUEST_ID": "req-test-1", "HTTP_IDEMPOTENCY_KEY": str(self.student.id)},
        )
        self.assertEqual(res.status_code, 400)
        payload = res.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "ERR_REWARD_EMPTY")

    def test_api_execute_draw_returns_presentation_payload(self):
        self.client.login(username="teacher2", password="pw12345")
        HSPrize.objects.create(
            classroom=self.classroom,
            name="학급 스티커",
            win_rate_percent=100,
            total_quantity=None,
            remaining_quantity=None,
        )
        url = reverse("happy_seed:api_execute_draw", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            data='{"student_id":"%s"}' % self.student.id,
            content_type="application/json",
            **{"HTTP_X_REQUEST_ID": "req-test-ok", "HTTP_IDEMPOTENCY_KEY": "7d930dc6-c41b-4a22-82ac-1b5c24c01112"},
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertIn("presentation", payload["data"])
        self.assertEqual(payload["data"]["presentation"]["student_name"], self.student.name)
        self.assertIn(payload["data"]["presentation"]["result_kind"], {"WIN", "LOSE"})

    def test_bloom_draw_redirect_primes_pending_presentation_overlay(self):
        self.client.login(username="teacher2", password="pw12345")
        self.student.ticket_count = 1
        self.student.save(update_fields=["ticket_count"])
        HSPrize.objects.create(
            classroom=self.classroom,
            name="깜짝 선물",
            win_rate_percent=100,
            total_quantity=None,
            remaining_quantity=None,
        )

        draw_url = reverse("happy_seed:bloom_draw", kwargs={"student_id": self.student.id})
        request_id = "b73c0d7f-f31c-4ece-aaaf-810592bfc8fe"
        res = self.client.post(draw_url, {"request_id": request_id})

        self.assertEqual(res.status_code, 302)
        self.assertRedirects(
            res,
            reverse("happy_seed:classroom_detail", kwargs={"classroom_id": self.classroom.id}),
            fetch_redirect_response=False,
        )

        session = self.client.session
        pending = session.get("happy_seed.pending_presentation")
        self.assertIsNotNone(pending)
        self.assertEqual(pending["classroom_id"], str(self.classroom.id))
        self.assertEqual(pending["presentation"]["student_name"], self.student.name)

        detail_res = self.client.get(reverse("happy_seed:classroom_detail", kwargs={"classroom_id": self.classroom.id}))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, "HAPPY_SEED_PENDING_PRESENTATION")
        self.assertContains(detail_res, self.student.name)
        self.assertNotIn("happy_seed.pending_presentation", self.client.session)

    def test_api_grant_and_execute_draw_rejects_invalid_amount(self):
        self.client.login(username="teacher2", password="pw12345")
        url = reverse("happy_seed:api_grant_and_execute_draw", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            data=json.dumps({"student_id": str(self.student.id), "seed_amount": 2}),
            content_type="application/json",
            **{"HTTP_X_REQUEST_ID": "req-test-combo-invalid"},
        )
        self.assertEqual(res.status_code, 400)
        payload = res.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "ERR_INVALID_SEED_GRANT_AMOUNT")

    def test_api_grant_and_execute_draw_grants_seed_then_returns_presentation_payload(self):
        self.client.login(username="teacher2", password="pw12345")
        config = HSClassroomConfig.objects.get(classroom=self.classroom)
        config.seeds_per_bloom = 10
        config.base_win_rate = 100
        config.save(update_fields=["seeds_per_bloom", "base_win_rate"])
        self.student.ticket_count = 0
        self.student.seed_count = 9
        self.student.save(update_fields=["ticket_count", "seed_count"])
        HSPrize.objects.create(
            classroom=self.classroom,
            name="즉시 보상",
            win_rate_percent=100,
            total_quantity=None,
            remaining_quantity=None,
        )

        url = reverse("happy_seed:api_grant_and_execute_draw", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            data=json.dumps(
                {
                    "student_id": str(self.student.id),
                    "seed_amount": 1,
                    "idempotency_key": "7d930dc6-c41b-4a22-82ac-1b5c24c09999",
                }
            ),
            content_type="application/json",
            **{
                "HTTP_X_REQUEST_ID": "req-test-combo-ok",
                "HTTP_IDEMPOTENCY_KEY": "7d930dc6-c41b-4a22-82ac-1b5c24c09999",
            },
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["granted_amount"], 1)
        self.assertIn("presentation", payload["data"])
        self.assertTrue(HSBloomDraw.objects.filter(student=self.student).exists())
        self.student.refresh_from_db()
        self.assertEqual(self.student.ticket_count, 0)
        self.assertEqual(self.student.seed_count, 0)

    def test_api_group_mission_success_returns_envelope_ok(self):
        self.client.login(username="teacher2", password="pw12345")
        student2 = HSStudent.objects.create(classroom=self.classroom, name="하람", number=3, ticket_count=0)
        HSGuardianConsent.objects.create(student=student2, status="approved")
        group = HSStudentGroup.objects.create(classroom=self.classroom, name="2모둠")
        group.members.add(self.student, student2)
        url = reverse("happy_seed:api_group_mission_success", kwargs={"classroom_id": self.classroom.id})
        res = self.client.post(
            url,
            data='{"group_id":"%s","winners_count":1}' % group.id,
            content_type="application/json",
            **{"HTTP_X_REQUEST_ID": "req-test-2"},
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["group_name"], "2모둠")
