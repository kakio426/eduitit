from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ConsultationMethod,
    ConsultationProposal,
    ConsultationRequest,
    ConsultationSlot,
    ParentContact,
    ParentNotice,
    ParentThread,
    ParentThreadMessage,
    ParentUrgentAlert,
)


User = get_user_model()


class ParentCommModelTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="parentcomm_teacher",
            password="pw12345",
            email="teacher@example.com",
        )
        self.contact = ParentContact.objects.create(
            teacher=self.teacher,
            student_name="민수",
            parent_name="김학부모",
        )

    def test_urgent_alert_message_length_limit(self):
        alert = ParentUrgentAlert(
            teacher=self.teacher,
            parent_contact=self.contact,
            alert_type=ParentUrgentAlert.AlertType.ABSENT,
            short_message="가" * 21,
        )
        with self.assertRaises(ValidationError):
            alert.full_clean()

    def test_thread_escalates_after_parent_message_limit(self):
        thread = ParentThread.objects.create(
            teacher=self.teacher,
            parent_contact=self.contact,
            subject="출결 문의",
            parent_message_limit=1,
        )

        ParentThreadMessage.objects.create(
            thread=thread,
            sender_role=ParentThreadMessage.SenderRole.PARENT,
            body="첫 문의",
        )
        thread.refresh_from_db()
        self.assertEqual(thread.status, ParentThread.Status.WAITING_TEACHER)

        ParentThreadMessage.objects.create(
            thread=thread,
            sender_role=ParentThreadMessage.SenderRole.PARENT,
            body="두 번째 문의",
        )
        thread.refresh_from_db()
        self.assertEqual(thread.status, ParentThread.Status.NEEDS_CONSULT)

    def test_consultation_slot_method_must_be_in_allowed_methods(self):
        request_obj = ConsultationRequest.objects.create(
            teacher=self.teacher,
            parent_contact=self.contact,
            reason="지속 상담 필요",
        )
        proposal = ConsultationProposal.objects.create(
            consultation_request=request_obj,
            teacher=self.teacher,
            allowed_methods=[ConsultationMethod.PHONE],
        )
        slot = ConsultationSlot(
            proposal=proposal,
            method=ConsultationMethod.VISIT,
            starts_at=timezone.make_aware(datetime(2026, 3, 1, 10, 0, 0)),
            ends_at=timezone.make_aware(datetime(2026, 3, 1, 10, 30, 0)),
        )

        with self.assertRaises(ValidationError):
            slot.full_clean()


@override_settings(ONBOARDING_EXEMPT_PATH_PREFIXES=["/parentcomm/"])
class ParentCommViewTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher_main",
            password="pw12345",
            email="teacher_main@example.com",
        )
        self.contact = ParentContact.objects.create(
            teacher=self.teacher,
            student_name="지우",
            parent_name="박학부모",
        )
        self.client.force_login(self.teacher)

    def test_main_page_renders(self):
        response = self.client.get(reverse("parentcomm:main"))
        self.assertEqual(response.status_code, 200)

    def test_teacher_can_add_contact_without_email_field(self):
        response = self.client.post(
            reverse("parentcomm:main"),
            {
                "action": "add_contact",
                "student_name": "이하늘",
                "student_grade": "4",
                "student_classroom": "4-1",
                "parent_name": "이학부모",
                "relationship": "아버지",
                "contact_phone": "010-5555-6666",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ParentContact.objects.filter(student_name="이하늘", parent_name="이학부모").exists())

    def test_teacher_can_bulk_add_contacts_from_text(self):
        response = self.client.post(
            reverse("parentcomm:main"),
            {
                "action": "add_contact_bulk_text",
                "bulk_text": "김하나,김학부모,010-1111-1111,5,5-1,어머니\n박둘,박학부모,010-2222-2222",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ParentContact.objects.filter(student_name="김하나", parent_name="김학부모").exists())
        self.assertTrue(ParentContact.objects.filter(student_name="박둘", parent_name="박학부모").exists())

    def test_teacher_can_bulk_add_contacts_from_csv(self):
        csv_text = (
            "student_name,parent_name,contact_phone,student_grade,student_classroom,relationship\n"
            "오민수,오학부모,010-8888-9999,3,3-2,아버지\n"
        )
        csv_file = SimpleUploadedFile("contacts.csv", csv_text.encode("utf-8"), content_type="text/csv")
        response = self.client.post(
            reverse("parentcomm:main"),
            {
                "action": "add_contact_csv",
                "csv_file": csv_file,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ParentContact.objects.filter(student_name="오민수", parent_name="오학부모").exists())

    def test_teacher_can_create_proposal_with_three_methods(self):
        request_obj = ConsultationRequest.objects.create(
            teacher=self.teacher,
            parent_contact=self.contact,
            reason="행동 상담 필요",
        )
        payload = {
            "action": "create_proposal",
            "consultation_request_id": request_obj.id,
            "note": "상황에 따라 채팅/전화/방문 중 선택 가능합니다.",
            "allowed_methods": [
                ConsultationMethod.CHAT,
                ConsultationMethod.PHONE,
                ConsultationMethod.VISIT,
            ],
        }
        response = self.client.post(reverse("parentcomm:main"), payload)
        self.assertEqual(response.status_code, 302)

        proposal = ConsultationProposal.objects.get(consultation_request=request_obj)
        self.assertCountEqual(
            proposal.allowed_methods,
            [ConsultationMethod.CHAT, ConsultationMethod.PHONE, ConsultationMethod.VISIT],
        )

    def test_parent_urgent_entry_rejects_message_over_20_chars(self):
        url = reverse("parentcomm:urgent_entry", kwargs={"access_id": self.contact.emergency_access_id})
        response = self.client.post(
            url,
            {
                "alert_type": ParentUrgentAlert.AlertType.LATE,
                "short_message": "가" * 21,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ParentUrgentAlert.objects.filter(parent_contact=self.contact).exists())

    def test_parent_urgent_entry_accepts_message_within_20_chars(self):
        url = reverse("parentcomm:urgent_entry", kwargs={"access_id": self.contact.emergency_access_id})
        response = self.client.post(
            url,
            {
                "alert_type": ParentUrgentAlert.AlertType.EARLY_LEAVE,
                "short_message": "병원 진료 후 조퇴",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ParentUrgentAlert.objects.filter(parent_contact=self.contact).exists())

    def test_teacher_can_acknowledge_urgent_alert(self):
        alert = ParentUrgentAlert.objects.create(
            teacher=self.teacher,
            parent_contact=self.contact,
            alert_type=ParentUrgentAlert.AlertType.ABSENT,
            short_message="고열로 결석",
        )
        response = self.client.post(
            reverse("parentcomm:acknowledge_urgent_alert", kwargs={"alert_id": alert.id})
        )
        self.assertEqual(response.status_code, 302)
        alert.refresh_from_db()
        self.assertTrue(alert.is_acknowledged)
        self.assertIsNotNone(alert.acknowledged_at)

    def test_teacher_can_create_notice_with_attachment(self):
        attachment = SimpleUploadedFile("notice.txt", b"school notice", content_type="text/plain")
        response = self.client.post(
            reverse("parentcomm:main"),
            {
                "action": "create_notice",
                "classroom_label": "3-2 바다반",
                "title": "내일 준비물 안내",
                "content": "체육복을 챙겨주세요.",
                "attachment": attachment,
            },
        )
        self.assertEqual(response.status_code, 302)
        notice = ParentNotice.objects.get(title="내일 준비물 안내")
        self.assertTrue(bool(notice.attachment))
