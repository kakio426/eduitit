import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(root: Path, raw: str, *, default_rel_path: str) -> Path:
    if not raw:
        return root / default_rel_path
    path = Path(str(raw))
    if not path.is_absolute():
        path = root / path
    return path


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


def _build_summary(
    *,
    readiness: dict[str, Any],
    decision: dict[str, Any],
    daily_start: dict[str, Any],
    archive_snapshot: dict[str, Any],
    sample_gap_summary: dict[str, Any],
    consent_freeze_snapshot: dict[str, Any],
) -> dict[str, Any]:
    readiness_overall = readiness.get("overall") or {}
    sample_gap_overall = sample_gap_summary.get("overall") or {}
    archive_quality = archive_snapshot.get("quality") or {}
    consent_reasons = [str(item) for item in (consent_freeze_snapshot.get("reasons") or []) if str(item)]
    next_actions: list[dict[str, str]] = []
    seen_commands: set[str] = set()

    action_sources = [
        ("daily_start", daily_start.get("next_actions") or []),
        ("sample_gap", sample_gap_overall.get("next_actions") or []),
        ("decision", decision.get("next_actions") or []),
    ]
    for source, actions in action_sources:
        for item in actions:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command") or "").strip()
            if not command or command in seen_commands:
                continue
            seen_commands.add(command)
            next_actions.append(
                {
                    "source": source,
                    "type": str(item.get("type") or ""),
                    "description": str(item.get("description") or "").strip(),
                    "command": command,
                }
            )

    return {
        "overall": str(daily_start.get("overall") or decision.get("decision") or "HOLD").upper(),
        "decision": str(decision.get("decision") or "HOLD").upper(),
        "readiness_status": str(readiness_overall.get("status") or "HOLD").upper(),
        "manual_pending": [str(item) for item in (readiness_overall.get("manual_pending") or []) if str(item)],
        "sample_gap_blockers": [
            str(item) for item in (sample_gap_overall.get("blockers") or []) if str(item)
        ],
        "archive_next_step": str(archive_quality.get("next_step") or ""),
        "consent_freeze_status": str(consent_freeze_snapshot.get("status") or "").upper(),
        "consent_freeze_reasons": consent_reasons,
        "next_actions": next_actions,
    }


