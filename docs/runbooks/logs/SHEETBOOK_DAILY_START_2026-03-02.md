# Sheetbook Daily Start Bundle (2026-03-02 22:54:06)

- days: 14
- overall: `HOLD`
- decision: `HOLD`
- readiness_status: `HOLD`
- manual_pending: staging_real_account_signoff, production_real_account_signoff
- sample_gap_ready: `False`
- sample_gap_blockers: pilot_home_opened_gap:5, pilot_create_gap:5, archive_event_gap:5
- archive_next_step: `collect_more_samples`
- consent_freeze_status: `PASS`
- json_output: `C:\Users\kakio\eduitit\docs\handoff\sheetbook_daily_start_bundle_latest.json`

## Commands
- [PASS] `python scripts/run_sheetbook_release_readiness.py --days 14`
- [PASS] `python scripts/run_sheetbook_signoff_decision.py`
- [PASS] `python scripts/run_sheetbook_release_signoff_log.py --date 2026-03-02 --author sheetbook-ops --owner sheetbook-release --next-action staging/prod 실계정 점검 --due-date 2026-03-03`
- [PASS] `python manage.py recommend_sheetbook_thresholds --days 14 --group-by-role`
- [PASS] `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
- [PASS] `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- [PASS] `python scripts/run_sheetbook_consent_freeze_snapshot.py`
- [PASS] `python scripts/run_sheetbook_sample_gap_summary.py --days 14`

## Next Actions
- 수동 signoff 완료 후 PASS 반영: `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
- 표본 부족량(blockers) 해소 후 bundle+gap summary 재실행: `python scripts/run_sheetbook_daily_start_bundle.py --days 14 && python scripts/run_sheetbook_sample_gap_summary.py --days 14`

## Sample Gap Next Actions
- 홈 진입 이벤트(workspace_home_opened) 5건 추가 확보: `python scripts/run_sheetbook_release_readiness.py --days 14`
- 홈에서 수첩 생성 이벤트(home_source_sheetbook_created) 5건 추가 확보: `python scripts/run_sheetbook_release_readiness.py --days 14`
- 아카이브 이벤트 5건 추가 확보 후 품질 판정 재확인: `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- 표본 수집 후 gap summary 재생성: `python scripts/run_sheetbook_sample_gap_summary.py --days 14`
