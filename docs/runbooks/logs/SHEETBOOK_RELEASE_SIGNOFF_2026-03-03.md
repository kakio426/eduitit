# Sheetbook Release Signoff (2026-03-03)

작성일: 2026-03-03  
작성자: sheetbook-ops

## 1) 자동 게이트 스냅샷

- 실행 명령:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
- 최종 판정 명령:
  - `python scripts/run_sheetbook_signoff_decision.py`
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:ok --set production_real_account_signoff=PASS:ok --set real_device_grid_1000_smoke=PASS:ok`
  - (실기기 면제 해제 시) `python scripts/run_sheetbook_signoff_decision.py --no-waive-real-device-smoke`
  - (베타 조건부 GO) `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta --set staging_real_account_signoff=PASS:ok --set production_real_account_signoff=PASS:ok`
  - (조건부 GO 검증 후 복구) `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`
- 출력 파일:
  - `docs/handoff/sheetbook_release_readiness_latest.json`
  - `docs/handoff/sheetbook_manual_signoff_latest.json`
  - `docs/handoff/sheetbook_release_decision_latest.json`
- `overall.status`: HOLD
- `blocking_reasons`: (없음)
- `manual_pending`: (없음)
- `manual_pending_raw(readiness)`: staging_real_account_signoff, production_real_account_signoff
- `waived_manual_checks`: real_device_grid_1000_smoke
- `next_actions` (decision json 자동 추천 명령):
- 게이트 상태 최신화 후 판정 재생성: `python scripts/run_sheetbook_release_readiness.py --days 14 && python scripts/run_sheetbook_signoff_decision.py`
- `decision_context.manual_alias_statuses`:
- `production_real_account_signoff`: `PASS`
- `real_device_grid_1000_smoke`: `PASS`
- `staging_real_account_signoff`: `PASS`

## 2) 수동 게이트 점검

| check_id | env | account_type | result(PASS/HOLD/FAIL) | notes |
|---|---|---|---|---|
| staging_real_account_signoff | staging | allowlisted | PASS | staging-ok |
| staging_real_account_signoff | staging | non_allowlisted | PASS | staging-ok |
| production_real_account_signoff | production | allowlisted | PASS | prod-ok |
| production_real_account_signoff | production | non_allowlisted | PASS | prod-ok |
| real_device_grid_1000_smoke | real-device | teacher | PASS | waived_by_policy(device-unavailable) |

## 3) 최종 판정

- decision: `GO`
- owner: sheetbook-release
- next_action: pilot 표본 보강 + 상태 재판정
- due_date: 2026-03-04
