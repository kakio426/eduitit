import argparse
import json
import os
import sys
from datetime import date, timedelta
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


def _to_nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return parsed if parsed >= 0 else int(default)


def _to_percentage_threshold(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    if parsed < 0:
        return 0.0
    if parsed > 100:
        return 100.0
    return round(parsed, 1)


def _threshold_reason_suffix(threshold_pct: float) -> str:
    if float(threshold_pct).is_integer():
        return str(int(threshold_pct))
    return str(threshold_pct).replace(".", "_")


def _collect_snapshot(
    days: int,
    *,
    min_events: int = 5,
    ignored_rate_threshold: float = 10.0,
    unchanged_rate_threshold: float = 50.0,
) -> dict[str, Any]:
    from django.utils import timezone

    from sheetbook.models import SheetbookMetricEvent

    min_events = _to_nonnegative_int(min_events, default=5) or 5
    ignored_rate_threshold = _to_percentage_threshold(ignored_rate_threshold, default=10.0)
    unchanged_rate_threshold = _to_percentage_threshold(unchanged_rate_threshold, default=50.0)

    since = timezone.now() - timedelta(days=days)
    rows = list(
        SheetbookMetricEvent.objects.filter(
            created_at__gte=since,
            event_name="sheetbook_archive_bulk_updated",
        ).values("metadata")
    )

    selected_count_total = 0
    matched_count_total = 0
    changed_total = 0
    unchanged_total = 0
    ignored_total = 0
    archive_changed_total = 0
    unarchive_changed_total = 0

    for row in rows:
        metadata = row.get("metadata") or {}
        selected_count = _to_nonnegative_int(metadata.get("selected_count"), default=0)
        matched_count = _to_nonnegative_int(metadata.get("matched_count"), default=0)
        changed_count = _to_nonnegative_int(metadata.get("changed_count"), default=0)
        unchanged_count = _to_nonnegative_int(metadata.get("unchanged_count"), default=0)
        ignored_count = _to_nonnegative_int(metadata.get("ignored_count"), default=0)
        archive_action = str(metadata.get("archive_action") or "").strip().lower()

        selected_count_total += selected_count
        matched_count_total += matched_count
        changed_total += changed_count
        unchanged_total += unchanged_count
        ignored_total += ignored_count
        if archive_action == "unarchive":
            unarchive_changed_total += changed_count
        else:
            archive_changed_total += changed_count

    attempted_total = changed_total + unchanged_total + ignored_total
    ignored_rate_pct = round((ignored_total / attempted_total) * 100, 1) if attempted_total else 0.0
    unchanged_rate_pct = round((unchanged_total / attempted_total) * 100, 1) if attempted_total else 0.0
    changed_rate_pct = round((changed_total / attempted_total) * 100, 1) if attempted_total else 0.0

    event_count = len(rows)
    has_enough_samples = event_count >= min_events
    sample_gap_count = max(0, min_events - event_count)
    needs_attention = has_enough_samples and (
        ignored_rate_pct > ignored_rate_threshold or unchanged_rate_pct > unchanged_rate_threshold
    )

    attention_reasons = []
    if has_enough_samples and ignored_rate_pct > ignored_rate_threshold:
        attention_reasons.append(
            f"ignored_rate_over_{_threshold_reason_suffix(ignored_rate_threshold)}pct"
        )
    if has_enough_samples and unchanged_rate_pct > unchanged_rate_threshold:
        attention_reasons.append(
            f"unchanged_rate_over_{_threshold_reason_suffix(unchanged_rate_threshold)}pct"
        )

    next_step = "continue_monitoring"
    if sample_gap_count > 0:
        next_step = "collect_more_samples"
    elif needs_attention:
        next_step = "investigate_bulk_flow"

    return {
        "days": days,
        "event_count": event_count,
        "counts": {
            "selected_count_total": selected_count_total,
            "matched_count_total": matched_count_total,
            "changed_total": changed_total,
            "unchanged_total": unchanged_total,
            "ignored_total": ignored_total,
            "archive_changed_total": archive_changed_total,
            "unarchive_changed_total": unarchive_changed_total,
        },
        "rates": {
            "changed_rate_pct": changed_rate_pct,
            "unchanged_rate_pct": unchanged_rate_pct,
            "ignored_rate_pct": ignored_rate_pct,
        },
        "quality": {
            "has_enough_samples": has_enough_samples,
            "sample_gap_count": sample_gap_count,
            "needs_attention": needs_attention,
            "attention_reasons": attention_reasons,
            "thresholds": {
                "min_events": min_events,
                "ignored_rate_threshold_pct": ignored_rate_threshold,
                "unchanged_rate_threshold_pct": unchanged_rate_threshold,
            },
            "next_step": next_step,
        },
    }


def _build_markdown(*, snapshot: dict[str, Any], json_output_path: Path) -> str:
    quality = snapshot.get("quality") or {}
    counts = snapshot.get("counts") or {}
    rates = snapshot.get("rates") or {}
    reasons = [str(item) for item in (quality.get("attention_reasons") or []) if str(item)]
    reasons_text = ", ".join(reasons) if reasons else "(없음)"
    md_output = str(snapshot.get("md_output") or "")

    return f"""# Sheetbook Archive Bulk Snapshot

- days: `{snapshot.get("days", 14)}`
- event_count: `{snapshot.get("event_count", 0)}`
- has_enough_samples: `{quality.get("has_enough_samples")}`
- sample_gap_count: `{quality.get("sample_gap_count", 0)}`
- needs_attention: `{quality.get("needs_attention")}`
- attention_reasons: {reasons_text}
- next_step: `{quality.get("next_step", "")}`
- changed_rate_pct: `{rates.get("changed_rate_pct", 0)}`
- unchanged_rate_pct: `{rates.get("unchanged_rate_pct", 0)}`
- ignored_rate_pct: `{rates.get("ignored_rate_pct", 0)}`
- archive_changed_total: `{counts.get("archive_changed_total", 0)}`
- unarchive_changed_total: `{counts.get("unarchive_changed_total", 0)}`
- json_output: `{json_output_path}`
- md_output: `{md_output}`
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect sheetbook bulk archive/unarchive quality snapshot."
    )
    parser.add_argument("--days", type=int, default=14, help="집계 기간(일). 기본 14")
    parser.add_argument(
        "--min-events",
        type=int,
        default=5,
        help="품질 판정에 필요한 최소 이벤트 수. 기본 5",
    )
    parser.add_argument(
        "--ignored-rate-threshold",
        type=float,
        default=10.0,
        help="ignored 비율 주의 임계치(%%). 기본 10.0",
    )
    parser.add_argument(
        "--unchanged-rate-threshold",
        type=float,
        default=50.0,
        help="unchanged 비율 주의 임계치(%%). 기본 50.0",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/sheetbook_archive_bulk_snapshot_latest.json",
        help="출력 JSON 경로",
    )
    parser.add_argument(
        "--md-output",
        default="",
        help="markdown output path (default: docs/runbooks/logs/SHEETBOOK_ARCHIVE_BULK_<YYYY-MM-DD>.md)",
    )
    args = parser.parse_args()

    _setup_django()
    days = _to_nonnegative_int(args.days, default=14) or 14
    today = date.today().isoformat()
    snapshot = _collect_snapshot(
        days=days,
        min_events=args.min_events,
        ignored_rate_threshold=args.ignored_rate_threshold,
        unchanged_rate_threshold=args.unchanged_rate_threshold,
    )
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = _repo_root() / output_path
    md_output_path = Path(args.md_output) if args.md_output else Path(
        f"docs/runbooks/logs/SHEETBOOK_ARCHIVE_BULK_{today}.md"
    )
    if not md_output_path.is_absolute():
        md_output_path = _repo_root() / md_output_path
    snapshot["md_output"] = str(md_output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_output_path.parent.mkdir(parents=True, exist_ok=True)
    md_output_path.write_text(
        _build_markdown(snapshot=snapshot, json_output_path=output_path),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                **snapshot,
                "output": str(output_path),
                "md_output": str(md_output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
