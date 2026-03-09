from django.core.management.base import BaseCommand

from classcalendar.models import CalendarMessageCapture, CalendarTask
from classcalendar.views import (
    MESSAGE_CAPTURE_RULE_VERSION,
    _build_message_capture_edit_diff,
    _build_message_capture_final_payload,
    _build_message_capture_initial_extract_payload,
)


class Command(BaseCommand):
    help = "기존 메시지 캡처 레코드에 스냅샷/분류 필드를 백필합니다."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="처리할 최대 건수")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 대상 건수만 확인합니다.",
        )

    def handle(self, *args, **options):
        queryset = CalendarMessageCapture.objects.select_related("committed_event", "committed_task").order_by("created_at", "id")
        limit = int(options.get("limit") or 0)
        if limit > 0:
            queryset = queryset[:limit]

        updated_count = 0
        dry_run = bool(options.get("dry_run"))

        for capture in queryset:
            dirty_fields = []
            predicted_item_type = capture.predicted_item_type or CalendarMessageCapture.ItemType.UNKNOWN
            if predicted_item_type == CalendarMessageCapture.ItemType.UNKNOWN:
                if capture.committed_task_id:
                    predicted_item_type = CalendarMessageCapture.ItemType.TASK
                elif capture.committed_event_id:
                    predicted_item_type = CalendarMessageCapture.ItemType.EVENT
                elif capture.extracted_start_time and capture.extracted_end_time:
                    predicted_item_type = CalendarMessageCapture.ItemType.EVENT

            parse_payload = capture.parse_payload if isinstance(capture.parse_payload, dict) else {}
            initial_extract_payload = capture.initial_extract_payload if isinstance(capture.initial_extract_payload, dict) else {}
            final_commit_payload = capture.final_commit_payload if isinstance(capture.final_commit_payload, dict) else {}
            edit_diff_payload = capture.edit_diff_payload if isinstance(capture.edit_diff_payload, dict) else {}

            if not initial_extract_payload:
                parsed_like = {
                    "predicted_item_type": predicted_item_type,
                    "confidence_label": parse_payload.get("confidence_label") or "low",
                    "warnings": list(parse_payload.get("warnings") or []),
                    "evidence": parse_payload.get("evidence") or {},
                    "deadline_only": False,
                    "location": "",
                    "materials": "",
                    "audience": "",
                    "category": "",
                    "recurrence_hint": "",
                    "extracted_title": capture.extracted_title or "메시지에서 만든 일정",
                    "extracted_start_time": capture.extracted_start_time,
                    "extracted_end_time": capture.extracted_end_time,
                    "extracted_is_all_day": capture.extracted_is_all_day,
                    "extracted_todo_summary": capture.extracted_todo_summary or "",
                    "extracted_priority": capture.extracted_priority or CalendarMessageCapture.Priority.NORMAL,
                    "task_due_at": capture.committed_task.due_at if capture.committed_task_id else capture.extracted_end_time,
                    "task_has_time": bool(capture.committed_task.has_time) if capture.committed_task_id else False,
                    "task_note": capture.committed_task.note if capture.committed_task_id else (capture.extracted_todo_summary or ""),
                }
                capture.initial_extract_payload = _build_message_capture_initial_extract_payload(parsed_like)
                dirty_fields.append("initial_extract_payload")

            if capture.predicted_item_type != predicted_item_type:
                capture.predicted_item_type = predicted_item_type
                dirty_fields.append("predicted_item_type")

            if not capture.rule_version:
                capture.rule_version = MESSAGE_CAPTURE_RULE_VERSION
                dirty_fields.append("rule_version")

            if not capture.confirmed_item_type:
                if capture.committed_task_id:
                    capture.confirmed_item_type = CalendarMessageCapture.ConfirmedItemType.TASK
                    dirty_fields.append("confirmed_item_type")
                elif capture.committed_event_id:
                    capture.confirmed_item_type = CalendarMessageCapture.ConfirmedItemType.EVENT
                    dirty_fields.append("confirmed_item_type")

            if not final_commit_payload and (capture.committed_event_id or capture.committed_task_id):
                if capture.committed_task_id:
                    final_commit_payload = _build_message_capture_final_payload(
                        {
                            "confirmed_item_type": CalendarMessageCapture.ItemType.TASK,
                            "title": capture.committed_task.title,
                            "note": capture.committed_task.note or "",
                            "due_at": capture.committed_task.due_at,
                            "has_time": bool(capture.committed_task.has_time),
                            "priority": capture.committed_task.priority or CalendarTask.Priority.NORMAL,
                        },
                        selected_attachment_ids=[],
                        source_context=None,
                    )
                else:
                    final_commit_payload = _build_message_capture_final_payload(
                        {
                            "confirmed_item_type": CalendarMessageCapture.ItemType.EVENT,
                            "title": capture.committed_event.title,
                            "todo_summary": capture.extracted_todo_summary or "",
                            "start_time": capture.committed_event.start_time,
                            "end_time": capture.committed_event.end_time,
                            "is_all_day": bool(capture.committed_event.is_all_day),
                            "color": capture.committed_event.color or "indigo",
                        },
                        selected_attachment_ids=[],
                        source_context=None,
                    )
                capture.final_commit_payload = final_commit_payload
                dirty_fields.append("final_commit_payload")

            if not edit_diff_payload and final_commit_payload:
                capture.edit_diff_payload = _build_message_capture_edit_diff(capture, final_commit_payload)
                dirty_fields.append("edit_diff_payload")

            if dirty_fields:
                updated_count += 1
                if not dry_run:
                    capture.save(update_fields=[*dirty_fields, "updated_at"])

        mode = "would backfill" if dry_run else "backfilled"
        self.stdout.write(self.style.SUCCESS(f"{mode} {updated_count} captures"))
