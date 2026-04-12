import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOME_TEMPLATE = REPO_ROOT / 'core' / 'templates' / 'core' / 'home_authenticated_v2.html'


BASE_COMMANDS = [
    ['python', 'manage.py', 'check'],
    ['python', 'scripts/check_teacher_first_static_contracts.py'],
    ['python', 'manage.py', 'test', 'core.tests.test_home_view', '-v', '1'],
    ['python', 'manage.py', 'test', 'core.tests.test_teacher_first_guides', 'products.tests.test_teacher_first_catalog', '-v', '1'],
    ['python', 'manage.py', 'test', 'noticegen.test_workflow_followup', 'consent.test_workflow_seed_prefill', 'signatures.tests.test_workflow_seed_prefill', '-v', '1'],
    ['python', 'manage.py', 'test', 'reservations.tests.ReservationsViewTest', 'parentcomm.tests.ParentCommViewTests', '-v', '1'],
    ['python', 'manage.py', 'test', 'classcalendar.tests.test_entry_route', 'classcalendar.tests.test_message_capture_api', '-v', '1'],
]

BLOCKED_PATTERNS = (
    "You don't have permission to access that port.",
    'Server not ready:',
    'PermissionError: [WinError 5]',
    '액세스가 거부되었습니다',
)


def _run_command(command, *, dry_run=False):
    label = ' '.join(command)
    if dry_run:
        return {'command': label, 'status': 'planned', 'returncode': 0, 'blocked_reason': None}

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=1200,
    )
    stdout_tail = '\n'.join((completed.stdout or '').splitlines()[-20:])
    stderr_tail = '\n'.join((completed.stderr or '').splitlines()[-20:])
    combined_output = '\n'.join(filter(None, [stdout_tail, stderr_tail]))
    blocked_reason = None
    if completed.returncode != 0:
        for pattern in BLOCKED_PATTERNS:
            if pattern in combined_output:
                blocked_reason = pattern
                break
    return {
        'command': label,
        'status': 'passed' if completed.returncode == 0 else ('blocked' if blocked_reason else 'failed'),
        'returncode': completed.returncode,
        'stdout_tail': stdout_tail,
        'stderr_tail': stderr_tail,
        'blocked_reason': blocked_reason,
    }


def _run_inline_js_check(*, dry_run=False):
    label = 'node --check core/templates/core/home_authenticated_v2.html:inline-script'
    if dry_run:
        return {'command': label, 'status': 'planned', 'returncode': 0, 'blocked_reason': None}

    content = HOME_TEMPLATE.read_text(encoding='utf-8')
    match = re.search(r'(?s)<script>\s*(.*?)\s*</script>', content)
    if not match:
        return {
            'command': label,
            'status': 'failed',
            'returncode': 1,
            'stderr_tail': 'inline script block not found',
            'blocked_reason': None,
        }

    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tmp:
        tmp.write(match.group(1))
        temp_path = Path(tmp.name)

    try:
        completed = subprocess.run(
            ['node', '--check', str(temp_path)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        return {
            'command': label,
            'status': 'passed' if completed.returncode == 0 else 'failed',
            'returncode': completed.returncode,
            'stdout_tail': '\n'.join((completed.stdout or '').splitlines()[-20:]),
            'stderr_tail': '\n'.join((completed.stderr or '').splitlines()[-20:]),
            'blocked_reason': None,
        }
    finally:
        temp_path.unlink(missing_ok=True)


def _build_smoke_commands(args):
    commands = []
    if not args.skip_home_smoke:
        commands.append(['python', 'scripts/run_teacher_first_home_smoke.py', '--port', str(args.home_port)])
    return commands


def main():
    parser = argparse.ArgumentParser(description='Teacher-first release gate runner.')
    parser.add_argument('--dry-run', action='store_true', help='Print planned checks without executing them.')
    parser.add_argument('--skip-smoke', action='store_true', help='Skip both browser smoke scripts.')
    parser.add_argument('--skip-calendar-smoke', action='store_true', help='Deprecated compatibility flag.')
    parser.add_argument('--skip-home-smoke', action='store_true', help='Skip home/workbench smoke.')
    parser.add_argument('--smoke-only', action='store_true', help='Run browser smoke checks only.')
    parser.add_argument('--calendar-port', type=int, default=8018)
    parser.add_argument('--home-port', type=int, default=8020)
    parser.add_argument('--output', default='', help='Optional JSON output path.')
    args = parser.parse_args()

    if args.skip_smoke:
        args.skip_calendar_smoke = True
        args.skip_home_smoke = True

    results = []
    if not args.smoke_only:
        for command in BASE_COMMANDS:
            results.append(_run_command(command, dry_run=args.dry_run))
        results.append(_run_inline_js_check(dry_run=args.dry_run))
    for smoke_command in _build_smoke_commands(args):
        results.append(_run_command(smoke_command, dry_run=args.dry_run))

    failed = [item['command'] for item in results if item['status'] == 'failed']
    blocked = [
        {
            'command': item['command'],
            'reason': item.get('blocked_reason') or 'environment blocked',
        }
        for item in results
        if item['status'] == 'blocked'
    ]
    summary = {
        'pass': not failed and not blocked,
        'failed': failed,
        'blocked': blocked,
        'results': results,
    }

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    if summary['pass']:
        return 0
    if blocked and not failed:
        return 2
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
