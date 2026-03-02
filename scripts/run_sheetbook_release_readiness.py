import argparse
import json
import os
import sys
import time
from datetime import timedelta
from io import StringIO
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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "pass": False, "detail": f"missing: {path}"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"exists": True, "pass": False, "detail": f"invalid json: {exc}"}

    evaluation = payload.get("evaluation") or {}
    passed = bool(evaluation.get("pass"))
    return {
        "exists": True,
        "pass": passed,
        "started_at": payload.get("started_at"),
        "evaluation": evaluation,
    }


def _run_preflight_case(
    *,
    enabled: bool,
    beta_usernames: list[str],
    beta_emails: list[str],
    recommend_days: int,
) -> dict[str, Any]:
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from django.test import override_settings

    stdout = StringIO()
    stderr = StringIO()
    started = time.perf_counter()
    with override_settings(
        SHEETBOOK_ENABLED=enabled,
        SHEETBOOK_BETA_USERNAMES=beta_usernames,
        SHEETBOOK_BETA_EMAILS=beta_emails,
        SHEETBOOK_BETA_USER_IDS=[],
    ):
        try:
            call_command(
                "check_sheetbook_preflight",
                "--strict",
                "--recommend-days",
                str(recommend_days),
                stdout=stdout,
                stderr=stderr,
            )
            ok = True
        except CommandError:
            ok = False

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
    merged = "\n".join(
        [line for line in [stdout.getvalue().strip(), stderr.getvalue().strip()] if line]
    ).strip()
    tail_lines = [line for line in merged.splitlines() if line][-15:]
    return {
        "pass": ok,
        "elapsed_ms": elapsed_ms,
        "log_tail": tail_lines,
    }


def _pilot_snapshot(days: int) -> dict[str, Any]:
    from django.conf import settings
    from django.utils import timezone

    from sheetbook.models import SheetbookMetricEvent

    since = timezone.now() - timedelta(days=days)
    event_qs = SheetbookMetricEvent.objects.filter(created_at__gte=since)
    home_count = event_qs.filter(event_name="workspace_home_opened").count()

    create_count = 0
    action_count = 0
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
            create_count += 1
        elif row["event_name"] == "action_execute_requested":
            action_count += 1

    min_home = int(getattr(settings, "SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE", 5) or 5)
    min_create = int(getattr(settings, "SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE", 5) or 5)
    enough_home = home_count >= min_home
    enough_create = create_count >= min_create
    ready = enough_home and enough_create

    home_to_create_rate = round((create_count / home_count) * 100, 1) if home_count else 0.0
    create_to_action_rate = round((action_count / create_count) * 100, 1) if create_count else 0.0

    return {
        "days": days,
        "ready_for_recalibration": ready,
        "counts": {
            "workspace_home_opened": home_count,
            "home_source_sheetbook_created": create_count,
            "home_source_action_execute_requested": action_count,
        },
        "rates": {
            "home_to_create_pct": home_to_create_rate,
            "create_to_action_pct": create_to_action_rate,
        },
        "minimum_samples": {
            "workspace_home_opened": min_home,
            "home_source_sheetbook_created": min_create,
        },
        "status": "PASS" if ready else "HOLD",
    }


def _build_overall(summary: dict[str, Any], *, waive_real_device_smoke: bool) -> dict[str, Any]:
    preflight = summary["preflight"]
    smokes = summary["smokes"]
    pilot = summary["pilot"]

    blocking_reasons: list[str] = []
    advisory_reasons: list[str] = []
    if not preflight["beta_strict"]["pass"]:
        blocking_reasons.append("preflight_beta_strict_failed")
    if not preflight["global_strict"]["pass"]:
        blocking_reasons.append("preflight_global_strict_failed")
    if not smokes["grid_1000"]["pass"]:
        blocking_reasons.append("smoke_grid_1000_failed")
    if not smokes["consent_recipients"]["pass"]:
        blocking_reasons.append("smoke_consent_recipients_failed")
    if smokes["consent_recipients_300"]["exists"] and not smokes["consent_recipients_300"]["pass"]:
        blocking_reasons.append("smoke_consent_recipients_300_failed")
    if not smokes["consent_recipients_300"]["exists"]:
        advisory_reasons.append("smoke_consent_recipients_300_missing")
    if not smokes["allowlist_access"]["pass"]:
        blocking_reasons.append("smoke_allowlist_access_failed")

    manual_pending = [
        "staging_real_account_signoff",
        "production_real_account_signoff",
    ]
    waived_manual_checks: list[str] = []
    if waive_real_device_smoke:
        waived_manual_checks.append("real_device_grid_1000_smoke")
    else:
        manual_pending.append("real_device_grid_1000_smoke")

    if blocking_reasons:
        status = "FAIL"
    elif pilot["status"] == "HOLD":
        status = "HOLD"
    else:
        status = "PASS"

    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "advisory_reasons": advisory_reasons,
        "manual_pending": manual_pending,
        "waived_manual_checks": waived_manual_checks,
        "automated_gate_pass": len(blocking_reasons) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate sheetbook release readiness from strict checks and smoke outputs."
    )
    parser.add_argument("--days", type=int, default=14, help="파일럿/권장치 집계 기간(일). 기본 14")
    parser.add_argument(
        "--allow-username",
        default="sheetbook_smoke_admin",
        help="베타 strict preflight 점검에 사용할 allowlist username",
    )
    parser.add_argument(
        "--allow-email",
        default="sheetbook-smoke-admin@example.com",
        help="베타 strict preflight 점검에 사용할 allowlist email",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/sheetbook_release_readiness_latest.json",
        help="JSON output path (repo-relative or absolute).",
    )
    parser.add_argument(
        "--waive-real-device-smoke",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "실기기 스모크를 readiness 수동 대기 항목에서 면제할지 여부. "
            "기본 True, --no-waive-real-device-smoke로 해제."
        ),
    )
    args = parser.parse_args()

    _setup_django()
    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    preflight = {
        "beta_strict": _run_preflight_case(
            enabled=False,
            beta_usernames=[args.allow_username],
            beta_emails=[args.allow_email],
            recommend_days=int(args.days),
        ),
        "global_strict": _run_preflight_case(
            enabled=True,
            beta_usernames=[],
            beta_emails=[],
            recommend_days=int(args.days),
        ),
    }

    smokes = {
        "grid_1000": _load_json(root / "docs/handoff/smoke_sheetbook_grid_1000_latest.json"),
        "consent_recipients": _load_json(
            root / "docs/handoff/smoke_sheetbook_consent_recipients_latest.json"
        ),
        "consent_recipients_300": _load_json(
            root / "docs/handoff/smoke_sheetbook_consent_recipients_300_latest.json"
        ),
        "allowlist_access": _load_json(root / "docs/handoff/smoke_sheetbook_allowlist_latest.json"),
    }

    pilot = _pilot_snapshot(days=int(args.days))

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "days": int(args.days),
        "preflight": preflight,
        "smokes": smokes,
        "pilot": pilot,
    }
    summary["overall"] = _build_overall(
        summary,
        waive_real_device_smoke=bool(args.waive_real_device_smoke),
    )

    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))

    if summary["overall"]["status"] == "FAIL":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
