import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _setup_django() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _safe_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return parsed if parsed > 0 else int(default)


def _safe_percentage(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    if parsed < 0:
        return 0.0
    if parsed > 100:
        return 100.0
    return round(parsed, 1)


def _recommend_target_rate(observed_rate: float, base_count: int) -> tuple[float, float]:
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


def _recommend_min_sample(base_count: int, ratio: float) -> int:
    suggested = int(round(base_count * ratio))
    return max(5, min(50, suggested))


def _normalize_role(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or "unknown"


def _build_funnel_snapshot(
    *,
    counts: dict[str, int],
    current_to_create_target: float,
    current_create_to_action_target: float,
    min_home_sample: int,
    min_create_sample: int,
    current_to_create_min_sample: int,
    current_create_to_action_min_sample: int,
) -> dict[str, Any]:
    home_count = counts["workspace_home_opened_count"]
    create_count = counts["workspace_source_create_count"]
    action_count = counts["workspace_source_action_requested_count"]

    home_to_create_rate = round((create_count / home_count) * 100, 1) if home_count else 0.0
    create_to_action_rate = round((action_count / create_count) * 100, 1) if create_count else 0.0

    to_create_target = current_to_create_target
    to_create_reason = "현재 설정 유지"
    if home_count >= min_home_sample:
        to_create_target, margin = _recommend_target_rate(home_to_create_rate, home_count)
        to_create_reason = f"관측치 {home_to_create_rate}% - 안정 마진 {margin}%"
    else:
        to_create_reason = f"샘플 부족({home_count} < {min_home_sample})"

    create_to_action_target = current_create_to_action_target
    create_to_action_reason = "현재 설정 유지"
    if create_count >= min_create_sample:
        create_to_action_target, margin = _recommend_target_rate(create_to_action_rate, create_count)
        create_to_action_reason = f"관측치 {create_to_action_rate}% - 안정 마진 {margin}%"
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
            "home_to_create": home_to_create_rate,
            "create_to_action": create_to_action_rate,
        },
        "recommended": {
            "to_create_target": to_create_target,
            "create_to_action_target": create_to_action_target,
            "to_create_min_sample": recommended_to_create_min_sample,
            "create_to_action_min_sample": recommended_create_to_action_min_sample,
            "to_create_reason": to_create_reason,
            "create_to_action_reason": create_to_action_reason,
        },
    }


