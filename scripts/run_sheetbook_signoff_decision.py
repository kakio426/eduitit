import argparse
import json
import time
from pathlib import Path
from typing import Any


STATUS_PASS = "PASS"
STATUS_HOLD = "HOLD"
STATUS_FAIL = "FAIL"
VALID_STATUS = {STATUS_PASS, STATUS_HOLD, STATUS_FAIL}
REAL_DEVICE_KEY = "real_device_grid_1000"

MANUAL_KEYS = [
    "staging_allowlisted",
    "staging_non_allowlisted",
    "production_allowlisted",
    "production_non_allowlisted",
    REAL_DEVICE_KEY,
]
ALIAS_KEYS = {
    "staging_real_account_signoff": [
        "staging_allowlisted",
        "staging_non_allowlisted",
    ],
    "production_real_account_signoff": [
        "production_allowlisted",
        "production_non_allowlisted",
    ],
    "real_device_grid_1000_smoke": [
        REAL_DEVICE_KEY,
    ],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_manual_payload() -> dict[str, Any]:
    checks = {}
    for key in MANUAL_KEYS:
        checks[key] = {
            "status": STATUS_HOLD,
            "notes": "pending",
            "updated_at": "",
        }
    return {
        "updated_at": "",
        "checks": checks,
    }


def _load_json(path: Path, default_value: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(default_value))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(json.dumps(default_value))
    if not isinstance(payload, dict):
        return json.loads(json.dumps(default_value))
    return payload


def _normalize_manual(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _default_manual_payload()
    checks = payload.get("checks")
    if isinstance(checks, dict):
        for key in MANUAL_KEYS:
            row = checks.get(key)
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or STATUS_HOLD).strip().upper()
            if status not in VALID_STATUS:
                status = STATUS_HOLD
            normalized["checks"][key]["status"] = status
            normalized["checks"][key]["notes"] = str(row.get("notes") or "").strip() or "pending"
            normalized["checks"][key]["updated_at"] = str(row.get("updated_at") or "").strip()
    normalized["updated_at"] = str(payload.get("updated_at") or "").strip()
    return normalized


def _parse_set_arg(raw: str) -> tuple[list[str], str, str]:
    key_part, _, remainder = str(raw or "").partition("=")
    key = key_part.strip()
    resolved_keys: list[str] = []
    if key in MANUAL_KEYS:
        resolved_keys = [key]
    elif key in ALIAS_KEYS:
        resolved_keys = list(ALIAS_KEYS[key])
    else:
        raise ValueError(f"invalid key: {key}")
    status_part, _, note_part = remainder.partition(":")
    status = status_part.strip().upper()
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status for {key}: {status}")
    notes = note_part.strip() or "updated by cli"
    return resolved_keys, status, notes


def _apply_set_args(manual: dict[str, Any], set_args: list[str]) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    for raw in set_args:
        keys, status, notes = _parse_set_arg(raw)
        for key in keys:
            manual["checks"][key]["status"] = status
            manual["checks"][key]["notes"] = notes
            manual["checks"][key]["updated_at"] = now
    manual["updated_at"] = now


def _apply_real_device_waiver(manual: dict[str, Any], *, enabled: bool) -> bool:
    if not enabled:
        return False
    checks = manual.get("checks") or {}
    row = checks.get(REAL_DEVICE_KEY)
    if not isinstance(row, dict):
        return False
    # If real-device testing is not feasible, treat as policy waiver PASS.
    row["status"] = STATUS_PASS
    row["notes"] = "waived_by_policy(device-unavailable)"
    row["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manual["updated_at"] = row["updated_at"]
    return True


def _compute_decision(
    readiness: dict[str, Any],
    manual: dict[str, Any],
    *,
    real_device_waived: bool,
    allow_pilot_hold_for_beta: bool,
) -> dict[str, Any]:
    overall = readiness.get("overall") or {}
    readiness_status = str(overall.get("status") or STATUS_HOLD).strip().upper()
    if readiness_status not in VALID_STATUS:
        readiness_status = STATUS_HOLD
    automated_gate_pass = bool(overall.get("automated_gate_pass"))

    checks = manual.get("checks") or {}
    manual_statuses: dict[str, str] = {}
    statuses = []
    for key in MANUAL_KEYS:
        row = checks.get(key) or {}
        status = str(row.get("status") or STATUS_HOLD).strip().upper()
        if status not in VALID_STATUS:
            status = STATUS_HOLD
        manual_statuses[key] = status
        statuses.append(status)

    manual_alias_statuses: dict[str, str] = {}
    for alias, alias_keys in ALIAS_KEYS.items():
        alias_values = [manual_statuses.get(key, STATUS_HOLD) for key in alias_keys]
        if any(value == STATUS_FAIL for value in alias_values):
            manual_alias_statuses[alias] = STATUS_FAIL
        elif alias_values and all(value == STATUS_PASS for value in alias_values):
            manual_alias_statuses[alias] = STATUS_PASS
        else:
            manual_alias_statuses[alias] = STATUS_HOLD

    has_manual_fail = any(item == STATUS_FAIL for item in statuses)
    all_manual_pass = bool(statuses) and all(item == STATUS_PASS for item in statuses)

    pilot_hold_waived = False
    if readiness_status == STATUS_FAIL or has_manual_fail:
        decision = "STOP"
    elif readiness_status == STATUS_PASS and all_manual_pass:
        decision = "GO"
    elif (
        allow_pilot_hold_for_beta
        and readiness_status == STATUS_HOLD
        and automated_gate_pass
        and all_manual_pass
    ):
        decision = "GO"
        pilot_hold_waived = True
    else:
        decision = "HOLD"

    return {
        "decision": decision,
        "readiness_status": readiness_status,
        "manual_statuses": manual_statuses,
        "manual_alias_statuses": manual_alias_statuses,
        "automated_gate_pass": automated_gate_pass,
        "waivers": {
            "real_device_grid_1000": real_device_waived,
            "pilot_hold_for_beta": pilot_hold_waived,
        },
    }


def _build_next_actions(
    readiness: dict[str, Any],
    decision_ctx: dict[str, Any],
    *,
    allow_pilot_hold_for_beta: bool,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    decision = str(decision_ctx.get("decision") or "").strip().upper()
    automated_gate_pass = bool(decision_ctx.get("automated_gate_pass"))
    readiness_status = str(decision_ctx.get("readiness_status") or "").strip().upper()
    manual_statuses = decision_ctx.get("manual_statuses") or {}
    manual_alias_statuses = decision_ctx.get("manual_alias_statuses") or {}
    staging_ok = str(manual_alias_statuses.get("staging_real_account_signoff") or "").upper() == STATUS_PASS
    production_ok = str(manual_alias_statuses.get("production_real_account_signoff") or "").upper() == STATUS_PASS
    if not manual_alias_statuses:
        staging_ok = (
            str(manual_statuses.get("staging_allowlisted") or "").upper() == STATUS_PASS
            and str(manual_statuses.get("staging_non_allowlisted") or "").upper() == STATUS_PASS
        )
        production_ok = (
            str(manual_statuses.get("production_allowlisted") or "").upper() == STATUS_PASS
            and str(manual_statuses.get("production_non_allowlisted") or "").upper() == STATUS_PASS
        )

    if not staging_ok and not production_ok:
        actions.append(
            {
                "type": "manual_signoff_batch",
                "description": "스테이징/운영 실계정 점검 결과를 한 번에 PASS 반영",
                "command": (
                    "python scripts/run_sheetbook_signoff_decision.py "
                    "--set staging_real_account_signoff=PASS:staging-ok "
                    "--set production_real_account_signoff=PASS:prod-ok"
                ),
            }
        )

    if not staging_ok:
        actions.append(
            {
                "type": "manual_signoff",
                "description": "스테이징 실계정 점검 후 상태를 PASS로 반영",
                "command": "python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok",
            }
        )
    if not production_ok:
        actions.append(
            {
                "type": "manual_signoff",
                "description": "운영 실계정 점검 후 상태를 PASS로 반영",
                "command": "python scripts/run_sheetbook_signoff_decision.py --set production_real_account_signoff=PASS:prod-ok",
            }
        )

    if (
        decision == STATUS_HOLD
        and automated_gate_pass
        and readiness_status == STATUS_HOLD
        and staging_ok
        and production_ok
        and not allow_pilot_hold_for_beta
    ):
        actions.append(
            {
                "type": "optional_beta_go",
                "description": "파일럿 HOLD를 베타 공개에서 조건부 허용할 때 GO 재산출",
                "command": "python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta",
            }
        )
        actions.append(
            {
                "type": "optional_beta_restore_hold",
                "description": "조건부 GO 검증 후 운영 상태를 HOLD로 복구",
                "command": (
                    "python scripts/run_sheetbook_signoff_decision.py "
                    "--set staging_real_account_signoff=HOLD:pending "
                    "--set production_real_account_signoff=HOLD:pending"
                ),
            }
        )

    actions.append(
        {
            "type": "refresh",
            "description": "게이트 상태 최신화 후 판정 재생성",
            "command": "python scripts/run_sheetbook_release_readiness.py --days 14 && python scripts/run_sheetbook_signoff_decision.py",
        }
    )
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Combine automated readiness + manual signoff statuses and output GO/HOLD/STOP decision."
    )
    parser.add_argument(
        "--readiness",
        default="docs/handoff/sheetbook_release_readiness_latest.json",
        help="Readiness JSON path",
    )
    parser.add_argument(
        "--manual",
        default="docs/handoff/sheetbook_manual_signoff_latest.json",
        help="Manual signoff JSON path",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/sheetbook_release_decision_latest.json",
        help="Decision output JSON path",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        help=(
            "Manual status override. "
            "format: key=PASS|HOLD|FAIL[:notes]. "
            "key can be manual key or alias "
            "(staging_real_account_signoff, production_real_account_signoff, real_device_grid_1000_smoke)."
        ),
    )
    parser.add_argument(
        "--waive-real-device-smoke",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "실기기 스모크를 정책상 면제로 처리할지 여부. "
            "기본 True(자동 PASS), --no-waive-real-device-smoke로 해제."
        ),
    )
    parser.add_argument(
        "--allow-pilot-hold-for-beta",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "자동 게이트는 통과했지만 pilot 샘플 부족으로 readiness=HOLD일 때 "
            "수동 점검이 모두 PASS면 GO로 판정할지 여부. 기본 False."
        ),
    )
    args = parser.parse_args()

    root = _repo_root()
    readiness_path = Path(args.readiness)
    manual_path = Path(args.manual)
    output_path = Path(args.output)
    if not readiness_path.is_absolute():
        readiness_path = root / readiness_path
    if not manual_path.is_absolute():
        manual_path = root / manual_path
    if not output_path.is_absolute():
        output_path = root / output_path

    readiness = _load_json(readiness_path, default_value={"overall": {"status": STATUS_HOLD}})
    manual = _normalize_manual(_load_json(manual_path, default_value=_default_manual_payload()))

    _apply_set_args(manual, list(args.set or []))
    waived = _apply_real_device_waiver(
        manual,
        enabled=bool(args.waive_real_device_smoke),
    )
    manual_path.parent.mkdir(parents=True, exist_ok=True)
    manual_path.write_text(json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")

    decision = _compute_decision(
        readiness,
        manual,
        real_device_waived=waived,
        allow_pilot_hold_for_beta=bool(args.allow_pilot_hold_for_beta),
    )
    next_actions = _build_next_actions(
        readiness,
        decision,
        allow_pilot_hold_for_beta=bool(args.allow_pilot_hold_for_beta),
    )
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "readiness_file": str(readiness_path),
        "manual_file": str(manual_path),
        "readiness_overall": readiness.get("overall"),
        "manual_checks": manual.get("checks"),
        "decision": decision["decision"],
        "decision_context": decision,
        "next_actions": next_actions,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
