from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSBloomDraw, HSClassroom, HSClassroomConfig, HSGuardianConsent, HSStudent


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
        res = self.client.post(url)
        self.assertEqual(res.status_code, 302)
        consent = HSGuardianConsent.objects.get(student=self.student)
        self.assertTrue(consent.external_url)
        self.assertIn("/signatures/sign/", consent.external_url)
