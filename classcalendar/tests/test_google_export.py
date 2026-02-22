from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from classcalendar.models import CalendarEvent, EventExternalMap, GoogleAccount
from classcalendar.oauth_views import _encrypt_secret
from happy_seed.models import HSClassroom

User = get_user_model()


class GoogleExportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="pw", email="teacher@example.com")
        self.client = Client()
        self.client.login(username="teacher", password="pw")
        self.classroom = HSClassroom.objects.create(name="Class 1", teacher=self.user, slug="class-1")
        self.account = GoogleAccount.objects.create(
            user=self.user,
            email=self.user.email,
            credentials={
                "refresh_token_encrypted": _encrypt_secret("refresh-token"),
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/calendar.events"],
            },
        )

    def _create_event(self, title="Local Event"):
        return CalendarEvent.objects.create(
            title=title,
            start_time="2026-04-01T10:00:00Z",
            end_time="2026-04-01T11:00:00Z",
            author=self.user,
            classroom=self.classroom,
        )

    def test_export_requires_google_connection(self):
        self.account.delete()
        event = self._create_event()
        response = self.client.post(reverse("classcalendar:api_google_export", kwargs={"event_id": str(event.id)}))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "google_not_connected")

    def test_export_new_event_creates_external_map(self):
        event = self._create_event()
        service = MagicMock()
        service.events.return_value.insert.return_value.execute.return_value = {
            "id": "google_abc123",
            "etag": '"etag_new"',
        }

        with patch("classcalendar.oauth_views._build_calendar_service", return_value=service):
            response = self.client.post(
                reverse("classcalendar:api_google_export", kwargs={"event_id": str(event.id)}),
                {"google_calendar_id": "primary"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        mapping = EventExternalMap.objects.filter(event=event, account=self.account, google_calendar_id="primary").first()
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.google_event_id, "google_abc123")
        self.assertEqual(mapping.etag, '"etag_new"')

    def test_export_update_event_detects_etag_mismatch(self):
        event = self._create_event(title="Local Event 2")
        EventExternalMap.objects.create(
            account=self.account,
            event=event,
            google_calendar_id="primary",
            google_event_id="google_123",
            etag='"local_old_etag"',
        )
        service = MagicMock()
        service.events.return_value.get.return_value.execute.return_value = {"etag": '"remote_new_etag"'}

        with patch("classcalendar.oauth_views._build_calendar_service", return_value=service):
            response = self.client.post(
                reverse("classcalendar:api_google_export", kwargs={"event_id": str(event.id)}),
                {"google_calendar_id": "primary"},
            )

        self.assertEqual(response.status_code, 412)
        self.assertEqual(response.json()["code"], "etag_mismatch")

    def test_export_update_event_success_updates_etag(self):
        event = self._create_event(title="Local Event 3")
        mapping = EventExternalMap.objects.create(
            account=self.account,
            event=event,
            google_calendar_id="primary",
            google_event_id="google_456",
            etag='"etag_old"',
        )
        service = MagicMock()
        service.events.return_value.get.return_value.execute.return_value = {"etag": '"etag_old"'}
        service.events.return_value.update.return_value.execute.return_value = {
            "id": "google_456",
            "etag": '"etag_new"',
        }

        with patch("classcalendar.oauth_views._build_calendar_service", return_value=service):
            response = self.client.post(
                reverse("classcalendar:api_google_export", kwargs={"event_id": str(event.id)}),
                {"google_calendar_id": "primary"},
            )

        self.assertEqual(response.status_code, 200)
        mapping.refresh_from_db()
        self.assertEqual(mapping.etag, '"etag_new"')
