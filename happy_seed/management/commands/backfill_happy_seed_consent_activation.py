from django.core.management.base import BaseCommand
from django.db import transaction

from happy_seed.models import HSGuardianConsent, HSStudent


class Command(BaseCommand):
    help = (
        "HSGuardianConsent 상태와 HSStudent.is_active 불일치를 정리합니다. "
        "withdrawn만 비활성(False), 그 외 상태는 활성(True)으로 맞춥니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB를 수정하지 않고 변경 대상 수만 출력합니다.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        consent_rows = HSGuardianConsent.objects.select_related("student")
        activate_ids = []
        deactivate_ids = []

        for consent in consent_rows:
            should_be_active = consent.status != "withdrawn"
            student = consent.student
            if student.is_active == should_be_active:
                continue
            if should_be_active:
                activate_ids.append(student.id)
            else:
                deactivate_ids.append(student.id)

        self.stdout.write(
            self.style.NOTICE(
                f"[backfill] activate={len(activate_ids)} deactivate={len(deactivate_ids)} dry_run={dry_run}"
            )
        )

        if dry_run:
            return

        with transaction.atomic():
            if activate_ids:
                HSStudent.objects.filter(id__in=activate_ids).update(is_active=True)
            if deactivate_ids:
                HSStudent.objects.filter(id__in=deactivate_ids).update(is_active=False)

        self.stdout.write(self.style.SUCCESS("[backfill] 완료"))
