from django.core.management.base import BaseCommand

from edu_materials.classification import apply_auto_metadata
from edu_materials.models import EduMaterial


class Command(BaseCommand):
    help = "기존 교육 자료에 자동 분류 메타데이터를 채웁니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="이미 분류 완료된 자료도 다시 계산합니다.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리할 최대 자료 수 (0이면 전체).",
        )

    def handle(self, *args, **options):
        force = bool(options.get("force"))
        limit = max(0, int(options.get("limit") or 0))

        queryset = EduMaterial.objects.all().order_by("id")
        if not force:
            queryset = queryset.exclude(metadata_status=EduMaterial.MetadataStatus.DONE)

        if limit > 0:
            queryset = queryset[:limit]

        total = queryset.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("처리할 교육 자료가 없습니다."))
            return

        processed = 0
        for material in queryset.iterator(chunk_size=200):
            apply_auto_metadata(material, save=True)
            processed += 1

        self.stdout.write(self.style.SUCCESS(f"자동 분류 완료: {processed}개 자료"))
