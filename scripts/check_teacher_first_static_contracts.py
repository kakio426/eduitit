import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

TEMPLATE_RULES = {
    'core/templates/core/home_authenticated_v2.html': {
        'required': [
            '오늘 바로 시작',
            '내 작업대',
            '최근 이어서',
            '새로 써보기',
            'data-workbench-live="true"',
            'aria-live="polite"',
            'id="workbenchKeyboardHint"',
            'aria-describedby="workbenchKeyboardHint"',
            'aria-label="앞으로 이동"',
            'aria-label="뒤로 이동"',
        ],
        'forbidden': [
            '진한 버튼은 바로 만들기',
            '교무수첩 사용 제한',
        ],
    },
    'products/templates/products/list.html': {
        'required': [
            '해야 하는 일을 먼저 찾으세요',
            '핵심 업무',
            '도움말 · 외부 서비스',
        ],
        'forbidden': [
            'Digital Solutions',
            'Play Now',
            '제품을 고르는 화면이 아니라, 지금 해야 하는 일을 바로 찾는 화면으로 정리했습니다.',
        ],
    },
    'core/templates/core/service_guide_list.html': {
        'required': [
            '빠른 사용 안내',
            '막힐 때만 짧게 확인할 수 있도록',
        ],
        'forbidden': [
            '교사들이 먼저 여는 핵심 가이드를 위에 두었습니다.',
            '홈에서 바로 시작하고, 막히는 순간에만 짧게 확인하는 안내만 남겼습니다.',
        ],
    },
    'hwpxchat/templates/hwpxchat/main.html': {
        'required': [
            '공문을 교무수첩 실행업무로 정리하기',
            'HWPX로 저장하는 방법',
        ],
        'forbidden': [
            '서비스 목록으로 돌아가기',
            'HWPX를 AI에 붙여넣을 글로 바꿉니다',
        ],
    },
    'textbooks/templates/textbooks/main.html': {
        'required': [
            '교과서 라이브',
            '수업 자료를 저장하고 바로 수업에 씁니다',
            '저장한 자료',
        ],
        'forbidden': [
            'PDF Live Classroom',
            '내 자료실',
        ],
    },
    'reservations/templates/reservations/dashboard.html': {
        'required': [
            "copyError: ''",
            '복사에 실패했습니다. 다시 시도해 주세요.',
            'navigator.clipboard.writeText(text).then(() => {',
        ],
        'forbidden': [
            'navigator.clipboard.writeText(text);',
        ],
    },
    'products/templates/products/mobile_not_supported.html': {
        'required': [
            '큰 화면에서 먼저 쓰는 기능',
            '홈으로',
        ],
        'forbidden': [
            '그래도 계속 진행',
            '모바일 미지원',
        ],
    },
    'noticegen/templates/noticegen/partials/result_panel.html': {
        'required': [
            "copyError: ''",
            '@click="copyText($refs.output.value)"',
            '복사에 실패했습니다. 직접 선택해 복사해 주세요.',
            '필요할 때 참고 문장 보기',
        ],
        'forbidden': [
            'navigator.clipboard.writeText($refs.output.value); copied = true;',
        ],
    },
    'parentcomm/templates/parentcomm/main.html': {
        'required': [
            "copyError: ''",
            '@click="copyLink($el.dataset.link)"',
            '복사에 실패했습니다. 링크를 눌러 직접 열어 주세요.',
            '더보기',
            '알림장과 연락처',
        ],
        'forbidden': [
            'navigator.clipboard.writeText($el.dataset.link); copied=true;',
        ],
    },
    'signatures/templates/signatures/maker.html': {
        'required': [
            '서명 목록으로',
            '보관함은 나중에 켜기',
            '서명 스타일을 저장했습니다.',
        ],
        'forbidden': [
            '연수 서명으로 돌아가기',
            '보관함이 필요하면 계정을 만드세요',
        ],
    },
    'core/templates/core/includes/mini_card.html': {
        'required': [
            'teacher_first_task_label|default:product.title',
            'teacher_first_support_label|truncatechars:72',
            '서비스 설명',
        ],
        'forbidden': [
            'product.solve_text',
            'truncatechars:40',
        ],
    },
}


def check_rules() -> dict:
    results = []
    failures = []
    for relative_path, rules in TEMPLATE_RULES.items():
        path = REPO_ROOT / relative_path
        content = path.read_text(encoding='utf-8')
        missing = [item for item in rules.get('required', []) if item not in content]
        present_forbidden = [item for item in rules.get('forbidden', []) if item in content]
        status = 'passed' if not missing and not present_forbidden else 'failed'
        row = {
            'path': relative_path,
            'status': status,
            'missing': missing,
            'present_forbidden': present_forbidden,
        }
        results.append(row)
        if status == 'failed':
            failures.append(row)
    return {
        'pass': not failures,
        'results': results,
        'failures': failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Check teacher-first static template contracts.')
    parser.add_argument('--output', default='', help='Optional JSON output path.')
    args = parser.parse_args()

    summary = check_rules()
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

