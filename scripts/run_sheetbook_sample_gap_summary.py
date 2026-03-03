import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalize_due_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return ""
    return parsed.isoformat()


def _build_sample_gap_next_actions(
    *,
    days: int,
    home_gap: int,
    create_gap: int,
    archive_event_gap: int,
    due_date: str = "",
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    days_value = max(1, int(days))
    action_gap = min(max(0, int(create_gap)), 3)
    has_any_gap = home_gap > 0 or create_gap > 0 or archive_event_gap > 0
    pilot_accumulate_output = "docs/handoff/smoke_sheetbook_collect_pilot_samples_progress_latest.json"
    pilot_output = "docs/handoff/smoke_sheetbook_collect_pilot_samples_latest.json"
    archive_output = "docs/handoff/smoke_sheetbook_collect_archive_events_latest.json"
    if home_gap > 0 or create_gap > 0:
        gap_tokens: list[str] = []
        if home_gap > 0:
            gap_tokens.append(f"workspace_home_opened {home_gap}건")
        if create_gap > 0:
            gap_tokens.append(f"home_source_sheetbook_created {create_gap}건")
        actions.append(
            {
                "type": "collect_pilot_samples",
                "description": "파일럿 이벤트 추가 확보(누적): " + ", ".join(gap_tokens),
                "command": (
                    "python scripts/run_sheetbook_collect_pilot_samples.py "
                    "--home-collection-mode direct-event "
                    f"--home-count {home_gap} --create-count {create_gap} "
                    f"--action-count {action_gap} --archive-event-count 0 "
                    f"--output {pilot_accumulate_output}"
                ),
            }
        )
        actions.append(
            {
                "type": "collect_pilot_samples_local_rehearsal",
                "description": (
                    "로컬 리허설용 표본 생성(운영 판정 분리): "
                    + ", ".join(gap_tokens)
                ),
                "command": (
                    "python scripts/run_sheetbook_collect_pilot_samples.py "
                    "--home-collection-mode direct-event "
                    f"--clear-before --home-count {home_gap} --create-count {create_gap} "
                    f"--action-count {action_gap} --archive-event-count 0 "
                    f"--output {pilot_output}"
                ),
            }
        )
    if archive_event_gap > 0:
        actions.append(
            {
                "type": "collect_archive_events",
                "description": f"아카이브 이벤트 {archive_event_gap}건 추가 확보 후 품질 판정 재확인",
                "command": f"python scripts/run_sheetbook_archive_bulk_snapshot.py --days {days_value}",
            }
        )
        actions.append(
            {
                "type": "collect_archive_events_local_rehearsal",
                "description": f"로컬 리허설용 아카이브 이벤트 {archive_event_gap}건 생성(운영 판정 분리)",
                "command": (
                    "python scripts/run_sheetbook_collect_pilot_samples.py "
                    "--home-collection-mode direct-event "
                    f"--home-count 0 --create-count 0 --archive-event-count {archive_event_gap} "
                    f"--output {archive_output}"
                ),
            }
        )
    if has_any_gap:
        actions.append(
            {
                "type": "collect_all_local_rehearsal_cycle",
                "description": "로컬 통합 리허설 사이클 1회 실행(수집 -> 검증 -> clear -> 복구)",
                "command": (
                    "python scripts/run_sheetbook_local_rehearsal_cycle.py "
                    f"--days {days_value} --home-count {home_gap} --create-count {create_gap} "
                    f"--action-count {action_gap} --archive-event-count {archive_event_gap} "
                    "--allow-pilot-hold-for-beta"
                    + (f" --due-date {due_date}" if str(due_date or "").strip() else "")
                ),
            }
        )
    if actions:
        actions.append(
            {
                "type": "refresh_gap_summary",
                "description": "표본 수집 후 gap summary 재생성",
                "command": f"python scripts/run_sheetbook_sample_gap_summary.py --days {days_value}",
            }
        )
        return actions
    return [
        {
            "type": "monitoring",
            "description": "표본 부족 없음, 주기적으로 gap summary 확인",
            "command": f"python scripts/run_sheetbook_sample_gap_summary.py --days {days_value}",
        }
    ]


def _build_sample_gap_summary(
    *,
    days: int,
    generated_at: str,
    readiness: dict[str, Any],
    archive_snapshot: dict[str, Any],
    due_date: str = "",
) -> dict[str, Any]:
    pilot = readiness.get("pilot") or {}
    pilot_counts = pilot.get("counts") or {}
    pilot_minimum = pilot.get("minimum_samples") or {}

    home_count = _to_int(pilot_counts.get("workspace_home_opened"), 0)
    create_count = _to_int(pilot_counts.get("home_source_sheetbook_created"), 0)
    action_count = _to_int(pilot_counts.get("home_source_action_execute_requested"), 0)
    min_home = _to_int(pilot_minimum.get("workspace_home_opened"), 5)
    min_create = _to_int(pilot_minimum.get("home_source_sheetbook_created"), 5)

    home_gap = max(0, min_home - home_count)
    create_gap = max(0, min_create - create_count)

    archive_quality = archive_snapshot.get("quality") or {}
    archive_event_count = _to_int(archive_snapshot.get("event_count"), 0)
    archive_event_gap = _to_int(archive_quality.get("sample_gap_count"), 0)
    archive_next_step = str(archive_quality.get("next_step") or "")

    pilot_ready = home_gap == 0 and create_gap == 0
    archive_ready = archive_event_gap == 0

    blockers = []
    if home_gap > 0:
        blockers.append(f"pilot_home_opened_gap:{home_gap}")
    if create_gap > 0:
        blockers.append(f"pilot_create_gap:{create_gap}")
    if archive_event_gap > 0:
        blockers.append(f"archive_event_gap:{archive_event_gap}")
    next_actions = _build_sample_gap_next_actions(
        days=days,
        home_gap=home_gap,
        create_gap=create_gap,
        archive_event_gap=archive_event_gap,
        due_date=str(due_date or "").strip(),
    )

    return {
        "generated_at": generated_at,
        "days": int(days),
        "pilot": {
            "counts": {
                "workspace_home_opened": home_count,
                "home_source_sheetbook_created": create_count,
                "home_source_action_execute_requested": action_count,
            },
            "minimum_samples": {
                "workspace_home_opened": min_home,
                "home_source_sheetbook_created": min_create,
            },
            "gaps": {
                "workspace_home_opened_gap": home_gap,
                "home_source_sheetbook_created_gap": create_gap,
            },
            "ready": pilot_ready,
        },
        "archive": {
            "event_count": archive_event_count,
            "event_gap": archive_event_gap,
            "next_step": archive_next_step,
            "ready": archive_ready,
        },
        "overall": {
            "ready": pilot_ready and archive_ready,
            "blockers": blockers,
            "next_actions": next_actions,
        },
    }


def _build_sample_gap_markdown(*, summary: dict[str, Any], json_output_path: Path) -> str:
    overall = summary.get("overall") or {}
    pilot = summary.get("pilot") or {}
    archive = summary.get("archive") or {}

    blockers = [str(item) for item in (overall.get("blockers") or []) if str(item)]
    blocker_text = ", ".join(blockers) if blockers else "(없음)"

    action_lines: list[str] = []
    for action in overall.get("next_actions") or []:
        if not isinstance(action, dict):
            continue
        desc = str(action.get("description") or "").strip()
        cmd = str(action.get("command") or "").strip()
        if desc and cmd:
            action_lines.append(f"- {desc}: `{cmd}`")
        elif cmd:
            action_lines.append(f"- `{cmd}`")
        elif desc:
            action_lines.append(f"- {desc}")
    if not action_lines:
        action_lines.append("- (none)")

    pilot_counts = pilot.get("counts") or {}
    pilot_gaps = pilot.get("gaps") or {}

    return f"""# Sheetbook Sample Gap Summary ({summary.get('generated_at', '')})

- days: `{summary.get("days", 14)}`
- overall_ready: `{overall.get("ready")}`
- blockers: {blocker_text}
- json_output: `{json_output_path}`

## Pilot
- workspace_home_opened: `{pilot_counts.get("workspace_home_opened", 0)}`
- home_source_sheetbook_created: `{pilot_counts.get("home_source_sheetbook_created", 0)}`
- home_source_action_execute_requested: `{pilot_counts.get("home_source_action_execute_requested", 0)}`
- workspace_home_opened_gap: `{pilot_gaps.get("workspace_home_opened_gap", 0)}`
- home_source_sheetbook_created_gap: `{pilot_gaps.get("home_source_sheetbook_created_gap", 0)}`

## Archive
- event_count: `{archive.get("event_count", 0)}`
- event_gap: `{archive.get("event_gap", 0)}`
- next_step: `{archive.get("next_step", "")}`

## Next Actions
{chr(10).join(action_lines)}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize current pilot/archive sample gaps from latest handoff JSON files."
    )
    parser.add_argument(
        "--readiness",
        default="docs/handoff/sheetbook_release_readiness_latest.json",
        help="readiness JSON path",
    )
    parser.add_argument(
        "--archive-snapshot",
        default="docs/handoff/sheetbook_archive_bulk_snapshot_latest.json",
        help="archive snapshot JSON path",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/sheetbook_sample_gap_summary_latest.json",
        help="summary output path",
    )
    parser.add_argument("--days", type=int, default=14, help="집계 기간(일). 기본 14")
    parser.add_argument("--due-date", default="", help="next action 명령에 포함할 due-date (YYYY-MM-DD)")
    parser.add_argument(
        "--md-output",
        default="",
        help="markdown output path (default: docs/runbooks/logs/SHEETBOOK_SAMPLE_GAP_<YYYY-MM-DD>.md)",
    )
    args = parser.parse_args()

    root = _repo_root()
    today = date.today().isoformat()
    readiness_path = Path(args.readiness)
    archive_path = Path(args.archive_snapshot)
    output_path = Path(args.output)
    if not readiness_path.is_absolute():
        readiness_path = root / readiness_path
    if not archive_path.is_absolute():
        archive_path = root / archive_path
    if not output_path.is_absolute():
        output_path = root / output_path

    readiness = _load_json(readiness_path)
    archive_snapshot = _load_json(archive_path)
    summary = _build_sample_gap_summary(
        days=int(args.days),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        readiness=readiness,
        archive_snapshot=archive_snapshot,
        due_date=_normalize_due_date(args.due_date),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_output = Path(args.md_output) if args.md_output else Path(
        f"docs/runbooks/logs/SHEETBOOK_SAMPLE_GAP_{today}.md"
    )
    if not md_output.is_absolute():
        md_output = root / md_output
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(
        _build_sample_gap_markdown(summary=summary, json_output_path=output_path),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "overall_ready": (summary.get("overall") or {}).get("ready"),
                "blockers": (summary.get("overall") or {}).get("blockers"),
                "next_actions": (summary.get("overall") or {}).get("next_actions"),
                "output": str(output_path),
                "md_output": str(md_output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