def _read_workspace_funnel_counts(since) -> dict[str, int]:
    from sheetbook.models import SheetbookMetricEvent

    event_qs = SheetbookMetricEvent.objects.filter(created_at__gte=since)
    workspace_home_opened_count = event_qs.filter(event_name="workspace_home_opened").count()

    workspace_source_create_count = 0
    workspace_source_action_requested_count = 0
    source_rows = event_qs.filter(
        event_name__in=["sheetbook_created", "action_execute_requested"]
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


def _read_workspace_funnel_counts_by_role(since) -> dict[str, dict[str, int]]:
    from sheetbook.models import SheetbookMetricEvent

    event_qs = SheetbookMetricEvent.objects.filter(created_at__gte=since)
    grouped_counts: dict[str, dict[str, int]] = {}

    def _ensure_role_counts(role_name: str) -> dict[str, int]:
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
        event_name__in=["sheetbook_created", "action_execute_requested"]
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


def _collect_snapshot(days: int) -> dict[str, Any]:
    from django.conf import settings
    from django.utils import timezone

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

    since = timezone.now() - timedelta(days=days)
    snapshot_core = _build_funnel_snapshot(
        counts=_read_workspace_funnel_counts(since),
        current_to_create_target=current_to_create_target,
        current_create_to_action_target=current_create_to_action_target,
        min_home_sample=current_to_create_min_sample,
        min_create_sample=current_create_to_action_min_sample,
        current_to_create_min_sample=current_to_create_min_sample,
        current_create_to_action_min_sample=current_create_to_action_min_sample,
    )
    role_breakdown = {
        role_name: _build_funnel_snapshot(
            counts=role_counts,
            current_to_create_target=current_to_create_target,
            current_create_to_action_target=current_create_to_action_target,
            min_home_sample=current_to_create_min_sample,
            min_create_sample=current_create_to_action_min_sample,
            current_to_create_min_sample=current_to_create_min_sample,
            current_create_to_action_min_sample=current_create_to_action_min_sample,
        )
        for role_name, role_counts in _read_workspace_funnel_counts_by_role(since).items()
    }

    return {
        "days": days,
        "counts": snapshot_core["counts"],
        "rates": snapshot_core["rates"],
        "current": {
            "to_create_target": current_to_create_target,
            "create_to_action_target": current_create_to_action_target,
            "to_create_min_sample": current_to_create_min_sample,
            "create_to_action_min_sample": current_create_to_action_min_sample,
        },
        "recommended": snapshot_core["recommended"],
        "role_breakdown": role_breakdown,
    }


def _upsert_csv_row(path: Path, row: dict[str, str], keys: tuple[str, ...]) -> None:
    fieldnames = [
        "date",
        "school_or_group",
        "class_scope",
        "active_teachers",
        "workspace_home_opened",
        "home_source_sheetbook_created",
        "home_source_action_execute_requested",
        "home_to_create_rate_pct",
        "create_to_action_rate_pct",
        "blockers",
        "next_action",
    ]

    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for existing in reader:
                normalized = {name: str(existing.get(name, "")) for name in fieldnames}
                rows.append(normalized)

    match_index = None
    for idx, existing in enumerate(rows):
        if all(str(existing.get(k, "")) == str(row.get(k, "")) for k in keys):
            match_index = idx
            break

    if match_index is None:
        rows.append(row)
    else:
        rows[match_index] = row

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_markdown(
    *,
    run_datetime: datetime,
    record_date: date,
    row: dict[str, str],
    snapshot: dict[str, Any],
    reflected_env: bool,
    reflected_reason: str,
) -> str:
    counts = snapshot["counts"]
    rates = snapshot["rates"]
    recommended = snapshot["recommended"]
    days = snapshot["days"]
    role_breakdown = snapshot.get("role_breakdown") or {}

    role_lines: list[str] = []
    for role_name in sorted(role_breakdown):
        role_snapshot = role_breakdown.get(role_name) or {}
        role_counts = role_snapshot.get("counts") or {}
        role_rates = role_snapshot.get("rates") or {}
        role_recommended = role_snapshot.get("recommended") or {}
        role_lines.append(
            f"- role={role_name}: "
            f"home={role_counts.get('workspace_home_opened_count', 0)}, "
            f"create={role_counts.get('workspace_source_create_count', 0)}, "
            f"action={role_counts.get('workspace_source_action_requested_count', 0)}, "
            f"home_to_create={role_rates.get('home_to_create', 0.0)}%, "
            f"create_to_action={role_rates.get('create_to_action', 0.0)}%, "
            f"to_create_target={role_recommended.get('to_create_target', '-') } ({role_recommended.get('to_create_reason', '사유 없음')}), "
            f"create_to_action_target={role_recommended.get('create_to_action_target', '-') } ({role_recommended.get('create_to_action_reason', '사유 없음')})"
        )
    role_markdown = "\n".join(role_lines) if role_lines else "- role breakdown 없음"

    return f"""# Sheetbook Pilot Event Log ({record_date.isoformat()})

기록 시각: {run_datetime.strftime("%Y-%m-%d %H:%M")}  
기준 명령: `python manage.py recommend_sheetbook_thresholds --days {days}`

## 1) 일일 기록 표

| date | school_or_group | class_scope | active_teachers | workspace_home_opened | home_source_sheetbook_created | home_source_action_execute_requested | home_to_create_rate(%) | create_to_action_rate(%) | blockers | next_action |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| {row["date"]} | {row["school_or_group"]} | {row["class_scope"]} | {row["active_teachers"]} | {row["workspace_home_opened"]} | {row["home_source_sheetbook_created"]} | {row["home_source_action_execute_requested"]} | {row["home_to_create_rate_pct"]} | {row["create_to_action_rate_pct"]} | {row["blockers"]} | {row["next_action"]} |

## 2) 주간 스냅샷

- 기간: 최근 {days}일
- 누적 `workspace_home_opened`: {counts["workspace_home_opened_count"]}
- 누적 `sheetbook_created(entry_source=workspace_home*)`: {counts["workspace_source_create_count"]}
- 누적 `action_execute_requested(entry_source=workspace_home*)`: {counts["workspace_source_action_requested_count"]}
- 누적 홈->수첩 생성 전환율: {rates["home_to_create"]}%
- 누적 수첩 생성->기능 실행 전환율: {rates["create_to_action"]}%
- 주요 이슈: {"샘플 부족" if counts["workspace_home_opened_count"] < snapshot["current"]["to_create_min_sample"] else "집계 정상"}
- 다음 주 액션: {row["next_action"]}

## 3) 역할별 스냅샷 참고

{role_markdown}

## 4) 재보정 실행 기록

### Output Snapshot

- 실행일: {record_date.isoformat()}
- 추천 목표(`SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE`): {recommended["to_create_target"]} ({recommended["to_create_reason"]})
- 추천 목표(`SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE`): {recommended["create_to_action_target"]} ({recommended["create_to_action_reason"]})
- 추천 샘플(`SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE`): {recommended["to_create_min_sample"]}
- 추천 샘플(`SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE`): {recommended["create_to_action_min_sample"]}
- 반영 여부(YES/NO): {"YES" if reflected_env else "NO"}
- 반영 사유: {reflected_reason}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect current sheetbook pilot funnel snapshot and write Markdown/CSV log files."
    )
    parser.add_argument("--days", type=int, default=14, help="집계 기간(일). 기본 14")
    parser.add_argument("--date", default="", help="기록 날짜(YYYY-MM-DD). 기본값: 오늘")
    parser.add_argument(
        "--school-or-group",
        default="local-pilot-baseline",
        help="로그 row의 school_or_group 값",
    )
    parser.add_argument("--class-scope", default="baseline", help="로그 row의 class_scope 값")
    parser.add_argument("--active-teachers", type=int, default=0, help="활성 교사 수")
    parser.add_argument(
        "--blockers",
        default="파일럿 실사용 트래픽 미유입",
        help="blockers 컬럼 값",
    )
    parser.add_argument(
        "--next-action",
        default="파일럿 계정 3개 학급 대상 홈 진입/수첩 생성/기능 실행 안내(운영자, 03-02)",
        help="next_action 컬럼 값",
    )
    parser.add_argument(
        "--reflected-env",
        action="store_true",
        help="추천 임계치를 env에 반영한 경우 YES로 기록",
    )
    parser.add_argument(
        "--reflected-reason",
        default="파일럿 데이터 부족으로 기본값 유지",
        help="반영 여부 사유",
    )
    parser.add_argument(
        "--md-output",
        default="",
        help="Markdown 출력 경로. 미지정 시 logs/SHEETBOOK_PILOT_EVENT_LOG_<date>.md",
    )
    parser.add_argument(
        "--csv-output",
        default="",
        help="CSV 출력 경로. 미지정 시 logs/sheetbook_pilot_event_log_<date>.csv",
    )
    args = parser.parse_args()

    _setup_django()

    today = date.today()
    if args.date:
        record_date = date.fromisoformat(args.date)
    else:
        record_date = today
    run_datetime = datetime.now()

    root = _repo_root()
    md_output = Path(args.md_output) if args.md_output else Path(
        f"docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_{record_date.isoformat()}.md"
    )
    csv_output = Path(args.csv_output) if args.csv_output else Path(
        f"docs/runbooks/logs/sheetbook_pilot_event_log_{record_date.isoformat()}.csv"
    )
    if not md_output.is_absolute():
        md_output = root / md_output
    if not csv_output.is_absolute():
        csv_output = root / csv_output

    days = _safe_positive_int(args.days, 14)
    snapshot = _collect_snapshot(days=days)
    counts = snapshot["counts"]
    rates = snapshot["rates"]

    row = {
        "date": record_date.isoformat(),
        "school_or_group": args.school_or_group,
        "class_scope": args.class_scope,
        "active_teachers": str(max(0, int(args.active_teachers))),
        "workspace_home_opened": str(counts["workspace_home_opened_count"]),
        "home_source_sheetbook_created": str(counts["workspace_source_create_count"]),
        "home_source_action_execute_requested": str(
            counts["workspace_source_action_requested_count"]
        ),
        "home_to_create_rate_pct": f'{rates["home_to_create"]:.1f}',
        "create_to_action_rate_pct": f'{rates["create_to_action"]:.1f}',
        "blockers": args.blockers,
        "next_action": args.next_action,
    }

    _upsert_csv_row(csv_output, row=row, keys=("date", "school_or_group", "class_scope"))

    markdown = _build_markdown(
        run_datetime=run_datetime,
        record_date=record_date,
        row=row,
        snapshot=snapshot,
        reflected_env=bool(args.reflected_env),
        reflected_reason=args.reflected_reason,
    )
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(markdown, encoding="utf-8")

    result = {
        "days": days,
        "record_date": record_date.isoformat(),
        "md_output": str(md_output),
        "csv_output": str(csv_output),
        "counts": counts,
        "rates": rates,
        "recommended": snapshot["recommended"],
        "role_breakdown": snapshot["role_breakdown"],
        "row": row,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
