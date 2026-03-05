from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from collect.schema import get_collect_schema_status


def _normalize_values(raw):
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        source = raw
    else:
        source = str(raw).split(",")
    values = []
    for item in source:
        value = str(item or "").strip()
        if value:
            values.append(value)
    return values


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


class Command(BaseCommand):
    help = "Validate Sheetbook beta rollout configuration and schema readiness."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="경고 항목이 있으면 실패 코드로 종료합니다.",
        )

    def handle(self, *args, **options):
        strict = bool(options.get("strict"))
        warnings = []
        issues = []

        enabled = bool(getattr(settings, "SHEETBOOK_ENABLED", False))
        beta_usernames = _normalize_values(getattr(settings, "SHEETBOOK_BETA_USERNAMES", ()))
        beta_emails = _normalize_values(getattr(settings, "SHEETBOOK_BETA_EMAILS", ()))
        beta_user_ids = _normalize_values(getattr(settings, "SHEETBOOK_BETA_USER_IDS", ()))

        to_create_target = _safe_float(getattr(settings, "SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE", 60.0), 60.0)
        create_to_action_target = _safe_float(
            getattr(settings, "SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE", 50.0),
            50.0,
        )
        to_create_min_sample = _safe_int(getattr(settings, "SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE", 5), 5)
        create_to_action_min_sample = _safe_int(
            getattr(settings, "SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE", 5),
            5,
        )
        consent_cleanup_target = _safe_float(
            getattr(settings, "SHEETBOOK_CONSENT_CLEANUP_TARGET_RATE", 30.0),
            30.0,
        )
        consent_cleanup_min_sample = _safe_int(
            getattr(settings, "SHEETBOOK_CONSENT_CLEANUP_MIN_SAMPLE", 5),
            5,
        )
        consent_cleanup_undo_alert = _safe_float(
            getattr(settings, "SHEETBOOK_CONSENT_CLEANUP_UNDO_ALERT_RATE", 20.0),
            20.0,
        )
        consent_cleanup_undo_min_sample = _safe_int(
            getattr(settings, "SHEETBOOK_CONSENT_CLEANUP_UNDO_MIN_SAMPLE", 5),
            5,
        )
        default_duration = _safe_int(getattr(settings, "SHEETBOOK_SCHEDULE_DEFAULT_DURATION_MINUTES", 50), 50)
        first_class_hour = _safe_int(getattr(settings, "SHEETBOOK_PERIOD_FIRST_CLASS_HOUR", 9), 9)
        first_class_minute = _safe_int(getattr(settings, "SHEETBOOK_PERIOD_FIRST_CLASS_MINUTE", 0), 0)
        grid_batch_size = _safe_int(getattr(settings, "SHEETBOOK_GRID_BULK_BATCH_SIZE", 400), 400)

        allowlist_total = len(set(beta_usernames + beta_emails + beta_user_ids))
        if not enabled and allowlist_total == 0:
            warnings.append("SHEETBOOK_ENABLED=False 상태에서 베타 allowlist가 비어 있어 접근 가능한 계정이 없습니다.")

        if not (0 <= to_create_target <= 100):
            issues.append("SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE 값은 0~100 사이여야 합니다.")
        if not (0 <= create_to_action_target <= 100):
            issues.append("SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE 값은 0~100 사이여야 합니다.")
        if to_create_min_sample < 1:
            issues.append("SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE 값은 1 이상이어야 합니다.")
        if create_to_action_min_sample < 1:
            issues.append("SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE 값은 1 이상이어야 합니다.")
        if not (0 <= consent_cleanup_target <= 100):
            issues.append("SHEETBOOK_CONSENT_CLEANUP_TARGET_RATE 값은 0~100 사이여야 합니다.")
        if consent_cleanup_min_sample < 1:
            issues.append("SHEETBOOK_CONSENT_CLEANUP_MIN_SAMPLE 값은 1 이상이어야 합니다.")
        if not (0 <= consent_cleanup_undo_alert <= 100):
            issues.append("SHEETBOOK_CONSENT_CLEANUP_UNDO_ALERT_RATE 값은 0~100 사이여야 합니다.")
        if consent_cleanup_undo_min_sample < 1:
            issues.append("SHEETBOOK_CONSENT_CLEANUP_UNDO_MIN_SAMPLE 값은 1 이상이어야 합니다.")
        if not (10 <= default_duration <= 240):
            issues.append("SHEETBOOK_SCHEDULE_DEFAULT_DURATION_MINUTES 값은 10~240 사이를 권장합니다.")
        if not (6 <= first_class_hour <= 18):
            issues.append("SHEETBOOK_PERIOD_FIRST_CLASS_HOUR 값은 6~18 사이여야 합니다.")
        if not (0 <= first_class_minute <= 59):
            issues.append("SHEETBOOK_PERIOD_FIRST_CLASS_MINUTE 값은 0~59 사이여야 합니다.")
        if not (50 <= grid_batch_size <= 2000):
            issues.append("SHEETBOOK_GRID_BULK_BATCH_SIZE 값은 50~2000 사이여야 합니다.")

        is_collect_ready, missing_tables, missing_columns, detail = get_collect_schema_status(force_refresh=True)
        if not is_collect_ready:
            issues.append("collect 스키마가 준비되지 않았습니다.")
            if detail:
                issues.append(f"상세: {detail}")
            if missing_tables:
                issues.append(f"누락 테이블: {', '.join(missing_tables)}")
            if missing_columns:
                pairs = []
                for table_name, columns in missing_columns.items():
                    pairs.append(f"{table_name}({', '.join(columns)})")
                issues.append(f"누락 컬럼: {', '.join(pairs)}")

        self.stdout.write(self.style.SUCCESS("[sheetbook] rollout 점검 시작"))
        self.stdout.write(f"- SHEETBOOK_ENABLED: {enabled}")
        self.stdout.write(
            f"- beta allowlist: usernames={len(beta_usernames)}, emails={len(beta_emails)}, ids={len(beta_user_ids)}"
        )
        self.stdout.write(
            "- KPI target: "
            f"home->create={to_create_target}%, create->action={create_to_action_target}%"
        )
        self.stdout.write(
            "- KPI min sample: "
            f"home={to_create_min_sample}, create={create_to_action_min_sample}"
        )
        self.stdout.write(
            "- consent cleanup target: "
            f"apply>={consent_cleanup_target}%, sample>={consent_cleanup_min_sample}"
        )
        self.stdout.write(
            "- consent cleanup undo alert: "
            f"use<={consent_cleanup_undo_alert}%, sample>={consent_cleanup_undo_min_sample}"
        )
        self.stdout.write(f"- default class duration: {default_duration}분")
        self.stdout.write(f"- first class start: {first_class_hour:02d}:{first_class_minute:02d}")
        self.stdout.write(f"- grid bulk batch size: {grid_batch_size}")
        self.stdout.write(f"- collect schema ready: {is_collect_ready}")

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"[경고] {warning}"))
        for issue in issues:
            self.stdout.write(self.style.ERROR(f"[오류] {issue}"))

        if issues:
            raise CommandError("Sheetbook rollout 점검 실패")
        if strict and warnings:
            raise CommandError("Sheetbook rollout 점검 경고(strict 모드)")

        self.stdout.write(self.style.SUCCESS("[sheetbook] rollout 점검 통과"))
