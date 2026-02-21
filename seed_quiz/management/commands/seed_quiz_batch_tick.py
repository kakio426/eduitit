from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from seed_quiz.models import SQBatchJob
from seed_quiz.services.batch_generator import (
    BatchConfig,
    ingest_completed_batch_output,
    submit_batch_job,
    sync_batch_job_status,
)
from seed_quiz.topics import TOPIC_LABELS


def _parse_target_month(raw: str) -> date:
    raw = (raw or "").strip()
    if raw:
        year, month = map(int, raw.split("-"))
        return date(year, month, 1)

    today = date.today()
    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1
    return date(year, month, 1)


class Command(BaseCommand):
    help = "Run monthly Seed Quiz batch pipeline tick (submit-if-missing + collect)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-month",
            type=str,
            default="",
            help="Target month in YYYY-MM format. Default: next month.",
        )
        parser.add_argument(
            "--preset-types",
            type=str,
            default=",".join(TOPIC_LABELS.keys()),
            help="Comma-separated preset types for submit step.",
        )
        parser.add_argument(
            "--grades",
            type=str,
            default="3,4,5,6",
            help="Comma-separated grades for submit step.",
        )
        parser.add_argument(
            "--model",
            type=str,
            default="gpt-4o-mini",
            help="Model name for submit step.",
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
            help="Optional username for created_by on submitted job.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Submit step only creates pending DB job without external API call.",
        )
        parser.add_argument(
            "--skip-submit",
            action="store_true",
            help="Skip submit-if-missing step.",
        )
        parser.add_argument(
            "--skip-collect",
            action="store_true",
            help="Skip collect(sync/ingest) step.",
        )
        parser.add_argument(
            "--no-ingest",
            action="store_true",
            help="Collect step syncs status only, without ingest.",
        )
        parser.add_argument(
            "--collect-target-month-only",
            action="store_true",
            help="Collect only jobs for --target-month.",
        )

    def handle(self, *args, **options):
        if not bool(getattr(settings, "SEED_QUIZ_BATCH_ENABLED", False)):
            self.stdout.write(
                self.style.WARNING(
                    "SEED_QUIZ_BATCH_ENABLED=False: 배치 자동화가 비활성화되어 있습니다 (CSV 운영 모드)."
                )
            )
            return

        try:
            target_month = _parse_target_month(options.get("target_month") or "")
        except Exception:
            self.stderr.write(self.style.ERROR("Invalid --target-month. Use YYYY-MM."))
            return

        preset_types = [p.strip() for p in (options.get("preset_types") or "").split(",") if p.strip()]
        grades: list[int] = []
        for raw in (options.get("grades") or "").split(","):
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

        if not options.get("skip_submit"):
            existing = SQBatchJob.objects.filter(target_month=target_month).exclude(
                status__in=["failed", "cancelled"]
            )
            if existing.exists():
                first = existing.order_by("-started_at").first()
                self.stdout.write(
                    f"[submit] skip existing job target_month={target_month} job={first.id} status={first.status}"
                )
            else:
                config = BatchConfig(
                    target_month=target_month,
                    preset_types=preset_types,
                    grades=grades,
                    model=options.get("model") or "gpt-4o-mini",
                    completion_window=options.get("completion_window") or "24h",
                )
                job = submit_batch_job(
                    config=config,
                    created_by=created_by,
                    dry_run=bool(options.get("dry_run")),
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[submit] created job={job.id} status={job.status} requested={job.requested_count}"
                    )
                )

        if options.get("skip_collect"):
            return

        jobs = SQBatchJob.objects.filter(
            status__in=["submitted", "validating", "in_progress", "finalizing", "completed"]
        )
        if options.get("collect_target_month_only"):
            jobs = jobs.filter(target_month=target_month)

        if not jobs.exists():
            self.stdout.write("[collect] no jobs")
            return

        no_ingest = bool(options.get("no_ingest"))
        for job in jobs.order_by("started_at"):
            try:
                before = job.status
                job = sync_batch_job_status(job)
                self.stdout.write(
                    f"[collect] job={job.id} status={before}->{job.status} batch_id={job.batch_id or '-'}"
                )
                if not no_ingest and job.status == "completed":
                    already_ingested = bool((job.meta_json or {}).get("ingested"))
                    if not already_ingested:
                        job = ingest_completed_batch_output(job)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[ingest] job={job.id} success={job.success_count} failed={job.failed_count}"
                            )
                        )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[error] job={job.id}: {e}"))
