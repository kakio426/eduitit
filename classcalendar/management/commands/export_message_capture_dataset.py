import json

from django.core.management.base import BaseCommand

from classcalendar.models import CalendarMessageCapture


class Command(BaseCommand):
    help = "메시지 캡처 학습용 데이터셋을 JSONL로 내보냅니다."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="", help="JSONL 출력 파일 경로")
        parser.add_argument("--limit", type=int, default=0, help="내보낼 최대 건수")
        parser.add_argument(
            "--include-uncommitted",
            action="store_true",
            help="미저장 캡처도 포함합니다.",
        )

    def handle(self, *args, **options):
        queryset = CalendarMessageCapture.objects.select_related("author", "committed_event", "committed_task").prefetch_related("attachments").order_by("created_at", "id")
        if not options["include_uncommitted"]:
            queryset = queryset.filter(confirmed_item_type__in=["event", "task"])
        limit = int(options.get("limit") or 0)
        if limit > 0:
            queryset = queryset[:limit]

        rows = []
        for capture in queryset:
            confirmed_item_type = capture.confirmed_item_type or ""
            if confirmed_item_type == CalendarMessageCapture.ConfirmedItemType.MANUAL_SKIP:
                label = CalendarMessageCapture.ItemType.IGNORE
            elif confirmed_item_type:
                label = confirmed_item_type
            else:
                label = capture.predicted_item_type or CalendarMessageCapture.ItemType.UNKNOWN
            rows.append(
                {
                    "capture_id": str(capture.id),
                    "author_id": capture.author_id,
                    "source_hint": capture.source_hint,
                    "raw_text": capture.raw_text,
                    "normalized_text": capture.normalized_text,
                    "predicted_item_type": capture.predicted_item_type,
                    "confirmed_item_type": confirmed_item_type,
                    "label": label,
                    "parse_status": capture.parse_status,
                    "confidence_score": float(capture.confidence_score or 0),
                    "rule_version": capture.rule_version,
                    "ml_scores": capture.ml_scores if isinstance(capture.ml_scores, dict) else {},
                    "initial_extract_payload": capture.initial_extract_payload if isinstance(capture.initial_extract_payload, dict) else {},
                    "final_commit_payload": capture.final_commit_payload if isinstance(capture.final_commit_payload, dict) else {},
                    "edit_diff_payload": capture.edit_diff_payload if isinstance(capture.edit_diff_payload, dict) else {},
                    "attachment_extensions": sorted(
                        {
                            (attachment.original_name or "").split(".")[-1].lower()
                            for attachment in capture.attachments.all()
                            if "." in (attachment.original_name or "")
                        }
                    ),
                }
            )

        output = options.get("output") or ""
        if output:
            with open(output, "w", encoding="utf-8") as fp:
                for row in rows:
                    fp.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.stdout.write(self.style.SUCCESS(f"exported {len(rows)} rows to {output}"))
            return

        for row in rows:
            self.stdout.write(json.dumps(row, ensure_ascii=False))
