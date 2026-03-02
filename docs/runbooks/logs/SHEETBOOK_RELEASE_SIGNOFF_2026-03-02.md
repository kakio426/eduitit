# Sheetbook Release Signoff (2026-03-02)

작성일: 2026-03-02  
작성자: codex-local

## 1) 자동 게이트 스냅샷

- 실행 명령:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`
- 출력 파일:
  - `docs/handoff/sheetbook_release_readiness_latest.json`
  - `docs/handoff/sheetbook_manual_signoff_latest.json`
  - `docs/handoff/sheetbook_release_decision_latest.json`
- 집계 시각:
  - readiness: `2026-03-02 18:56:54`
  - decision/manual: `2026-03-02 19:00:07`
- `overall.status`:
  - `HOLD`
- `blocking_reasons`:
  - 없음(자동 게이트 통과)
- `manual_pending`:
  - `staging_real_account_signoff`
  - `production_real_account_signoff`
- `waived_manual_checks`:
  - `real_device_grid_1000_smoke`
- `next_actions` (자동 추천):
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
  - `python scripts/run_sheetbook_release_readiness.py --days 14 && python scripts/run_sheetbook_signoff_decision.py`
- `decision_context.manual_alias_statuses`:
  - `staging_real_account_signoff=HOLD`
  - `production_real_account_signoff=HOLD`
  - `real_device_grid_1000_smoke=PASS`

## 2) 수동 게이트 점검

| check_id | env | account_type | result(PASS/HOLD/FAIL) | notes |
|---|---|---|---|---|
| staging_real_account_signoff | staging | allowlisted | HOLD | pending |
| staging_real_account_signoff | staging | non_allowlisted | HOLD | pending |
| production_real_account_signoff | production | allowlisted | HOLD | pending |
| production_real_account_signoff | production | non_allowlisted | HOLD | pending |
| real_device_grid_1000_smoke | real-device | teacher | PASS(waived) | waived_by_policy(device-unavailable) |

## 3) 추가 점검

- 다건 아카이브 품질 스냅샷:
  - 실행: `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
  - 결과: `event_count=0`, `has_enough_samples=false`, `needs_attention=false`
- freeze 회귀 빠른 점검:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary` -> OK
  - `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate` -> OK

## 4) 최종 판정

- decision: `HOLD`
- owner: 운영 담당
- next_action:
  - staging/production 실계정 signoff 2건 수행 후 PASS 반영
  - 다건 아카이브 실사용 표본(`event_count>=5`) 확보 후 비율 재판정
- due_date:
  - 수동 signoff 확보 즉시 재판정
