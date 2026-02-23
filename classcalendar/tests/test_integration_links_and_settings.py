import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.integrations import (
    SOURCE_COLLECT_DEADLINE,
    SOURCE_CONSENT_EXPIRY,
    SOURCE_RESERVATION,
    SOURCE_SIGNATURES_TRAINING,
)
from classcalendar.models import CalendarEvent, CalendarIntegrationSetting
from classcalendar.views import INTEGRATION_SYNC_SESSION_KEY


User = get_user_model()


class IntegrationLinksAndSettingsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cc_link_user",
            password="pw12345",
            email="cc_link_user@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _create_locked_event(self, *, source, key, title):
        now = timezone.now()
        return CalendarEvent.objects.create(
            title=title,
            author=self.user,
            start_time=now,
            end_time=now + timedelta(hours=1),
            is_all_day=False,
            source=CalendarEvent.SOURCE_LOCAL,
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            integration_source=source,
            integration_key=key,
            is_locked=True,
        )

    def test_api_events_includes_source_links_for_all_integrations(self):
        self._create_locked_event(
            source=SOURCE_COLLECT_DEADLINE,
            key=f"collect:{uuid.uuid4()}",
            title="수합 마감",
        )
        self._create_locked_event(
            source=SOURCE_CONSENT_EXPIRY,
            key=f"consent:{uuid.uuid4()}",
            title="동의서 만료",
        )
        self._create_locked_event(
            source=SOURCE_RESERVATION,
            key="reservation:1:test-school:2026-03-01",
            title="특별실 예약",
        )
        self._create_locked_event(
            source=SOURCE_SIGNATURES_TRAINING,
            key=f"signatures:{uuid.uuid4()}",
            title="서명 연수",
        )
        session = self.client.session
        session[INTEGRATION_SYNC_SESSION_KEY] = timezone.now().timestamp()
        session.save()

        response = self.client.get(reverse("classcalendar:api_events"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "success")

        source_map = {}
        for item in payload.get("events", []):
            source_map[item.get("integration_source")] = item

        self.assertTrue(source_map[SOURCE_COLLECT_DEADLINE]["source_url"])
        self.assertTrue(source_map[SOURCE_CONSENT_EXPIRY]["source_url"])
        self.assertTrue(source_map[SOURCE_RESERVATION]["source_url"])
        self.assertTrue(source_map[SOURCE_SIGNATURES_TRAINING]["source_url"])

    def test_api_integration_settings_disables_and_cleans_up_sources(self):
        self._create_locked_event(
            source=SOURCE_COLLECT_DEADLINE,
            key=f"collect:{uuid.uuid4()}",
            title="수합 마감",
        )
        self._create_locked_event(
            source=SOURCE_SIGNATURES_TRAINING,
            key=f"signatures:{uuid.uuid4()}",
            title="서명 연수",
        )

        response = self.client.post(
            reverse("classcalendar:api_integration_settings"),
            {
                "collect_deadline_enabled": "false",
                "consent_expiry_enabled": "true",
                "reservation_enabled": "true",
                "signatures_training_enabled": "false",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "success")
        self.assertFalse(payload["settings"]["collect_deadline_enabled"])
        self.assertFalse(payload["settings"]["signatures_training_enabled"])

        self.assertFalse(
            CalendarEvent.objects.filter(
                author=self.user,
                integration_source=SOURCE_COLLECT_DEADLINE,
            ).exists()
        )
        self.assertFalse(
            CalendarEvent.objects.filter(
                author=self.user,
                integration_source=SOURCE_SIGNATURES_TRAINING,
            ).exists()
        )

        setting = CalendarIntegrationSetting.objects.get(user=self.user)
        self.assertFalse(setting.collect_deadline_enabled)
        self.assertFalse(setting.signatures_training_enabled)
