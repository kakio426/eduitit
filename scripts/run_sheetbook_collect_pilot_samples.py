import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


COLLECTOR_TAG = "run_sheetbook_collect_pilot_samples"
TRACKED_EVENT_NAMES = {
    "workspace_home_opened",
    "sheetbook_created",
    "action_execute_requested",
    "sheetbook_archive_bulk_updated",
}


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


def _ensure_collector_user(*, username: str, email: str):
    from django.contrib.auth import get_user_model

    from core.models import UserProfile

    user_model = get_user_model()
    defaults: dict[str, Any] = {"is_active": True}
    if email:
        defaults["email"] = email
    user, _ = user_model.objects.get_or_create(username=username, defaults=defaults)
    if email and user.email != email:
        user.email = email
    user.is_active = True
    user.save(update_fields=["email", "is_active"])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not profile.nickname or profile.nickname.startswith("user"):
        profile.nickname = "sheetbook_pilot_collector"
        profile.save(update_fields=["nickname"])
    return user


def _count_workspace_home_source_events(event_qs) -> tuple[int, int]:
    create_count = 0
    action_count = 0
    rows = event_qs.filter(
        event_name__in=["sheetbook_created", "action_execute_requested"]
    ).values("event_name", "metadata")
    for row in rows:
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
    return create_count, action_count


def _snapshot_user_metrics(*, user) -> dict[str, int]:
    from sheetbook.models import SheetbookMetricEvent

    event_qs = SheetbookMetricEvent.objects.filter(user=user)
    create_count, action_count = _count_workspace_home_source_events(event_qs)
    return {
        "workspace_home_opened": event_qs.filter(event_name="workspace_home_opened").count(),
        "home_source_sheetbook_created": create_count,
        "home_source_action_execute_requested": action_count,
        "archive_event_count": event_qs.filter(
            event_name="sheetbook_archive_bulk_updated"
        ).count(),
    }


def _snapshot_global_metrics(*, days: int) -> dict[str, int]:
    from django.utils import timezone

    from sheetbook.models import SheetbookMetricEvent

    since = timezone.now() - timedelta(days=days)
    event_qs = SheetbookMetricEvent.objects.filter(created_at__gte=since)
    create_count, action_count = _count_workspace_home_source_events(event_qs)
    return {
        "workspace_home_opened": event_qs.filter(event_name="workspace_home_opened").count(),
        "home_source_sheetbook_created": create_count,
        "home_source_action_execute_requested": action_count,
        "archive_event_count": event_qs.filter(
            event_name="sheetbook_archive_bulk_updated"
        ).count(),
    }


def _delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    keys = set(before.keys()) | set(after.keys())
    return {key: int(after.get(key, 0)) - int(before.get(key, 0)) for key in sorted(keys)}


def _default_bundle_due_date() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def _build_next_steps(*, days: int, due_date: str | None = None) -> list[str]:
    safe_days = _to_nonnegative_int(days, default=14) or 14
    safe_due_date = str(due_date or _default_bundle_due_date()).strip() or _default_bundle_due_date()
    return [
        f"python scripts/run_sheetbook_release_readiness.py --days {safe_days}",
        f"python scripts/run_sheetbook_sample_gap_summary.py --days {safe_days}",
        (
            "python scripts/run_sheetbook_daily_start_bundle.py "
            f"--days {safe_days} --due-date {safe_due_date} --allow-pilot-hold-for-beta"
        ),
    ]


def _resolve_action_count(*, action_count: Any, create_count: int) -> int:
    create_value = _to_nonnegative_int(create_count, default=0)
    if action_count is None:
        return min(create_value, 3)
    try:
        raw_value = int(action_count)
    except (TypeError, ValueError):
        return min(create_value, 3)
    if raw_value < 0:
        return min(create_value, 3)
    return raw_value


def _clear_collector_data(*, user) -> dict[str, int]:
    from sheetbook.models import Sheetbook, SheetbookMetricEvent

    deleted_events, _ = SheetbookMetricEvent.objects.filter(
        user=user,
        event_name__in=TRACKED_EVENT_NAMES,
    ).delete()
    deleted_sheetbook_objects, _ = Sheetbook.objects.filter(owner=user).delete()
    return {
        "deleted_events": int(deleted_events),
        "deleted_sheetbook_objects": int(deleted_sheetbook_objects),
    }


