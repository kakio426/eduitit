# Sheetbook Release Signoff (Template)

작성일: YYYY-MM-DD  
작성자:

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
- `overall.status`:
- `blocking_reasons`:
- `manual_pending`:
- `waived_manual_checks`:
- `next_actions` (decision json 자동 추천 명령):
- `decision_context.manual_alias_statuses`:

## 2) 수동 게이트 점검

| check_id | env | account_type | result(PASS/HOLD/FAIL) | notes |
|---|---|---|---|---|
| staging_real_account_signoff | staging | allowlisted |  |  |
| staging_real_account_signoff | staging | non_allowlisted |  |  |
| production_real_account_signoff | production | allowlisted |  |  |
| production_real_account_signoff | production | non_allowlisted |  |  |
| real_device_grid_1000_smoke | real-device | teacher |  |  |

## 3) 최종 판정

- decision: `GO / HOLD / STOP`
- owner:
- next_action:
- due_date:
