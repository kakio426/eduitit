from django.core.management.base import BaseCommand

from consent.models import SignatureRequest


class Command(BaseCommand):
    help = "동의서 요청의 첨부 문서 접근 가능 여부를 점검합니다."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="검사할 최대 요청 수 (0이면 전체)")
        parser.add_argument("--only-missing", action="store_true", help="문제 항목만 출력")

    def handle(self, *args, **options):
        limit = options["limit"]
        only_missing = options["only_missing"]

        qs = SignatureRequest.objects.select_related("document", "created_by").order_by("-created_at")
        if limit > 0:
            qs = qs[:limit]

        total = 0
        missing = 0
        unknown = 0

        for req in qs:
            total += 1
            doc = req.document
            ff = doc.original_file
            file_name = ff.name or ""
            storage_name = ff.storage.__class__.__name__

            exists = None
            error = ""
            if file_name:
                try:
                    exists = ff.storage.exists(file_name)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
            else:
                exists = False
                error = "파일 경로가 비어 있음"

            if exists is True:
                if not only_missing:
                    self.stdout.write(
                        f"[OK] {req.request_id} | {req.title} | {storage_name} | {file_name}"
                    )
                continue

            if exists is False:
                missing += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"[MISSING] {req.request_id} | {req.title} | {storage_name} | {file_name}"
                    )
                )
                continue

            unknown += 1
            self.stdout.write(
                self.style.WARNING(
                    f"[UNKNOWN] {req.request_id} | {req.title} | {storage_name} | {file_name} | {error}"
                )
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"[SUMMARY] total={total}, missing={missing}, unknown={unknown}, ok={max(total - missing - unknown, 0)}"
            )
        )
