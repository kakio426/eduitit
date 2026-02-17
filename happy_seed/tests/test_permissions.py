from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom


User = get_user_model()


class HappySeedPermissionTests(TestCase):
    def setUp(self):
        self.teacher1 = User.objects.create_user(username="teacherA", password="pw12345")
        self.teacher2 = User.objects.create_user(username="teacherB", password="pw12345")
        self.teacher2.email = "teacherb@example.com"
        self.teacher2.save(update_fields=["email"])
        UserProfile.objects.update_or_create(
            user=self.teacher2,
            defaults={"nickname": "선생님B", "role": "school"},
        )
        self.classroom = HSClassroom.objects.create(teacher=self.teacher1, name="4-1")

    def test_other_teacher_cannot_access_classroom(self):
        self.client.login(username="teacherB", password="pw12345")
        url = reverse("happy_seed:classroom_detail", kwargs={"classroom_id": self.classroom.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)
