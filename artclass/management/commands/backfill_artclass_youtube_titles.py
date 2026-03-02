import time

from django.core.management.base import BaseCommand
from django.db.utils import OperationalError, ProgrammingError

from artclass.models import ArtClass
from artclass.views import _fetch_youtube_title


class Command(BaseCommand):
    help = "기존 미술 수업 제목을 유튜브 실제 제목으로 일괄 갱신합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리할 최대 수업 수 (0이면 전체).",
        )
        parser.add_argument(
            "--sleep-ms",
            type=int,
            default=120,
            help="요청 간 대기 시간(ms). 기본값 120.",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="현재 제목이 비어 있는 수업만 처리합니다.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB 저장 없이 변경 예정 건수만 출력합니다.",
        )

    def handle(self, *args, **options):
        limit = max(0, int(options.get("limit") or 0))
        sleep_ms = max(0, int(options.get("sleep_ms") or 0))
        only_empty = bool(options.get("only_empty"))
        dry_run = bool(options.get("dry_run"))

        queryset = ArtClass.objects.all().order_by("id")
        if only_empty:
            queryset = queryset.filter(title="")
        if limit > 0:
            queryset = queryset[:limit]

        try:
            total = queryset.count()
        except (OperationalError, ProgrammingError):
            self.stderr.write(
                self.style.ERROR(
                    "artclass 테이블이 아직 없습니다. 먼저 마이그레이션을 적용한 뒤 다시 실행해 주세요."
                )
            )
            return
        if total == 0:
            self.stdout.write(self.style.WARNING("처리할 미술 수업이 없습니다."))
            return

        updated = 0
        skipped_same = 0
        skipped_fetch_fail = 0

        for idx, art_class in enumerate(queryset.iterator(chunk_size=100), start=1):
            youtube_title = _fetch_youtube_title(art_class.youtube_url)
            if not youtube_title:
                skipped_fetch_fail += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[{idx}/{total}] #{art_class.pk} 제목 조회 실패 (URL: {art_class.youtube_url})"
                    )
                )
                continue

            current_title = (art_class.title or "").strip()
            if current_title == youtube_title:
                skipped_same += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN {idx}/{total}] #{art_class.pk} '{current_title}' -> '{youtube_title}'"
                )
                updated += 1
            else:
                art_class.title = youtube_title
                art_class.save(update_fields=["title"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{idx}/{total}] #{art_class.pk} 제목 업데이트: '{current_title}' -> '{youtube_title}'"
                    )
                )
                updated += 1

            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

        mode = "DRY-RUN" if dry_run else "완료"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: 대상 {total}개 / 변경 {updated}개 / 동일 {skipped_same}개 / 조회실패 {skipped_fetch_fail}개"
            )
        )
