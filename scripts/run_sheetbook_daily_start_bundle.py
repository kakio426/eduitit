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
            "md_output": str(consent_freeze_snapshot.get("md_output") or ""),
        },
        "sample_gap": {
            "ready": bool(sample_gap_overall.get("ready")),
            "blockers": list(sample_gap_overall.get("blockers") or []),
            "next_actions": list(sample_gap_overall.get("next_actions") or []),
        },
        "has_command_failures": command_failed,
    }
    summary["overall"] = "HOLD" if command_failed else summary["decision"]
    summary["next_actions"] = _build_bundle_next_actions(summary)
    return summary


def _build_bundle_next_actions(summary: dict[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    days = int(summary.get("days") or 14)
    if bool(summary.get("has_command_failures")):
        actions.append(
            {
                "type": "rerun_failed_commands",
                "description": "실패한 명령을 우선 재실행하고 로그 tail 확인",
                "command": f"python scripts/run_sheetbook_daily_start_bundle.py --days {days}",
            }
        )
        return actions

    manual_pending = [str(item) for item in (summary.get("manual_pending") or []) if str(item)]
    if manual_pending:
        actions.append(
            {
                "type": "manual_signoff_pending",
                "description": "수동 signoff 완료 후 PASS 반영",
                "command": (
                    "python scripts/run_sheetbook_signoff_decision.py "
                    "--set staging_real_account_signoff=PASS:staging-ok "
                    "--set production_real_account_signoff=PASS:prod-ok"
                ),
            }
        )

    sample_gap = summary.get("sample_gap") or {}
    blockers = [str(item) for item in (sample_gap.get("blockers") or []) if str(item)]
    if blockers:
        actions.append(
            {
                "type": "collect_samples",
                "description": "표본 부족량(blockers) 해소 후 bundle+gap summary 재실행",
                "command": (
                    f"python scripts/run_sheetbook_daily_start_bundle.py --days {days} && "
                    f"python scripts/run_sheetbook_sample_gap_summary.py --days {days}"
                ),
            }
        )

    if str(summary.get("decision") or "").upper() == "HOLD" and not manual_pending and not blockers:
        actions.append(
            {
                "type": "review_hold_reasons",
                "description": "자동/수동 게이트 상태 재검토 후 GO/HOLD 재판정",
                "command": "python scripts/run_sheetbook_signoff_decision.py",
            }
        )

    if not actions:
        actions.append(
            {
                "type": "monitoring",
                "description": "현재 상태 유지, 정기적으로 bundle 재실행",
                "command": f"python scripts/run_sheetbook_daily_start_bundle.py --days {days}",
            }
        )
    return actions


def _build_bundle_markdown(*, summary: dict[str, Any], json_output_path: Path) -> str:
    commands = summary.get("commands") or []
    command_lines: list[str] = []
    for item in commands:
        if not isinstance(item, dict):
            continue
        command = str(item.get("command") or "").strip()
        ok = bool(item.get("ok"))
        command_lines.append(f"- [{'PASS' if ok else 'FAIL'}] `{command}`")
    if not command_lines:
        command_lines.append("- (no commands)")

    action_lines: list[str] = []
    for action in summary.get("next_actions") or []:
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

    sample_gap_action_lines: list[str] = []
    for action in (summary.get("sample_gap") or {}).get("next_actions") or []:
        if not isinstance(action, dict):
            continue
        desc = str(action.get("description") or "").strip()
        cmd = str(action.get("command") or "").strip()
        if desc and cmd:
            sample_gap_action_lines.append(f"- {desc}: `{cmd}`")
        elif cmd:
            sample_gap_action_lines.append(f"- `{cmd}`")
        elif desc:
            sample_gap_action_lines.append(f"- {desc}")
    if not sample_gap_action_lines:
        sample_gap_action_lines.append("- (none)")

    blockers = [str(item) for item in (summary.get("sample_gap") or {}).get("blockers", []) if str(item)]
    blocker_text = ", ".join(blockers) if blockers else "(없음)"

    return f"""# Sheetbook Daily Start Bundle ({summary.get('generated_at', '')})

- days: {summary.get("days")}
- overall: `{summary.get("overall")}`
- decision: `{summary.get("decision")}`
- readiness_status: `{summary.get("readiness_status")}`
- manual_pending: {", ".join(summary.get("manual_pending") or []) or "(없음)"}
- sample_gap_ready: `{(summary.get("sample_gap") or {}).get("ready")}`
- sample_gap_blockers: {blocker_text}
- archive_next_step: `{(summary.get("archive") or {}).get("next_step", "")}`
- consent_freeze_status: `{(summary.get("consent_freeze") or {}).get("status", "")}`
- consent_freeze_report: `{(summary.get("consent_freeze") or {}).get("md_output", "")}`
- json_output: `{json_output_path}`

## Commands
{chr(10).join(command_lines)}

## Next Actions
{chr(10).join(action_lines)}

## Sample Gap Next Actions
{chr(10).join(sample_gap_action_lines)}
"""


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
    parser.add_argument(
        "--md-output",
        default="",
        help="markdown output path (default: docs/runbooks/logs/SHEETBOOK_DAILY_START_<YYYY-MM-DD>.md)",
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
        ["python", "scripts/run_sheetbook_sample_gap_summary.py", "--days", str(args.days)],
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

    md_output = Path(args.md_output) if args.md_output else Path(
        f"docs/runbooks/logs/SHEETBOOK_DAILY_START_{today}.md"
    )
    if not md_output.is_absolute():
        md_output = root / md_output
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(
        _build_bundle_markdown(summary=summary, json_output_path=output_path),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "overall": summary.get("overall"),
                "decision": summary.get("decision"),
                "has_command_failures": summary.get("has_command_failures"),
                "output": str(output_path),
                "md_output": str(md_output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
