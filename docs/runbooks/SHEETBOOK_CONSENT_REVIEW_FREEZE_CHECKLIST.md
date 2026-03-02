# SHEETBOOK Consent Review Freeze Checklist

## 1. 목적
- `consent_review` 화면의 핵심 UX/계측 요소를 고정해
  파일럿 기간 중 회귀를 빠르게 판별한다.

## 2. 고정 범위 (Freeze Scope)
- 문제 줄 탐지/정리 동선
- 문제 줄 이동 동선(이전/다음/맨 위/맨 아래)
- 제출 가드(유효 수신자 0명 시 비활성화)
- 계측 hidden 필드 및 제출 메타데이터
- QA 식별자(`data-testid`)

## 3. UI 고정 항목
아래 컨트롤은 id/의미를 변경하지 않는다.

- `id="recipients-textarea"`
- `id="recipients-cleanup-btn"`
- `id="recipients-cleanup-undo-btn"`
- `id="recipients-copy-issues-btn"`
- `id="recipients-prev-issue-btn"`
- `id="recipients-next-issue-btn"`
- `data-recipients-jump="top|bottom"`
- `id="recipients-submit-btn"`

## 4. QA 식별자 고정 항목
아래 `data-testid`는 E2E/수동 점검 기준으로 고정한다.

- `recipients-textarea`
- `recipients-cleanup-btn`
- `recipients-cleanup-undo-btn`
- `recipients-copy-issues-btn`
- `recipients-prev-issue-btn`
- `recipients-next-issue-btn`
- `recipients-jump-top-btn`
- `recipients-jump-bottom-btn`
- `recipients-submit-btn`

## 5. 계측 고정 항목
아래 hidden 필드 제출을 유지한다.

- `recipients_cleanup_applied`
- `recipients_cleanup_removed_count`
- `recipients_cleanup_undo_used`
- `recipients_issue_copy_used`
- `recipients_issue_jump_count`

그리고 `consent_review_submitted` 이벤트 메타데이터로 집계 가능해야 한다.

## 6. 회귀 테스트 명령
```bash
python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary
python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1
python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage
python manage.py check
```

## 7. Freeze 승인 기준
- 위 테스트가 모두 통과한다.
- 핵심 버튼 문구/순서가 사용자 가이드와 일치한다.
- QA 식별자와 계측 필드 이름이 변경되지 않는다.
