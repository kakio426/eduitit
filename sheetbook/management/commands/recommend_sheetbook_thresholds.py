from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from sheetbook.models import SheetbookMetricEvent


def _safe_positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return parsed if parsed > 0 else int(default)


def _safe_percentage(value, default):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    if parsed < 0:
        return 0.0
    if parsed > 100:
        return 100.0
    return round(parsed, 1)


def _read_workspace_funnel_counts(since):
    event_qs = SheetbookMetricEvent.objects.filter(created_at__gte=since)
    workspace_home_opened_count = event_qs.filter(event_name="workspace_home_opened").count()

    workspace_source_create_count = 0
    workspace_source_action_requested_count = 0
    source_rows = event_qs.filter(
        event_name__in=["sheetbook_created", "action_execute_requested"],
    ).values("event_name", "metadata")

    for row in source_rows:
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            continue
        source = str(metadata.get("entry_source") or "").strip().lower()
        if not source.startswith("workspace_home"):
            continue
        if row["event_name"] == "sheetbook_created":
            workspace_source_create_count += 1
        elif row["event_name"] == "action_execute_requested":
            workspace_source_action_requested_count += 1

    return {
        "workspace_home_opened_count": workspace_home_opened_count,
        "workspace_source_create_count": workspace_source_create_count,
        "workspace_source_action_requested_count": workspace_source_action_requested_count,
    }


def _recommend_target_rate(observed_rate, base_count):
    if base_count < 10:
        margin = 15.0
    elif base_count < 30:
        margin = 10.0
    elif base_count < 100:
        margin = 7.5
    else:
        margin = 5.0
    recommended = round(max(10.0, min(95.0, observed_rate - margin)), 1)
    return recommended, margin


def _recommend_min_sample(base_count, ratio):
    suggested = int(round(base_count * ratio))
    return max(5, min(50, suggested))


def _normalize_role(value):
    normalized = str(value or "").strip().lower()
    return normalized or "unknown"


def _build_funnel_snapshot(
    *,
    counts,
    current_to_create_target,
    current_create_to_action_target,
    min_home_sample,
    min_create_sample,
    current_to_create_min_sample,
    current_create_to_action_min_sample,
):
    home_count = counts["workspace_home_opened_count"]
    create_count = counts["workspace_source_create_count"]
    action_requested_count = counts["workspace_source_action_requested_count"]

    workspace_to_create_rate = round((create_count / home_count) * 100, 1) if home_count else 0.0
    create_to_action_rate = (
        round((action_requested_count / create_count) * 100, 1) if create_count else 0.0
    )

    to_create_recommended_target = current_to_create_target
    to_create_reason = "현재 설정 유지"
    if home_count >= min_home_sample:
        to_create_recommended_target, to_create_margin = _recommend_target_rate(
            workspace_to_create_rate,
            home_count,
        )
        to_create_reason = f"관측치 {workspace_to_create_rate}% - 안정 마진 {to_create_margin}%"
    else:
        to_create_reason = f"샘플 부족({home_count} < {min_home_sample})"

    create_to_action_recommended_target = current_create_to_action_target
    create_to_action_reason = "현재 설정 유지"
    if create_count >= min_create_sample:
        create_to_action_recommended_target, create_to_action_margin = _recommend_target_rate(
            create_to_action_rate,
            create_count,
        )
        create_to_action_reason = (
            f"관측치 {create_to_action_rate}% - 안정 마진 {create_to_action_margin}%"
        )
    else:
        create_to_action_reason = f"샘플 부족({create_count} < {min_create_sample})"

    recommended_to_create_min_sample = (
        _recommend_min_sample(home_count, ratio=0.2)
        if home_count >= min_home_sample
        else current_to_create_min_sample
    )
    recommended_create_to_action_min_sample = (
        _recommend_min_sample(create_count, ratio=0.3)
        if create_count >= min_create_sample
        else current_create_to_action_min_sample
    )

    return {
        "counts": counts,
        "rates": {
            "home_to_create": workspace_to_create_rate,
            "create_to_action": create_to_action_rate,
        },
        "recommended": {
            "to_create_target": to_create_recommended_target,
            "create_to_action_target": create_to_action_recommended_target,
            "to_create_min_sample": recommended_to_create_min_sample,
            "create_to_action_min_sample": recommended_create_to_action_min_sample,
            "to_create_reason": to_create_reason,
            "create_to_action_reason": create_to_action_reason,
        },
    }


def _read_workspace_funnel_counts_by_role(since):
    event_qs = SheetbookMetricEvent.objects.filter(created_at__gte=since)
    grouped_counts = {}

    def _ensure_role_counts(role_name):
        return grouped_counts.setdefault(
            role_name,
            {
                "workspace_home_opened_count": 0,
                "workspace_source_create_count": 0,
                "workspace_source_action_requested_count": 0,
            },
        )

    home_roles = event_qs.filter(event_name="workspace_home_opened").values_list(
        "user__userprofile__role",
        flat=True,
    )
    for raw_role in home_roles:
        _ensure_role_counts(_normalize_role(raw_role))["workspace_home_opened_count"] += 1

    source_rows = event_qs.filter(
        event_name__in=["sheetbook_created", "action_execute_requested"],
    ).values("user__userprofile__role", "event_name", "metadata")

    for row in source_rows:
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            continue
        source = str(metadata.get("entry_source") or "").strip().lower()
        if not source.startswith("workspace_home"):
            continue
        role_counts = _ensure_role_counts(_normalize_role(row.get("user__userprofile__role")))
        if row["event_name"] == "sheetbook_created":
            role_counts["workspace_source_create_count"] += 1
        elif row["event_name"] == "action_execute_requested":
            role_counts["workspace_source_action_requested_count"] += 1

    return {role_name: grouped_counts[role_name] for role_name in sorted(grouped_counts)}


