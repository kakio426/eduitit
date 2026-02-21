import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from seed_quiz.models import SQQuizBank, SQQuizBankItem
from seed_quiz.services.validator import validate_quiz_payload

PRESET_LABELS = {
    "general": "상식",
    "math": "수학",
    "korean": "국어",
    "science": "과학",
    "social": "사회",
    "english": "영어",
}


class Command(BaseCommand):
    help = "Seed SQQuizBank with fallback quizzes (idempotent)."

    def handle(self, *args, **options):
        data_file = Path(__file__).resolve().parents[2] / "data" / "fallback_quizzes_v1.json"
        if not data_file.exists():
            self.stdout.write(self.style.ERROR(f"fallback file not found: {data_file}"))
            return

        with data_file.open(encoding="utf-8") as f:
            raw = json.load(f)

        quizzes = raw.get("quizzes", {})
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for preset_type, by_grade in quizzes.items():
            if preset_type not in PRESET_LABELS:
                continue
            for grade_str, quiz_sets in by_grade.items():
                try:
                    grade = int(grade_str)
                except (TypeError, ValueError):
                    continue
                if grade not in range(1, 7):
                    continue

                for idx, payload in enumerate(quiz_sets, start=1):
                    ok, errors = validate_quiz_payload(payload)
                    if not ok:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"[skip] invalid payload preset={preset_type} grade={grade} idx={idx} errors={errors}"
                            )
                        )
                        continue

                    title = f"[공식] {grade}학년 {PRESET_LABELS[preset_type]} #{idx}"
                    with transaction.atomic():
                        bank, created = SQQuizBank.objects.get_or_create(
                            title=title,
                            preset_type=preset_type,
                            grade=grade,
                            source="manual",
                            defaults={
                                "is_official": True,
                                "is_public": False,
                                "is_active": True,
                            },
                        )
                        if created:
                            created_count += 1
                        else:
                            changed_fields = []
                            if not bank.is_official:
                                bank.is_official = True
                                changed_fields.append("is_official")
                            if bank.is_public:
                                bank.is_public = False
                                changed_fields.append("is_public")
                            if not bank.is_active:
                                bank.is_active = True
                                changed_fields.append("is_active")
                            if changed_fields:
                                bank.save(update_fields=changed_fields)
                                updated_count += 1

                        bank.items.all().delete()
                        for order_no, item in enumerate(payload["items"], start=1):
                            SQQuizBankItem.objects.create(
                                bank=bank,
                                order_no=order_no,
                                question_text=item["question_text"],
                                choices=item["choices"],
                                correct_index=item["correct_index"],
                                explanation=item.get("explanation", ""),
                                difficulty=item.get("difficulty", "medium"),
                            )

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_quiz_bank complete: created={created_count}, updated={updated_count}, skipped={skipped_count}"
            )
        )
