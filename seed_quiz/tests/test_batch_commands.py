from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from seed_quiz.models import SQBatchJob


class BatchCommandTest(TestCase):
    def test_batch_tick_submits_dry_run_when_missing(self):
        out = StringIO()
        call_command(
            "seed_quiz_batch_tick",
            "--target-month",
            "2026-03",
            "--dry-run",
            "--skip-collect",
            stdout=out,
        )
        job = SQBatchJob.objects.filter(target_month=date(2026, 3, 1)).first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "pending")
        self.assertGreater(job.requested_count, 0)

    def test_batch_tick_skip_submit_when_existing_job(self):
        SQBatchJob.objects.create(
            provider="openai",
            target_month=date(2026, 3, 1),
            status="submitted",
            requested_count=10,
        )
        out = StringIO()
        call_command(
            "seed_quiz_batch_tick",
            "--target-month",
            "2026-03",
            "--dry-run",
            "--skip-collect",
            stdout=out,
        )
        self.assertEqual(SQBatchJob.objects.filter(target_month=date(2026, 3, 1)).count(), 1)

    @patch("seed_quiz.management.commands.seed_quiz_batch_tick.ingest_completed_batch_output")
    @patch("seed_quiz.management.commands.seed_quiz_batch_tick.sync_batch_job_status")
    def test_batch_tick_collect_target_month_only(self, mock_sync, mock_ingest):
        march_job = SQBatchJob.objects.create(
            provider="openai",
            target_month=date(2026, 3, 1),
            status="completed",
            requested_count=10,
            batch_id="batch_march",
        )
        SQBatchJob.objects.create(
            provider="openai",
            target_month=date(2026, 4, 1),
            status="completed",
            requested_count=10,
            batch_id="batch_april",
        )
        mock_sync.side_effect = lambda job: job
        mock_ingest.side_effect = lambda job: job

        call_command(
            "seed_quiz_batch_tick",
            "--skip-submit",
            "--collect-target-month-only",
            "--target-month",
            "2026-03",
            stdout=StringIO(),
        )

        self.assertEqual(mock_sync.call_count, 1)
        self.assertEqual(mock_ingest.call_count, 1)
        called_job = mock_sync.call_args[0][0]
        self.assertEqual(called_job.id, march_job.id)