class Command(BaseCommand):
    help = "Recommend sheetbook funnel thresholds from recent pilot metric events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=14,
            help="최근 집계 기간(일). 기본 14",
        )
        parser.add_argument(
            "--min-home-sample",
            type=int,
            default=None,
            help="home->create 추천을 계산할 최소 샘플 수(기본: 설정값 사용).",
        )
        parser.add_argument(
            "--min-create-sample",
            type=int,
            default=None,
            help="create->action 추천을 계산할 최소 샘플 수(기본: 설정값 사용).",
        )
        parser.add_argument(
            "--group-by-role",
            action="store_true",
            help="role별 참고 집계를 함께 출력합니다.",
        )

    def handle(self, *args, **options):
        days = _safe_positive_int(options.get("days"), 14)
        if days < 1:
            raise CommandError("--days 값은 1 이상이어야 합니다.")

        current_to_create_target = _safe_percentage(
            getattr(settings, "SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE", 60.0),
            60.0,
        )
        current_create_to_action_target = _safe_percentage(
            getattr(settings, "SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE", 50.0),
            50.0,
        )
        current_to_create_min_sample = _safe_positive_int(
            getattr(settings, "SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE", 5),
            5,
        )
        current_create_to_action_min_sample = _safe_positive_int(
            getattr(settings, "SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE", 5),
            5,
        )

        min_home_sample = _safe_positive_int(
            options.get("min_home_sample"),
            current_to_create_min_sample,
        )
        min_create_sample = _safe_positive_int(
            options.get("min_create_sample"),
            current_create_to_action_min_sample,
        )

        since = timezone.now() - timedelta(days=days)
        snapshot = _build_funnel_snapshot(
            counts=_read_workspace_funnel_counts(since),
            current_to_create_target=current_to_create_target,
            current_create_to_action_target=current_create_to_action_target,
            min_home_sample=min_home_sample,
            min_create_sample=min_create_sample,
            current_to_create_min_sample=current_to_create_min_sample,
            current_create_to_action_min_sample=current_create_to_action_min_sample,
        )
        home_count = snapshot["counts"]["workspace_home_opened_count"]
        create_count = snapshot["counts"]["workspace_source_create_count"]
        action_requested_count = snapshot["counts"]["workspace_source_action_requested_count"]
        workspace_to_create_rate = snapshot["rates"]["home_to_create"]
        create_to_action_rate = snapshot["rates"]["create_to_action"]
        to_create_recommended_target = snapshot["recommended"]["to_create_target"]
        create_to_action_recommended_target = snapshot["recommended"]["create_to_action_target"]
        recommended_to_create_min_sample = snapshot["recommended"]["to_create_min_sample"]
        recommended_create_to_action_min_sample = snapshot["recommended"]["create_to_action_min_sample"]
        to_create_reason = snapshot["recommended"]["to_create_reason"]
        create_to_action_reason = snapshot["recommended"]["create_to_action_reason"]

        self.stdout.write(self.style.SUCCESS("[sheetbook] 임계치 재보정 추천"))
        self.stdout.write(f"- 기간: 최근 {days}일")
        self.stdout.write(
            f"- 관측: 홈 진입={home_count}, 홈 유입 수첩 생성={create_count}, 홈 유입 기능 실행 시작={action_requested_count}"
        )
        self.stdout.write(
            f"- 관측 전환율: 홈->수첩 생성={workspace_to_create_rate}%, 수첩 생성->기능 실행={create_to_action_rate}%"
        )
        self.stdout.write("")
        self.stdout.write(
            f"- 홈->수첩 생성 목표 추천: {to_create_recommended_target}% ({to_create_reason})"
        )
        self.stdout.write(
            f"- 수첩 생성->기능 실행 목표 추천: {create_to_action_recommended_target}% ({create_to_action_reason})"
        )
        self.stdout.write(
            f"- 샘플 수 추천: home={recommended_to_create_min_sample}, create={recommended_create_to_action_min_sample}"
        )
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[sheetbook] env 권장값"))
        self.stdout.write(
            f"SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE={to_create_recommended_target}"
        )
        self.stdout.write(
            f"SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE={create_to_action_recommended_target}"
        )
        self.stdout.write(
            f"SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE={recommended_to_create_min_sample}"
        )
        self.stdout.write(
            f"SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE={recommended_create_to_action_min_sample}"
        )

        if options.get("group_by_role"):
            role_breakdown = _read_workspace_funnel_counts_by_role(since)
            self.stdout.write("")
            self.stdout.write("[sheetbook] role별 재보정 참고")
            if not role_breakdown:
                self.stdout.write("- role breakdown 없음")
            for role_name in sorted(role_breakdown):
                role_snapshot = _build_funnel_snapshot(
                    counts=role_breakdown[role_name],
                    current_to_create_target=current_to_create_target,
                    current_create_to_action_target=current_create_to_action_target,
                    min_home_sample=min_home_sample,
                    min_create_sample=min_create_sample,
                    current_to_create_min_sample=current_to_create_min_sample,
                    current_create_to_action_min_sample=current_create_to_action_min_sample,
                )
                role_counts = role_snapshot["counts"]
                role_rates = role_snapshot["rates"]
                self.stdout.write(
                    f"- role={role_name}: home={role_counts['workspace_home_opened_count']}, "
                    f"create={role_counts['workspace_source_create_count']}, "
                    f"action={role_counts['workspace_source_action_requested_count']}, "
                    f"rate={role_rates['home_to_create']}%/{role_rates['create_to_action']}%"
                )
