import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


SEED_TAG = "run_sheetbook_seed_metric_samples"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _setup_django() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _to_nonnegative_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return parsed if parsed >= 0 else int(default)


def _ensure_seed_user(*, username: str, email: str):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    defaults: dict[str, Any] = {}
    if email:
        defaults["email"] = email
    user, _ = User.objects.get_or_create(username=username, defaults=defaults)
    if email and user.email != email:
        user.email = email
        user.save(update_fields=["email"])
    return user


def _seed_metric_events(
    *,
    user,
    home_count: int,
    create_count: int,
    action_count: int,
    archive_event_count: int,
) -> dict[str, int]:
    from sheetbook.models import SheetbookMetricEvent

    home_count = _to_nonnegative_int(home_count, default=0)
    create_count = _to_nonnegative_int(create_count, default=0)
    action_count = _to_nonnegative_int(action_count, default=0)
    archive_event_count = _to_nonnegative_int(archive_event_count, default=0)

    created = {
        "workspace_home_opened": 0,
        "sheetbook_created": 0,
        "action_execute_requested": 0,
        "sheetbook_archive_bulk_updated": 0,
    }

    for _ in range(home_count):
        SheetbookMetricEvent.objects.create(
            event_name="workspace_home_opened",
            user=user,
            metadata={
                "entry_source": "workspace_home_seed",
                "seeded_by": SEED_TAG,
                "seed_kind": "home",
            },
        )
        created["workspace_home_opened"] += 1

    for _ in range(create_count):
        SheetbookMetricEvent.objects.create(
            event_name="sheetbook_created",
            user=user,
            metadata={
                "entry_source": "workspace_home_seed",
                "seeded_by": SEED_TAG,
                "seed_kind": "create",
            },
        )
        created["sheetbook_created"] += 1

    for _ in range(action_count):
        SheetbookMetricEvent.objects.create(
            event_name="action_execute_requested",
            user=user,
            metadata={
                "entry_source": "workspace_home_seed",
                "seeded_by": SEED_TAG,
                "seed_kind": "action",
            },
        )
        created["action_execute_requested"] += 1

    for idx in range(archive_event_count):
        archive_action = "archive" if idx % 2 == 0 else "unarchive"
        SheetbookMetricEvent.objects.create(
            event_name="sheetbook_archive_bulk_updated",
            user=user,
            metadata={
                "selected_count": 10,
                "matched_count": 10,
                "changed_count": 8,
                "unchanged_count": 1,
                "ignored_count": 1,
                "archive_action": archive_action,
                "seeded_by": SEED_TAG,
                "seed_kind": "archive_bulk",
            },
        )
        created["sheetbook_archive_bulk_updated"] += 1

    return created


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seed local sheetbook metric events for pilot/archive snapshot rehearsal. "
            "This command is intended for local testing only."
        )
    )
    parser.add_argument("--username", default="sheetbook_seed_operator", help="seed user username")
    parser.add_argument(
        "--email",
        default="sheetbook-seed-operator@example.com",
        help="seed user email",
    )
    parser.add_argument("--home-count", type=int, default=5, help="workspace_home_opened 생성 건수")
    parser.add_argument("--create-count", type=int, default=5, help="sheetbook_created 생성 건수")
    parser.add_argument(
        "--action-count",
        type=int,
        default=3,
        help="action_execute_requested 생성 건수",
    )
    parser.add_argument(
        "--archive-event-count",
        type=int,
        default=5,
        help="sheetbook_archive_bulk_updated 생성 건수",
    )
    parser.add_argument(
        "--clear-seeded",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="기존 seed 이벤트(SEED_TAG)를 먼저 삭제할지 여부. 기본 False",
    )
    args = parser.parse_args()

    _setup_django()

    from sheetbook.models import SheetbookMetricEvent

    user = _ensure_seed_user(username=str(args.username or "").strip(), email=str(args.email or "").strip())

    removed = 0
    if bool(args.clear_seeded):
        removed, _ = SheetbookMetricEvent.objects.filter(metadata__seeded_by=SEED_TAG).delete()

    created = _seed_metric_events(
        user=user,
        home_count=args.home_count,
        create_count=args.create_count,
        action_count=args.action_count,
        archive_event_count=args.archive_event_count,
    )

    result = {
        "seed_tag": SEED_TAG,
        "removed_seed_events": int(removed),
        "seed_user_id": int(user.id),
        "seed_username": str(user.username),
        "created": created,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
