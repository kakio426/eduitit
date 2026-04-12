import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from _smoke_runtime import managed_smoke_database


RENDER_LOG_RE = re.compile(
    r"render rows=(?P<rows_loaded>\d+)/(?P<rows_total>\d+), "
    r"cols=(?P<cols>\d+), limit=(?P<limit>\d+), mode=(?P<mode>[a-z]+), "
    r"chunks=(?P<chunks>\d+), chunk_size=(?P<chunk_size>\d+), render_ms=(?P<render_ms>[0-9.]+)"
)
DEFAULT_FINAL_RENDER_BUDGET_MS = 2000.0
DEFAULT_INITIAL_RENDER_WARN_MS = 3000.0
IGNORED_CONSOLE_ERROR_PATTERNS = (
    "status of 409 (Conflict)",
    "Failed to load resource: net::ERR_NAME_NOT_RESOLVED",
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


def _prepare_smoke_data(rows: int, cols: int, batch_size: int) -> dict[str, Any]:
    _setup_django()

    from django.conf import settings as django_settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import Client

    from core.models import UserProfile
    from sheetbook.models import SheetColumn, SheetTab, Sheetbook
    from sheetbook.views import _paste_matrix_into_grid_tab

    username = "sheetbook_smoke_admin"
    password = "SheetbookSmoke!2026"
    email = "sheetbook-smoke-admin@example.com"
    sheetbook_title = "[smoke] SB-006 1000-row"
    tab_name = "smoke-grid-1000"

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
            profile.nickname = "smoke_teacher"
            profile.save(update_fields=["nickname"])

        sheetbook, _ = Sheetbook.objects.get_or_create(
            owner=user,
            title=sheetbook_title,
            defaults={"academic_year": 2026},
        )
        if sheetbook.academic_year != 2026:
            sheetbook.academic_year = 2026
            sheetbook.save(update_fields=["academic_year"])

        tab, _ = SheetTab.objects.get_or_create(
            sheetbook=sheetbook,
            name=tab_name,
            defaults={"tab_type": SheetTab.TYPE_GRID, "sort_order": 1},
        )
        if tab.tab_type != SheetTab.TYPE_GRID:
            tab.tab_type = SheetTab.TYPE_GRID
            tab.save(update_fields=["tab_type"])

        # Re-seed deterministic grid data for repeatable smoke runs.
        tab.rows.all().delete()
        tab.columns.all().delete()

        for idx in range(cols):
            SheetColumn.objects.create(
                tab=tab,
                key=f"c_{idx + 1}",
                label=f"col-{idx + 1}",
                column_type=SheetColumn.TYPE_TEXT,
                sort_order=idx + 1,
            )

        matrix = []
        for row_idx in range(rows):
            matrix.append(
                [f"student-{row_idx + 1:04d}-value-{col_idx + 1:02d}" for col_idx in range(cols)]
            )

        paste_result = _paste_matrix_into_grid_tab(
            tab=tab,
            matrix=matrix,
            start_row_index=0,
            start_col_index=0,
            actor=user,
            batch_size=batch_size,
        )

        client = Client()
        client.force_login(user)
        session_cookie_name = django_settings.SESSION_COOKIE_NAME
        session_cookie_value = client.cookies[session_cookie_name].value

    return {
        "sheetbook_id": sheetbook.id,
        "tab_id": tab.id,
        "rows": rows,
        "cols": cols,
        "paste_result": paste_result,
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


def _parse_render_line(line: str) -> dict[str, Any] | None:
    match = RENDER_LOG_RE.search(line)
    if not match:
        return None
    return {
        "rows_loaded": int(match.group("rows_loaded")),
        "rows_total": int(match.group("rows_total")),
        "cols": int(match.group("cols")),
        "limit": int(match.group("limit")),
        "mode": match.group("mode"),
        "chunks": int(match.group("chunks")),
        "chunk_size": int(match.group("chunk_size")),
        "render_ms": float(match.group("render_ms")),
        "raw": line,
    }


def _should_ignore_console_error(text: str) -> bool:
    normalized = str(text or "")
    return any(pattern in normalized for pattern in IGNORED_CONSOLE_ERROR_PATTERNS)


def _wait_until_saved(page, timeout_ms: int = 15000) -> dict[str, Any]:
    started = time.perf_counter()
    deadline = time.time() + (timeout_ms / 1000.0)
    last_status = ""
    while time.time() < deadline:
        try:
            last_status = page.locator("#grid-status").inner_text(timeout=1000).strip()
        except Exception:
            last_status = ""
        if "저장 안 된 칸" in last_status:
            return {
                "ok": False,
                "status": last_status,
                "wait_ms": (time.perf_counter() - started) * 1000.0,
            }
        if "충돌" in last_status:
            return {
                "ok": False,
                "status": last_status,
                "wait_ms": (time.perf_counter() - started) * 1000.0,
            }
        if "저장됨" in last_status:
            return {
                "ok": True,
                "status": last_status,
                "wait_ms": (time.perf_counter() - started) * 1000.0,
            }
        page.wait_for_timeout(150)
    return {
        "ok": False,
        "status": f"timeout: {last_status}",
        "wait_ms": (time.perf_counter() - started) * 1000.0,
    }


def _click_with_retry(page, cell, *, selector: str, timeout_ms: int = 10000) -> None:
    cell.scroll_into_view_if_needed(timeout=60000)
    cell.wait_for(state="visible", timeout=60000)
    try:
        cell.click(timeout=timeout_ms)
        return
    except Exception:
        # Fallback for transient hit-target instability in virtualized grids.
        page.wait_for_timeout(250)
        cell.scroll_into_view_if_needed(timeout=60000)
        try:
            cell.click(timeout=timeout_ms * 2, force=True)
            return
        except Exception:
            # Final fallback: dispatch DOM-level focus/click when pointer path is unstable.
            cell.evaluate(
                """(el) => {
                    el.scrollIntoView({ block: "center", inline: "nearest" });
                    el.focus();
                    el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
                    el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
                    el.click();
                }"""
            )
            page.wait_for_timeout(100)


def _edit_cell_and_save(page, *, selector: str, value: str, row_index: int) -> dict[str, Any]:
    last_result = {"ok": False, "status": "not_started", "wait_ms": 0.0}
    for attempt in (1, 2):
        cell = page.locator(selector).first
        _click_with_retry(page, cell, selector=selector, timeout_ms=10000)
        page.keyboard.press("Control+A")
        page.keyboard.type(value)
        page.keyboard.press("Tab")
        result = _wait_until_saved(page)
        result["row_index"] = row_index
        result["attempt"] = attempt
        last_result = result
        if result.get("ok"):
            return result
        if "충돌" not in str(result.get("status", "")):
            return result
        page.wait_for_timeout(300)
    return last_result


def _run_scenario(
    playwright,
    *,
    label: str,
    base_url: str,
    session_cookie_name: str,
    session_cookie_value: str,
    sheetbook_id: int,
    tab_id: int,
    device_name: str | None = None,
) -> dict[str, Any]:
    browser = playwright.chromium.launch(headless=True)
    if device_name:
        device = playwright.devices[device_name]
        context = browser.new_context(**device)
    else:
        context = browser.new_context(viewport={"width": 1536, "height": 960})
    page = context.new_page()

    render_logs: list[dict[str, Any]] = []
    console_errors: list[str] = []
    ignored_console_errors: list[str] = []
    raw_console: list[str] = []

    def _on_console(msg) -> None:
        text_attr = getattr(msg, "text", "")
        text = text_attr() if callable(text_attr) else str(text_attr)
        raw_console.append(f"{msg.type}: {text}")
        if msg.type == "error":
            # Expected save-race noise (409) and external DNS CDN misses are non-blocking.
            if _should_ignore_console_error(text):
                ignored_console_errors.append(text)
            else:
                console_errors.append(text)
        if "[sheetbook:grid] render" in text:
            parsed = _parse_render_line(text)
            if parsed:
                parsed["ts"] = time.perf_counter()
                render_logs.append(parsed)

    page.on("console", _on_console)

    detail_path = f"/sheetbook/{sheetbook_id}/?tab={tab_id}&grid_limit=1000"
    context.add_cookies(
        [
            {
                "name": session_cookie_name,
                "value": session_cookie_value,
                "url": base_url,
            }
        ]
    )

    submit_started = time.perf_counter()
    page.goto(f"{base_url}{detail_path}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_url(re.compile(rf".*/sheetbook/{sheetbook_id}/.*"), timeout=60000)

    try:
        page.wait_for_selector("[data-row-index='0'][data-col-index='0']", timeout=60000)
    except Exception as exc:
        try:
            body_text = page.locator("body").inner_text(timeout=2000)
        except Exception:
            body_text = ""
        debug_payload = {
            "url": page.url,
            "title": page.title(),
            "body_head": body_text[:600],
        }
        raise RuntimeError(
            f"grid cell bootstrap timeout: {json.dumps(debug_payload, ensure_ascii=False)}"
        ) from exc

    # Wait until render log reaches 1000 rows or timeout.
    render_wait_deadline = time.time() + 60
    while time.time() < render_wait_deadline:
        if any(item["rows_total"] >= 1000 and item["rows_loaded"] >= 1000 for item in render_logs):
            break
        page.wait_for_timeout(200)

    def _seek_row(row_index: int) -> float:
        selector = f"[data-row-index='{row_index}'][data-col-index='0']"
        started = time.perf_counter()
        cell = page.locator(selector).first
        cell.scroll_into_view_if_needed(timeout=60000)
        cell.wait_for(state="visible", timeout=60000)
        return (time.perf_counter() - started) * 1000.0

    seek_ms = {
        "row_0": _seek_row(0),
        "row_500": _seek_row(499),
        "row_1000": _seek_row(999),
    }

    edit_results = []
    for row_index in (0, 499, 999):
        selector = f"[data-row-index='{row_index}'][data-col-index='1']"
        save_result = _edit_cell_and_save(
            page,
            selector=selector,
            value=f"{label}-edit-row-{row_index + 1}",
            row_index=row_index,
        )
        edit_results.append(save_result)

    # Shift-select range to verify action layer visibility.
    first_cell = page.locator("[data-row-index='0'][data-col-index='0']").first
    second_cell = page.locator("[data-row-index='1'][data-col-index='1']").first
    _click_with_retry(
        page,
        first_cell,
        selector="[data-row-index='0'][data-col-index='0']",
        timeout_ms=10000,
    )
    page.keyboard.down("Shift")
    _click_with_retry(
        page,
        second_cell,
        selector="[data-row-index='1'][data-col-index='1']",
        timeout_ms=10000,
    )
    page.keyboard.up("Shift")
    action_layer_visible = page.locator("#grid-action-layer").is_visible()

    final_status = ""
    try:
        final_status = page.locator("#grid-status").inner_text(timeout=2000).strip()
    except Exception:
        final_status = ""

    initial_render_ms = None
    if render_logs:
        initial_render_ms = (render_logs[0]["ts"] - submit_started) * 1000.0

    result = {
        "scenario": label,
        "device": device_name or "desktop-default",
        "detail_path": detail_path,
        "initial_render_ms": initial_render_ms,
        "final_render_log": render_logs[-1] if render_logs else None,
        "render_log_count": len(render_logs),
        "seek_ms": seek_ms,
        "edit_results": edit_results,
        "action_layer_visible": action_layer_visible,
        "final_status": final_status,
        "console_error_count": len(console_errors),
        "console_errors": console_errors,
        "ignored_console_error_count": len(ignored_console_errors),
        "ignored_console_errors": ignored_console_errors,
        "console_tail": raw_console[-20:],
    }

    context.close()
    browser.close()
    return result


def _evaluate_pass_fail(
    summary: dict[str, Any],
    *,
    max_final_render_ms: float,
    warn_initial_render_ms: float,
) -> dict[str, Any]:
    desktop = summary["desktop"]
    tablet = summary["tablet"]

    def scenario_ok(item: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        reasons = []
        warnings = []
        initial_render_ms = item.get("initial_render_ms")
        if initial_render_ms is None:
            reasons.append("initial_render_ms_missing")
        elif initial_render_ms > warn_initial_render_ms:
            warnings.append(f"initial_render_ms>{warn_initial_render_ms:.0f}")

        final_log = item.get("final_render_log") or {}
        if final_log.get("rows_loaded", 0) < 1000:
            reasons.append("rows_loaded_lt_1000")
        final_render_ms = final_log.get("render_ms")
        if final_render_ms is None:
            reasons.append("final_render_ms_missing")
        elif final_render_ms > max_final_render_ms:
            reasons.append(f"final_render_ms>{max_final_render_ms:.0f}")
        if item.get("console_error_count", 0) > 0:
            reasons.append("console_errors_present")
        if not item.get("action_layer_visible"):
            reasons.append("action_layer_not_visible")
        for edit in item.get("edit_results", []):
            if not edit.get("ok"):
                reasons.append(f"edit_failed_row_{edit.get('row_index')}")
                break
        return (len(reasons) == 0), reasons, warnings

    desktop_ok, desktop_reasons, desktop_warnings = scenario_ok(desktop)
    tablet_ok, tablet_reasons, tablet_warnings = scenario_ok(tablet)
    all_ok = desktop_ok and tablet_ok
    return {
        "pass": all_ok,
        "desktop_pass": desktop_ok,
        "tablet_pass": tablet_ok,
        "desktop_reasons": desktop_reasons,
        "tablet_reasons": tablet_reasons,
        "desktop_warnings": desktop_warnings,
        "tablet_warnings": tablet_warnings,
        "has_warnings": bool(desktop_warnings or tablet_warnings),
        "thresholds": {
            "max_final_render_ms": max_final_render_ms,
            "warn_initial_render_ms": warn_initial_render_ms,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sheetbook 1000-row browser smoke with Playwright.")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--cols", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument(
        "--max-final-render-ms",
        type=float,
        default=DEFAULT_FINAL_RENDER_BUDGET_MS,
        help="최종 render_ms PASS 상한(기본 2000).",
    )
    parser.add_argument(
        "--warn-initial-render-ms",
        type=float,
        default=DEFAULT_INITIAL_RENDER_WARN_MS,
        help="initial_render_ms 경고 임계치(기본 3000).",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/smoke_sheetbook_grid_1000_latest.json",
        help="JSON output path (repo-relative or absolute).",
    )
    args = parser.parse_args()

    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with managed_smoke_database(root):
        data = _prepare_smoke_data(rows=args.rows, cols=args.cols, batch_size=args.batch_size)

        base_url = f"http://127.0.0.1:{args.port}"
        runserver_env = os.environ.copy()
        runserver_env["SHEETBOOK_ENABLED"] = "True"
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
                    session_cookie_name=data["session_cookie_name"],
                    session_cookie_value=data["session_cookie_value"],
                    sheetbook_id=data["sheetbook_id"],
                    tab_id=data["tab_id"],
                )
                tablet = _run_scenario(
                    playwright,
                    label="tablet",
                    base_url=base_url,
                    session_cookie_name=data["session_cookie_name"],
                    session_cookie_value=data["session_cookie_value"],
                    sheetbook_id=data["sheetbook_id"],
                    tab_id=data["tab_id"],
                    device_name="iPad Pro 11",
                )

            summary = {
                "started_at": started_at,
                "base_url": base_url,
                "dataset": data,
                "desktop": desktop,
                "tablet": tablet,
            }
            summary["evaluation"] = _evaluate_pass_fail(
                summary,
                max_final_render_ms=float(args.max_final_render_ms),
                warn_initial_render_ms=float(args.warn_initial_render_ms),
            )

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
