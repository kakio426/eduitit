import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


IGNORED_CONSOLE_ERROR_PATTERNS = (
    'Failed to load resource: net::ERR_NAME_NOT_RESOLVED',
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
    raise RuntimeError(f'Server not ready: {url}. last_error={last_error}')


def _should_ignore_console_error(text: str) -> bool:
    normalized = str(text or '')
    return any(pattern in normalized for pattern in IGNORED_CONSOLE_ERROR_PATTERNS)


def _run_scenario(playwright, *, base_url: str) -> dict[str, Any]:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 960})
    page = context.new_page()

    console_errors: list[str] = []
    ignored_console_errors: list[str] = []
    page_errors: list[str] = []
    console_tail: list[str] = []

    def _on_console(msg) -> None:
        text_attr = getattr(msg, 'text', '')
        text = text_attr() if callable(text_attr) else str(text_attr)
        console_tail.append(f'{msg.type}: {text}')
        if len(console_tail) > 20:
            console_tail.pop(0)
        if msg.type == 'error':
            if _should_ignore_console_error(text):
                ignored_console_errors.append(text)
            else:
                console_errors.append(text)

    page.on('console', _on_console)
    page.on('pageerror', lambda exc: page_errors.append(str(exc)))

    result: dict[str, Any] = {
        'pass': False,
        'console_errors': console_errors,
        'ignored_console_errors': ignored_console_errors,
        'page_errors': page_errors,
        'console_tail': console_tail,
    }

    try:
        page.goto(f'{base_url}/fairy-games/', wait_until='networkidle', timeout=30000)
        page.locator('text=전략 게임 6종').wait_for(state='visible', timeout=15000)

        reversi_link = page.locator('a[href$="/fairy-games/reversi/play/"]').first
        reversi_link.wait_for(state='visible', timeout=10000)
        reversi_link.click(timeout=10000)

        page.wait_for_url(f'{base_url}/fairy-games/reversi/play/', timeout=15000)
        page.locator('.fg-board-grid').wait_for(state='visible', timeout=10000)
        page.locator('.fg-cell').first.wait_for(state='visible', timeout=10000)

        status_locator = page.locator('#fg-status')
        status_locator.wait_for(state='visible', timeout=10000)
        initial_status = status_locator.inner_text(timeout=2000).strip()
        if not initial_status or initial_status == '준비 중':
            raise RuntimeError(f'initial status not ready: {initial_status}')

        if status_locator.get_attribute('aria-live') != 'polite':
            raise RuntimeError('status aria-live should be polite')

        cell_count = page.locator('.fg-cell').count()
        if cell_count != 64:
            raise RuntimeError(f'expected 64 board cells, got {cell_count}')

        legal_cell = page.locator('.fg-cell.hint').first
        legal_cell.wait_for(state='visible', timeout=10000)
        legal_label = legal_cell.get_attribute('aria-label') or ''
        if '둘 수 있는 칸' not in legal_label:
            raise RuntimeError(f'legal cell aria-label missing move hint: {legal_label}')
        legal_cell.click(timeout=10000)

        post_move_status = status_locator.inner_text(timeout=2000).strip()
        if post_move_status == initial_status:
            raise RuntimeError('status did not change after first move')

        open_rules_btn = page.locator('#fg-open-rules')
        open_rules_btn.focus()
        open_rules_btn.click(timeout=10000)

        rules_modal = page.locator('#fg-rules-modal')
        rules_modal.wait_for(state='visible', timeout=10000)
        active_id = page.evaluate('() => document.activeElement && document.activeElement.id')
        if active_id != 'fg-rules-close':
            raise RuntimeError(f'rules modal did not focus close button: active={active_id}')

        page.keyboard.press('Tab')
        active_after_tab = page.evaluate('() => document.activeElement && document.activeElement.id')
        if active_after_tab != 'fg-rules-close':
            raise RuntimeError(f'rules modal focus trap failed: active={active_after_tab}')

        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        if rules_modal.get_attribute('aria-hidden') != 'true':
            raise RuntimeError('rules modal did not close on Escape')
        restored_focus = page.evaluate('() => document.activeElement && document.activeElement.id')
        if restored_focus != 'fg-open-rules':
            raise RuntimeError(f'focus did not return to rules trigger: active={restored_focus}')

        page.locator('#fg-reset').click(timeout=10000)
        page.locator('.fg-cell').first.wait_for(state='visible', timeout=10000)
        reset_status = status_locator.inner_text(timeout=2000).strip()
        reset_count = page.locator('.fg-cell').count()
        if reset_count != 64:
            raise RuntimeError(f'expected 64 board cells after reset, got {reset_count}')
        if '점수 2:2' not in reset_status:
            raise RuntimeError(f'unexpected reset status: {reset_status}')

        result.update({
            'pass': not console_errors and not page_errors,
            'initial_status': initial_status,
            'post_move_status': post_move_status,
            'reset_status': reset_status,
            'legal_cell_label': legal_label,
            'cell_count': cell_count,
            'reset_cell_count': reset_count,
        })
        return result
    except Exception as exc:
        result['error'] = str(exc)
        return result
    finally:
        context.close()
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='Run fairy games reversi browser smoke with Playwright.')
    parser.add_argument('--port', type=int, default=8031, help='Port for temporary runserver.')
    parser.add_argument('--output', default='tmp_fairy_games_reversi_smoke_latest.json', help='JSON output path (repo-relative or absolute).')
    args = parser.parse_args()

    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_url = f'http://127.0.0.1:{args.port}'
    runserver_env = os.environ.copy()
    runserver_env.setdefault('PYTHONUNBUFFERED', '1')

    server_proc = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{args.port}', '--noreload'],
        cwd=str(root),
        env=runserver_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    started_at = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        _wait_for_http(f'{base_url}/health/', timeout_sec=90)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            scenario = _run_scenario(playwright, base_url=base_url)

        summary = {
            'started_at': started_at,
            'base_url': base_url,
            'scenario': scenario,
            'evaluation': {
                'pass': scenario.get('pass', False),
                'failed_checks': [] if scenario.get('pass') else [scenario.get('error', 'unknown')],
            },
        }
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if summary['evaluation']['pass'] else 2
    finally:
        if server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()
                server_proc.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
