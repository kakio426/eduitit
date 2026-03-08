import argparse
import json
import subprocess
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


def _normalize_due_date(value: Any) -> tuple[str, bool]:
    raw = str(value or "").strip()
    fallback = date.today().isoformat()
    if not raw:
        return fallback, False
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return fallback, True
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
    due_date: str,
    allow_pilot_hold_for_beta: bool,
) -> list[str]:
    cmd = [
        "python",
        "scripts/run_sheetbook_daily_start_bundle.py",
        "--days",
        str(int(days)),
        "--due-date",
        str(due_date),
    ]
    if allow_pilot_hold_for_beta:
        cmd.append("--allow-pilot-hold-for-beta")
    return cmd


def _build_command_plan(
    *,
    days: int,
    due_date: str,
    allow_pilot_hold_for_beta: bool,
    grid_port: int,
    with_check: bool,
) -> list[list[str]]:
    plan: list[list[str]] = [
        ["python", "scripts/run_sheetbook_allowlist_smoke.py"],
        ["python", "scripts/run_sheetbook_consent_smoke.py"],
        ["python", "scripts/run_sheetbook_grid_smoke.py", "--port", str(int(grid_port))],
        ["python", "scripts/run_sheetbook_calendar_embed_smoke.py", "--port", str(int(grid_port))],
        _build_bundle_command(
            days=int(days),
            due_date=str(due_date),
            allow_pilot_hold_for_beta=bool(allow_pilot_hold_for_beta),
        ),
        [
            "python",
            "scripts/run_sheetbook_sample_gap_summary.py",
            "--days",
            str(int(days)),
            "--due-date",
            str(due_date),
        ],
    ]
    if with_check:
        plan.append(["python", "manage.py", "check"])
    return plan