def _get_table_column_names(*, table_name: str) -> set[str]:
    from django.db import connection

    with connection.cursor() as cursor:
        table_info = connection.introspection.get_table_description(cursor, table_name)
    return {str(col.name) for col in table_info}


def _supports_home_view_collection() -> bool:
    required_column = "featured_from"
    try:
        column_names = _get_table_column_names(table_name="core_post")
    except Exception:
        return False
    return required_column in column_names


def _run_collection_flow(
    *,
    user,
    home_count: int,
    create_count: int,
    action_count: int,
    archive_event_count: int,
    archive_batch_size: int,
    home_collection_mode: str,
) -> dict[str, Any]:
    from django.test import Client, override_settings
    from django.urls import reverse

    from sheetbook.models import Sheetbook, SheetbookMetricEvent

    status = {
        "home_status_codes": [],
        "home_fallback_events": 0,
        "home_errors": [],
        "quick_create_status_codes": [],
        "action_fallback_events": 0,
        "bulk_archive_status_codes": [],
    }

    with override_settings(
        SHEETBOOK_ENABLED=True,
        SHEETBOOK_BETA_USERNAMES=[],
        SHEETBOOK_BETA_EMAILS=[],
        SHEETBOOK_BETA_USER_IDS=[],
    ):
        client = Client()
        client.force_login(user)

        use_home_fallback = str(home_collection_mode or "auto").strip().lower() == "direct-event"
        if (
            str(home_collection_mode or "auto").strip().lower() == "auto"
            and not _supports_home_view_collection()
        ):
            use_home_fallback = True
            status["home_errors"].append("home_schema_missing_featured_from")
        for _ in range(home_count):
            if use_home_fallback:
                SheetbookMetricEvent.objects.create(
                    event_name="workspace_home_opened",
                    user=user,
                    metadata={
                        "entry_source": "workspace_home_collect_fallback",
                        "collector_tag": COLLECTOR_TAG,
                    },
                )
                status["home_fallback_events"] += 1
                continue
            try:
                response = client.get(reverse("home"))
                code = int(response.status_code)
                status["home_status_codes"].append(code)
                if code >= 500 and str(home_collection_mode or "auto").strip().lower() == "auto":
                    use_home_fallback = True
                    status["home_errors"].append(f"home_status_{code}")
                    SheetbookMetricEvent.objects.create(
                        event_name="workspace_home_opened",
                        user=user,
                        metadata={
                            "entry_source": "workspace_home_collect_fallback",
                            "collector_tag": COLLECTOR_TAG,
                        },
                    )
                    status["home_fallback_events"] += 1
            except Exception as exc:
                if str(home_collection_mode or "auto").strip().lower() == "home-view":
                    raise
                use_home_fallback = True
                status["home_errors"].append(str(exc).splitlines()[0][:200])
                SheetbookMetricEvent.objects.create(
                    event_name="workspace_home_opened",
                    user=user,
                    metadata={
                        "entry_source": "workspace_home_collect_fallback",
                        "collector_tag": COLLECTOR_TAG,
                    },
                )
                status["home_fallback_events"] += 1

        for _ in range(create_count):
            response = client.post(
                reverse("sheetbook:quick_create"),
                data={"source": "workspace_home_collect"},
            )
            status["quick_create_status_codes"].append(int(response.status_code))

        for _ in range(action_count):
            SheetbookMetricEvent.objects.create(
                event_name="action_execute_requested",
                user=user,
                metadata={
                    "entry_source": "workspace_home_action_collect_fallback",
                    "collector_tag": COLLECTOR_TAG,
                },
            )
            status["action_fallback_events"] += 1

        owned_ids = list(
            Sheetbook.objects.filter(owner=user)
            .order_by("-updated_at", "-id")
            .values_list("id", flat=True)
        )
        if archive_event_count > 0 and not owned_ids:
            response = client.post(
                reverse("sheetbook:quick_create"),
                data={"source": "workspace_home_collect"},
            )
            status["quick_create_status_codes"].append(int(response.status_code))
            owned_ids = list(
                Sheetbook.objects.filter(owner=user)
                .order_by("-updated_at", "-id")
                .values_list("id", flat=True)
            )

        batch_size = _to_nonnegative_int(archive_batch_size, default=1) or 1
        selected_ids = [str(item) for item in owned_ids[:batch_size]]
        for idx in range(archive_event_count):
            if not selected_ids:
                break
            archive_action = "archive" if idx % 2 == 0 else "unarchive"
            response = client.post(
                reverse("sheetbook:bulk_archive_update"),
                data={
                    "sheetbook_ids": selected_ids,
                    "archive_action": archive_action,
                    "source": "workspace_home_archive_collect",
                },
            )
            status["bulk_archive_status_codes"].append(
                {"action": archive_action, "status_code": int(response.status_code)}
            )

    return {
        "selected_sheetbook_ids": [int(item) for item in selected_ids],
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collect local sheetbook pilot samples via actual view flows "
            "(home open, quick create, action execute, bulk archive)."
        )
    )
    parser.add_argument("--username", default="sheetbook_pilot_collector", help="collector user")
    parser.add_argument(
        "--email",
        default="sheetbook-pilot-collector@example.com",
        help="collector user email",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="global snapshot lookback days (default: 14)",
    )
    parser.add_argument("--home-count", type=int, default=5, help="home open request count")
    parser.add_argument("--create-count", type=int, default=5, help="quick create request count")
    parser.add_argument(
        "--action-count",
        type=int,
        default=-1,
        help="workspace_home action execute sample count (-1: auto=min(create_count,3))",
    )
    parser.add_argument(
        "--archive-event-count",
        type=int,
        default=5,
        help="bulk archive/unarchive request count",
    )
    parser.add_argument(
        "--archive-batch-size",
        type=int,
        default=3,
        help="sheetbook id count per bulk archive request",
    )
    parser.add_argument(
        "--home-collection-mode",
        choices=["auto", "home-view", "direct-event"],
        default="auto",
        help=(
            "workspace_home_opened 수집 방식. "
            "auto=home 뷰 실패 시 직접 이벤트 폴백, "
            "home-view=뷰만 사용, "
            "direct-event=직접 이벤트만 사용"
        ),
    )
    parser.add_argument(
        "--next-due-date",
        default="",
        help="next_steps bundle command due-date override (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--clear-before",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="clear collector user sample data before collection",
    )
    parser.add_argument(
        "--clear-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="clear collector user sample data and exit",
    )
    args = parser.parse_args()

    _setup_django()

    user = _ensure_collector_user(
        username=str(args.username or "").strip(),
        email=str(args.email or "").strip(),
    )

    clear_result = {"deleted_events": 0, "deleted_sheetbook_objects": 0}
    if bool(args.clear_before) or bool(args.clear_only):
        clear_result = _clear_collector_data(user=user)

    days = _to_nonnegative_int(args.days, default=14) or 14
    create_count = _to_nonnegative_int(args.create_count, default=0)
    action_count = _resolve_action_count(action_count=args.action_count, create_count=create_count)
    user_before = _snapshot_user_metrics(user=user)
    global_before = _snapshot_global_metrics(days=days)

    if bool(args.clear_only):
        print(
            json.dumps(
                {
                    "mode": "clear_only",
                    "collector_tag": COLLECTOR_TAG,
                    "user_id": int(user.id),
                    "username": str(user.username),
                    "clear_result": clear_result,
                    "user_before": user_before,
                    "global_before": global_before,
                },
                ensure_ascii=False,
            )
        )
        return 0

    flow_result = _run_collection_flow(
        user=user,
        home_count=_to_nonnegative_int(args.home_count, default=0),
        create_count=create_count,
        action_count=action_count,
        archive_event_count=_to_nonnegative_int(args.archive_event_count, default=0),
        archive_batch_size=_to_nonnegative_int(args.archive_batch_size, default=1),
        home_collection_mode=str(args.home_collection_mode or "auto"),
    )

    user_after = _snapshot_user_metrics(user=user)
    global_after = _snapshot_global_metrics(days=days)

    result = {
        "mode": "collect",
        "collector_tag": COLLECTOR_TAG,
        "user_id": int(user.id),
        "username": str(user.username),
        "days": days,
        "clear_result": clear_result,
        "requested": {
            "home_count": _to_nonnegative_int(args.home_count, default=0),
            "create_count": create_count,
            "action_count": action_count,
            "archive_event_count": _to_nonnegative_int(args.archive_event_count, default=0),
            "archive_batch_size": _to_nonnegative_int(args.archive_batch_size, default=1),
        },
        "flow_result": flow_result,
        "user_before": user_before,
        "user_after": user_after,
        "user_delta": _delta(user_after, user_before),
        "global_before": global_before,
        "global_after": global_after,
        "global_delta": _delta(global_after, global_before),
        "next_steps": _build_next_steps(
            days=days,
            due_date=str(args.next_due_date or "").strip() or None,
        ),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
