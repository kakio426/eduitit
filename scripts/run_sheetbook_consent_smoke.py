import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


SUMMARY_RE = re.compile(
    r"현재 입력 기준:\s*(?P<input>\d+)줄\s*·\s*(?P<accepted>\d+)명 반영"
    r"(?:\s*·\s*중복\s*(?P<duplicate>\d+)줄\s*·\s*형식 확인\s*(?P<skipped>\d+)줄)?"
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


def _build_recipients_text(valid_count: int = 180, duplicate_count: int = 20, invalid_count: int = 20) -> str:
    valid_lines = []
    for idx in range(1, valid_count + 1):
        valid_lines.append(f"학생{idx:03d},학생{idx:03d} 보호자,010{idx:08d}")

    duplicate_lines = valid_lines[:duplicate_count]
    invalid_lines = [f"형식확인필요-{idx:02d}" for idx in range(1, invalid_count + 1)]

    # Place invalid/duplicate rows in mixed order to emulate dense issue zones.
    valid_pivot = min(90, len(valid_lines))
    issue_pivot = 10
    merged = []
    merged.extend(valid_lines[:valid_pivot])
    merged.extend(duplicate_lines[:issue_pivot])
    merged.extend(invalid_lines[:issue_pivot])
    merged.extend(valid_lines[valid_pivot:])
    merged.extend(duplicate_lines[issue_pivot:])
    merged.extend(invalid_lines[issue_pivot:])
    return "\n".join(merged)


def _prepare_smoke_data(
    *,
    valid_count: int,
    duplicate_count: int,
    invalid_count: int,
) -> dict[str, Any]:
    _setup_django()

    from django.conf import settings as django_settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import Client
    from django.urls import reverse
    from django.utils import timezone

    from core.models import UserProfile
    from sheetbook.models import SheetTab, Sheetbook

    username = "sheetbook_consent_smoke_admin"
    password = "SheetbookSmoke!2026"
    email = "sheetbook-consent-smoke-admin@example.com"
    sheetbook_title = "[smoke] SB-013 consent recipients"
    tab_name = "consent-smoke-grid"

    recipients_text = _build_recipients_text(
        valid_count=valid_count,
        duplicate_count=duplicate_count,
        invalid_count=invalid_count,
    )
    total_lines = len(recipients_text.splitlines())

    user_model = get_user_model()
    with transaction.atomic():
        user, created = user_model.objects.get_or_create(username=username, defaults={"email": email})
        update_fields = []
        user.email = email
        update_fields.append("email")
        user.is_staff = True
        update_fields.append("is_staff")
        user.is_superuser = True
        update_fields.append("is_superuser")
        user.is_active = True
        update_fields.append("is_active")
        if created or not user.check_password(password):
            user.set_password(password)
            update_fields.append("password")
        user.save(update_fields=update_fields)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.nickname or profile.nickname.startswith("user"):
            profile.nickname = "consent_smoke_teacher"
            profile.save(update_fields=["nickname"])

        sheetbook, _ = Sheetbook.objects.get_or_create(
            owner=user,
            title=sheetbook_title,
            defaults={"academic_year": 2026},
        )
        tab, _ = SheetTab.objects.get_or_create(
            sheetbook=sheetbook,
            name=tab_name,
            defaults={"tab_type": SheetTab.TYPE_GRID, "sort_order": 1},
        )
        if tab.tab_type != SheetTab.TYPE_GRID:
            tab.tab_type = SheetTab.TYPE_GRID
            tab.save(update_fields=["tab_type"])

        client = Client()
        client.force_login(user)
        session = client.session
        token = secrets.token_urlsafe(12)
        seeds = session.get("sheetbook_action_seeds", {})
        if not isinstance(seeds, dict):
            seeds = {}
        seeds[token] = {
            "action": "consent",
            "data": {
                "title": "학부모 확인 동의서",
                "message": "수신자 목록을 확인해 주세요.",
                "document_title": "가정통신문",
                "recipients_text": recipients_text,
                "range_label": f"A1:C{total_lines}",
            },
            "created_at": timezone.now().isoformat(),
        }
        session["sheetbook_action_seeds"] = seeds
        session.save()

        session_cookie_name = django_settings.SESSION_COOKIE_NAME
        session_cookie_value = client.cookies[session_cookie_name].value
        review_path = (
            reverse("sheetbook:consent_seed_review", kwargs={"pk": sheetbook.id, "tab_pk": tab.id})
            + f"?sb_seed={token}"
        )

    return {
        "sheetbook_id": sheetbook.id,
        "tab_id": tab.id,
        "seed_token": token,
        "review_path": review_path,
        "session_cookie_name": session_cookie_name,
        "session_cookie_value": session_cookie_value,
        "initial_recipients_text_lines": total_lines,
        "expected": {
            "valid_count": valid_count,
            "duplicate_count": duplicate_count,
            "invalid_count": invalid_count,
            "total_lines": total_lines,
        },
    }


def _wait_for_http(url: str, timeout_sec: int) -> None:
    deadline = time.time() + timeout_sec
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # pragma: no cover
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Server not ready: {url}. last_error={last_error}")


def _parse_summary(text: str) -> dict[str, int]:
    text = str(text or "").strip()
    match = SUMMARY_RE.search(text)
    if not match:
        return {"input": -1, "accepted": -1, "duplicate": -1, "skipped": -1}
    return {
        "input": int(match.group("input")),
        "accepted": int(match.group("accepted")),
        "duplicate": int(match.group("duplicate") or 0),
        "skipped": int(match.group("skipped") or 0),
    }


def _current_line_state(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
            const t = document.getElementById('recipients-textarea');
            const indicator = document.getElementById('recipients-active-line');
            if (!t) return { line: -1, selectionStart: -1, indicator: '' };
            const pos = Number(t.selectionStart || 0);
            const head = String(t.value || '').slice(0, pos);
            const line = head.split(/\\r?\\n/).length;
            return {
              line,
              selectionStart: pos,
              indicator: indicator ? indicator.textContent.trim() : '',
              scrollTop: Number(t.scrollTop || 0),
            };
        }"""
    )


def _append_line(page, line: str) -> None:
    page.evaluate(
        """(line) => {
            const t = document.getElementById('recipients-textarea');
            if (!t) return;
            const sep = String(t.value || '').endsWith('\\n') ? '' : '\\n';
            t.value = `${t.value}${sep}${line}`;
            t.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        line,
    )


def _collect_minimap_marker_meta(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
            const nodes = Array.from(
              document.querySelectorAll('#recipients-issue-minimap-markers [data-recipients-line]')
            );
            const rows = nodes.map((node, index) => {
              const rect = node.getBoundingClientRect();
              const top = Number(rect.top.toFixed(2));
              return {
                index,
                line: Number(node.dataset.recipientsLine || 0),
                lane: Number(node.dataset.recipientsLane || 0),
                top,
              };
            });
            const laneCount = new Set(rows.map((row) => row.lane)).size;
            const uniquePlacementCount = new Set(
              rows.map((row) => `${row.lane}:${row.top.toFixed(2)}`)
            ).size;
            const denseAdjacencies = rows.reduce((count, row, index) => {
              if (index === 0) return count;
              const prev = rows[index - 1];
              return count + ((row.line - prev.line) <= 2 ? 1 : 0);
            }, 0);
            return {
              count: rows.length,
              lane_count: laneCount,
              duplicate_lane_top_count: Math.max(0, rows.length - uniquePlacementCount),
              dense_adjacencies: denseAdjacencies,
              lines: rows,
            };
        }"""
    )


def _collect_marker_check_indices(marker_lines: list[dict[str, Any]]) -> list[int]:
    if not marker_lines:
        return []
    indices = {0, len(marker_lines) // 2, len(marker_lines) - 1}
    for index in range(1, len(marker_lines)):
        prev = marker_lines[index - 1]
        current = marker_lines[index]
        if int(current.get("line") or 0) - int(prev.get("line") or 0) <= 2:
            indices.add(index - 1)
            indices.add(index)
            break
    return sorted(indices)


def _run_scenario(
    playwright,
    *,
    label: str,
    base_url: str,
    review_path: str,
    expected_seed_token: str,
    session_cookie_name: str,
    session_cookie_value: str,
    device_name: str | None = None,
) -> dict[str, Any]:
    browser = playwright.chromium.launch(headless=True)
    if device_name:
        device = playwright.devices[device_name]
        context = browser.new_context(**device)
    else:
        context = browser.new_context(viewport={"width": 1536, "height": 960})
    page = context.new_page()

    console_errors: list[str] = []
    console_tail: list[str] = []

    def _on_console(msg) -> None:
        text_attr = getattr(msg, "text", "")
        text = text_attr() if callable(text_attr) else str(text_attr)
        row = f"{msg.type}: {text}"
        console_tail.append(row)
        if len(console_tail) > 40:
            del console_tail[:-40]
        if msg.type == "error":
            console_errors.append(text)

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

    started = time.perf_counter()
    page.goto(f"{base_url}{review_path}", wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("#recipients-textarea", timeout=60000)
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
            f"consent review bootstrap timeout: {json.dumps(debug_payload, ensure_ascii=False)}"
        ) from exc
    open_ms = (time.perf_counter() - started) * 1000.0

    summary_text = page.locator("#recipients-live-summary").inner_text(timeout=10000).strip()
    initial_summary = _parse_summary(summary_text)

    issue_panel_visible = page.locator("#recipients-issue-line-panel").is_visible()
    issue_button_locator = page.locator("#recipients-issue-line-buttons [data-recipients-line]")
    issue_list_locator = page.locator("#recipients-issue-line-list [data-recipients-line]")
    minimap_locator = page.locator("#recipients-issue-minimap")
    marker_locator = page.locator("#recipients-issue-minimap-markers [data-recipients-line]")

    issue_buttons_count = issue_button_locator.count()
    issue_list_count = issue_list_locator.count()
    minimap_visible = minimap_locator.is_visible()
    marker_count = marker_locator.count()
    marker_meta = _collect_minimap_marker_meta(page) if marker_count > 0 else {
        "count": 0,
        "lane_count": 0,
        "duplicate_lane_top_count": 0,
        "dense_adjacencies": 0,
        "lines": [],
    }

    line_jump_by_button = {"ok": False}
    if issue_buttons_count > 0:
        first_line = int(issue_button_locator.first.get_attribute("data-recipients-line") or "0")
        issue_button_locator.first.click(timeout=10000, force=True)
        page.wait_for_timeout(250)
        state = _current_line_state(page)
        line_jump_by_button = {
            "target_line": first_line,
            "current_line": state.get("line"),
            "indicator": state.get("indicator"),
            "ok": state.get("line") == first_line and str(first_line) in str(state.get("indicator") or ""),
        }

    line_jump_by_minimap = {"ok": False, "checked_count": 0, "samples": []}
    if marker_count > 0:
        marker_lines = marker_meta.get("lines") or []
        check_indices = _collect_marker_check_indices(marker_lines)
        samples = []
        for index in check_indices:
            target_line = int(marker_locator.nth(index).get_attribute("data-recipients-line") or "0")
            target_lane = int(marker_locator.nth(index).get_attribute("data-recipients-lane") or "0")
            marker_locator.nth(index).click(timeout=10000, force=True)
            page.wait_for_timeout(250)
            state = _current_line_state(page)
            ok = state.get("line") == target_line and str(target_line) in str(state.get("indicator") or "")
            samples.append(
                {
                    "index": index,
                    "target_line": target_line,
                    "target_lane": target_lane,
                    "current_line": state.get("line"),
                    "indicator": state.get("indicator"),
                    "ok": ok,
                }
            )
        line_jump_by_minimap = {
            "ok": bool(samples) and all(item.get("ok") for item in samples),
            "checked_count": len(samples),
            "samples": samples,
            "dense_adjacencies": int(marker_meta.get("dense_adjacencies") or 0),
        }

    page.locator("[data-recipients-jump='bottom']").click(timeout=10000)
    page.wait_for_timeout(200)
    bottom_state = _current_line_state(page)
    page.locator("[data-recipients-jump='top']").click(timeout=10000)
    page.wait_for_timeout(200)
    top_state = _current_line_state(page)

    _append_line(page, "형식검증추가줄")
    _append_line(page, "학생001,학생001 보호자,01000000001")
    page.wait_for_timeout(400)
    updated_summary_text = page.locator("#recipients-live-summary").inner_text(timeout=10000).strip()
    updated_summary = _parse_summary(updated_summary_text)

    with page.expect_navigation(timeout=60000):
        page.get_by_role("button", name="확인 후 동의서 만들기").click(timeout=10000)

    final_url = page.url
    final_path = urlparse(final_url).path
    final_query = parse_qs(urlparse(final_url).query)

    result = {
        "scenario": label,
        "device": device_name or "desktop-default",
        "expected_seed_token": expected_seed_token,
        "open_ms": open_ms,
        "review_path": review_path,
        "initial_summary_text": summary_text,
        "initial_summary": initial_summary,
        "issue_panel_visible": issue_panel_visible,
        "issue_buttons_count": issue_buttons_count,
        "issue_list_count": issue_list_count,
        "minimap_visible": minimap_visible,
        "marker_count": marker_count,
        "minimap_lane_count": int(marker_meta.get("lane_count") or 0),
        "minimap_duplicate_lane_top_count": int(marker_meta.get("duplicate_lane_top_count") or 0),
        "minimap_dense_adjacencies": int(marker_meta.get("dense_adjacencies") or 0),
        "line_jump_by_button": line_jump_by_button,
        "line_jump_by_minimap": line_jump_by_minimap,
        "bottom_scroll_top": bottom_state.get("scrollTop"),
        "top_scroll_top": top_state.get("scrollTop"),
        "updated_summary_text": updated_summary_text,
        "updated_summary": updated_summary,
        "final_url": final_url,
        "final_path": final_path,
        "final_seed_token": (final_query.get("sb_seed") or [""])[0],
        "console_error_count": len(console_errors),
        "console_errors": console_errors,
        "console_tail": console_tail,
    }

    context.close()
    browser.close()
    return result


def _evaluate(summary: dict[str, Any]) -> dict[str, Any]:
    expected = summary.get("expected") or {}
    required_input = int(expected.get("total_lines") or 150)
    required_accepted = int(expected.get("valid_count") or 1)
    required_duplicate = int(expected.get("duplicate_count") or 1)
    required_skipped = int(expected.get("invalid_count") or 1)

    def scenario_eval(item: dict[str, Any]) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        initial = item.get("initial_summary") or {}
        updated = item.get("updated_summary") or {}
        seed_token = str(item.get("expected_seed_token") or "")
        if initial.get("input", -1) < required_input:
            reasons.append(f"initial_input_lt_{required_input}")
        if initial.get("accepted", -1) < required_accepted:
            reasons.append(f"initial_accepted_lt_{required_accepted}")
        if initial.get("duplicate", -1) < required_duplicate:
            reasons.append(f"initial_duplicate_lt_{required_duplicate}")
        if initial.get("skipped", -1) < required_skipped:
            reasons.append(f"initial_skipped_lt_{required_skipped}")
        if not item.get("issue_panel_visible"):
            reasons.append("issue_panel_hidden")
        if not item.get("minimap_visible") or item.get("marker_count", 0) <= 0:
            reasons.append("minimap_missing")
        if item.get("marker_count", 0) >= 10 and item.get("minimap_lane_count", 0) < 2:
            reasons.append("minimap_lane_split_missing")
        if item.get("minimap_duplicate_lane_top_count", 0) > 0:
            reasons.append("minimap_duplicate_lane_top_detected")
        if not (item.get("line_jump_by_button") or {}).get("ok"):
            reasons.append("line_jump_button_failed")
        if not (item.get("line_jump_by_minimap") or {}).get("ok"):
            reasons.append("line_jump_minimap_failed")
        if int((item.get("line_jump_by_minimap") or {}).get("checked_count") or 0) < 3:
            reasons.append("line_jump_minimap_samples_too_few")
        if item.get("bottom_scroll_top", 0) <= item.get("top_scroll_top", 0):
            reasons.append("top_bottom_jump_not_effective")
        if updated.get("input", -1) < initial.get("input", -1) + 2:
            reasons.append("summary_input_not_updated")
        if updated.get("duplicate", -1) < initial.get("duplicate", -1) + 1:
            reasons.append("summary_duplicate_not_updated")
        if updated.get("skipped", -1) < initial.get("skipped", -1) + 1:
            reasons.append("summary_skipped_not_updated")
        if item.get("final_path") != "/consent/create/step1/":
            reasons.append("redirect_path_unexpected")
        if item.get("final_seed_token") != seed_token:
            reasons.append("seed_token_mismatch_after_submit")
        if item.get("console_error_count", 0) > 0:
            reasons.append("console_errors_present")
        return (len(reasons) == 0), reasons

    desktop_ok, desktop_reasons = scenario_eval(summary["desktop"])
    tablet_ok, tablet_reasons = scenario_eval(summary["tablet"])
    return {
        "pass": desktop_ok and tablet_ok,
        "desktop_pass": desktop_ok,
        "tablet_pass": tablet_ok,
        "desktop_reasons": desktop_reasons,
        "tablet_reasons": tablet_reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sheetbook consent recipient mass-edit smoke with Playwright.")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--valid-count", type=int, default=180)
    parser.add_argument("--duplicate-count", type=int, default=20)
    parser.add_argument("--invalid-count", type=int, default=20)
    parser.add_argument(
        "--output",
        default="docs/handoff/smoke_sheetbook_consent_recipients_latest.json",
        help="JSON output path (repo-relative or absolute).",
    )
    args = parser.parse_args()

    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    valid_count = max(1, int(args.valid_count))
    duplicate_count = max(1, int(args.duplicate_count))
    invalid_count = max(1, int(args.invalid_count))

    desktop_data = _prepare_smoke_data(
        valid_count=valid_count,
        duplicate_count=duplicate_count,
        invalid_count=invalid_count,
    )
    tablet_data = _prepare_smoke_data(
        valid_count=valid_count,
        duplicate_count=duplicate_count,
        invalid_count=invalid_count,
    )
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
                review_path=desktop_data["review_path"],
                expected_seed_token=desktop_data["seed_token"],
                session_cookie_name=desktop_data["session_cookie_name"],
                session_cookie_value=desktop_data["session_cookie_value"],
            )
            tablet = _run_scenario(
                playwright,
                label="tablet",
                base_url=base_url,
                review_path=tablet_data["review_path"],
                expected_seed_token=tablet_data["seed_token"],
                session_cookie_name=tablet_data["session_cookie_name"],
                session_cookie_value=tablet_data["session_cookie_value"],
                device_name="iPad Pro 11",
            )

        summary = {
            "started_at": started_at,
            "base_url": base_url,
            "expected": {
                "valid_count": valid_count,
                "duplicate_count": duplicate_count,
                "invalid_count": invalid_count,
                "total_lines": desktop_data["expected"]["total_lines"],
            },
            "datasets": {
                "desktop": desktop_data,
                "tablet": tablet_data,
            },
            "desktop": desktop,
            "tablet": tablet,
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
            except subprocess.TimeoutExpired:  # pragma: no cover
                server_proc.kill()
                server_proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
