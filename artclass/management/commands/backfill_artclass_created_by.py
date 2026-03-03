from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from artclass.models import ArtClass


class Command(BaseCommand):
    help = "created_by가 비어 있는 미술 수업을 지정 사용자로 귀속합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help="귀속할 사용자 username",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리할 최대 수업 수 (0이면 전체).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB를 변경하지 않고 대상 수업만 출력합니다.",
        )

    def handle(self, *args, **options):
        username = (options.get("username") or "").strip()
        limit = max(0, int(options.get("limit") or 0))
        dry_run = bool(options.get("dry_run"))

        user_model = get_user_model()
        try:
            owner = user_model.objects.get(username=username)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"username={username!r} 사용자를 찾을 수 없습니다.") from exc

        queryset = ArtClass.objects.filter(created_by__isnull=True).order_by("id")
        if limit > 0:
            queryset = queryset[:limit]

        total = queryset.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("created_by가 비어 있는 미술 수업이 없습니다."))
            return

        samples = list(queryset.values_list("id", "title", "is_shared")[:20])
        self.stdout.write(f"대상 수업 수: {total}")
        self.stdout.write(f"귀속 대상 사용자: id={owner.id}, username={owner.username}")
        self.stdout.write(f"샘플(최대 20개): {samples}")

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run 모드: DB를 변경하지 않았습니다."))
            return

        updated = queryset.update(created_by=owner)
        self.stdout.write(self.style.SUCCESS(f"created_by 백필 완료: {updated}개"))