def _build_snapshot_summary(root: Path) -> dict[str, Any]:
    allowlist = _load_json(root / "docs/handoff/smoke_sheetbook_allowlist_latest.json")
    consent = _load_json(root / "docs/handoff/smoke_sheetbook_consent_recipients_latest.json")
    grid = _load_json(root / "docs/handoff/smoke_sheetbook_grid_1000_latest.json")
    calendar_embed = _load_json(root / "docs/handoff/smoke_sheetbook_calendar_embed_latest.json")
    daily = _load_json(root / "docs/handoff/sheetbook_daily_start_bundle_latest.json")
    gap = _load_json(root / "docs/handoff/sheetbook_sample_gap_summary_latest.json")
    readiness = _load_json(root / "docs/handoff/sheetbook_release_readiness_latest.json")
    decision = _load_json(root / "docs/handoff/sheetbook_release_decision_latest.json")

    allowlist_pass = bool((allowlist.get("evaluation") or {}).get("pass"))
    consent_pass = bool((consent.get("evaluation") or {}).get("pass"))
    grid_pass = bool((grid.get("evaluation") or {}).get("pass"))
    calendar_embed_pass = bool((calendar_embed.get("evaluation") or {}).get("pass"))
    daily_overall = str(daily.get("overall") or "").upper()
    daily_decision = str(daily.get("decision") or "").upper()
    daily_readiness = str(daily.get("readiness_status") or "").upper()
    gap_ready = bool((gap.get("overall") or {}).get("ready"))
    readiness_status = str((readiness.get("overall") or {}).get("status") or "").upper()
    release_decision = str(decision.get("decision") or "").upper()

    return {
        "allowlist": {
            "started_at": str(allowlist.get("started_at") or ""),
            "pass": allowlist_pass,
        },
        "consent": {
            "started_at": str(consent.get("started_at") or ""),
            "pass": consent_pass,
        },
        "grid": {
            "started_at": str(grid.get("started_at") or ""),
            "pass": grid_pass,
            "has_warnings": bool((grid.get("evaluation") or {}).get("has_warnings")),
            "desktop_warnings": list((grid.get("evaluation") or {}).get("desktop_warnings") or []),
            "tablet_warnings": list((grid.get("evaluation") or {}).get("tablet_warnings") or []),
        },
        "calendar_embed": {
            "started_at": str(calendar_embed.get("started_at") or ""),
            "pass": calendar_embed_pass,
            "desktop_pass": bool((calendar_embed.get("evaluation") or {}).get("desktop_pass")),
            "tablet_pass": bool((calendar_embed.get("evaluation") or {}).get("tablet_pass")),
            "mobile_pass": bool((calendar_embed.get("evaluation") or {}).get("mobile_pass")),
        },
        "daily": {
            "overall": daily_overall,
            "decision": daily_decision,
            "readiness_status": daily_readiness,
        },
        "release": {
            "readiness_status": readiness_status,
            "decision": release_decision,
        },
        "gap": {
            "ready": gap_ready,
            "blockers": list((gap.get("overall") or {}).get("blockers") or []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run sheetbook smoke sync cycle (allowlist/consent/grid/calendar + bundle/gap/check)."
    )
    parser.add_argument("--days", type=int, default=14, help="집계 기간(일). 기본 14")
    parser.add_argument(
        "--due-date",
        default="",
        help="bundle/gap due-date (YYYY-MM-DD). 기본 오늘 날짜",
    )
    parser.add_argument("--grid-port", type=int, default=8015, help="grid smoke runserver port")
    parser.add_argument(
        "--allow-pilot-hold-for-beta",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="daily bundle 실행 시 allow-pilot-hold-for-beta 포함 여부 (기본 True)",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="마지막 `python manage.py check` 실행 생략",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/smoke_sheetbook_ops_cycle_latest.json",
        help="사이클 실행 요약 JSON 경로",
    )
    args = parser.parse_args()

    root = _repo_root()
    days = max(1, int(args.days or 14))
    due_date, used_due_date_fallback = _normalize_due_date(args.due_date)
    grid_port = max(1, int(args.grid_port or 8015))
    with_check = not bool(args.skip_check)

    command_plan = _build_command_plan(
        days=days,
        due_date=due_date,
        allow_pilot_hold_for_beta=bool(args.allow_pilot_hold_for_beta),
        grid_port=grid_port,
        with_check=with_check,
    )

    command_results: list[dict[str, Any]] = []
    failed_index: int | None = None
    failure_code = 0
    for idx, cmd in enumerate(command_plan):
        result = _run_command(root, cmd)
        command_results.append(result)
        if not bool(result.get("ok")):
            failed_index = idx
            failure_code = int(result.get("returncode") or 1)
            break

    snapshot = _build_snapshot_summary(root)
    pass_flags = [
        bool((snapshot.get("allowlist") or {}).get("pass")),
        bool((snapshot.get("consent") or {}).get("pass")),
        bool((snapshot.get("grid") or {}).get("pass")),
        bool((snapshot.get("calendar_embed") or {}).get("pass")),
        str((snapshot.get("daily") or {}).get("overall") or "").upper() == "GO",
        str((snapshot.get("daily") or {}).get("decision") or "").upper() == "GO",
        str((snapshot.get("daily") or {}).get("readiness_status") or "").upper() == "PASS",
        bool((snapshot.get("gap") or {}).get("ready")),
    ]
    status = "PASS" if all(pass_flags) else "HOLD"
    if failed_index is not None:
        status = "FAIL"

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "days": int(days),
        "due_date": due_date,
        "used_due_date_fallback": bool(used_due_date_fallback),
        "allow_pilot_hold_for_beta": bool(args.allow_pilot_hold_for_beta),
        "grid_port": int(grid_port),
        "with_check": bool(with_check),
        "success": failed_index is None,
        "failed_index": failed_index,
        "status": status,
        "commands": command_results,
        "snapshot": snapshot,
    }

    output_path = Path(str(args.output or "").strip() or "docs/handoff/smoke_sheetbook_ops_cycle_latest.json")
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "success": summary.get("success"),
                "failed_index": summary.get("failed_index"),
                "output": str(output_path),
                "snapshot": {
                    "allowlist_pass": (snapshot.get("allowlist") or {}).get("pass"),
                    "consent_pass": (snapshot.get("consent") or {}).get("pass"),
                    "grid_pass": (snapshot.get("grid") or {}).get("pass"),
                    "daily_overall": (snapshot.get("daily") or {}).get("overall"),
                    "daily_readiness_status": (snapshot.get("daily") or {}).get("readiness_status"),
                    "gap_ready": (snapshot.get("gap") or {}).get("ready"),
                },
            },
            ensure_ascii=False,
        )
    )

    if failed_index is None:
        return 0
    return failure_code if failure_code != 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
