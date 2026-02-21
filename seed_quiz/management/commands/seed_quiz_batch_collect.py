import uuid

from django.core.management.base import BaseCommand

from seed_quiz.models import SQBatchJob
from seed_quiz.services.batch_generator import ingest_completed_batch_output, sync_batch_job_status


class Command(BaseCommand):
    help = "Collect status/output for Seed Quiz batch jobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            type=str,
            default="",
            help="Optional SQBatchJob UUID.",
        )
        parser.add_argument(
            "--no-ingest",
            action="store_true",
            help="Only sync status. Skip output ingestion.",
        )

    def handle(self, *args, **options):
        job_id_raw = (options.get("job_id") or "").strip()
        no_ingest = bool(options.get("no_ingest"))

        jobs = SQBatchJob.objects.none()
        if job_id_raw:
            try:
                job_uuid = uuid.UUID(job_id_raw)
            except ValueError:
                self.stderr.write(self.style.ERROR("Invalid --job-id UUID"))
                return
            jobs = SQBatchJob.objects.filter(id=job_uuid)
        else:
            jobs = SQBatchJob.objects.filter(status__in=["submitted", "validating", "in_progress", "finalizing", "completed"])

        if not jobs.exists():
            self.stdout.write("No batch jobs to collect.")
            return

        for job in jobs.order_by("started_at"):
            try:
                before = job.status
                job = sync_batch_job_status(job)
                self.stdout.write(
                    f"[sync] job={job.id} status={before} -> {job.status} batch_id={job.batch_id or '-'}"
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
