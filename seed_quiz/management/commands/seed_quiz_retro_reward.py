import uuid

from django.core.management.base import BaseCommand, CommandError

from seed_quiz.services.grading import (
    apply_retroactive_rewards,
    list_retroactive_reward_candidate_ids,
)


class Command(BaseCommand):
    help = "Apply retroactive Seed Quiz rewards for perfect attempts after consent approval."

    def add_arguments(self, parser):
        parser.add_argument(
            "--classroom-id",
            type=str,
            default="",
            help="Optional classroom UUID filter.",
        )
        parser.add_argument(
            "--student-id",
            type=str,
            default="",
            help="Optional student UUID filter.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Max attempts to process (0 or negative means no limit). Default: 500",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not apply rewards, only show candidate count.",
        )

    def handle(self, *args, **options):
        classroom_id = self._parse_uuid(options.get("classroom_id") or "", "--classroom-id")
        student_id = self._parse_uuid(options.get("student_id") or "", "--student-id")
        limit_raw = int(options.get("limit") or 0)
        limit = None if limit_raw <= 0 else limit_raw

        if options.get("dry_run"):
            candidate_ids = list_retroactive_reward_candidate_ids(
                classroom_id=classroom_id,
                student_id=student_id,
                limit=limit,
            )
            self.stdout.write(
                f"[dry-run] candidate={len(candidate_ids)} rewarded=0 skipped={len(candidate_ids)}"
            )
            return

        stats = apply_retroactive_rewards(
            classroom_id=classroom_id,
            student_id=student_id,
            trigger="command",
            limit=limit,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "seed_quiz_retro_reward complete: "
                f"candidate={stats['candidate_count']} "
                f"rewarded={stats['rewarded_count']} skipped={stats['skipped_count']}"
            )
        )

    def _parse_uuid(self, raw: str, label: str) -> uuid.UUID | None:
        raw_value = (raw or "").strip()
        if not raw_value:
            return None
        try:
            return uuid.UUID(raw_value)
        except ValueError:
            raise CommandError(f"Invalid {label} value: {raw_value}")
