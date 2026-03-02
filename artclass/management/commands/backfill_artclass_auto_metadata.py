from django.core.management.base import BaseCommand

from artclass.classification import apply_auto_metadata
from artclass.models import ArtClass


class Command(BaseCommand):
    help = "기존 미술 수업에 자동 카테고리/태그/검색 텍스트를 채웁니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="이미 자동 분류된 수업도 다시 계산합니다.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리할 최대 수업 수 (0이면 전체).",
        )

    def handle(self, *args, **options):
        force = bool(options.get("force"))
        limit = max(0, int(options.get("limit") or 0))

        queryset = ArtClass.objects.all().order_by("id")
        if not force:
            queryset = queryset.filter(is_auto_classified=False)

        if limit > 0:
            queryset = queryset[:limit]

        total = queryset.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("처리할 미술 수업이 없습니다."))
            return

        processed = 0
        for art_class in queryset.iterator(chunk_size=200):
            apply_auto_metadata(art_class, save=True)
            processed += 1

        self.stdout.write(self.style.SUCCESS(f"자동 분류 완료: {processed}개 수업"))
