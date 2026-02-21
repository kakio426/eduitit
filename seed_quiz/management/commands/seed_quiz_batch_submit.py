from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from seed_quiz.models import SQBatchJob
from seed_quiz.services.batch_generator import BatchConfig, submit_batch_job


class Command(BaseCommand):
    help = "Submit a monthly OpenAI Batch job for Seed Quiz."

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-month",
            type=str,
            help="Target month in YYYY-MM format. Default: next month.",
        )
        parser.add_argument(
            "--preset-types",
            type=str,
            default="general,korean,math,science,social,english",
            help="Comma-separated preset types.",
        )
        parser.add_argument(
            "--grades",
            type=str,
            default="3,4,5,6",
            help="Comma-separated grades.",
        )
        parser.add_argument(
            "--model",
            type=str,
            default="gpt-4o-mini",
            help="Model name for batch requests.",
        )
        parser.add_argument(
            "--completion-window",
            type=str,
            default="24h",
            help="OpenAI batch completion window (e.g. 24h).",
        )
        parser.add_argument(
            "--created-by",
            type=str,
            default="",
            help="Optional username for created_by field.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Create job record without external API submission.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Submit even if active/completed job already exists for target month.",
        )

    def handle(self, *args, **options):
        target_month_str = (options.get("target_month") or "").strip()
        if target_month_str:
            try:
                year, month = map(int, target_month_str.split("-"))
                target_month = date(year, month, 1)
            except Exception:
                self.stderr.write(self.style.ERROR("Invalid --target-month. Use YYYY-MM."))
                return
        else:
            today = date.today()
            year = today.year + (1 if today.month == 12 else 0)
            month = 1 if today.month == 12 else today.month + 1
            target_month = date(year, month, 1)

        preset_types = [p.strip() for p in options["preset_types"].split(",") if p.strip()]
        grades = []
        for raw in options["grades"].split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                grades.append(int(raw))
            except ValueError:
                self.stderr.write(self.style.WARNING(f"skip invalid grade: {raw}"))

        created_by = None
        username = (options.get("created_by") or "").strip()
        if username:
            created_by = get_user_model().objects.filter(username=username).first()
            if not created_by:
                self.stderr.write(self.style.WARNING(f"created_by user not found: {username}"))

        config = BatchConfig(
            target_month=target_month,
            preset_types=preset_types,
            grades=grades,
            model=options["model"],
            completion_window=options["completion_window"],
        )
        if not bool(options.get("force")):
            existing = SQBatchJob.objects.filter(target_month=target_month).exclude(
                status__in=["failed", "cancelled"]
            )
            if existing.exists():
                first = existing.order_by("-started_at").first()
                self.stdout.write(
                    self.style.WARNING(
                        f"skip submit: existing job={first.id} status={first.status} target_month={target_month}"
                    )
                )
                return

        job = submit_batch_job(config=config, created_by=created_by, dry_run=bool(options["dry_run"]))
        self.stdout.write(
            self.style.SUCCESS(
                f"batch submit done: job={job.id} status={job.status} requested={job.requested_count} batch_id={job.batch_id or '-'}"
            )
        )
