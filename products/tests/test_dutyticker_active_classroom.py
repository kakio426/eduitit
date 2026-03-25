from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSGuardianConsent, HSStudent
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

    def _create_hs_student(self, classroom, number, name, consent_status=None):
        student = HSStudent.objects.create(
            classroom=classroom,
            number=number,
            name=name,
        )
        if consent_status is not None:
            HSGuardianConsent.objects.create(student=student, status=consent_status)
        return student

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

    def test_admin_upload_students_csv_creates_rows_in_selected_classroom(self):
        self._set_active_classroom(self.classroom_a)
        csv_file = SimpleUploadedFile(
            "students.csv",
            "번호,이름\n1,김하늘\n2,박바다\n".encode("utf-8-sig"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("dt_admin_upload_students_csv"),
            data={"csv_file": csv_file},
        )

        self.assertEqual(response.status_code, 302)
        students = list(
            DTStudent.objects.filter(user=self.user, classroom=self.classroom_a).order_by("number")
        )
        self.assertEqual([(student.number, student.name) for student in students], [(1, "김하늘"), (2, "박바다")])

    def test_admin_clear_example_students_removes_known_sample_names_only(self):
        self._set_active_classroom(self.classroom_a)
        DTStudent.objects.create(user=self.user, classroom=self.classroom_a, name="김철수", number=1)
        DTStudent.objects.create(user=self.user, classroom=self.classroom_a, name="진짜학생", number=2)

        response = self.client.post(reverse("dt_admin_clear_example_students"))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(DTStudent.objects.filter(user=self.user, classroom=self.classroom_a, name="김철수").exists())
        self.assertTrue(DTStudent.objects.filter(user=self.user, classroom=self.classroom_a, name="진짜학생").exists())

    def test_api_data_does_not_seed_example_students_when_empty(self):
        self._set_active_classroom(self.classroom_a)

        response = self.client.get(reverse("dt_api_data"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["students"], [])
        self.assertEqual(payload["roles"], [])
        self.assertFalse(DTStudent.objects.filter(user=self.user, classroom=self.classroom_a).exists())

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

    def test_api_data_uses_default_classroom_when_session_is_empty(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.default_classroom = self.classroom_b
        profile.save(update_fields=["default_classroom"])

        DTStudent.objects.create(user=self.user, classroom=self.classroom_b, name="기본반 학생", number=1)
        DTRole.objects.create(user=self.user, classroom=self.classroom_b, name="기본반 역할", time_slot="점심")
        DTStudent.objects.create(user=self.user, classroom=None, name="전역 학생", number=2)

        self._set_active_classroom(None)
        response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual([row["name"] for row in payload["students"]], ["기본반 학생"])
        self.assertEqual([row["name"] for row in payload["roles"]], ["기본반 역할"])
        session = self.client.session
        self.assertEqual(session["active_classroom_source"], "hs")
        self.assertEqual(session["active_classroom_id"], str(self.classroom_b.id))

    def test_admin_dashboard_shows_consent_summary_for_selected_classroom(self):
        self._create_hs_student(self.classroom_a, 1, "김동의", "approved")
        self._create_hs_student(self.classroom_a, 2, "박대기")
        self._create_hs_student(self.classroom_a, 3, "최거부", "rejected")
        self._create_hs_student(self.classroom_b, 1, "다른반 만료", "expired")

        self._set_active_classroom(self.classroom_a)
        response = self.client.get(reverse("dt_admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        summary = response.context["consent_summary"]
        self.assertTrue(summary["enabled"])
        self.assertEqual(summary["classroom_name"], self.classroom_a.name)
        self.assertEqual(summary["total_count"], 3)
        self.assertEqual(summary["approved_count"], 1)
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["expired_count"], 0)
        self.assertEqual(summary["needs_attention_count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["preview_students"]],
            ["박대기", "최거부"],
        )
        self.assertContains(
            response,
            reverse("happy_seed:consent_manage", kwargs={"classroom_id": self.classroom_a.id}),
        )
        self.assertContains(response, "확인 필요한 학생 2명")
        self.assertContains(response, "박대기")
        self.assertContains(response, "최거부")
        self.assertNotContains(response, "다른반 만료")

    def test_admin_dashboard_shows_disabled_consent_cta_without_selected_classroom(self):
        self._set_active_classroom(None)

        response = self.client.get(reverse("dt_admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        summary = response.context["consent_summary"]
        self.assertFalse(summary["enabled"])
        self.assertEqual(summary["preview_students"], [])
        self.assertContains(response, "반을 먼저 고르면")
        self.assertContains(response, "이 기능을 필요할 때만")
