import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import Any

from _smoke_runtime import managed_smoke_database

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

    from classcalendar.models import CalendarEvent, CalendarTask
    from core.models import ProductFavorite, ProductUsageLog, UserPolicyConsent, UserProfile
    from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
    from products.models import Product
    from reservations.models import School, SchoolConfig

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
        'quickdrop': {
            'title': '[smoke] 바로전송',
            'description': '빠른 전송 smoke용 도구',
            'service_type': 'classroom',
            'solve_text': '회의 링크와 메모를 바로 보냅니다.',
            'icon': 'fa-solid fa-bolt',
            'display_order': -95,
            'launch_route_name': 'quickdrop:landing',
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
        UserPolicyConsent.objects.get_or_create(
            user=user,
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            defaults={
                'provider': 'direct',
                'agreed_at': timezone.now(),
                'agreement_source': 'required_gate',
            },
        )

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
            product.launch_route_name = spec.get('launch_route_name', '')
            product.external_url = ''
            product.save(update_fields=['description', 'price', 'is_active', 'service_type', 'solve_text', 'icon', 'display_order', 'launch_route_name', 'external_url'])
            products[key] = product

        ProductFavorite.objects.filter(user=user).delete()
        ProductUsageLog.objects.filter(user=user).delete()

        ProductFavorite.objects.create(user=user, product=products['workspace'], pin_order=1)
        ProductFavorite.objects.create(user=user, product=products['notice'], pin_order=2)
        ProductUsageLog.objects.create(user=user, product=products['recent'], action='launch', source='home_quick')
        school, _ = School.objects.get_or_create(
            slug='teacher-first-home-smoke-school',
            defaults={
                'name': '스모크초',
                'owner': user,
            },
        )
        if school.owner_id != user.id or school.name != '스모크초':
            school.owner = user
            school.name = '스모크초'
            school.save(update_fields=['owner', 'name'])
        SchoolConfig.objects.get_or_create(school=school)

        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        CalendarEvent.objects.update_or_create(
            author=user,
            title='[smoke] 오늘 일정',
            defaults={
                'start_time': now + timedelta(hours=1),
                'end_time': now + timedelta(hours=2),
                'is_all_day': False,
            },
        )
        CalendarTask.objects.update_or_create(
            author=user,
            title='[smoke] 오늘 할 일',
            defaults={
                'due_at': now + timedelta(hours=3),
                'has_time': True,
                'status': CalendarTask.Status.OPEN,
            },
        )

        client = Client()
        client.force_login(user)
        session_cookie_name = django_settings.SESSION_COOKIE_NAME
        session_cookie_value = client.cookies[session_cookie_name].value

    return {
        'username': username,
        'workspace_title': products['workspace'].title,
        'notice_title': products['notice'].title,
        'collect_title': products['collect'].title,
        'recent_title': products['recent'].title,
        'quickdrop_title': products['quickdrop'].title,
        'reservation_school_name': school.name,
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


def _wait_for_text(page, locator, expected_fragment: str, timeout_ms: int = 10000) -> str:
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
    raise RuntimeError(f"text timeout waiting for '{expected_fragment}': {last_text}")


def _wait_for_attr(page, locator, name: str, expected_value: str, timeout_ms: int = 10000) -> str:
    deadline = time.time() + (timeout_ms / 1000.0)
    last_value = ''
    while time.time() < deadline:
        try:
            last_value = locator.get_attribute(name, timeout=1000) or ''
        except Exception:
            last_value = ''
        if last_value == expected_value:
            return last_value
        page.wait_for_timeout(120)
    raise RuntimeError(f"attr timeout waiting for {name}={expected_value}: {last_value}")


def _run_scenario(
    playwright,
    *,
    label: str,
    base_url: str,
    session_cookie_name: str,
    session_cookie_value: str,
    layout_version: str,
    device_name: str | None = None,
    expect_mobile_layout: bool = False,
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
        shell = page.locator(f'[data-home-design-version="{layout_version}"]:visible').first
        shell.wait_for(state='visible', timeout=20000)

        page.get_by_role('heading', name='내 작업대').first.wait_for(state='visible', timeout=10000)

        if expect_mobile_layout:
            if layout_version == 'v6':
                workbench = page.locator('[data-home-v6-workbench="mobile"]:visible').first
                workbench_cards = page.locator('[data-home-v6-mobile-workbench-card="true"]:visible')
                quickdrop_panel = page.locator('[data-home-v6-mobile-quickdrop="true"]:visible').first
                quickdrop_form = page.locator('[data-home-v6-mobile-quickdrop-form="true"]:visible').first
            else:
                workbench = page.locator('[data-home-v5-mobile-workbench="true"]:visible').first
                workbench_cards = page.locator('[data-home-v5-mobile-workbench-card="true"]:visible')
                quickdrop_panel = page.locator('[data-home-v4-mobile-quickdrop="true"]:visible').first
                quickdrop_form = page.locator('[data-home-v4-mobile-quickdrop-form="true"]:visible').first
        else:
            if layout_version == 'v6':
                workbench = page.locator('[data-home-v6-favorites-panel="true"]:visible').first
                workbench_cards = page.locator('[data-home-v6-favorite-card="true"]:visible')
                quickdrop_panel = page.locator('[data-home-v6-quickdrop-panel="true"]:visible').first
                quickdrop_form = page.locator('[data-home-v6-quickdrop-form="true"]:visible').first
            else:
                workbench = page.locator('[data-home-v4-favorites-panel="true"]:visible').first
                workbench_cards = page.locator('[data-home-v4-favorite-card="true"]:visible')
                quickdrop_panel = page.locator('[data-home-v4-quickdrop-panel="true"]:visible').first
                quickdrop_form = page.locator('[data-home-v4-quickdrop-form="true"]:visible').first

        workbench.wait_for(state='visible', timeout=20000)
        initial_count = workbench_cards.count()
        if initial_count < 2:
            raise RuntimeError(f'expected at least 2 workbench cards, got {initial_count}')

        reservation_card = page.locator('[data-home-reservations-card="true"]:visible').first
        reservation_card.wait_for(state='visible', timeout=10000)
        calendar_card = page.locator('[data-classcalendar-home-card="true"]:visible').first
        calendar_card.wait_for(state='visible', timeout=15000)

        developer_chat_visible = False
        if not expect_mobile_layout:
            if layout_version == 'v6':
                developer_chat_card = page.locator('[data-home-v6-developer-chat-card="desktop"]:visible').first
            else:
                developer_chat_card = page.locator('[data-home-v4-developer-chat-card="desktop"]:visible').first
            developer_chat_card.wait_for(state='visible', timeout=10000)
            developer_chat_visible = True

        favorite_toggle = workbench.locator('[data-favorite-toggle="true"]').first
        favorite_toggle.wait_for(state='visible', timeout=10000)
        _wait_for_attr(page, favorite_toggle, 'aria-pressed', 'true', timeout_ms=12000)
        favorite_toggle.click(timeout=10000)
        _wait_for_attr(page, favorite_toggle, 'aria-pressed', 'false', timeout_ms=12000)
        favorite_toggle.click(timeout=10000)
        _wait_for_attr(page, favorite_toggle, 'aria-pressed', 'true', timeout_ms=12000)

        quickdrop_panel.wait_for(state='visible', timeout=10000)
        quickdrop_form.wait_for(state='visible', timeout=10000)
        quickdrop_text = f'{label} quickdrop smoke'
        quickdrop_textarea = quickdrop_form.locator('textarea[name="text"]').first
        quickdrop_textarea.fill(quickdrop_text, timeout=10000)
        quickdrop_form.get_by_role('button', name='지금 보내기').click(timeout=10000)
        quickdrop_summary = _wait_for_text(
            page,
            quickdrop_panel.locator('[data-initial-summary]').first,
            quickdrop_text,
            timeout_ms=15000,
        )

        page.wait_for_timeout(800)
        page_html = page.content()
        mobile_order_ok = None
        if expect_mobile_layout:
            if layout_version == 'v6':
                markers = [
                    'data-home-v6-workbench="mobile"',
                    'data-home-v6-calendar-panel="mobile"',
                    'data-home-v6-mobile-quickdrop="true"',
                    'data-home-v6-reservations-panel="mobile"',
                    'data-home-v6-mobile-sns="true"',
                ]
            else:
                markers = [
                    'data-home-v5-mobile-workbench="true"',
                    'data-home-v5-mobile-calendar-panel="true"',
                    'data-home-v4-mobile-quickdrop="true"',
                    'data-home-reservations-card="true"',
                    'data-home-v5-mobile-sns="true"',
                ]
            positions = [page_html.find(marker) for marker in markers]
            visible_positions = [position for position in positions if position != -1]
            mobile_order_ok = visible_positions == sorted(visible_positions)
            if not mobile_order_ok:
                raise RuntimeError(f'mobile section order mismatch: {positions}')

        result.update({
            'pass': not console_errors and not fatal_console_warnings,
            'layout_version': layout_version,
            'workbench_count': initial_count,
            'reservation_visible': True,
            'calendar_visible': True,
            'developer_chat_visible': developer_chat_visible,
            'quickdrop_summary': quickdrop_summary,
            'favorite_toggle_roundtrip_ok': True,
            'mobile_order_ok': mobile_order_ok,
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
    parser = argparse.ArgumentParser(description='Smoke test for authenticated v6 home surface flows.')
    parser.add_argument('--port', type=int, default=8020, help='Port for temporary runserver.')
    parser.add_argument('--layout-version', default='v6', choices=['v5', 'v6'], help='Authenticated home layout version to exercise.')
    parser.add_argument('--output', default='tmp_teacher_first_home_smoke_latest.json', help='JSON output path (repo-relative or absolute).')
    args = parser.parse_args()

    root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with managed_smoke_database(root):
        data = _prepare_smoke_data()
        base_url = f'http://127.0.0.1:{args.port}'
        runserver_env = os.environ.copy()
        runserver_env.setdefault('PYTHONUNBUFFERED', '1')
        runserver_env['HOME_LAYOUT_VERSION'] = args.layout_version
        runserver_env['FEATURE_MESSAGE_CAPTURE_ENABLED'] = 'True'

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
                    layout_version=args.layout_version,
                )
                tablet = _run_scenario(
                    playwright,
                    label='tablet',
                    base_url=base_url,
                    session_cookie_name=data['session_cookie_name'],
                    session_cookie_value=data['session_cookie_value'],
                    layout_version=args.layout_version,
                    device_name='iPad Pro 11',
                    expect_mobile_layout=True,
                )
                mobile = _run_scenario(
                    playwright,
                    label='mobile',
                    base_url=base_url,
                    session_cookie_name=data['session_cookie_name'],
                    session_cookie_value=data['session_cookie_value'],
                    layout_version=args.layout_version,
                    device_name='iPhone 13',
                    expect_mobile_layout=True,
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
