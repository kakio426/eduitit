from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from core.models import UserProfile
from products.models import DTStudent


class PpobgiViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher",
            password="password123",
            email="teacher@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "담임교사"
        profile.role = "school"
        profile.save()

    def test_main_requires_login(self):
        response = self.client.get(reverse("ppobgi:main"))
        self.assertEqual(response.status_code, 302)

    def test_main_page_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("ppobgi:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "추첨 준비")
        self.assertContains(response, "추첨 우주 시작")
        self.assertContains(response, "사다리 뽑기")
        self.assertContains(response, reverse("dutyticker"))
        self.assertContains(response, "title=\"반짝반짝 우리반 알림판\"")

    def test_roster_names_returns_active_students(self):
        self.client.force_login(self.user)
        DTStudent.objects.create(user=self.user, name="3번 학생", number=3, is_active=True)
        DTStudent.objects.create(user=self.user, name="1번 학생", number=1, is_active=True)
        DTStudent.objects.create(user=self.user, name="비활성 학생", number=2, is_active=False)

        response = self.client.get(reverse("ppobgi:roster_names"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["names"], ["1번 학생", "3번 학생"])

    def test_roster_names_requires_login(self):
        response = self.client.get(reverse("ppobgi:roster_names"))
        self.assertEqual(response.status_code, 302)
