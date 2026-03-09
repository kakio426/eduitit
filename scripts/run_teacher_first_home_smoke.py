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
FATAL_CONSOLE_WARNING_PATTERNS = (
    'window.showToast is not a function',
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _setup_django() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django

    django.setup()


def _prepare_smoke_data() -> dict[str, Any]:
    _setup_django()

    from django.conf import settings as django_settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import Client
    from django.utils import timezone

    from core.models import ProductFavorite, ProductUsageLog, ProductWorkbenchBundle, UserProfile
    from products.models import Product

    username = 'teacher_first_home_smoke_admin'
    password = 'TeacherFirstSmoke!2026'
    email = 'teacher-first-home-smoke@example.com'

    product_specs = {
        'workspace': {
            'title': '[smoke] 홈 교무수첩',
            'description': '학급 운영 작업대 smoke용 도구',
            'service_type': 'classroom',
            'solve_text': '학급 운영을 바로 이어갑니다.',
            'icon': 'fa-solid fa-book-open',
            'display_order': -100,
        },
        'notice': {
            'title': '[smoke] 홈 안내문',
            'description': '안내문 작성 smoke용 도구',
            'service_type': 'work',
            'solve_text': '안내문을 바로 만듭니다.',
            'icon': 'fa-solid fa-file-lines',
            'display_order': -99,
        },
        'collect': {
            'title': '[smoke] 홈 동의서',
            'description': '수합·서명 smoke용 도구',
            'service_type': 'collect_sign',
            'solve_text': '동의와 회수를 이어서 합니다.',
            'icon': 'fa-solid fa-signature',
            'display_order': -98,
        },
        'recent': {
            'title': '[smoke] 홈 교실활동',
            'description': '최근 사용 smoke용 도구',
            'service_type': 'game',
            'solve_text': '교실 활동을 빠르게 엽니다.',
            'icon': 'fa-solid fa-chess-knight',
            'display_order': -97,
        },
        'discovery': {
            'title': '[smoke] 홈 가이드',
            'description': '발견성 smoke용 도구',
            'service_type': 'edutech',
            'solve_text': '새로운 도구를 가볍게 찾아봅니다.',
            'icon': 'fa-solid fa-lightbulb',
            'display_order': -96,
        },
    }

    user_model = get_user_model()
    with transaction.atomic():
        user, _ = user_model.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save(update_fields=['email', 'is_staff', 'is_superuser', 'is_active', 'password'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.nickname = 'teacher_first_home_smoke'
        profile.role = 'school'
        profile.save(update_fields=['nickname', 'role'])

        products = {}
        for key, spec in product_specs.items():
            product, _ = Product.objects.get_or_create(
                title=spec['title'],
                defaults={
                    'description': spec['description'],
                    'price': 0,
                    'is_active': True,
                    'service_type': spec['service_type'],
                },
            )
            product.description = spec['description']
            product.price = 0
            product.is_active = True
            product.service_type = spec['service_type']
            product.solve_text = spec['solve_text']
            product.icon = spec['icon']
            product.display_order = spec['display_order']
            product.launch_route_name = ''
            product.external_url = ''
            product.save(update_fields=['description', 'price', 'is_active', 'service_type', 'solve_text', 'icon', 'display_order', 'launch_route_name', 'external_url'])
            products[key] = product

        ProductFavorite.objects.filter(user=user).delete()
        ProductWorkbenchBundle.objects.filter(user=user).delete()
        ProductUsageLog.objects.filter(user=user).delete()

        ProductFavorite.objects.create(user=user, product=products['workspace'], pin_order=1)
        ProductFavorite.objects.create(user=user, product=products['notice'], pin_order=2)
        ProductUsageLog.objects.create(user=user, product=products['recent'], action='launch', source='home_quick')

        bundle = ProductWorkbenchBundle.objects.create(
            user=user,
            name='학급 운영 세트',
            product_ids=[products['notice'].id, products['workspace'].id],
            last_used_at=timezone.now(),
        )

        client = Client()
        client.force_login(user)
        session_cookie_name = django_settings.SESSION_COOKIE_NAME
        session_cookie_value = client.cookies[session_cookie_name].value

    return {
        'username': username,
        'bundle_id': bundle.id,
        'bundle_name': bundle.name,
        'workspace_title': products['workspace'].title,
        'notice_title': products['notice'].title,
        'collect_title': products['collect'].title,
        'recent_title': products['recent'].title,
        'session_cookie_name': session_cookie_name,
        'session_cookie_value': session_cookie_value,
        'home_path': '/',
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
    raise RuntimeError(f'Server not ready: {url}. last_error={last_error}')


def _should_ignore_console_error(text: str) -> bool:
    normalized = str(text or '')
    return any(pattern in normalized for pattern in IGNORED_CONSOLE_ERROR_PATTERNS)


def _is_fatal_console_warning(text: str) -> bool:
    normalized = str(text or '')
    return any(pattern in normalized for pattern in FATAL_CONSOLE_WARNING_PATTERNS)


def _wait_for_live_message(page, expected_fragment: str, timeout_ms: int = 10000) -> str:
    locator = page.locator('[data-workbench-live="true"]')
    deadline = time.time() + (timeout_ms / 1000.0)
    last_text = ''
    while time.time() < deadline:
        try:
            last_text = locator.inner_text(timeout=1000).strip()
        except Exception:
            last_text = ''
        if expected_fragment in last_text:
            return last_text
        page.wait_for_timeout(120)
    raise RuntimeError(f"live region timeout waiting for '{expected_fragment}': {last_text}")


def _get_card_titles(page) -> list[str]:
    cards = page.locator('[data-workbench-card="true"]')
    titles: list[str] = []
    for index in range(cards.count()):
        title = cards.nth(index).get_attribute('data-workbench-title') or ''
        titles.append(title)
    return titles


def _run_scenario(
    playwright,
    *,
    label: str,
    base_url: str,
    session_cookie_name: str,
    session_cookie_value: str,
    bundle_name: str,
    expect_mobile_controls: bool = False,
    device_name: str | None = None,
) -> dict[str, Any]:
    browser = playwright.chromium.launch(headless=True)
    if device_name:
        device = playwright.devices[device_name]
        context = browser.new_context(**device)
    else:
        context = browser.new_context(viewport={'width': 1536, 'height': 960})

    context.add_cookies([
        {
            'name': session_cookie_name,
            'value': session_cookie_value,
            'domain': '127.0.0.1',
            'path': '/',
            'httpOnly': True,
            'secure': False,
        }
    ])
    page = context.new_page()

    console_errors: list[str] = []
    ignored_console_errors: list[str] = []
    fatal_console_warnings: list[str] = []
    console_tail: list[str] = []

    def _on_console(msg) -> None:
        text_attr = getattr(msg, 'text', '')
        text = text_attr() if callable(text_attr) else str(text_attr)
        row = f'{msg.type}: {text}'
        console_tail.append(row)
        if len(console_tail) > 40:
            console_tail.pop(0)
        if msg.type == 'error':
            if _should_ignore_console_error(text):
                ignored_console_errors.append(text)
            else:
                console_errors.append(text)
        elif msg.type == 'warning' and _is_fatal_console_warning(text):
            fatal_console_warnings.append(text)

    page.on('console', _on_console)

    result: dict[str, Any] = {
        'label': label,
        'pass': False,
        'console_errors': console_errors,
        'ignored_console_errors': ignored_console_errors,
        'fatal_console_warnings': fatal_console_warnings,
        'console_tail': console_tail,
    }

    try:
        page.goto(f'{base_url}/', wait_until='networkidle', timeout=30000)
        page.locator('[data-workbench="true"]').wait_for(state='visible', timeout=20000)
        page.get_by_role('heading', name='내 작업대').wait_for(state='visible', timeout=10000)
        page.get_by_role('heading', name='최근 이어서').wait_for(state='visible', timeout=10000)
        page.get_by_role('heading', name='같이 쓰면 좋은 도구').wait_for(state='visible', timeout=10000)
        page.locator('[data-workbench-live="true"]').wait_for(state='attached', timeout=10000)
        page.locator('#workbenchKeyboardHint').wait_for(state='attached', timeout=10000)

        workbench_cards = page.locator('[data-workbench-card="true"]')
        initial_count = workbench_cards.count()
        if initial_count < 2:
            raise RuntimeError(f'expected at least 2 workbench cards, got {initial_count}')
        initial_titles = _get_card_titles(page)

        edit_toggle = page.locator('[data-workbench-edit-toggle="true"]').first
        edit_toggle.click(timeout=10000)
        page.get_by_role('button', name='정리 끝').wait_for(state='visible', timeout=10000)

        first_card = page.locator('[data-workbench-card="true"]').nth(0)
        first_card.focus()
        page.keyboard.press('ArrowRight')
        live_text = _wait_for_live_message(page, '2번째', timeout_ms=12000)
        reordered_titles = _get_card_titles(page)
        if len(reordered_titles) < 2 or reordered_titles[1] != initial_titles[0]:
            raise RuntimeError(f'keyboard reorder failed: before={initial_titles}, after={reordered_titles}')

        bundle_button = page.locator(f'[data-workbench-bundle-apply="true"][data-bundle-name="{bundle_name}"]').first
        bundle_button.click(timeout=10000)
        page.wait_for_timeout(800)
        page.get_by_role('heading', name='내 작업대').wait_for(state='visible', timeout=10000)
        applied_titles = _get_card_titles(page)

        add_button = page.locator('[data-favorite-toggle="true"][data-favorite-off-text="작업대에 추가"]').first
        if add_button.count() < 1:
            raise RuntimeError('no add-to-workbench button found in recommendation sections')
        added_product_id = add_button.get_attribute('data-product-id') or ''
        add_button.click(timeout=10000)
        page.wait_for_timeout(800)
        page.get_by_role('heading', name='내 작업대').wait_for(state='visible', timeout=10000)
        if added_product_id:
            page.locator(f'[data-workbench-card="true"][data-product-id="{added_product_id}"]').wait_for(state='visible', timeout=10000)
        expanded_count = page.locator('[data-workbench-card="true"]').count()
        if expanded_count < len(applied_titles):
            raise RuntimeError(f'workbench card count regressed after add: before={len(applied_titles)} after={expanded_count}')

        mobile_move_ok = None
        if expect_mobile_controls:
            page.locator('[data-workbench-edit-toggle="true"]').first.click(timeout=10000)
            control = page.locator('[data-workbench-control="right"]').first
            control.wait_for(state='visible', timeout=10000)
            control.click(timeout=10000)
            page.wait_for_timeout(400)
            mobile_move_ok = True

        result.update({
            'pass': not console_errors and not fatal_console_warnings,
            'initial_titles': initial_titles,
            'reordered_titles': reordered_titles,
            'applied_titles': applied_titles,
            'expanded_count': expanded_count,
            'live_text': live_text,
            'mobile_move_ok': mobile_move_ok,
        })
        return result
    except Exception as exc:
        result['error'] = str(exc)
        return result
    finally:
        context.close()
        browser.close()


def _evaluate(summary: dict[str, Any]) -> dict[str, Any]:
    scenario_labels = ['desktop', 'tablet', 'mobile']
    failures: list[str] = []
    for label in scenario_labels:
        scenario = summary[label]
        if not scenario.get('pass'):
            failures.append(label)
        if scenario.get('console_errors'):
            failures.append(f'{label}:console_errors')
        if scenario.get('fatal_console_warnings'):
            failures.append(f'{label}:console_warnings')
    return {
        'pass': not failures,
        'failed_checks': failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Smoke test for teacher-first home/workbench flows.')
    parser.add_argument('--port', type=int, default=8020, help='Port for temporary runserver.')
    parser.add_argument('--output', default='tmp_teacher_first_home_smoke_latest.json', help='JSON output path (repo-relative or absolute).')
    args = parser.parse_args()

    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = _prepare_smoke_data()
    base_url = f'http://127.0.0.1:{args.port}'
    runserver_env = os.environ.copy()
    runserver_env.setdefault('PYTHONUNBUFFERED', '1')
    runserver_env['HOME_V2_ENABLED'] = 'True'

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
            desktop = _run_scenario(
                playwright,
                label='desktop',
                base_url=base_url,
                session_cookie_name=data['session_cookie_name'],
                session_cookie_value=data['session_cookie_value'],
                bundle_name=data['bundle_name'],
            )
            tablet = _run_scenario(
                playwright,
                label='tablet',
                base_url=base_url,
                session_cookie_name=data['session_cookie_name'],
                session_cookie_value=data['session_cookie_value'],
                bundle_name=data['bundle_name'],
                device_name='iPad Pro 11',
            )
            mobile = _run_scenario(
                playwright,
                label='mobile',
                base_url=base_url,
                session_cookie_name=data['session_cookie_name'],
                session_cookie_value=data['session_cookie_value'],
                bundle_name=data['bundle_name'],
                device_name='iPhone 13',
                expect_mobile_controls=True,
            )

        summary = {
            'started_at': started_at,
            'base_url': base_url,
            'dataset': data,
            'desktop': desktop,
            'tablet': tablet,
            'mobile': mobile,
        }
        summary['evaluation'] = _evaluate(summary)
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
