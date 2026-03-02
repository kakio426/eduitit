import argparse
import json
from datetime import datetime
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


def _build_sample_gap_summary(
    *,
    generated_at: str,
    readiness: dict[str, Any],
    archive_snapshot: dict[str, Any],
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

    return {
        "generated_at": generated_at,
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
        },
    }


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
    args = parser.parse_args()

    root = _repo_root()
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
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        readiness=readiness,
        archive_snapshot=archive_snapshot,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "overall_ready": (summary.get("overall") or {}).get("ready"),
                "blockers": (summary.get("overall") or {}).get("blockers"),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
