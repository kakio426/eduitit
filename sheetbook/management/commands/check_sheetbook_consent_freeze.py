from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from scripts.run_sheetbook_consent_freeze_snapshot import _build_report


class Command(BaseCommand):
    help = "Check that sheetbook consent_review template still preserves frozen recipient UX tokens."

    def add_arguments(self, parser):
        parser.add_argument(
            "--template-path",
            default="",
            help="점검할 consent_review template 경로",
        )
        parser.add_argument(
            "--strict-extras",
            action="store_true",
            help="허용되지 않은 extra token도 실패로 처리합니다.",
        )

    def handle(self, *args, **options):
        raw_template_path = str(options.get("template_path") or "").strip()
        if raw_template_path:
            template_path = Path(raw_template_path).expanduser()
        else:
            template_path = (
                Path(__file__).resolve().parents[2]
                / "templates"
                / "sheetbook"
                / "consent_review.html"
            )
        content = template_path.read_text(encoding="utf-8")
        report = _build_report(
            content=content,
            template_path=str(template_path),
            strict_extras=bool(options.get("strict_extras")),
        )

        if report.get("status") != "PASS":
            message_parts = ["consent freeze 점검 실패"]
            missing = report.get("missing") or {}
            for item in missing.get("ids") or []:
                message_parts.append(f'누락: id="{item}"')
            for item in missing.get("testids") or []:
                message_parts.append(f'누락: data-testid="{item}"')
            for item in missing.get("jump_values") or []:
                message_parts.append(f'누락: data-recipients-jump="{item}"')
            for item in missing.get("hidden_names") or []:
                message_parts.append(f'누락: hidden name="{item}"')
            extra = report.get("extra") or {}
            if bool(options.get("strict_extras")):
                for item in extra.get("ids") or []:
                    message_parts.append(f'추가됨: id="{item}"')
                for item in extra.get("testids") or []:
                    message_parts.append(f'추가됨: data-testid="{item}"')
            for item in report.get("order_checks") or []:
                if not item.get("ok"):
                    message_parts.append(f"순서 오류: {item.get('name')} ({item.get('error') or 'unknown'})")
            raise CommandError(" | ".join(message_parts))

        self.stdout.write(self.style.SUCCESS(f"consent freeze 점검 통과: {template_path}"))

