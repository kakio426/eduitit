# Sheetbook Daily Start Bundle (2026-03-03 23:16:59)

- days: 14
- overall: `GO`
- decision: `GO`
- pilot_hold_for_beta: `True`
- readiness_status: `HOLD`
- manual_pending: (없음)
- manual_pending_raw(readiness): staging_real_account_signoff, production_real_account_signoff
- sample_gap_ready: `False`
- sample_gap_blockers: pilot_home_opened_gap:5, pilot_create_gap:5, archive_event_gap:5
- archive_next_step: `collect_more_samples`
- archive_report: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_ARCHIVE_BULK_2026-03-03.md`
- consent_freeze_status: `PASS`
- consent_freeze_reasons: (없음)
- consent_freeze_report: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_CONSENT_FREEZE_2026-03-03.md`
- ops_index_report: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_OPS_INDEX_2026-03-03.md`
- json_output: `C:\Users\kakio\eduitit\docs\handoff\sheetbook_daily_start_bundle_latest.json`

## Commands
- [PASS] `python scripts/run_sheetbook_release_readiness.py --days 14`
- [PASS] `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta`
- [PASS] `python scripts/run_sheetbook_release_signoff_log.py --date 2026-03-03 --author sheetbook-ops --owner sheetbook-release --next-action pilot 표본 보강 + 상태 재판정 --due-date 2026-03-04`
- [PASS] `python manage.py recommend_sheetbook_thresholds --days 14 --group-by-role`
- [PASS] `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
- [PASS] `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- [PASS] `python scripts/run_sheetbook_consent_freeze_snapshot.py`
- [PASS] `python scripts/run_sheetbook_sample_gap_summary.py --days 14`
- [PASS] `python scripts/run_sheetbook_ops_index_report.py --record-date 2026-03-03 --daily-start C:\Users\kakio\eduitit\docs\handoff\sheetbook_daily_start_bundle_latest.json --output C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_OPS_INDEX_2026-03-03.md`

## Next Actions
- 표본 부족량(blockers) 해소 후 bundle+gap summary 재실행: `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --allow-pilot-hold-for-beta --due-date 2026-03-04 && python scripts/run_sheetbook_sample_gap_summary.py --days 14`
- 로컬 리허설 사이클 실행(수집 -> 검증 -> clear -> 상태 복구): `python scripts/run_sheetbook_local_rehearsal_cycle.py --days 14 --home-count 5 --create-count 5 --action-count 3 --archive-event-count 5 --allow-pilot-hold-for-beta --due-date 2026-03-04`

## Sample Gap Next Actions
- 파일럿 이벤트 추가 확보(누적): workspace_home_opened 5건, home_source_sheetbook_created 5건: `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --home-count 5 --create-count 5 --action-count 3 --archive-event-count 0 --output docs/handoff/smoke_sheetbook_collect_pilot_samples_progress_latest.json`
- 로컬 리허설용 표본 생성(운영 판정 분리): workspace_home_opened 5건, home_source_sheetbook_created 5건: `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --clear-before --home-count 5 --create-count 5 --action-count 3 --archive-event-count 0 --output docs/handoff/smoke_sheetbook_collect_pilot_samples_latest.json`
- 아카이브 이벤트 5건 추가 확보 후 품질 판정 재확인: `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- 로컬 리허설용 아카이브 이벤트 5건 생성(운영 판정 분리): `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --home-count 0 --create-count 0 --archive-event-count 5 --output docs/handoff/smoke_sheetbook_collect_archive_events_latest.json`
- 로컬 통합 리허설 사이클 1회 실행(수집 -> 검증 -> clear -> 복구): `python scripts/run_sheetbook_local_rehearsal_cycle.py --days 14 --home-count 5 --create-count 5 --action-count 3 --archive-event-count 5 --allow-pilot-hold-for-beta`
- 표본 수집 후 gap summary 재생성: `python scripts/run_sheetbook_sample_gap_summary.py --days 14`
