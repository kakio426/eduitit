import uuid
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSBloomDraw, HSClassroom, HSClassroomConfig, HSGuardianConsent, HSStudent


User = get_user_model()


class HappySeedFlowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher_flow",
            password="pw12345",
            email="teacher_flow@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.teacher,
            defaults={"nickname": "담임교사", "role": "school"},
        )
        self.classroom = HSClassroom.objects.create(teacher=self.teacher, name="6-1", school_name="행복초")
        HSClassroomConfig.objects.create(classroom=self.classroom, seeds_per_bloom=10, base_win_rate=5)

    def test_teacher_core_flow_end_to_end(self):
        self.client.login(username="teacher_flow", password="pw12345")

        add_url = reverse("happy_seed:student_add", kwargs={"classroom_id": self.classroom.id})
        add_res = self.client.post(add_url, {"name": "민수", "number": 1})
        self.assertEqual(add_res.status_code, 200)
        student = HSStudent.objects.get(classroom=self.classroom, number=1)
        self.assertEqual(student.name, "민수")

        consent_url = reverse("happy_seed:consent_update", kwargs={"student_id": student.id})
        consent_res = self.client.post(consent_url, {"status": "approved"})
        self.assertEqual(consent_res.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.consent.status, "approved")

        grant_url = reverse("happy_seed:bloom_grant", kwargs={"classroom_id": self.classroom.id})
        grant_res = self.client.post(grant_url, {"student_id": str(student.id), "source": "participation", "amount": 1})
        self.assertEqual(grant_res.status_code, 302)
        student.refresh_from_db()
        self.assertEqual(student.ticket_count, 1)

        draw_url = reverse("happy_seed:bloom_draw", kwargs={"student_id": student.id})
        draw_res = self.client.post(draw_url, {"request_id": str(uuid.uuid4())})
        self.assertEqual(draw_res.status_code, 302)
        parsed = urlparse(draw_res.url)
        query = parse_qs(parsed.query)
        self.assertIn("token", query)

        celebrate_res = self.client.get(draw_res.url)
        self.assertEqual(celebrate_res.status_code, 200)

        draw = HSBloomDraw.objects.get(student=student)
        close_url = reverse("happy_seed:close_celebration", kwargs={"draw_id": draw.id})
        close_res = self.client.post(close_url)
        self.assertEqual(close_res.status_code, 302)
        draw.refresh_from_db()
        self.assertTrue(draw.celebration_closed)

    def test_public_garden_accessible_without_login(self):
        student = HSStudent.objects.create(classroom=self.classroom, name="지수", number=2, seed_count=3)
        HSGuardianConsent.objects.create(student=student, status="approved")
        url = reverse("happy_seed:garden_public", kwargs={"slug": self.classroom.slug})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
