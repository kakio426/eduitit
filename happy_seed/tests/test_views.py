from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from happy_seed.models import HSBloomDraw, HSClassroom, HSClassroomConfig, HSGuardianConsent, HSStudent


User = get_user_model()


class HappySeedViewTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher2", password="pw12345")
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
