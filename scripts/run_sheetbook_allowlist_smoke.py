import argparse
import json
import os
import sys
import time
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


def _prepare_users() -> dict[str, Any]:
    from django.contrib.auth import get_user_model
    from django.db import transaction

    from core.models import UserProfile

    user_model = get_user_model()
    with transaction.atomic():
        allow_user, _ = user_model.objects.get_or_create(
            username="sheetbook_allow_smoke_teacher",
            defaults={"email": "sheetbook-allow-smoke@example.com"},
        )
        allow_user.email = "sheetbook-allow-smoke@example.com"
        allow_user.is_active = True
        allow_user.set_password("SheetbookSmoke!2026")
        allow_user.save(update_fields=["email", "is_active", "password"])
        allow_profile, _ = UserProfile.objects.get_or_create(user=allow_user)
        if not allow_profile.nickname or allow_profile.nickname.startswith("user"):
            allow_profile.nickname = "allow_smoke_teacher"
            allow_profile.save(update_fields=["nickname"])

        blocked_user, _ = user_model.objects.get_or_create(
            username="sheetbook_block_smoke_teacher",
            defaults={"email": "sheetbook-block-smoke@example.com"},
        )
        blocked_user.email = "sheetbook-block-smoke@example.com"
        blocked_user.is_active = True
        blocked_user.set_password("SheetbookSmoke!2026")
        blocked_user.save(update_fields=["email", "is_active", "password"])
        blocked_profile, _ = UserProfile.objects.get_or_create(user=blocked_user)
        if not blocked_profile.nickname or blocked_profile.nickname.startswith("user"):
            blocked_profile.nickname = "block_smoke_teacher"
            blocked_profile.save(update_fields=["nickname"])

    return {
        "allow_user_id": allow_user.id,
        "allow_username": allow_user.username,
        "allow_email": allow_user.email,
        "blocked_user_id": blocked_user.id,
        "blocked_username": blocked_user.username,
        "blocked_email": blocked_user.email,
    }


def _run_case_beta_only(users: dict[str, Any], title_suffix: str) -> dict[str, Any]:
    from django.test import Client, override_settings
    from django.urls import reverse

    from sheetbook.models import Sheetbook

    title = f"[smoke] allowlist beta only {title_suffix}"

    with override_settings(
        SHEETBOOK_ENABLED=False,
        SHEETBOOK_BETA_USERNAMES=[users["allow_username"]],
        SHEETBOOK_BETA_EMAILS=[users["allow_email"]],
        SHEETBOOK_BETA_USER_IDS=[],
    ):
        allow_client = Client()
        allow_client.force_login(_get_user(users["allow_user_id"]))
        allow_index = allow_client.get(reverse("sheetbook:index"))
        allow_create = allow_client.post(
            reverse("sheetbook:create"),
            data={"title": title, "academic_year": 2026},
        )

        allow_created = (
            Sheetbook.objects.filter(owner_id=users["allow_user_id"], title=title)
            .order_by("-id")
            .first()
        )
        allow_detail_status = None
        if allow_created:
            allow_detail_status = allow_client.get(
                reverse("sheetbook:detail", kwargs={"pk": allow_created.id})
            ).status_code

        blocked_client = Client()
        blocked_client.force_login(_get_user(users["blocked_user_id"]))
        blocked_index = blocked_client.get(reverse("sheetbook:index"))
        blocked_create = blocked_client.post(
            reverse("sheetbook:create"),
            data={"title": f"{title} blocked", "academic_year": 2026},
        )

    return {
        "case": "beta_only_allowlist",
        "settings": {
            "SHEETBOOK_ENABLED": False,
            "SHEETBOOK_BETA_USERNAMES_count": 1,
            "SHEETBOOK_BETA_EMAILS_count": 1,
            "SHEETBOOK_BETA_USER_IDS_count": 0,
        },
        "allowlisted": {
            "index_status": allow_index.status_code,
            "create_status": allow_create.status_code,
            "detail_status": allow_detail_status,
            "created_sheetbook_id": allow_created.id if allow_created else None,
        },
        "blocked": {
            "index_status": blocked_index.status_code,
            "create_status": blocked_create.status_code,
        },
    }


