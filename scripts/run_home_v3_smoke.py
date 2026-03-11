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

    from datetime import timedelta

    from django.conf import settings as django_settings
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.utils import timezone

    from classcalendar.models import CalendarEvent
    from core.models import Post, ProductFavorite, ProductUsageLog, UserProfile
    from products.models import Product
    from sheetbook.models import SheetCell, SheetColumn, SheetRow, SheetTab, Sheetbook

    user_model = get_user_model()
    username = 'home_v3_smoke_teacher'
    password = 'HomeV3Smoke!2026'
    email = 'home-v3-smoke@example.com'
    run_token = int(time.time())

    user, _ = user_model.objects.get_or_create(
        username=username,
        defaults={'email': email},
    )
    user.email = email
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_password(password)
    user.save(update_fields=['email', 'is_active', 'is_staff', 'is_superuser', 'password'])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = 'v3스모크'
    profile.role = 'school'
    profile.save(update_fields=['nickname', 'role'])

    staff_user, _ = user_model.objects.get_or_create(
        username='home_v3_smoke_staff',
        defaults={'email': 'home-v3-smoke-staff@example.com'},
    )
    staff_user.email = 'home-v3-smoke-staff@example.com'
    staff_user.is_active = True
    staff_user.is_staff = True
    staff_user.is_superuser = True
    staff_user.set_password(password)
    staff_user.save(update_fields=['email', 'is_active', 'is_staff', 'is_superuser', 'password'])
    staff_profile, _ = UserProfile.objects.get_or_create(user=staff_user)
    staff_profile.nickname = '운영'
    staff_profile.role = 'school'
    staff_profile.save(update_fields=['nickname', 'role'])

    product_specs = [
        {
            'slug': 'featured',
            'title': '[smoke-v3] 오늘 학급 운영',
            'description': '오늘 수업과 학급 운영을 바로 이어갑니다.',
            'service_type': 'classroom',
            'solve_text': '오늘 학급 운영을 바로 시작합니다.',
            'icon': 'fa-solid fa-book-open',
            'display_order': -210,
            'is_featured': True,
        },
        {
            'slug': 'collect',
            'title': '[smoke-v3] 동의서 확인',
            'description': '수합과 동의서 확인 흐름을 빠르게 엽니다.',
            'service_type': 'collect_sign',
            'solve_text': '동의서 진행 상태를 바로 확인합니다.',
            'icon': 'fa-solid fa-signature',
            'display_order': -209,
            'is_featured': False,
        },
        {
            'slug': 'notice',
            'title': '[smoke-v3] 안내문 작성',
            'description': '가정통신문과 안내문 작성을 바로 시작합니다.',
            'service_type': 'work',
            'solve_text': '안내문 초안을 빠르게 만듭니다.',
            'icon': 'fa-solid fa-file-lines',
            'display_order': -208,
            'is_featured': False,
        },
        {
            'slug': 'calendar',
            'title': '[smoke-v3] 일정 정리',
            'description': '학급 일정을 홈과 캘린더에서 이어서 관리합니다.',
            'service_type': 'classroom',
            'solve_text': '일정을 빠르게 정리합니다.',
            'icon': 'fa-solid fa-calendar-days',
            'display_order': -207,
            'is_featured': False,
        },
        {
            'slug': 'game',
            'title': '[smoke-v3] 교실 활동',
            'description': '학생과 바로 시작하는 활동 도구입니다.',
            'service_type': 'game',
            'solve_text': '교실 활동을 곧바로 엽니다.',
            'icon': 'fa-solid fa-chess-knight',
            'display_order': -206,
            'is_featured': False,
        },
        {
            'slug': 'guide',
            'title': '[smoke-v3] 서비스 가이드',
            'description': '새 도구를 차분히 읽어보고 시작합니다.',
            'service_type': 'edutech',
            'solve_text': '가이드를 먼저 확인합니다.',
            'icon': 'fa-solid fa-lightbulb',
            'display_order': -205,
            'is_featured': False,
        },
    ]

    products: dict[str, Product] = {}
    for spec in product_specs:
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
        product.is_featured = spec['is_featured']
        product.launch_route_name = ''
        product.external_url = ''
        product.save(
            update_fields=[
                'description',
                'price',
                'is_active',
                'service_type',
                'solve_text',
                'icon',
                'display_order',
                'is_featured',
                'launch_route_name',
                'external_url',
            ]
        )
        products[spec['slug']] = product

    ProductFavorite.objects.filter(user=user).delete()
    ProductUsageLog.objects.filter(user=user).delete()
    ProductFavorite.objects.create(user=user, product=products['featured'], pin_order=1)
    ProductFavorite.objects.create(user=user, product=products['notice'], pin_order=2)
    ProductUsageLog.objects.create(user=user, product=products['calendar'], action='launch', source='home_quick')
    ProductUsageLog.objects.create(user=user, product=products['calendar'], action='launch', source='home_quick')
    ProductUsageLog.objects.create(user=user, product=products['collect'], action='launch', source='home_quick')

    Post.objects.filter(content__startswith='[smoke-v3]').delete()
    Post.objects.create(
        author=user,
        content='[smoke-v3] 오늘 학급 운영에서 바로 확인할 공지입니다.',
        post_type='general',
        approval_status='approved',
    )
    Post.objects.create(
        author=staff_user,
        content='[smoke-v3] 읽어볼 운영 링크',
        post_type='news_link',
        approval_status='approved',
        source_url='https://example.com/home-v3-smoke',
        og_title='[smoke-v3] 홈 운영 읽을거리',
        og_description='홈 v3 읽을거리 카드가 상단 구조를 방해하지 않는지 확인하는 링크입니다.',
        og_image_url='https://example.com/home-v3-smoke.jpg',
        publisher='스모크 운영실',
    )

    now = timezone.now()
    today_event, _ = CalendarEvent.objects.get_or_create(
        title='[smoke-v3] 오늘 상담 준비',
        author=user,
        defaults={
            'start_time': now.replace(hour=9, minute=0, second=0, microsecond=0),
            'end_time': now.replace(hour=10, minute=0, second=0, microsecond=0),
            'is_all_day': False,
            'color': 'indigo',
        },
    )
    today_event.start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    today_event.end_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    today_event.is_all_day = False
    today_event.color = 'indigo'
    today_event.save(update_fields=['start_time', 'end_time', 'is_all_day', 'color'])

    week_event, _ = CalendarEvent.objects.get_or_create(
        title='[smoke-v3] 이번 주 학년 회의',
        author=user,
        defaults={
            'start_time': (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0),
            'end_time': (now + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0),
            'is_all_day': False,
            'color': 'emerald',
        },
    )
    week_event.start_time = (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    week_event.end_time = (now + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
    week_event.is_all_day = False
    week_event.color = 'emerald'
    week_event.save(update_fields=['start_time', 'end_time', 'is_all_day', 'color'])

    row_title = '[smoke-v3] 학부모 연락 정리'
    sheetbook = Sheetbook.objects.create(
        owner=user,
        title=f'[smoke-v3] 2026 3-2반 운영 기록 {run_token}',
        academic_year=2026,
    )
    tab = SheetTab.objects.create(
        sheetbook=sheetbook,
        name='오늘 일정',
        tab_type=SheetTab.TYPE_GRID,
        sort_order=1,
    )
    col_title = SheetColumn.objects.create(
        tab=tab,
        key='title',
        label='제목',
        column_type=SheetColumn.TYPE_TEXT,
        sort_order=1,
    )
    col_date = SheetColumn.objects.create(
        tab=tab,
        key='date',
        label='날짜',
        column_type=SheetColumn.TYPE_DATE,
        sort_order=2,
    )
    row = SheetRow.objects.create(
        tab=tab,
        sort_order=1,
        created_by=user,
        updated_by=user,
    )
    SheetCell.objects.create(row=row, column=col_title, value_text=row_title)
    SheetCell.objects.create(row=row, column=col_date, value_date=timezone.localdate())

    client = Client()
    client.force_login(user)
    session_cookie_name = django_settings.SESSION_COOKIE_NAME
    session_cookie_value = client.cookies[session_cookie_name].value

    return {
        'username': username,
        'password': password,
        'session_cookie_name': session_cookie_name,
        'session_cookie_value': session_cookie_value,
        'featured_product_id': products['featured'].id,
        'home_path': '/',
        'record_board_row_title': row_title,
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


def _normalize_href(base_url: str, href: str) -> str:
    if href.startswith('http://') or href.startswith('https://'):
        return href
    if href.startswith('/'):
        return f'{base_url}{href}'
    return f'{base_url}/{href.lstrip("/")}'


def _assert_slot_order(page) -> None:
    order = page.evaluate(
        """
        () => ['primary-zone', 'discovery-sections', 'secondary-sections']
            .map((id) => [...document.querySelectorAll('section')].findIndex((el) => el.id === id))
        """
    )
    if order != sorted(order) or any(index < 0 for index in order):
        raise RuntimeError(f'unexpected section order: {order}')


def _open_and_close_search(page) -> None:
    page.locator('[data-home-v3-search="true"]').first.click(timeout=10000)
    page.wait_for_function("() => !!document.getElementById('searchModal') && !document.getElementById('searchModal').classList.contains('hidden')")
    page.keyboard.press('Escape')
    page.wait_for_function("() => !!document.getElementById('searchModal') && document.getElementById('searchModal').classList.contains('hidden')")


def _toggle_favorite(page) -> dict[str, str]:
    from playwright.sync_api import expect

    button = page.locator('[data-favorite-toggle="true"]').first
    button.wait_for(state='visible', timeout=10000)
    product_id = button.get_attribute('data-product-id') or ''
    before = button.get_attribute('aria-pressed') or 'false'
    button.click(timeout=10000)
    expect(button).not_to_have_attribute('aria-pressed', before, timeout=10000)
    after = button.get_attribute('aria-pressed') or 'false'
    return {'product_id': product_id, 'before': before, 'after': after}


def _toggle_sns_panel(page) -> None:
    toggle = page.locator('[data-home-v3-sns-toggle="true"]').first
    toggle.click(timeout=10000)
    page.locator('textarea[name="content"]').wait_for(state='visible', timeout=10000)
    toggle.click(timeout=10000)
    page.wait_for_timeout(300)


def _open_first_related_shortcut(page, base_url: str) -> str:
    card = page.locator('[data-home-v3-related-shortcuts="true"] a').first
    card.wait_for(state='visible', timeout=10000)
    href = card.get_attribute('href') or ''
    target_url = _normalize_href(base_url, href)
    card.click(timeout=10000)
    page.wait_for_url(target_url, timeout=15000)
    current_url = page.url
    page.go_back(wait_until='networkidle', timeout=15000)
    page.locator('#primary-zone').wait_for(state='visible', timeout=10000)
    return current_url


def _calendar_week_count(page) -> int:
    raw = page.locator('[data-home-v3-calendar-week-count="true"]').inner_text(timeout=10000).strip()
    return int(raw or '0')


def _submit_calendar_quick_add(page) -> str:
    from datetime import datetime, timedelta
    from playwright.sync_api import expect

    title = f'[smoke-v3] 빠른 일정 {int(time.time())}'
    now = datetime.now().replace(second=0, microsecond=0)
    start_at = (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
    end_at = (now + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
    week_count_before = _calendar_week_count(page)
    page.locator('[data-home-v3-calendar-add="true"]').click(timeout=10000)
    page.get_by_role('heading', name='일정 빠른 추가').wait_for(state='visible', timeout=10000)
    page.locator('input[x-model="form.title"]').fill(title, timeout=10000)
    page.locator('input[x-model="form.start_time"]').fill(start_at, timeout=10000)
    page.locator('input[x-model="form.end_time"]').fill(end_at, timeout=10000)
    page.locator('textarea[x-model="form.note"]').fill('홈 v3 스모크로 등록한 일정입니다.', timeout=10000)
    page.get_by_role('button', name='저장').click(timeout=10000)
    page.wait_for_load_state('networkidle', timeout=20000)
    page.locator('#primary-zone').wait_for(state='visible', timeout=10000)
    expect(page.locator('[data-home-v3-calendar-week-count="true"]')).to_have_text(str(week_count_before + 1), timeout=10000)
    return title


def _create_browser_context(playwright, *, session_cookie_name: str | None = None, session_cookie_value: str | None = None, device_name: str | None = None):
    browser = playwright.chromium.launch(headless=True)
    if device_name:
        device = playwright.devices[device_name]
        context = browser.new_context(**device)
    else:
        context = browser.new_context(viewport={'width': 1536, 'height': 960})

    if session_cookie_name and session_cookie_value:
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
    return browser, context


def _run_scenario(playwright, *, label: str, base_url: str, session_cookie_name: str | None = None, session_cookie_value: str | None = None, device_name: str | None = None, step) -> dict[str, Any]:
    browser, context = _create_browser_context(
        playwright,
        session_cookie_name=session_cookie_name,
        session_cookie_value=session_cookie_value,
        device_name=device_name,
    )
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
        page.locator('#primary-zone').wait_for(state='visible', timeout=15000)
        _assert_slot_order(page)
        result.update(step(page))
        result['pass'] = not console_errors and not fatal_console_warnings
        return result
    except Exception as exc:
        result['error'] = str(exc)
        return result
    finally:
        context.close()
        browser.close()


def _anonymous_step(page) -> dict[str, Any]:
    page.get_by_role('heading', name='학급 하루를 캘린더에서 시작하세요').wait_for(state='visible', timeout=10000)
    _open_and_close_search(page)
    preview_count = page.locator('.sns-preview-card').count()
    return {
        'search_modal_ok': True,
        'sns_preview_count': preview_count,
    }


def _authenticated_step(page, *, expect_sheetbook_enabled: bool, record_board_row_title: str) -> dict[str, Any]:
    page.get_by_role('heading', name='오늘 해야 하는 것').wait_for(state='visible', timeout=10000)
    _open_and_close_search(page)
    favorite_result = _toggle_favorite(page)
    launched_url = _open_first_related_shortcut(page, page.url.split('/', 3)[0] + '//' + page.url.split('/', 3)[2])
    _toggle_sns_panel(page)
    created_title = _submit_calendar_quick_add(page)
    page_text = page.locator('body').inner_text(timeout=10000)
    if '교무수첩' in page_text:
        raise RuntimeError('unexpected legacy public term on home v3')
    if expect_sheetbook_enabled and record_board_row_title not in page_text:
        raise RuntimeError('expected record board continue item in calendar hub')
    if not expect_sheetbook_enabled and record_board_row_title in page_text:
        raise RuntimeError('record board continue item should stay hidden when sheetbook is disabled')
    return {
        'favorite_toggle': favorite_result,
        'launched_url': launched_url,
        'calendar_created_title': created_title,
        'record_board_enabled': expect_sheetbook_enabled,
    }


def _mobile_step(page) -> dict[str, Any]:
    page.get_by_role('heading', name='오늘 해야 하는 것').wait_for(state='visible', timeout=10000)
    _toggle_sns_panel(page)
    return {
        'sns_toggled': True,
        'viewport_width': page.viewport_size['width'] if page.viewport_size else None,
    }


def _evaluate(summary: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    for label in ('anonymous_desktop', 'authenticated_desktop_off', 'authenticated_mobile_off', 'authenticated_desktop_on'):
        scenario = summary[label]
        if not scenario.get('pass'):
            failures.append(label)
        if scenario.get('console_errors'):
            failures.append(f'{label}:console_errors')
        if scenario.get('fatal_console_warnings'):
            failures.append(f'{label}:console_warnings')
    return {'pass': not failures, 'failed_checks': failures}


def _run_server(*, port: int, home_layout_version: str, sheetbook_enabled: bool, sheetbook_discovery_visible: bool):
    root = _repo_root()
    runserver_env = os.environ.copy()
    runserver_env.setdefault('PYTHONUNBUFFERED', '1')
    runserver_env['HOME_LAYOUT_VERSION'] = home_layout_version
    runserver_env['SHEETBOOK_ENABLED'] = 'True' if sheetbook_enabled else 'False'
    runserver_env['SHEETBOOK_DISCOVERY_VISIBLE'] = 'True' if sheetbook_discovery_visible else 'False'
    return subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'],
        cwd=str(root),
        env=runserver_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_server(server_proc) -> None:
    if server_proc.poll() is None:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description='Smoke test for home v3 core flows.')
    parser.add_argument('--port-off', type=int, default=8030, help='Port for HOME_LAYOUT_VERSION=v3 + Sheetbook off server.')
    parser.add_argument('--port-on', type=int, default=8031, help='Port for HOME_LAYOUT_VERSION=v3 + Sheetbook on server.')
    parser.add_argument('--output', default='', help='Optional JSON output path.')
    args = parser.parse_args()

    data = _prepare_smoke_data()
    started_at = time.strftime('%Y-%m-%d %H:%M:%S')

    summary: dict[str, Any] = {
        'started_at': started_at,
        'dataset': data,
    }

    off_server = _run_server(
        port=args.port_off,
        home_layout_version='v3',
        sheetbook_enabled=False,
        sheetbook_discovery_visible=False,
    )
    try:
        off_base_url = f'http://127.0.0.1:{args.port_off}'
        _wait_for_http(f'{off_base_url}/health/', timeout_sec=90)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            summary['anonymous_desktop'] = _run_scenario(
                playwright,
                label='anonymous_desktop',
                base_url=off_base_url,
                step=_anonymous_step,
            )
            summary['authenticated_desktop_off'] = _run_scenario(
                playwright,
                label='authenticated_desktop_off',
                base_url=off_base_url,
                session_cookie_name=data['session_cookie_name'],
                session_cookie_value=data['session_cookie_value'],
                step=lambda page: _authenticated_step(
                    page,
                    expect_sheetbook_enabled=False,
                    record_board_row_title=data['record_board_row_title'],
                ),
            )
            summary['authenticated_mobile_off'] = _run_scenario(
                playwright,
                label='authenticated_mobile_off',
                base_url=off_base_url,
                session_cookie_name=data['session_cookie_name'],
                session_cookie_value=data['session_cookie_value'],
                device_name='iPhone 13',
                step=_mobile_step,
            )
    finally:
        _stop_server(off_server)

    on_server = _run_server(
        port=args.port_on,
        home_layout_version='v3',
        sheetbook_enabled=True,
        sheetbook_discovery_visible=True,
    )
    try:
        on_base_url = f'http://127.0.0.1:{args.port_on}'
        _wait_for_http(f'{on_base_url}/health/', timeout_sec=90)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            summary['authenticated_desktop_on'] = _run_scenario(
                playwright,
                label='authenticated_desktop_on',
                base_url=on_base_url,
                session_cookie_name=data['session_cookie_name'],
                session_cookie_value=data['session_cookie_value'],
                step=lambda page: _authenticated_step(
                    page,
                    expect_sheetbook_enabled=True,
                    record_board_row_title=data['record_board_row_title'],
                ),
            )
    finally:
        _stop_server(on_server)

    summary['evaluation'] = _evaluate(summary)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = _repo_root() / output_path
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    sys.stdout.buffer.write(json.dumps(summary, ensure_ascii=False).encode('utf-8'))
    sys.stdout.buffer.write(b'\n')
    return 0 if summary['evaluation']['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
