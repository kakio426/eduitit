from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from classcalendar.models import CalendarEvent, EventPageBlock
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

    def _create_event(self, title="기존 일정", author=None):
        owner = author or self.teacher
        return CalendarEvent.objects.create(
            title=title,
            classroom=self.classroom,
            author=owner,
            start_time="2026-03-01T10:00:00Z",
            end_time="2026-03-01T11:00:00Z",
            color="indigo",
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )

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
        event = CalendarEvent.objects.filter(title="Test Event", author=self.teacher).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.visibility, CalendarEvent.VISIBILITY_TEACHER)

    def test_teacher_can_create_event_with_note(self):
        response = self.client_teacher.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "메모 일정",
                "note": "실험 키트 챙기기\n학생 역할 분배",
                "start_time": "2026-03-02T09:00",
                "end_time": "2026-03-02T10:00",
                "color": "indigo",
            },
        )
        self.assertEqual(response.status_code, 201)
        event = CalendarEvent.objects.filter(title="메모 일정", author=self.teacher).first()
        self.assertIsNotNone(event)
        text_block = event.blocks.filter(block_type="text").first()
        self.assertIsNotNone(text_block)
        self.assertEqual(text_block.content.get("text"), "실험 키트 챙기기\n학생 역할 분배")

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

    def test_create_event_without_active_classroom_creates_personal_event(self):
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
        self.assertEqual(response.status_code, 201)
        event = CalendarEvent.objects.filter(title="No Classroom", author=self.teacher).first()
        self.assertIsNotNone(event)
        self.assertIsNone(event.classroom)

    def test_unauthenticated_user_cannot_create_event(self):
        response = Client().post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "Anonymous Event",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_teacher_can_update_own_event(self):
        event = self._create_event()
        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "수정된 일정",
                "start_time": "2026-03-01T13:00",
                "end_time": "2026-03-01T14:30",
                "color": "emerald",
            },
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.title, "수정된 일정")
        self.assertEqual(event.color, "emerald")
        self.assertEqual(event.visibility, CalendarEvent.VISIBILITY_TEACHER)

    def test_teacher_can_update_event_note(self):
        event = self._create_event(title="노트 수정 일정")
        EventPageBlock.objects.create(
            event=event,
            block_type="text",
            content={"text": "이전 메모"},
            order=0,
        )
        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "노트 수정 일정",
                "note": "새로운 준비물 체크",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
                "color": "indigo",
            },
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        text_block = event.blocks.filter(block_type="text").first()
        self.assertIsNotNone(text_block)
        self.assertEqual(text_block.content.get("text"), "새로운 준비물 체크")

    def test_teacher_can_delete_own_event(self):
        event = self._create_event()
        response = self.client_teacher.post(
            reverse("classcalendar:api_delete_event", kwargs={"event_id": str(event.id)})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CalendarEvent.objects.filter(id=event.id).exists())

    def test_teacher_cannot_update_other_teacher_event(self):
        event = self._create_event(author=self.other_teacher)
        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "권한없는 수정",
                "start_time": "2026-03-01T13:00",
                "end_time": "2026-03-01T14:30",
                "color": "rose",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_update_locked_integration_event(self):
        event = self._create_event()
        event.is_locked = True
        event.integration_source = "collect_deadline"
        event.integration_key = "collect:test"
        event.save(update_fields=["is_locked", "integration_source", "integration_key", "updated_at"])

        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "잠금 수정 시도",
                "start_time": "2026-03-01T13:00",
                "end_time": "2026-03-01T14:00",
                "color": "rose",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "integration_event_readonly")

    def test_teacher_cannot_delete_locked_integration_event(self):
        event = self._create_event()
        event.is_locked = True
        event.integration_source = "consent_expiry"
        event.integration_key = "consent:test"
        event.save(update_fields=["is_locked", "integration_source", "integration_key", "updated_at"])

        response = self.client_teacher.post(
            reverse("classcalendar:api_delete_event", kwargs={"event_id": str(event.id)})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "integration_event_readonly")