def _run_case_global_enabled(users: dict[str, Any], title_suffix: str) -> dict[str, Any]:
    from django.test import Client, override_settings
    from django.urls import reverse

    from sheetbook.models import Sheetbook

    title = f"[smoke] allowlist global on {title_suffix}"

    with override_settings(
        SHEETBOOK_ENABLED=True,
        SHEETBOOK_BETA_USERNAMES=[],
        SHEETBOOK_BETA_EMAILS=[],
        SHEETBOOK_BETA_USER_IDS=[],
    ):
        blocked_client = Client()
        blocked_client.force_login(_get_user(users["blocked_user_id"]))
        blocked_index = blocked_client.get(reverse("sheetbook:index"))
        blocked_create = blocked_client.post(
            reverse("sheetbook:create"),
            data={"title": title, "academic_year": 2026},
        )

        blocked_created = (
            Sheetbook.objects.filter(owner_id=users["blocked_user_id"], title=title)
            .order_by("-id")
            .first()
        )
        blocked_detail_status = None
        if blocked_created:
            blocked_detail_status = blocked_client.get(
                reverse("sheetbook:detail", kwargs={"pk": blocked_created.id})
            ).status_code

    return {
        "case": "global_enabled",
        "settings": {
            "SHEETBOOK_ENABLED": True,
            "SHEETBOOK_BETA_USERNAMES_count": 0,
            "SHEETBOOK_BETA_EMAILS_count": 0,
            "SHEETBOOK_BETA_USER_IDS_count": 0,
        },
        "non_allowlisted": {
            "index_status": blocked_index.status_code,
            "create_status": blocked_create.status_code,
            "detail_status": blocked_detail_status,
            "created_sheetbook_id": blocked_created.id if blocked_created else None,
        },
    }


def _get_user(user_id: int):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.get(id=user_id)


def _evaluate(summary: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []

    beta_case = summary["beta_only_allowlist"]
    global_case = summary["global_enabled"]

    allowlisted = beta_case["allowlisted"]
    blocked = beta_case["blocked"]
    if allowlisted.get("index_status") != 200:
        reasons.append("beta_allowlisted_index_not_200")
    if allowlisted.get("create_status") not in (302, 303):
        reasons.append("beta_allowlisted_create_not_redirect")
    if allowlisted.get("detail_status") != 200:
        reasons.append("beta_allowlisted_detail_not_200")
    if blocked.get("index_status") != 404:
        reasons.append("beta_blocked_index_not_404")
    if blocked.get("create_status") != 404:
        reasons.append("beta_blocked_create_not_404")

    non_allowlisted = global_case["non_allowlisted"]
    if non_allowlisted.get("index_status") != 200:
        reasons.append("global_non_allowlisted_index_not_200")
    if non_allowlisted.get("create_status") not in (302, 303):
        reasons.append("global_non_allowlisted_create_not_redirect")
    if non_allowlisted.get("detail_status") != 200:
        reasons.append("global_non_allowlisted_detail_not_200")

    return {
        "pass": len(reasons) == 0,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sheetbook allowlist access smoke checks.")
    parser.add_argument(
        "--output",
        default="docs/handoff/smoke_sheetbook_allowlist_latest.json",
        help="JSON output path (repo-relative or absolute).",
    )
    args = parser.parse_args()

    _setup_django()
    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    users = _prepare_users()
    beta_only_result = _run_case_beta_only(users, stamp)
    global_enabled_result = _run_case_global_enabled(users, stamp)

    summary = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "users": users,
        "beta_only_allowlist": beta_only_result,
        "global_enabled": global_enabled_result,
    }
    summary["evaluation"] = _evaluate(summary)

    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["evaluation"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