def _build_markdown(
    *,
    record_date: str,
    summary: dict[str, Any],
    report_paths: dict[str, str],
) -> str:
    manual_pending = ", ".join(summary.get("manual_pending") or []) or "(없음)"
    blockers = ", ".join(summary.get("sample_gap_blockers") or []) or "(없음)"
    consent_reasons = ", ".join(summary.get("consent_freeze_reasons") or []) or "(없음)"

    report_lines = [f"- {name}: `{path}`" for name, path in report_paths.items()]
    if not report_lines:
        report_lines = ["- (none)"]

    action_lines: list[str] = []
    for action in summary.get("next_actions") or []:
        if not isinstance(action, dict):
            continue
        source = str(action.get("source") or "").strip()
        desc = str(action.get("description") or "").strip()
        cmd = str(action.get("command") or "").strip()
        if source and desc and cmd:
            action_lines.append(f"- [{source}] {desc}: `{cmd}`")
        elif source and cmd:
            action_lines.append(f"- [{source}] `{cmd}`")
        elif cmd:
            action_lines.append(f"- `{cmd}`")
    if not action_lines:
        action_lines.append("- (none)")

    return f"""# Sheetbook Ops Index ({record_date})

- overall: `{summary.get("overall")}`
- decision: `{summary.get("decision")}`
- readiness_status: `{summary.get("readiness_status")}`
- manual_pending: {manual_pending}
- sample_gap_blockers: {blockers}
- archive_next_step: `{summary.get("archive_next_step")}`
- consent_freeze_status: `{summary.get("consent_freeze_status")}`
- consent_freeze_reasons: {consent_reasons}

## Reports
{chr(10).join(report_lines)}

## Next Actions
{chr(10).join(action_lines)}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate sheetbook operations index markdown from latest handoff JSON files."
    )
    parser.add_argument("--record-date", default="", help="report date (YYYY-MM-DD). default=today")
    parser.add_argument(
        "--daily-start",
        default="docs/handoff/sheetbook_daily_start_bundle_latest.json",
        help="daily start bundle JSON path",
    )
    parser.add_argument(
        "--readiness",
        default="docs/handoff/sheetbook_release_readiness_latest.json",
        help="readiness JSON path",
    )
    parser.add_argument(
        "--decision",
        default="docs/handoff/sheetbook_release_decision_latest.json",
        help="decision JSON path",
    )
    parser.add_argument(
        "--archive-snapshot",
        default="docs/handoff/sheetbook_archive_bulk_snapshot_latest.json",
        help="archive snapshot JSON path",
    )
    parser.add_argument(
        "--sample-gap-summary",
        default="docs/handoff/sheetbook_sample_gap_summary_latest.json",
        help="sample gap summary JSON path",
    )
    parser.add_argument(
        "--consent-freeze-snapshot",
        default="docs/handoff/sheetbook_consent_freeze_snapshot_latest.json",
        help="consent freeze snapshot JSON path",
    )
    parser.add_argument(
        "--output",
        default="",
        help="markdown output path (default: docs/runbooks/logs/SHEETBOOK_OPS_INDEX_<YYYY-MM-DD>.md)",
    )
    args = parser.parse_args()

    root = _repo_root()
    record_date = args.record_date.strip() or date.today().isoformat()
    output_path = _resolve_path(
        root,
        args.output,
        default_rel_path=f"docs/runbooks/logs/SHEETBOOK_OPS_INDEX_{record_date}.md",
    )
    daily_start = _load_json(_resolve_path(root, args.daily_start, default_rel_path=args.daily_start))
    readiness = _load_json(_resolve_path(root, args.readiness, default_rel_path=args.readiness))
    decision = _load_json(_resolve_path(root, args.decision, default_rel_path=args.decision))
    archive_snapshot = _load_json(
        _resolve_path(root, args.archive_snapshot, default_rel_path=args.archive_snapshot)
    )
    sample_gap_summary = _load_json(
        _resolve_path(root, args.sample_gap_summary, default_rel_path=args.sample_gap_summary)
    )
    consent_freeze_snapshot = _load_json(
        _resolve_path(
            root,
            args.consent_freeze_snapshot,
            default_rel_path=args.consent_freeze_snapshot,
        )
    )

    summary = _build_summary(
        readiness=readiness,
        decision=decision,
        daily_start=daily_start,
        archive_snapshot=archive_snapshot,
        sample_gap_summary=sample_gap_summary,
        consent_freeze_snapshot=consent_freeze_snapshot,
    )
    report_paths = {
        "daily_start": str(daily_start.get("md_output") or root / f"docs/runbooks/logs/SHEETBOOK_DAILY_START_{record_date}.md"),
        "release_signoff": str(root / f"docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_{record_date}.md"),
        "pilot_log": str(root / f"docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_{record_date}.md"),
        "archive_bulk": str(archive_snapshot.get("md_output") or root / f"docs/runbooks/logs/SHEETBOOK_ARCHIVE_BULK_{record_date}.md"),
        "sample_gap": str(sample_gap_summary.get("md_output") or root / f"docs/runbooks/logs/SHEETBOOK_SAMPLE_GAP_{record_date}.md"),
        "consent_freeze": str(
            consent_freeze_snapshot.get("md_output")
            or root / f"docs/runbooks/logs/SHEETBOOK_CONSENT_FREEZE_{record_date}.md"
        ),
        "ops_index": str(output_path),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _build_markdown(
            record_date=record_date,
            summary=summary,
            report_paths=report_paths,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "record_date": record_date,
                "overall": summary.get("overall"),
                "decision": summary.get("decision"),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
