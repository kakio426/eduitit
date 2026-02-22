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

    def test_dashboard_requires_login(self):
        res = self.client.get(reverse("happy_seed:dashboard"))
        self.assertEqual(res.status_code, 302)

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
