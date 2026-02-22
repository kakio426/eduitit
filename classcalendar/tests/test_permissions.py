from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from classcalendar.models import CalendarEvent
from happy_seed.models import HSClassroom

User = get_user_model()


class PermissionTest(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="pw", email="teacher@example.com")
        self.other_teacher = User.objects.create_user(username="other", password="pw", email="other@example.com")
        self.classroom = HSClassroom.objects.create(
            name="Test Class",
            teacher=self.teacher,
            slug="test-class-123",
        )
        self.client_teacher = Client()
        self.client_teacher.login(username="teacher", password="pw")
        session = self.client_teacher.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

        self.client_student = Client()

    def test_teacher_can_create_event(self):
        response = self.client_teacher.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "Test Event",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
                "visibility": "class_readonly",
                "color": "indigo",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(CalendarEvent.objects.filter(title="Test Event", author=self.teacher).exists())

    def test_create_event_rejects_invalid_time_range(self):
        response = self.client_teacher.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "Invalid Event",
                "start_time": "2026-03-01T11:00",
                "end_time": "2026-03-01T10:00",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "validation_error")

    def test_create_event_requires_active_classroom(self):
        client = Client()
        client.login(username="teacher", password="pw")
        response = client.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "No Classroom",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "active_classroom_required")

    def test_student_cannot_create_event(self):
        response = self.client_student.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "Student Event",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_student_view_hides_teacher_only_events(self):
        CalendarEvent.objects.create(
            title="Class Event",
            classroom=self.classroom,
            author=self.teacher,
            start_time="2026-03-01T10:00:00Z",
            end_time="2026-03-01T11:00:00Z",
            visibility=CalendarEvent.VISIBILITY_CLASS,
        )
        CalendarEvent.objects.create(
            title="Teacher Secret",
            classroom=self.classroom,
            author=self.teacher,
            start_time="2026-03-01T12:00:00Z",
            end_time="2026-03-01T13:00:00Z",
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )

        response = self.client_student.get(reverse("classcalendar:student_view", kwargs={"slug": self.classroom.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Class Event")
        self.assertNotContains(response, "Teacher Secret")
