import json
import os
from unittest.mock import patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent, EventPageBlock

User = get_user_model()


class ExternalCalendarWebhookTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="user694",
            password="pw12345",
            email="user694@example.com",
        )
        owner_profile = self.owner.userprofile
        owner_profile.nickname = "관리자"
        owner_profile.role = "school"
        owner_profile.save(update_fields=["nickname", "role"])

    def test_external_calendar_webhook_requires_valid_hook_token(self):
        with patch.dict(os.environ, {"HOOK_TOKEN": "test-hook-token"}, clear=False):
            response = self.client.post(
                reverse("classcalendar:external_calendar_webhook"),
                data=json.dumps({}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "auth_failed")

    def test_external_calendar_webhook_creates_event_for_user694(self):
        payload = {
            "title": "오픈클로 일정",
            "note": "웹훅으로 들어온 일정",
            "start_time": "2026-03-27T09:00:00+09:00",
            "end_time": "2026-03-27T10:00:00+09:00",
            "external_id": "openclo-evt-1",
        }

        with patch.dict(os.environ, {"HOOK_TOKEN": "test-hook-token"}, clear=False):
            response = self.client.post(
                reverse("classcalendar:external_calendar_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_HOOK_TOKEN="test-hook-token",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["result"], "created")
        event = CalendarEvent.objects.get(author=self.owner, integration_key="openclo-evt-1")
        self.assertEqual(event.integration_source, "openclo_webhook")
        self.assertEqual(event.title, "오픈클로 일정")
        self.assertTrue(
            EventPageBlock.objects.filter(
                event=event,
                block_type="text",
                content={"text": "웹훅으로 들어온 일정"},
            ).exists()
        )

    def test_external_calendar_webhook_updates_existing_event_when_external_id_repeats(self):
        existing_event = CalendarEvent.objects.create(
            title="기존 제목",
            author=self.owner,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            source=CalendarEvent.SOURCE_LOCAL,
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            integration_source="openclo_webhook",
            integration_key="openclo-evt-1",
        )

        payload = {
            "title": "업데이트된 제목",
            "start_time": "2026-03-28T13:00:00+09:00",
            "end_time": "2026-03-28T14:00:00+09:00",
            "external_id": "openclo-evt-1",
        }

        with patch.dict(os.environ, {"HOOK_TOKEN": "test-hook-token"}, clear=False):
            response = self.client.post(
                reverse("classcalendar:external_calendar_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_HOOK_TOKEN="test-hook-token",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "updated")
        self.assertEqual(CalendarEvent.objects.filter(author=self.owner, integration_key="openclo-evt-1").count(), 1)
        existing_event.refresh_from_db()
        self.assertEqual(existing_event.title, "업데이트된 제목")
