import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from seed_quiz.models import SQBatchJob, SQQuizBank
from seed_quiz.services.batch_generator import ingest_completed_batch_output


@override_settings(SEED_QUIZ_BATCH_ENABLED=True)
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

    def test_seed_quiz_bank_command_keeps_fallback_banks_public(self):
        call_command("seed_quiz_bank", stdout=StringIO())

        bank = SQQuizBank.objects.filter(is_official=True).first()
        self.assertIsNotNone(bank)
        self.assertTrue(bank.is_public)
        self.assertTrue(bank.share_opt_in)

    @patch("seed_quiz.services.batch_generator._get_openai_client")
    def test_completed_batch_ingest_keeps_official_banks_public(self, mock_client):
        payload = {
            "items": [
                {
                    "question_text": "맞춤법이 바른 것은?",
                    "choices": ["되요", "돼요", "돼여", "되여"],
                    "correct_index": 1,
                    "explanation": "돼요가 바릅니다.",
                    "difficulty": "easy",
                },
                {
                    "question_text": "띄어쓰기가 바른 것은?",
                    "choices": ["할수 있다", "할 수 있다", "할 수있다", "할수있다"],
                    "correct_index": 1,
                    "explanation": "할 수 있다가 바릅니다.",
                    "difficulty": "easy",
                },
                {
                    "question_text": "표준어는?",
                    "choices": ["설거지", "설겆이", "설거쥐", "설걷이"],
                    "correct_index": 0,
                    "explanation": "설거지가 표준어입니다.",
                    "difficulty": "easy",
                },
            ]
        }
        line = json.dumps(
            {
                "custom_id": "sq:2026-03-01:orthography:3",
                "response": {
                    "body": {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(payload, ensure_ascii=False),
                                }
                            }
                        ]
                    }
                },
            },
            ensure_ascii=False,
        )
        mock_client.return_value.files.content.return_value.text = line
        job = SQBatchJob.objects.create(
            provider="openai",
            target_month=date(2026, 3, 1),
            status="completed",
            requested_count=1,
            output_file_id="file-output",
        )

        ingest_completed_batch_output(job)

        bank = SQQuizBank.objects.get(title="[공식] 2026-03-01 3학년 맞춤법")
        self.assertTrue(bank.is_public)
        self.assertTrue(bank.share_opt_in)
