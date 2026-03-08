import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


IGNORED_CONSOLE_ERROR_PATTERNS = (
    "status of 409 (Conflict)",
    "Failed to load resource: net::ERR_NAME_NOT_RESOLVED",
)
FATAL_CONSOLE_WARNING_PATTERNS = (
    "window.showToast is not a function",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _setup_django() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _prepare_smoke_data() -> dict[str, Any]:
    _setup_django()

    from django.conf import settings as django_settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import Client
    from django.utils import timezone

    from core.models import UserProfile
    from sheetbook.models import SheetCell, SheetColumn, SheetRow, SheetTab, Sheetbook

    username = "sheetbook_calendar_smoke_admin"
    password = "SheetbookSmoke!2026"
    email = "sheetbook-calendar-smoke-admin@example.com"
    sheetbook_title = "[smoke] SB-calendar-embed"
    schedule_tab_name = "일정 원본"
    calendar_tab_name = "달력"
    schedule_date = timezone.localdate()

    user_model = get_user_model()
    with transaction.atomic():
        user, _ = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save(update_fields=["email", "is_staff", "is_superuser", "is_active", "password"])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.nickname or profile.nickname.startswith("user"):
            profile.nickname = "calendar_smoke_teacher"
            profile.role = "school"
            profile.save(update_fields=["nickname", "role"])
        elif profile.role != "school":
            profile.role = "school"
            profile.save(update_fields=["role"])

        sheetbook, _ = Sheetbook.objects.get_or_create(
            owner=user,
            title=sheetbook_title,
            defaults={"academic_year": schedule_date.year},
        )
        if sheetbook.academic_year != schedule_date.year:
            sheetbook.academic_year = schedule_date.year
            sheetbook.save(update_fields=["academic_year"])

        schedule_tab, _ = SheetTab.objects.get_or_create(
            sheetbook=sheetbook,
            name=schedule_tab_name,
            defaults={"tab_type": SheetTab.TYPE_GRID, "sort_order": 1},
        )
        calendar_tab, _ = SheetTab.objects.get_or_create(
            sheetbook=sheetbook,
            name=calendar_tab_name,
            defaults={"tab_type": SheetTab.TYPE_CALENDAR, "sort_order": 2},
        )

        if schedule_tab.tab_type != SheetTab.TYPE_GRID:
            schedule_tab.tab_type = SheetTab.TYPE_GRID
            schedule_tab.save(update_fields=["tab_type"])
        if calendar_tab.tab_type != SheetTab.TYPE_CALENDAR:
            calendar_tab.tab_type = SheetTab.TYPE_CALENDAR
            calendar_tab.save(update_fields=["tab_type"])

        schedule_tab.rows.all().delete()
        schedule_tab.columns.all().delete()

        date_col = SheetColumn.objects.create(
            tab=schedule_tab,
            key="date",
            label="날짜",
            column_type=SheetColumn.TYPE_DATE,
            sort_order=1,
        )
        title_col = SheetColumn.objects.create(
            tab=schedule_tab,
            key="title",
            label="제목",
            column_type=SheetColumn.TYPE_TEXT,
            sort_order=2,
        )
        note_col = SheetColumn.objects.create(
            tab=schedule_tab,
            key="note",
            label="메모",
            column_type=SheetColumn.TYPE_TEXT,
            sort_order=3,
        )
        row = SheetRow.objects.create(tab=schedule_tab, sort_order=1, created_by=user, updated_by=user)
        SheetCell.objects.create(row=row, column=date_col, value_date=schedule_date)
        SheetCell.objects.create(row=row, column=title_col, value_text="sync smoke event")
        SheetCell.objects.create(row=row, column=note_col, value_text="calendar embed smoke sync")

        if sheetbook.preferred_schedule_tab_id != schedule_tab.id or sheetbook.preferred_calendar_tab_id != calendar_tab.id:
            sheetbook.preferred_schedule_tab = schedule_tab
            sheetbook.preferred_calendar_tab = calendar_tab
            sheetbook.save(update_fields=["preferred_schedule_tab", "preferred_calendar_tab", "updated_at"])

        client = Client()
        client.force_login(user)
        session_cookie_name = django_settings.SESSION_COOKIE_NAME
        session_cookie_value = client.cookies[session_cookie_name].value

    return {
        "username": username,
        "sheetbook_id": sheetbook.id,
        "schedule_tab_id": schedule_tab.id,
        "calendar_tab_id": calendar_tab.id,
        "detail_path": f"/sheetbook/{sheetbook.id}/?tab={calendar_tab.id}",
        "today": schedule_date.isoformat(),
        "sheetbook_title": sheetbook.title,
        "schedule_tab_name": schedule_tab.name,
        "session_cookie_name": session_cookie_name,
        "session_cookie_value": session_cookie_value,
    }


def _wait_for_http(url: str, timeout_sec: int) -> None:
    deadline = time.time() + timeout_sec
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # pragma: no cover - environment dependent
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Server not ready: {url}. last_error={last_error}")


def _should_ignore_console_error(text: str) -> bool:
    normalized = str(text or "")
    return any(pattern in normalized for pattern in IGNORED_CONSOLE_ERROR_PATTERNS)


def _is_fatal_console_warning(text: str) -> bool:
    normalized = str(text or "")
    return any(pattern in normalized for pattern in FATAL_CONSOLE_WARNING_PATTERNS)


def _wait_for_status(page, expected_text: str, timeout_ms: int = 20000) -> str:
    locator = page.locator("#sheetbook-calendar-status")
    deadline = time.time() + (timeout_ms / 1000.0)
    last_text = ""
    while time.time() < deadline:
        try:
            last_text = locator.inner_text(timeout=1000).strip()
        except Exception:
            last_text = ""
        if expected_text in last_text:
            return last_text
        page.wait_for_timeout(150)
    raise RuntimeError(f"status timeout waiting for '{expected_text}': {last_text}")


def _click_locator(locator, *, timeout_ms: int = 15000) -> None:
    locator.wait_for(state="visible", timeout=timeout_ms)
    try:
        locator.click(timeout=timeout_ms)
    except Exception:
        time.sleep(0.5)
        locator.evaluate("el => el.click()")


def _click_host_button(page, selector: str, timeout_ms: int = 15000) -> None:
    _click_locator(page.locator(selector), timeout_ms=timeout_ms)


def _open_event_and_collect_source(page, event_title: str) -> dict[str, Any]:
    surface = page.locator("#sheetbook-calendar-surface")
    event_button = surface.get_by_role("button", name=re.compile(re.escape(event_title))).first
    event_button.wait_for(state="visible", timeout=20000)
    _click_locator(event_button, timeout_ms=10000)
    detail_modal = surface.locator("div[x-show='detailModalOpen']")
    detail_modal.wait_for(state="visible", timeout=20000)
    source_link = detail_modal.locator("a[href*='/sheetbook/']").first
    source_link.wait_for(state="visible", timeout=10000)
    payload = {
        "href": source_link.get_attribute("href"),
        "target": source_link.get_attribute("target"),
        "text": source_link.inner_text(timeout=2000).strip(),
    }
    _click_locator(detail_modal.get_by_role("button", name="닫기"), timeout_ms=10000)
    return payload


def _run_scenario(
    playwright,
    *,
    label: str,
    base_url: str,
    detail_path: str,
    today: str,
    sheetbook_id: int,
    session_cookie_name: str,
    session_cookie_value: str,
    device_name: str | None = None,
    expect_sync_enabled: bool = True,
    expect_mobile_compact: bool = False,
) -> dict[str, Any]:
    browser = playwright.chromium.launch(headless=True)
    if device_name:
        device = playwright.devices[device_name]
        context = browser.new_context(**device)
    else:
        context = browser.new_context(viewport={"width": 1536, "height": 960})
    page = context.new_page()

    console_errors: list[str] = []
    ignored_console_errors: list[str] = []
    fatal_console_warnings: list[str] = []
    console_tail: list[str] = []

    def _on_console(msg) -> None:
        text_attr = getattr(msg, "text", "")
        text = text_attr() if callable(text_attr) else str(text_attr)
        row = f"{msg.type}: {text}"
        console_tail.append(row)
        if len(console_tail) > 40:
            del console_tail[:-40]
        if msg.type == "error":
            if _should_ignore_console_error(text):
                ignored_console_errors.append(text)
            else:
                console_errors.append(text)
            return
        if msg.type == "warning" and _is_fatal_console_warning(text):
            fatal_console_warnings.append(text)

    page.on("console", _on_console)
    context.add_cookies(
        [
            {
                "name": session_cookie_name,
                "value": session_cookie_value,
                "url": base_url,
            }
        ]
    )

    page.goto(f"{base_url}{detail_path}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#sheetbook-calendar-surface", timeout=60000)
    page.locator("#sheetbook-calendar-surface").get_by_role("button", name="이전 달").wait_for(state="visible", timeout=60000)
    _wait_for_status(page, "열었어요.")

    sync_button = page.locator("#sheetbook-calendar-sync-btn")
    message_button = page.locator("#sheetbook-calendar-message-btn")
    create_button = page.locator("#sheetbook-calendar-create-btn")
    sync_button.wait_for(state="visible", timeout=15000)
    create_button.wait_for(state="visible", timeout=15000)

    sync_disabled = sync_button.is_disabled()
    create_disabled = create_button.is_disabled()
    message_disabled = False
    if message_button.count():
        message_disabled = message_button.is_disabled()

    sync_status = ""
    sync_summary = ""
    mobile_guidance = ""
    if expect_sync_enabled:
        _click_host_button(page, "#sheetbook-calendar-sync-btn")
        sync_status = _wait_for_status(page, "반영 완료:")
        sync_summary = page.locator("#sheetbook-calendar-sync-summary-text").inner_text(timeout=10000).strip()
        page.locator("#sheetbook-calendar-surface").get_by_role("button", name="이전 달").wait_for(state="visible", timeout=60000)
        page.wait_for_timeout(1200)
    else:
        sync_status = _wait_for_status(page, "열었어요.")
        mobile_guidance = page.locator("#sheetbook-calendar-embed p").filter(has_text="휴대폰에서는 일정 확인과 일정 1건 추가만 할 수 있어요.").inner_text(timeout=10000).strip()

    create_title = f"{label} create smoke"
    _click_host_button(page, "#sheetbook-calendar-create-btn")
    create_open_status = _wait_for_status(page, "일정 1건 추가 창을 열었어요.")
    create_modal = page.locator("#sheetbook-calendar-surface div[x-show='createModalOpen']")
    create_modal.wait_for(state="visible", timeout=20000)
    create_modal.locator("input[x-model='createForm.title']").fill(create_title, timeout=10000)
    _click_locator(create_modal.get_by_role("button", name="저장"), timeout_ms=10000)
    create_save_status = _wait_for_status(page, "일정을 저장했어요.")
    create_source = _open_event_and_collect_source(page, create_title)

    message_title = f"{label} message smoke"
    _click_host_button(page, "#sheetbook-calendar-message-btn")
    message_open_status = _wait_for_status(page, "메시지 붙여넣기 창을 열었어요.")
    message_modal = page.locator("#sheetbook-calendar-surface div[x-show='messageCaptureModalOpen']")
    message_modal.wait_for(state="visible", timeout=20000)
    message_modal.locator("textarea[x-model='messageCaptureInputText']").fill(
        "2026-03-22 09:00-10:00 학급 회의",
        timeout=10000,
    )
    _click_locator(message_modal.get_by_role("button", name="자동으로 읽기"), timeout_ms=10000)
    message_confirm = page.locator("#sheetbook-calendar-surface input[x-model='messageCaptureDraft.title']")
    message_confirm.wait_for(state="visible", timeout=20000)
    message_confirm.fill(message_title, timeout=10000)
    page.locator("#sheetbook-calendar-surface input[x-model='messageCaptureDraft.start_date']").fill(today, timeout=10000)
    page.locator("#sheetbook-calendar-surface input[x-model='messageCaptureDraft.end_date']").fill(today, timeout=10000)
    _click_locator(page.locator("#sheetbook-calendar-surface").get_by_role("button", name="이대로 저장"), timeout_ms=10000)
    message_save_status = _wait_for_status(page, "메시지를 일정으로 저장했어요.")
    message_source = _open_event_and_collect_source(page, message_title)

    result = {
        "scenario": label,
        "device": device_name or "desktop-default",
        "detail_path": detail_path,
        "sheetbook_id": sheetbook_id,
        "sync_status": sync_status,
        "sync_summary": sync_summary,
        "sync_disabled": sync_disabled,
        "message_disabled": message_disabled,
        "create_disabled": create_disabled,
        "mobile_guidance": mobile_guidance,
        "create_open_status": create_open_status,
        "create_save_status": create_save_status,
        "create_source": create_source,
        "message_open_status": message_open_status,
        "message_save_status": message_save_status,
        "message_source": message_source,
        "console_error_count": len(console_errors),
        "console_errors": console_errors,
        "ignored_console_error_count": len(ignored_console_errors),
        "ignored_console_errors": ignored_console_errors,
        "fatal_console_warning_count": len(fatal_console_warnings),
        "fatal_console_warnings": fatal_console_warnings,
        "console_tail": console_tail,
    }

    context.close()
    browser.close()
    return result


def _evaluate(summary: dict[str, Any]) -> dict[str, Any]:
    def scenario_eval(item: dict[str, Any]) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        is_mobile_compact = bool(item.get("scenario") == "mobile")
        if is_mobile_compact:
            if not bool(item.get("sync_disabled")):
                reasons.append("mobile_sync_not_disabled")
            if "휴대폰에서는 일정 확인과 일정 1건 추가만 할 수 있어요." not in str(item.get("mobile_guidance") or ""):
                reasons.append("mobile_guidance_missing")
        else:
            if bool(item.get("sync_disabled")):
                reasons.append("sync_unexpectedly_disabled")
            if "반영 완료:" not in str(item.get("sync_status") or ""):
                reasons.append("sync_status_missing")
            if "일정 원본" not in str(item.get("sync_summary") or ""):
                reasons.append("sync_summary_missing")
        if bool(item.get("create_disabled")):
            reasons.append("create_disabled")
        if bool(item.get("message_disabled")):
            reasons.append("message_disabled")
        if "일정 1건 추가 창" not in str(item.get("create_open_status") or ""):
            reasons.append("create_open_status_missing")
        if "일정을 저장했어요." not in str(item.get("create_save_status") or ""):
            reasons.append("create_save_status_missing")
        if (item.get("create_source") or {}).get("target") != "_top":
            reasons.append("create_source_target_not_top")
        if f"/sheetbook/{item.get('sheetbook_id')}/" not in str((item.get("create_source") or {}).get("href") or ""):
            reasons.append("create_source_href_unexpected")
        if "메시지 붙여넣기 창" not in str(item.get("message_open_status") or ""):
            reasons.append("message_open_status_missing")
        if "메시지를 일정으로 저장했어요." not in str(item.get("message_save_status") or ""):
            reasons.append("message_save_status_missing")
        if (item.get("message_source") or {}).get("target") != "_top":
            reasons.append("message_source_target_not_top")
        if f"/sheetbook/{item.get('sheetbook_id')}/" not in str((item.get("message_source") or {}).get("href") or ""):
            reasons.append("message_source_href_unexpected")
        if int(item.get("console_error_count") or 0) > 0:
            reasons.append("console_errors_present")
        if int(item.get("fatal_console_warning_count") or 0) > 0:
            reasons.append("fatal_console_warnings_present")
        return (len(reasons) == 0), reasons

    desktop_ok, desktop_reasons = scenario_eval(summary["desktop"])
    tablet_ok, tablet_reasons = scenario_eval(summary["tablet"])
    mobile_ok, mobile_reasons = scenario_eval(summary["mobile"])
    return {
        "pass": desktop_ok and tablet_ok and mobile_ok,
        "desktop_pass": desktop_ok,
        "tablet_pass": tablet_ok,
        "mobile_pass": mobile_ok,
        "desktop_reasons": desktop_reasons,
        "tablet_reasons": tablet_reasons,
        "mobile_reasons": mobile_reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sheetbook calendar embed smoke with Playwright.")
    parser.add_argument("--port", type=int, default=8004)
    parser.add_argument(
        "--output",
        default="docs/handoff/smoke_sheetbook_calendar_embed_latest.json",
        help="JSON output path (repo-relative or absolute).",
    )
    args = parser.parse_args()

    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = _prepare_smoke_data()
    base_url = f"http://127.0.0.1:{args.port}"
    runserver_env = os.environ.copy()
    runserver_env["SHEETBOOK_ENABLED"] = "True"
    runserver_env["FEATURE_MESSAGE_CAPTURE_ENABLED"] = "True"
    runserver_env["FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES"] = data["username"]
    runserver_env.setdefault("PYTHONUNBUFFERED", "1")

    server_proc = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{args.port}", "--noreload"],
        cwd=str(root),
        env=runserver_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        _wait_for_http(f"{base_url}/health/", timeout_sec=90)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            desktop = _run_scenario(
                playwright,
                label="desktop",
                base_url=base_url,
                detail_path=data["detail_path"],
                today=data["today"],
                sheetbook_id=data["sheetbook_id"],
                session_cookie_name=data["session_cookie_name"],
                session_cookie_value=data["session_cookie_value"],
            )
            tablet = _run_scenario(
                playwright,
                label="tablet",
                base_url=base_url,
                detail_path=data["detail_path"],
                today=data["today"],
                sheetbook_id=data["sheetbook_id"],
                session_cookie_name=data["session_cookie_name"],
                session_cookie_value=data["session_cookie_value"],
                device_name="iPad Pro 11",
            )
            mobile = _run_scenario(
                playwright,
                label="mobile",
                base_url=base_url,
                detail_path=data["detail_path"],
                today=data["today"],
                sheetbook_id=data["sheetbook_id"],
                session_cookie_name=data["session_cookie_name"],
                session_cookie_value=data["session_cookie_value"],
                device_name="iPhone 13",
                expect_sync_enabled=False,
                expect_mobile_compact=True,
            )

        summary = {
            "started_at": started_at,
            "base_url": base_url,
            "dataset": data,
            "desktop": desktop,
            "tablet": tablet,
            "mobile": mobile,
        }
        summary["evaluation"] = _evaluate(summary)
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if summary["evaluation"]["pass"] else 2
    finally:
        if server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - environment dependent
                server_proc.kill()
                server_proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
