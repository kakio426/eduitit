from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from classcalendar.models import CalendarEvent, GoogleAccount, GoogleSyncState
from classcalendar.oauth_views import _encrypt_secret

User = get_user_model()


class FakeGoogleError(Exception):
    def __init__(self, status):
        super().__init__(f"status={status}")
        self.resp = SimpleNamespace(status=status)


class GoogleSyncTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="pw", email="teacher@example.com")
        from core.models import UserProfile

        UserProfile.objects.filter(user=self.user).update(nickname="teacher_nick")
        self.client = Client()
        self.client.login(username="teacher", password="pw")

    def _create_connected_account(self):
        return GoogleAccount.objects.create(
            user=self.user,
            email=self.user.email,
            credentials={
                "refresh_token_encrypted": _encrypt_secret("refresh-token"),
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
            },
        )

    def test_oauth_login_redirects_to_google_authorize_url(self):
        flow = MagicMock()
        flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?state=test", "state-1")

        with patch("classcalendar.oauth_views._build_oauth_flow", return_value=flow):
            response = self.client.get(reverse("classcalendar:oauth_login"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response["Location"])
        self.assertEqual(self.client.session.get("classcalendar_google_oauth_state"), "state-1")

    def test_oauth_callback_rejects_state_mismatch(self):
        session = self.client.session
        session["classcalendar_google_oauth_state"] = "expected-state"
        session.save()

        response = self.client.get(
            reverse("classcalendar:oauth_callback"),
            {"state": "wrong-state", "code": "auth-code"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=oauth_state_mismatch", response["Location"])

    def test_oauth_callback_saves_encrypted_refresh_token(self):
        session = self.client.session
        session["classcalendar_google_oauth_state"] = "state-ok"
        session.save()

        credentials = SimpleNamespace(
            refresh_token="real-refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        flow = MagicMock()
        flow.credentials = credentials

        with patch("classcalendar.oauth_views._build_oauth_flow", return_value=flow):
            response = self.client.get(
                reverse("classcalendar:oauth_callback"),
                {"state": "state-ok", "code": "auth-code"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("success=google_connected", response["Location"])
        account = GoogleAccount.objects.get(user=self.user)
        saved = account.credentials
        self.assertIn("refresh_token_encrypted", saved)
        self.assertNotEqual(saved["refresh_token_encrypted"], "real-refresh-token")

    def test_api_google_sync_without_connection_returns_401(self):
        response = self.client.post(reverse("classcalendar:api_google_sync"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "google_not_connected")

    def test_api_google_sync_success_creates_local_event_and_updates_sync_token(self):
        account = self._create_connected_account()
        service = MagicMock()
        events_resource = MagicMock()
        events_resource.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "google-event-1",
                    "summary": "Google Imported Event",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-03-01T10:00:00+09:00"},
                    "end": {"dateTime": "2026-03-01T11:00:00+09:00"},
                    "etag": '"etag-1"',
                }
            ],
            "nextSyncToken": "sync-token-1",
        }
        service.events.return_value = events_resource

        with patch("classcalendar.oauth_views._build_calendar_service", return_value=service):
            response = self.client.post(
                reverse("classcalendar:api_google_sync"),
                {"google_calendar_id": "primary"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["counts"]["created"], 1)
        self.assertTrue(
            CalendarEvent.objects.filter(author=self.user, title="Google Imported Event", source="google").exists()
        )
        sync_state = GoogleSyncState.objects.get(account=account, google_calendar_id="primary")
        self.assertEqual(sync_state.sync_token, "sync-token-1")

    def test_api_google_sync_returns_429_on_rate_limit(self):
        self._create_connected_account()
        with patch("classcalendar.oauth_views._build_calendar_service", side_effect=FakeGoogleError(429)):
            response = self.client.post(reverse("classcalendar:api_google_sync"))

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "google_rate_limited")
