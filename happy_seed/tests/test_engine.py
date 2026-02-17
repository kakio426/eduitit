import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from happy_seed.models import HSClassroom, HSClassroomConfig, HSGuardianConsent, HSStudent
from happy_seed.services.engine import (
    ConsentRequiredError,
    add_seeds,
    execute_bloom_draw,
    grant_tickets,
)


User = get_user_model()


class HappySeedEngineTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher1", password="pw12345")
        self.classroom = HSClassroom.objects.create(teacher=self.teacher, name="6-1")
        self.config = HSClassroomConfig.objects.create(classroom=self.classroom, seeds_per_bloom=10, base_win_rate=5)
        self.student = HSStudent.objects.create(classroom=self.classroom, name="민수", number=1)
        HSGuardianConsent.objects.create(student=self.student, status="approved")

    def test_add_seeds_auto_convert_to_ticket(self):
        add_seeds(self.student, 10, "teacher_grant", "테스트")
        self.student.refresh_from_db()
        self.assertEqual(self.student.seed_count, 0)
        self.assertEqual(self.student.ticket_count, 1)

    def test_grant_tickets_requires_consent(self):
        student2 = HSStudent.objects.create(classroom=self.classroom, name="지수", number=2)
        HSGuardianConsent.objects.create(student=student2, status="pending")
        with self.assertRaises(ConsentRequiredError):
            grant_tickets(student2, "participation", 1, "성실 참여")

    def test_execute_bloom_draw_idempotent_by_request_id(self):
        self.student.ticket_count = 1
        self.student.pending_forced_win = True
        self.student.save(update_fields=["ticket_count", "pending_forced_win"])
        request_id = uuid.uuid4()
        draw1 = execute_bloom_draw(self.student, self.classroom, self.teacher, request_id=request_id)
        draw2 = execute_bloom_draw(self.student, self.classroom, self.teacher, request_id=request_id)
        self.assertEqual(draw1.id, draw2.id)
