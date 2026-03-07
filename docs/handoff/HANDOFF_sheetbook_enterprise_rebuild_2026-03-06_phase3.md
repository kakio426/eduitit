# Sheetbook Enterprise Rebuild Handoff (2026-03-06)

## Scope
- target_app: sheetbook, classcalendar
- do_not_touch_apps: all others
- branch: feature/sheetbook

## 이번 세션에서 완료한 것
1. `scripts/run_sheetbook_pilot_log_snapshot.py`
   - `role_breakdown` 집계 추가
   - 역할별 counts / rates / recommended 계산 추가
   - markdown의 `## 3) 역할별 스냅샷 참고`가 실제 줄바꿈으로 출력되도록 유지
2. `sheetbook/management/commands/recommend_sheetbook_thresholds.py`
   - `--group-by-role` 옵션 추가
   - role별 funnel 집계 출력 추가
   - 전체 추천 산식과 role별 산식을 같은 패턴으로 정리
3. 검증
   - role 관련 타깃 테스트 통과
   - `sheetbook.tests --failfast` 재실행으로 다음 blocker 확인

## 수정 파일
- `C:\Users\kakio\eduitit\scripts\run_sheetbook_pilot_log_snapshot.py`
- `C:\Users\kakio\eduitit\sheetbook\management\commands\recommend_sheetbook_thresholds.py`

## 통과한 검증
- `git diff --check -- scripts/run_sheetbook_pilot_log_snapshot.py sheetbook/management/commands/recommend_sheetbook_thresholds.py`
- `python manage.py test sheetbook.tests.SheetbookThresholdRecommendationCommandTests.test_recommend_sheetbook_thresholds_outputs_role_breakdown sheetbook.tests.SheetbookPilotLogSnapshotScriptTests.test_pilot_snapshot_includes_role_breakdown sheetbook.tests.SheetbookPilotLogSnapshotScriptTests.test_pilot_markdown_role_section_uses_actual_newlines -v 1`

## 전체 fail-fast 결과
- 명령: `python manage.py test sheetbook.tests --failfast -v 1`
- 진행 결과: 155 tests run, 19 skipped 후 첫 실패 발견

### 현재 blocker
- failing test:
  - `sheetbook.tests.SheetbookConsentFreezeCommandTests.test_check_sheetbook_consent_freeze_fails_when_required_token_missing`
- failure message:
  - `Unknown command: 'check_sheetbook_consent_freeze'`

즉, 다음 작업은 `check_sheetbook_consent_freeze` management command가 없거나 로드되지 않는 문제를 복구하는 것입니다.

## 집에서 바로 이어갈 순서
1. 관련 테스트와 기대값 확인
   - `rg -n "check_sheetbook_consent_freeze|ConsentFreezeCommandTests" sheetbook/tests.py sheetbook/management -S`
2. 명령 파일 존재 여부 확인
   - `rg --files sheetbook/management/commands | rg "consent_freeze|freeze"`
3. 명령이 없으면 추가, 있으면 Django command name / 등록 경로 / 클래스명 확인
4. 타깃 테스트 재실행
   - `python manage.py test sheetbook.tests.SheetbookConsentFreezeCommandTests -v 1`
5. 다시 전체 확인
   - `python manage.py test sheetbook.tests --failfast -v 1`

## 주의 사항
- worktree에 `products/*` 등 unrelated dirty files가 있음. 건드리지 않았음.
- `sheetbook` 작업만 유지할 것.
- 브라우저 스모크까지 이어가려면 이 command blocker 정리 후 다시 판단.
