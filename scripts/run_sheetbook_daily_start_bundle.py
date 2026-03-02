import argparse
import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_command(root: Path, cmd: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    merged_lines = []
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


def _build_bundle_summary(
    *,
    generated_at: str,
    days: int,
    command_results: list[dict[str, Any]],
    readiness: dict[str, Any],
    decision: dict[str, Any],
    archive_snapshot: dict[str, Any],
    consent_freeze_snapshot: dict[str, Any],
    sample_gap_summary: dict[str, Any],
) -> dict[str, Any]:
    readiness_overall = readiness.get("overall") or {}
    decision_context = decision.get("decision_context") or {}
    pilot = readiness.get("pilot") or {}
    pilot_counts = pilot.get("counts") or {}
    archive_quality = archive_snapshot.get("quality") or {}
    command_failed = any(not bool(item.get("ok")) for item in command_results)
    sample_gap_overall = sample_gap_summary.get("overall") or {}

    summary = {
        "generated_at": generated_at,
        "days": int(days),
        "commands": command_results,
        "readiness_status": str(readiness_overall.get("status") or "HOLD").upper(),
        "decision": str(decision.get("decision") or "HOLD").upper(),
        "manual_pending": list(readiness_overall.get("manual_pending") or []),
        "manual_alias_statuses": dict(decision_context.get("manual_alias_statuses") or {}),
        "pilot_counts": {
            "workspace_home_opened": int(pilot_counts.get("workspace_home_opened") or 0),
            "home_source_sheetbook_created": int(
                pilot_counts.get("home_source_sheetbook_created") or 0
            ),
            "home_source_action_execute_requested": int(
                pilot_counts.get("home_source_action_execute_requested") or 0
            ),
        },
        "archive": {
            "event_count": int(archive_snapshot.get("event_count") or 0),
            "next_step": str(archive_quality.get("next_step") or ""),
            "needs_attention": bool(archive_quality.get("needs_attention")),
        },
        "consent_freeze": {
            "status": str(consent_freeze_snapshot.get("status") or "").upper(),
            "reasons": list(consent_freeze_snapshot.get("reasons") or []),
        },
        "sample_gap": {
            "ready": bool(sample_gap_overall.get("ready")),
            "blockers": list(sample_gap_overall.get("blockers") or []),
        },
        "has_command_failures": command_failed,
    }
    summary["overall"] = "HOLD" if command_failed else summary["decision"]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run sheetbook daily-start checklist commands and save a compact JSON summary."
    )
    parser.add_argument("--days", type=int, default=14, help="집계 기간(일). 기본 14")
    parser.add_argument("--author", default="sheetbook-ops", help="signoff log author")
    parser.add_argument("--owner", default="sheetbook-release", help="signoff log owner")
    parser.add_argument(
        "--next-action",
        default="staging/prod 실계정 점검",
        help="signoff log next_action",
    )
    parser.add_argument("--due-date", default="", help="signoff log due_date (YYYY-MM-DD)")
    parser.add_argument(
        "--output",
        default="docs/handoff/sheetbook_daily_start_bundle_latest.json",
        help="summary JSON output path",
    )
    args = parser.parse_args()

    root = _repo_root()
    today = date.today().isoformat()
    due_date = args.due_date.strip() or today

    command_plan: list[list[str]] = [
        ["python", "scripts/run_sheetbook_release_readiness.py", "--days", str(args.days)],
        ["python", "scripts/run_sheetbook_signoff_decision.py"],
        [
            "python",
            "scripts/run_sheetbook_release_signoff_log.py",
            "--date",
            today,
            "--author",
            args.author,
            "--owner",
            args.owner,
            "--next-action",
            args.next_action,
            "--due-date",
            due_date,
        ],
        [
            "python",
            "manage.py",
            "recommend_sheetbook_thresholds",
            "--days",
            str(args.days),
            "--group-by-role",
        ],
        ["python", "scripts/run_sheetbook_pilot_log_snapshot.py", "--days", str(args.days)],
        ["python", "scripts/run_sheetbook_archive_bulk_snapshot.py", "--days", str(args.days)],
        ["python", "scripts/run_sheetbook_consent_freeze_snapshot.py"],
        ["python", "scripts/run_sheetbook_sample_gap_summary.py"],
    ]

    command_results = [_run_command(root, cmd) for cmd in command_plan]

    readiness = _load_json(root / "docs/handoff/sheetbook_release_readiness_latest.json")
    decision = _load_json(root / "docs/handoff/sheetbook_release_decision_latest.json")
    archive_snapshot = _load_json(root / "docs/handoff/sheetbook_archive_bulk_snapshot_latest.json")
    consent_freeze_snapshot = _load_json(
        root / "docs/handoff/sheetbook_consent_freeze_snapshot_latest.json"
    )
    sample_gap_summary = _load_json(root / "docs/handoff/sheetbook_sample_gap_summary_latest.json")
    summary = _build_bundle_summary(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        days=int(args.days),
        command_results=command_results,
        readiness=readiness,
        decision=decision,
        archive_snapshot=archive_snapshot,
        consent_freeze_snapshot=consent_freeze_snapshot,
        sample_gap_summary=sample_gap_summary,
    )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "overall": summary.get("overall"),
                "decision": summary.get("decision"),
                "has_command_failures": summary.get("has_command_failures"),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
