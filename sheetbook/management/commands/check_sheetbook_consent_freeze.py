from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate consent_review freeze baseline (ids/data-testid/order/hidden fields)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--template-path",
            default="",
            help="검증할 consent_review 템플릿 경로. 미지정 시 기본 경로 사용.",
        )

    def handle(self, *args, **options):
        template_path = self._resolve_template_path(options.get("template_path"))
        try:
            content = template_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise CommandError(
                f"[sheetbook] consent freeze 점검 실패: 템플릿 파일을 찾을 수 없습니다. ({template_path})"
            ) from exc
        except OSError as exc:
            raise CommandError(
                f"[sheetbook] consent freeze 점검 실패: 템플릿 파일을 읽을 수 없습니다. ({template_path})"
            ) from exc

        errors = []

        required_id_tokens = [
            'id="recipients-textarea"',
            'id="recipients-cleanup-btn"',
            'id="recipients-cleanup-undo-btn"',
            'id="recipients-copy-issues-btn"',
            'id="recipients-prev-issue-btn"',
            'id="recipients-next-issue-btn"',
            'id="recipients-submit-btn"',
        ]
        required_testid_tokens = [
            'data-testid="recipients-textarea"',
            'data-testid="recipients-cleanup-btn"',
            'data-testid="recipients-cleanup-undo-btn"',
            'data-testid="recipients-copy-issues-btn"',
            'data-testid="recipients-prev-issue-btn"',
            'data-testid="recipients-next-issue-btn"',
            'data-testid="recipients-jump-top-btn"',
            'data-testid="recipients-jump-bottom-btn"',
            'data-testid="recipients-submit-btn"',
        ]
        required_jump_tokens = [
            'data-recipients-jump="top"',
            'data-recipients-jump="bottom"',
        ]
        required_hidden_field_names = [
            'name="recipients_cleanup_applied"',
            'name="recipients_cleanup_removed_count"',
            'name="recipients_cleanup_undo_used"',
            'name="recipients_issue_copy_used"',
            'name="recipients_issue_jump_count"',
        ]

        for token in (
            required_id_tokens
            + required_testid_tokens
            + required_jump_tokens
            + required_hidden_field_names
        ):
            if token not in content:
                errors.append(f"누락: {token}")

        self._validate_order(
            content,
            errors,
            order_name="cleanup button order",
            tokens=[
                'id="recipients-cleanup-btn"',
                'id="recipients-cleanup-undo-btn"',
                'id="recipients-copy-issues-btn"',
            ],
        )
        self._validate_order(
            content,
            errors,
            order_name="issue navigation order",
            tokens=[
                'id="recipients-prev-issue-btn"',
                'id="recipients-next-issue-btn"',
                'data-testid="recipients-jump-top-btn"',
                'data-testid="recipients-jump-bottom-btn"',
            ],
        )

        if errors:
            message = "[sheetbook] consent freeze 점검 실패\n- " + "\n- ".join(errors)
            raise CommandError(message)

        self.stdout.write(self.style.SUCCESS("[sheetbook] consent freeze 점검 통과"))
        self.stdout.write(f"- template: {template_path}")
        self.stdout.write(
            "- checked: ids/data-testid/jump attributes/hidden fields/button order"
        )

    @staticmethod
    def _resolve_template_path(raw_path):
        if raw_path:
            path = Path(str(raw_path))
            return path if path.is_absolute() else (Path.cwd() / path)
        return (
            Path(__file__).resolve().parents[3]
            / "sheetbook"
            / "templates"
            / "sheetbook"
            / "consent_review.html"
        )

    @staticmethod
    def _validate_order(content, errors, *, order_name, tokens):
        indices = [content.find(token) for token in tokens]
        if any(idx < 0 for idx in indices):
            return
        for left, right in zip(indices, indices[1:]):
            if left >= right:
                errors.append(
                    f"순서 오류({order_name}): {' -> '.join(tokens)}"
                )
                return
