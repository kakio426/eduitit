from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarCollaborator, CalendarEvent
from core.models import UserProfile

User = get_user_model()


class CalendarCollaborationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="calendar_owner",
            password="pw12345",
            email="calendar_owner@example.com",
        )
        self.editor = User.objects.create_user(
            username="calendar_editor",
            password="pw12345",
            email="calendar_editor@example.com",
        )
        self.viewer = User.objects.create_user(
            username="calendar_viewer",
            password="pw12345",
            email="calendar_viewer@example.com",
        )
        self.extra_user = User.objects.create_user(
            username="calendar_extra",
            password="pw12345",
            email="calendar_extra@example.com",
        )
        for user, nickname in (
            (self.owner, "오너"),
            (self.editor, "편집자"),
            (self.viewer, "조회자"),
            (self.extra_user, "추가사용자"),
        ):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.nickname = nickname
            profile.save(update_fields=["nickname"])

        self.owner_client = Client()
        self.owner_client.force_login(self.owner)
        self.editor_client = Client()
        self.editor_client.force_login(self.editor)
        self.viewer_client = Client()
        self.viewer_client.force_login(self.viewer)

        now = timezone.now()
        self.owner_event = CalendarEvent.objects.create(
            title="공유 원본 일정",
            author=self.owner,
            start_time=now,
            end_time=now + timedelta(hours=1),
            color="indigo",
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            source=CalendarEvent.SOURCE_LOCAL,
        )

        CalendarCollaborator.objects.create(
            owner=self.owner,
            collaborator=self.editor,
            can_edit=True,
        )
        CalendarCollaborator.objects.create(
            owner=self.owner,
            collaborator=self.viewer,
            can_edit=False,
        )

    def test_collaborator_can_view_owner_events_via_api(self):
        response = self.editor_client.get(reverse("classcalendar:api_events"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        titles = [item.get("title") for item in payload.get("events", [])]
        self.assertIn("공유 원본 일정", titles)

    def test_editor_can_create_event_on_owner_calendar(self):
        response = self.editor_client.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "협업 생성 일정",
                "calendar_owner_id": str(self.owner.id),
                "start_time": "2026-03-05T09:00",
                "end_time": "2026-03-05T10:00",
                "color": "emerald",
            },
        )
        self.assertEqual(response.status_code, 201)
        event = CalendarEvent.objects.filter(title="협업 생성 일정").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.author_id, self.owner.id)

    def test_owner_sees_collaborator_created_event(self):
        self.editor_client.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "함께 쓰는 일정",
                "calendar_owner_id": str(self.owner.id),
                "start_time": "2026-03-06T09:00",
                "end_time": "2026-03-06T10:00",
            },
        )
        response = self.owner_client.get(reverse("classcalendar:api_events"))
        self.assertEqual(response.status_code, 200)
        titles = [item.get("title") for item in response.json().get("events", [])]
        self.assertIn("함께 쓰는 일정", titles)

    def test_viewer_cannot_create_event_on_owner_calendar(self):
        response = self.viewer_client.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "권한없는 생성",
                "calendar_owner_id": str(self.owner.id),
                "start_time": "2026-03-05T09:00",
                "end_time": "2026-03-05T10:00",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get("code"), "permission_denied")

    def test_editor_can_update_owner_event(self):
        response = self.editor_client.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(self.owner_event.id)}),
            {
                "title": "편집 반영 일정",
                "start_time": "2026-03-01T12:00",
                "end_time": "2026-03-01T13:00",
                "color": "rose",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.owner_event.refresh_from_db()
        self.assertEqual(self.owner_event.title, "편집 반영 일정")

    def test_viewer_cannot_update_owner_event(self):
        response = self.viewer_client.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(self.owner_event.id)}),
            {
                "title": "권한없는 수정",
                "start_time": "2026-03-01T12:00",
                "end_time": "2026-03-01T13:00",
                "color": "rose",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_add_collaborator_by_email(self):
        response = self.owner_client.post(
            reverse("classcalendar:collaborator_add"),
            {
                "collaborator_query": self.extra_user.email,
                "can_edit": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CalendarCollaborator.objects.filter(
                owner=self.owner,
                collaborator=self.extra_user,
                can_edit=True,
            ).exists()
        )

    def test_owner_cannot_add_collaborator_by_username(self):
        response = self.owner_client.post(
            reverse("classcalendar:collaborator_add"),
            {
                "collaborator_query": self.extra_user.username,
                "can_edit": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CalendarCollaborator.objects.filter(
                owner=self.owner,
                collaborator=self.extra_user,
            ).exists()
        )

    def test_owner_can_remove_collaborator(self):
        relation = CalendarCollaborator.objects.create(
            owner=self.owner,
            collaborator=self.extra_user,
            can_edit=True,
        )
        response = self.owner_client.post(
            reverse("classcalendar:collaborator_remove", kwargs={"collaborator_id": self.extra_user.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CalendarCollaborator.objects.filter(id=relation.id).exists())
