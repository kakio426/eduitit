from django.core.management.base import BaseCommand

from core.models import NewsSource
from core.news_ingest import DEFAULT_NEWS_SOURCES


class Command(BaseCommand):
    help = "기본 뉴스 RSS 소스를 NewsSource 테이블에 등록합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--activate-all",
            action="store_true",
            help="이미 존재하는 소스도 활성화 상태로 맞춥니다.",
        )

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for payload in DEFAULT_NEWS_SOURCES:
            source, created = NewsSource.objects.get_or_create(
                url=payload["url"],
                defaults={
                    "name": payload["name"],
                    "source_type": payload["source_type"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
                continue

            changed = False
            if source.name != payload["name"]:
                source.name = payload["name"]
                changed = True
            if source.source_type != payload["source_type"]:
                source.source_type = payload["source_type"]
                changed = True
            if options["activate_all"] and not source.is_active:
                source.is_active = True
                changed = True
            if changed:
                source.save()
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 생성 {created_count}개 / 갱신 {updated_count}개"
            )
        )
