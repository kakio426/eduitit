import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


VALID_STATUS = {"PASS", "HOLD", "FAIL"}
MANUAL_ROW_SPECS = [
    ("staging_allowlisted", "staging_real_account_signoff", "staging", "allowlisted"),
    ("staging_non_allowlisted", "staging_real_account_signoff", "staging", "non_allowlisted"),
    ("production_allowlisted", "production_real_account_signoff", "production", "allowlisted"),
    ("production_non_allowlisted", "production_real_account_signoff", "production", "non_allowlisted"),
    ("real_device_grid_1000", "real_device_grid_1000_smoke", "real-device", "teacher"),
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(root: Path, raw: str) -> Path:
    path = Path(raw)
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


def _format_items(items: list[Any]) -> str:
    normalized = [str(item).strip() for item in items if str(item).strip()]
    if not normalized:
        return "(없음)"
    return ", ".join(normalized)


def _normalize_manual_row(manual_checks: dict[str, Any], key: str) -> tuple[str, str]:
    row = manual_checks.get(key) or {}
    status = str(row.get("status") or "HOLD").strip().upper()
    if status not in VALID_STATUS:
        status = "HOLD"
    notes = str(row.get("notes") or "").strip() or "pending"
    return status, notes


def _derive_effective_manual_pending(
    *,
    manual_pending_raw: list[Any],
    alias_statuses: dict[str, Any],
) -> list[str]:
    effective: list[str] = []
    seen: set[str] = set()
    for item in manual_pending_raw:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        status = str(alias_statuses.get(key) or "").strip().upper()
        if status == "PASS":
            continue
        effective.append(key)

    for key in ("staging_real_account_signoff", "production_real_account_signoff"):
        status = str(alias_statuses.get(key) or "").strip().upper()
        if status and status != "PASS" and key not in seen and key not in effective:
            effective.append(key)
    return effective


def _build_manual_rows(manual_checks: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, check_id, env, account_type in MANUAL_ROW_SPECS:
        status, notes = _normalize_manual_row(manual_checks, key)
        lines.append(f"| {check_id} | {env} | {account_type} | {status} | {notes} |")
    return "\n".join(lines)


def _build_next_actions_lines(next_actions: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for action in next_actions:
        if not isinstance(action, dict):
            continue
        description = str(action.get("description") or "").strip()
        command = str(action.get("command") or "").strip()
        if description and command:
            lines.append(f"- {description}: `{command}`")
        elif command:
            lines.append(f"- `{command}`")
        elif description:
            lines.append(f"- {description}")
    if not lines:
        lines.append("- (없음)")
    return "\n".join(lines)


def _build_alias_lines(alias_statuses: dict[str, Any]) -> str:
    if not alias_statuses:
        return "- (없음)"
    lines: list[str] = []
    for alias in sorted(alias_statuses.keys()):
        lines.append(f"- `{alias}`: `{str(alias_statuses.get(alias) or 'HOLD').upper()}`")
    return "\n".join(lines)


def _build_markdown(
    *,
    record_date: date,
    author: str,
    readiness: dict[str, Any],
    manual: dict[str, Any],
    decision: dict[str, Any],
    owner: str,
    next_action: str,
    due_date: str,
) -> str:
    readiness_overall = readiness.get("overall") or {}
    manual_checks = manual.get("checks") or decision.get("manual_checks") or {}
    decision_context = decision.get("decision_context") or {}
    manual_alias_statuses = decision_context.get("manual_alias_statuses") or {}
    decision_value = str(decision.get("decision") or "HOLD").strip().upper()
    if decision_value not in {"GO", "HOLD", "STOP"}:
        decision_value = "HOLD"

    blocking_reasons = _format_items(readiness_overall.get("blocking_reasons") or [])
    manual_pending_raw_list = list(readiness_overall.get("manual_pending") or [])
    manual_pending_effective_list = _derive_effective_manual_pending(
        manual_pending_raw=manual_pending_raw_list,
        alias_statuses=manual_alias_statuses,
    )
    manual_pending = _format_items(manual_pending_effective_list)
    manual_pending_raw = _format_items(manual_pending_raw_list)
    waived_manual_checks = _format_items(readiness_overall.get("waived_manual_checks") or [])
    next_actions = _build_next_actions_lines(decision.get("next_actions") or [])
    alias_lines = _build_alias_lines(manual_alias_statuses)
    manual_rows = _build_manual_rows(manual_checks)

    rendered_author = author or "-"
    rendered_owner = owner or "-"
    rendered_next_action = next_action or "-"
    rendered_due_date = due_date or "-"

    return f"""# Sheetbook Release Signoff ({record_date.isoformat()})

작성일: {record_date.isoformat()}  
작성자: {rendered_author}

## 1) 자동 게이트 스냅샷

- 실행 명령:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
- 최종 판정 명령:
  - `python scripts/run_sheetbook_signoff_decision.py`
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:ok --set production_real_account_signoff=PASS:ok --set real_device_grid_1000_smoke=PASS:ok`
  - (실기기 면제 해제 시) `python scripts/run_sheetbook_signoff_decision.py --no-waive-real-device-smoke`
  - (베타 조건부 GO) `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta --set staging_real_account_signoff=PASS:ok --set production_real_account_signoff=PASS:ok`
  - (조건부 GO 검증 후 복구) `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`
- 출력 파일:
  - `docs/handoff/sheetbook_release_readiness_latest.json`
  - `docs/handoff/sheetbook_manual_signoff_latest.json`
  - `docs/handoff/sheetbook_release_decision_latest.json`
- `overall.status`: {str(readiness_overall.get("status") or "HOLD").upper()}
- `blocking_reasons`: {blocking_reasons}
- `manual_pending`: {manual_pending}
- `manual_pending_raw(readiness)`: {manual_pending_raw}
- `waived_manual_checks`: {waived_manual_checks}
- `next_actions` (decision json 자동 추천 명령):
{next_actions}
- `decision_context.manual_alias_statuses`:
{alias_lines}

## 2) 수동 게이트 점검

| check_id | env | account_type | result(PASS/HOLD/FAIL) | notes |
|---|---|---|---|---|
{manual_rows}

## 3) 최종 판정

- decision: `{decision_value}`
- owner: {rendered_owner}
- next_action: {rendered_next_action}
- due_date: {rendered_due_date}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate sheetbook release signoff markdown log from latest readiness/manual/decision JSON files."
    )
    parser.add_argument(
        "--readiness",
        default="docs/handoff/sheetbook_release_readiness_latest.json",
        help="readiness JSON path",
    )
    parser.add_argument(
        "--manual",
        default="docs/handoff/sheetbook_manual_signoff_latest.json",
        help="manual signoff JSON path",
    )
    parser.add_argument(
        "--decision",
        default="docs/handoff/sheetbook_release_decision_latest.json",
        help="release decision JSON path",
    )
    parser.add_argument("--date", default="", help="record date (YYYY-MM-DD), default=today")
    parser.add_argument("--author", default="", help="author name for markdown header")
    parser.add_argument("--owner", default="", help="owner value for final decision section")
    parser.add_argument("--next-action", default="", help="next_action value for final decision section")
    parser.add_argument("--due-date", default="", help="due_date value for final decision section")
    parser.add_argument(
        "--output",
        default="",
        help="markdown output path (default: docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_<date>.md)",
    )
    args = parser.parse_args()

    record_date = date.today()
    if args.date:
        record_date = date.fromisoformat(args.date)

    root = _repo_root()
    readiness_path = _resolve_path(root, args.readiness)
    manual_path = _resolve_path(root, args.manual)
    decision_path = _resolve_path(root, args.decision)
    if args.output:
        output_path = _resolve_path(root, args.output)
    else:
        output_path = root / "docs" / "runbooks" / "logs" / f"SHEETBOOK_RELEASE_SIGNOFF_{record_date.isoformat()}.md"

    readiness = _load_json(readiness_path)
    manual = _load_json(manual_path)
    decision = _load_json(decision_path)

    markdown = _build_markdown(
        record_date=record_date,
        author=str(args.author or "").strip(),
        readiness=readiness,
        manual=manual,
        decision=decision,
        owner=str(args.owner or "").strip(),
        next_action=str(args.next_action or "").strip(),
        due_date=str(args.due_date or "").strip(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    result = {
        "record_date": record_date.isoformat(),
        "readiness_input": str(readiness_path),
        "manual_input": str(manual_path),
        "decision_input": str(decision_path),
        "md_output": str(output_path),
        "decision": str((decision.get("decision") or "HOLD")).upper(),
        "readiness_status": str((readiness.get("overall") or {}).get("status") or "HOLD").upper(),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
