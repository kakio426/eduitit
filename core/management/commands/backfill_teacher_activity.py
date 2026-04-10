from django.core.management.base import BaseCommand

from core.teacher_activity import backfill_teacher_activity


class Command(BaseCommand):
    help = "기존 로그를 기반으로 교사 활동 지수를 백필합니다."

    def handle(self, *args, **options):
        stats = backfill_teacher_activity()
        self.stdout.write(self.style.SUCCESS("교사 활동 지수 백필을 마쳤습니다."))
        for key, value in stats.items():
            self.stdout.write(f"- {key}: {value}")
