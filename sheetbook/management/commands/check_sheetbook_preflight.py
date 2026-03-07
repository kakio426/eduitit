from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run sheetbook preflight checks (collect schema, rollout, consent freeze, threshold recommendation)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="rollout 점검을 strict 모드로 실행합니다.",
        )
        parser.add_argument(
            "--recommend-days",
            type=int,
            default=14,
            help="임계치 추천 커맨드 집계 기간(일). 기본 14",
        )
        parser.add_argument(
            "--skip-recommend",
            action="store_true",
            help="임계치 추천 커맨드 실행을 건너뜁니다.",
        )
        parser.add_argument(
            "--skip-consent-freeze",
            action="store_true",
            help="consent freeze 점검을 건너뜁니다.",
        )

    def handle(self, *args, **options):
        strict = bool(options.get("strict"))
        skip_recommend = bool(options.get("skip_recommend"))
        skip_consent_freeze = bool(options.get("skip_consent_freeze"))
        raw_recommend_days = options.get("recommend_days")
        recommend_days = 14 if raw_recommend_days is None else int(raw_recommend_days)
        if recommend_days < 1:
            raise CommandError("--recommend-days 값은 1 이상이어야 합니다.")

        self.stdout.write(self.style.SUCCESS("[sheetbook] preflight start"))
        self.stdout.write("- check_collect_schema")
        call_command("check_collect_schema")

        if strict:
            self.stdout.write("- check_sheetbook_rollout --strict")
            call_command("check_sheetbook_rollout", "--strict")
        else:
            self.stdout.write("- check_sheetbook_rollout")
            call_command("check_sheetbook_rollout")

        if not skip_consent_freeze:
            self.stdout.write("- check_sheetbook_consent_freeze")
            call_command("check_sheetbook_consent_freeze")

        if not skip_recommend:
            self.stdout.write(f"- recommend_sheetbook_thresholds --days {recommend_days}")
            call_command("recommend_sheetbook_thresholds", "--days", str(recommend_days))

        self.stdout.write(self.style.SUCCESS("[sheetbook] preflight done"))
