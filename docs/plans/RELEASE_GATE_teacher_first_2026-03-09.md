# Teacher-First Release Gate

작성일: 2026-03-09

## One-Command Entry
- Dry-run: `python scripts/check_teacher_first_release_gate.py --dry-run`
- Full gate: `python scripts/check_teacher_first_release_gate.py`
- Smoke 제외 확인: `python scripts/check_teacher_first_release_gate.py --skip-smoke`
- Smoke만 확인: `python scripts/check_teacher_first_release_gate.py --smoke-only`

## Required Commands
- `python manage.py check`
- `python scripts/check_teacher_first_static_contracts.py`
- `python manage.py test core.tests.test_home_view -v 1`
- `python manage.py test noticegen.test_workflow_followup consent.test_workflow_seed_prefill signatures.tests.test_workflow_seed_prefill -v 1`
- `python manage.py test reservations.tests.ReservationsViewTest parentcomm.tests.ParentCommViewTests -v 1`
- `python manage.py test tests.test_sheetbook_navigation_contracts classcalendar.tests.test_sheetbook_bridge classcalendar.tests.test_message_capture_api -v 1`
- 홈 inline JS `node --check`
- `python scripts/run_sheetbook_calendar_embed_smoke.py --port 8018`
- `python scripts/run_teacher_first_home_smoke.py --port 8020`

## Runtime Smoke
### Home / Workbench
- 로그인 후 홈 진입
- `내 작업대` 카드 1개 이상 노출
- `작업대 정리` 진입 후 좌우 버튼으로 위치 변경
- 키보드 좌우 화살표로 위치 변경
- `이 조합 저장` 저장/적용
- 추천 카드 `작업대에 추가`
- 무반응 버튼 없음

### Workflow Bundles
- `noticegen -> consent`
- `noticegen -> signatures`
- `reservations -> noticegen`
- `reservations -> parentcomm`
- 모든 후속 화면에서 원본 복귀 링크 확인

## Environment Notes
- 2026-03-09 local escalated run에서는 브라우저 smoke와 full gate가 실제 통과했다.
- 권한이 제한된 환경에서는 여전히 `blocked`가 날 수 있으며, 이 경우는 코드 실패가 아니라 환경 실패로 분리한다.
- SQLite 개발 DB에서는 브라우저 smoke를 병렬 실행하지 않는다. 반드시 순차 실행한다.

## Accessibility Contract
- 정적 계약 검사에는 홈 작업대의 `aria-live`, 키보드 힌트, 모바일 순서 버튼 라벨도 포함한다.
- focus: 모달/편집 진입 후 초점이 적절히 이동하고, 닫으면 원래 버튼으로 돌아온다.
- dialog: 확인/상세 모달은 dialog semantics를 유지한다.
- keyboard only: 주요 CTA와 작업대 정렬이 키보드만으로 가능하다.
- aria-live: 작업대 순서 변경 같은 비동기 상태는 시각 안내 없이도 알 수 있어야 한다.

## Console Contract
- 주요 교사형 화면에서 `ReferenceError` 0
- 실패한 `fetch`는 모두 사용자 피드백을 남긴다.
- 복사 CTA처럼 권한/브라우저 의존 기능도 실패 피드백 없이 끝나지 않는다.

## Logging / Failure Feedback
- 사용 기록 저장 실패는 조용히 삼키지 않는다.
- seed/follow-up 실패는 fallback 문구 또는 원본 화면 유지로 끝난다.
- 저장/적용/재정렬 실패는 toast 또는 alert로 즉시 보인다.

## Rollback Readiness
- 변경 대상 앱과 범위를 기록한다.
- smoke 실패 시 되돌릴 커밋 범위를 명확히 적는다.
- 임시 스크립트/산출물은 커밋하지 않는다.

## Latest Run
- 2026-03-09 local escalated full gate: `PASS`
- `python scripts/check_teacher_first_release_gate.py` 통과
- `python scripts/run_teacher_first_home_smoke.py --port 8020` desktop / tablet / mobile PASS
- `python scripts/run_sheetbook_calendar_embed_smoke.py --port 8018` PASS

## Pass / Fail
- 위 명령과 정적 계약 검사, smoke가 모두 통과하면 `PASS`
- 접근성/콘솔/후속 복귀/정적 계약 중 하나라도 깨지면 `FAIL`
- smoke가 포트/권한 문제로 실행되지 못하면 `BLOCKED`
