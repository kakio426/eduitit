import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from classcalendar.models import CalendarEvent, CalendarMessageCapture

User = get_user_model()


class MessageCaptureCommandTests(TestCase):
    def test_export_message_capture_dataset_includes_snapshot_fields(self):
        user = User.objects.create_user(username="dataset_teacher", password="pw12345")
        capture = CalendarMessageCapture.objects.create(
            author=user,
            raw_text="2026-03-15까지 보고서 제출",
            normalized_text="2026-03-15까지 보고서 제출",
            parse_status=CalendarMessageCapture.ParseStatus.PARSED,
            predicted_item_type=CalendarMessageCapture.ItemType.TASK,
            confirmed_item_type=CalendarMessageCapture.ConfirmedItemType.TASK,
            decision_source=CalendarMessageCapture.DecisionSource.MANUAL,
            initial_extract_payload={"predicted_item_type": "task", "draft_task": {"due_at": "2026-03-15T23:59:00+09:00"}},
            final_commit_payload={"item_type": "task", "title": "보고서 제출"},
            edit_diff_payload={"changed_fields": ["title"]},
            rule_version="mvp-v2",
        )
        out = StringIO()
        call_command("export_message_capture_dataset", stdout=out)
        lines = [line for line in out.getvalue().splitlines() if line.strip() and not line.startswith("exported ")]
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["capture_id"], str(capture.id))
        self.assertEqual(payload["label"], "task")
        self.assertIn("initial_extract_payload", payload)
        self.assertIn("final_commit_payload", payload)
        self.assertIn("edit_diff_payload", payload)

    def test_backfill_message_capture_snapshots_populates_missing_fields(self):
        user = User.objects.create_user(username="backfill_teacher", password="pw12345")
        event = CalendarEvent.objects.create(
            author=user,
            title="학년 협의회",
            start_time="2026-03-20T15:00:00+09:00",
            end_time="2026-03-20T16:00:00+09:00",
            is_all_day=False,
            color="indigo",
        )
        capture = CalendarMessageCapture.objects.create(
            author=user,
            raw_text="3월 20일 3시 학년 협의회",
            normalized_text="3월 20일 3시 학년 협의회",
            parse_status=CalendarMessageCapture.ParseStatus.PARSED,
            predicted_item_type=CalendarMessageCapture.ItemType.UNKNOWN,
            extracted_title="학년 협의회",
            extracted_start_time=event.start_time,
            extracted_end_time=event.end_time,
            committed_event=event,
        )

        out = StringIO()
        call_command("backfill_message_capture_snapshots", stdout=out)
        self.assertIn("backfilled 1 captures", out.getvalue())

        capture.refresh_from_db()
        self.assertEqual(capture.predicted_item_type, CalendarMessageCapture.ItemType.EVENT)
        self.assertEqual(capture.confirmed_item_type, CalendarMessageCapture.ConfirmedItemType.EVENT)
        self.assertEqual(capture.rule_version, "mvp-v2")
        self.assertEqual(capture.initial_extract_payload.get("predicted_item_type"), "event")
        self.assertEqual(capture.final_commit_payload.get("item_type"), "event")
        self.assertIn("field_changes", capture.edit_diff_payload)
