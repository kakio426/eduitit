from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ConsultationMethod,
    ConsultationProposal,
    ConsultationRequest,
    ConsultationSlot,
    ParentContact,
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
            contact_email="parent@example.com",
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
            contact_email="parent2@example.com",
        )
        self.client.force_login(self.teacher)

    def test_main_page_renders(self):
        response = self.client.get(reverse("parentcomm:main"))
        self.assertEqual(response.status_code, 200)

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
