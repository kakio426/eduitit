from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom
from products.models import DTRole, DTRoleAssignment, DTStudent

User = get_user_model()


class DutyTickerActiveClassroomTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dt_classroom_user",
            password="pw12345",
            email="dt_classroom_user@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "dt-classroom"
        profile.save(update_fields=["nickname"])
        self.client = Client()
        self.client.force_login(self.user)

        self.classroom_a = HSClassroom.objects.create(
            teacher=self.user,
            name="3학년 1반",
            slug="dt-3-1",
        )
        self.classroom_b = HSClassroom.objects.create(
            teacher=self.user,
            name="3학년 2반",
            slug="dt-3-2",
        )

    def _set_active_classroom(self, classroom):
        session = self.client.session
        if classroom is None:
            session.pop("active_classroom_source", None)
            session.pop("active_classroom_id", None)
        else:
            session["active_classroom_source"] = "hs"
            session["active_classroom_id"] = str(classroom.id)
        session.save()

    def test_api_data_uses_selected_classroom_scope(self):
        student_a = DTStudent.objects.create(user=self.user, classroom=self.classroom_a, name="가반 학생", number=1)
        role_a = DTRole.objects.create(user=self.user, classroom=self.classroom_a, name="가반 역할", time_slot="아침")
        DTRoleAssignment.objects.create(user=self.user, classroom=self.classroom_a, role=role_a, student=student_a)

        student_b = DTStudent.objects.create(user=self.user, classroom=self.classroom_b, name="나반 학생", number=1)
        role_b = DTRole.objects.create(user=self.user, classroom=self.classroom_b, name="나반 역할", time_slot="점심")
        DTRoleAssignment.objects.create(user=self.user, classroom=self.classroom_b, role=role_b, student=student_b)

        self._set_active_classroom(self.classroom_a)
        response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual([row["name"] for row in payload["students"]], ["가반 학생"])
        self.assertEqual([row["name"] for row in payload["roles"]], ["가반 역할"])
        self.assertEqual([row["student_name"] for row in payload["assignments"]], ["가반 학생"])

    def test_admin_add_student_creates_row_in_selected_classroom(self):
        self._set_active_classroom(self.classroom_b)

        response = self.client.post(reverse("dt_admin_add_student"), data={"names": "새학생"})
        self.assertEqual(response.status_code, 302)

        student = DTStudent.objects.get(user=self.user, name="새학생")
        self.assertEqual(student.classroom_id, self.classroom_b.id)

    def test_api_data_uses_global_scope_when_no_selected_classroom(self):
        DTStudent.objects.create(user=self.user, classroom=None, name="전역 학생", number=1)
        DTRole.objects.create(user=self.user, classroom=None, name="전역 역할", time_slot="아침")
        DTStudent.objects.create(user=self.user, classroom=self.classroom_a, name="가반 학생", number=2)
        DTRole.objects.create(user=self.user, classroom=self.classroom_a, name="가반 역할", time_slot="점심")

        self._set_active_classroom(None)
        response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual([row["name"] for row in payload["students"]], ["전역 학생"])
        self.assertEqual([row["name"] for row in payload["roles"]], ["전역 역할"])
