import argparse
import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _to_nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    if parsed < 0:
        return int(default)
    return parsed


def _resolve_action_count(value: Any, *, create_count: int) -> tuple[int, str, bool]:
    auto_value = min(max(0, int(create_count)), 3)
    if value is None:
        return auto_value, "auto", False
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return auto_value, "auto", True
    if parsed == -1:
        return auto_value, "auto", False
    if parsed < -1:
        return auto_value, "auto", True
    return parsed, "explicit", False


def _normalize_due_date(value: Any) -> tuple[str, bool]:
    raw = str(value or "").strip()
    if not raw:
        return "", False
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return "", True
    return parsed.isoformat(), False


def _run_command(root: Path, cmd: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    merged_lines: list[str] = []
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if stdout:
        merged_lines.extend(stdout.splitlines())
    if stderr:
        merged_lines.extend(stderr.splitlines())
    return {
        "command": " ".join(cmd),
        "ok": completed.returncode == 0,
        "returncode": int(completed.returncode),
        "tail": merged_lines[-20:],
    }


def _build_bundle_command(
    *,
    days: int,
    allow_pilot_hold_for_beta: bool,
    due_date: str,
) -> list[str]:
    cmd = [
        "python",
        "scripts/run_sheetbook_daily_start_bundle.py",
        "--days",
        str(int(days)),
    ]
    if allow_pilot_hold_for_beta:
        cmd.append("--allow-pilot-hold-for-beta")
    due_date_value = str(due_date or "").strip()
    if due_date_value:
        cmd.extend(["--due-date", due_date_value])
    return cmd


def _build_collect_command(
    *,
    home_count: int,
    create_count: int,
    action_count: Any,
    archive_event_count: int,
    output: str,
    clear_before: bool = False,
    clear_only: bool = False,
    strict_inputs: bool = False,
    home_collection_mode: str = "direct-event",
) -> list[str]:
    cmd = [
        "python",
        "scripts/run_sheetbook_collect_pilot_samples.py",
        "--home-collection-mode",
        str(home_collection_mode or "direct-event"),
    ]
    if clear_before:
        cmd.append("--clear-before")
    if clear_only:
        cmd.append("--clear-only")
    if strict_inputs:
        cmd.append("--strict-inputs")
    if not clear_only:
        cmd.extend(
            [
                "--home-count",
                str(int(home_count)),
                "--create-count",
                str(int(create_count)),
                "--action-count",
                str(action_count),
                "--archive-event-count",
                str(int(archive_event_count)),
            ]
        )
    output_value = str(output or "").strip()
    if output_value:
        cmd.extend(["--output", output_value])
    return cmd


def _build_command_plan(
    *,
    days: int,
    home_count: int,
    create_count: int,
    action_count_arg: Any,
    archive_event_count: int,
    allow_pilot_hold_for_beta: bool,
    due_date: str,
    collect_output: str,
    clear_output: str,
) -> list[list[str]]:
    bundle_cmd = _build_bundle_command(
        days=int(days),
        allow_pilot_hold_for_beta=bool(allow_pilot_hold_for_beta),
        due_date=str(due_date or "").strip(),
    )
    return [
        _build_collect_command(
            home_count=int(home_count),
            create_count=int(create_count),
            action_count=action_count_arg,
            archive_event_count=int(archive_event_count),
            clear_before=True,
            strict_inputs=True,
            output=str(collect_output or "").strip(),
        ),
        bundle_cmd,
        ["python", "scripts/run_sheetbook_sample_gap_summary.py", "--days", str(int(days))],
        _build_collect_command(
            home_count=0,
            create_count=0,
            action_count=0,
            archive_event_count=0,
            clear_only=True,
            output=str(clear_output or "").strip(),
        ),
        bundle_cmd,
        ["python", "scripts/run_sheetbook_sample_gap_summary.py", "--days", str(int(days))],
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local sheetbook rehearsal cycle (collect -> verify -> clear -> restore)."
    )
    parser.add_argument("--days", type=int, default=14, help="집계 기간(일). 기본 14")
    parser.add_argument("--home-count", type=int, default=5, help="workspace_home_opened 목표 수집량")
    parser.add_argument(
        "--create-count",
        type=int,
        default=5,
        help="home_source_sheetbook_created 목표 수집량",
    )
    parser.add_argument(
        "--action-count",
        type=int,
        default=-1,
        help="home_source_action_execute_requested 수집량(-1이면 create_count 기준 자동)",
    )
    parser.add_argument(
        "--archive-event-count",
        type=int,
        default=5,
        help="sheetbook_archive_bulk_updated 수집량",
    )
    parser.add_argument("--due-date", default="", help="bundle due-date (YYYY-MM-DD)")
    parser.add_argument(
        "--allow-pilot-hold-for-beta",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="bundle 재실행 시 allow-pilot-hold-for-beta 옵션 포함 여부",
    )
    parser.add_argument(
        "--collect-output",
        default="docs/handoff/smoke_sheetbook_collect_samples_bundle_latest.json",
        help="리허설 수집 결과 JSON 경로",
    )
    parser.add_argument(
        "--clear-output",
        default="docs/handoff/smoke_sheetbook_collect_samples_bundle_clear_latest.json",
        help="리허설 clear 결과 JSON 경로",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/smoke_sheetbook_local_rehearsal_cycle_latest.json",
        help="사이클 실행 요약 JSON 경로",
    )
    args = parser.parse_args()

    root = _repo_root()
    warnings: list[str] = []

    days = max(1, _to_nonnegative_int(args.days, default=14) or 14)
    home_count = _to_nonnegative_int(args.home_count, default=0)
    create_count = _to_nonnegative_int(args.create_count, default=0)
    archive_event_count = _to_nonnegative_int(args.archive_event_count, default=0)
    action_count, action_count_mode, used_action_count_fallback = _resolve_action_count(
        args.action_count,
        create_count=create_count,
    )
    if used_action_count_fallback:
        warnings.append("action_count_invalid_fallback")
    due_date, used_due_date_fallback = _normalize_due_date(args.due_date)
    if used_due_date_fallback:
        warnings.append("due_date_invalid_omitted")

    command_plan = _build_command_plan(
        days=days,
        home_count=home_count,
        create_count=create_count,
        action_count_arg=-1 if action_count_mode == "auto" else action_count,
        archive_event_count=archive_event_count,
        allow_pilot_hold_for_beta=bool(args.allow_pilot_hold_for_beta),
        due_date=due_date,
        collect_output=str(args.collect_output or "").strip(),
        clear_output=str(args.clear_output or "").strip(),
    )

    command_results: list[dict[str, Any]] = []
    failed_index: int | None = None
    failure_returncode: int = 0
    for idx, cmd in enumerate(command_plan):
        result = _run_command(root, cmd)
        command_results.append(result)
        if not bool(result.get("ok")):
            failed_index = idx
            failure_returncode = int(result.get("returncode") or 1)
            break

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "days": int(days),
        "warnings": warnings,
        "requested": {
            "home_count": int(home_count),
            "create_count": int(create_count),
            "action_count": int(action_count),
            "action_count_mode": str(action_count_mode),
            "archive_event_count": int(archive_event_count),
            "due_date": due_date,
            "allow_pilot_hold_for_beta": bool(args.allow_pilot_hold_for_beta),
        },
        "collect_output": str(args.collect_output or "").strip(),
        "clear_output": str(args.clear_output or "").strip(),
        "success": failed_index is None,
        "failed_index": failed_index,
        "commands": command_results,
    }

    output_path = Path(str(args.output or "").strip() or "docs/handoff/smoke_sheetbook_local_rehearsal_cycle_latest.json")
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary["output"] = str(output_path)
    print(json.dumps(summary, ensure_ascii=False))

    if failed_index is None:
        return 0
    return failure_returncode if failure_returncode != 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
