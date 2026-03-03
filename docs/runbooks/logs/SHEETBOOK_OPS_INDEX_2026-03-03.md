# Sheetbook Ops Index (2026-03-03)

- overall: `GO`
- decision: `GO`
- pilot_hold_for_beta: `True`
- readiness_status: `HOLD`
- manual_pending: (없음)
- sample_gap_blockers: pilot_home_opened_gap:5, pilot_create_gap:5, archive_event_gap:5
- archive_next_step: `collect_more_samples`
- consent_freeze_status: `PASS`
- consent_freeze_reasons: (없음)

## Reports
- daily_start: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_DAILY_START_2026-03-03.md`
- release_signoff: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_RELEASE_SIGNOFF_2026-03-03.md`
- pilot_log: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_PILOT_EVENT_LOG_2026-03-03.md`
- archive_bulk: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_ARCHIVE_BULK_2026-03-03.md`
- sample_gap: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_SAMPLE_GAP_2026-03-03.md`
- consent_freeze: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_CONSENT_FREEZE_2026-03-03.md`
- ops_index: `C:\Users\kakio\eduitit\docs\runbooks\logs\SHEETBOOK_OPS_INDEX_2026-03-03.md`

## Next Actions
- [daily_start] 표본 부족량(blockers) 해소 후 bundle+gap summary 재실행: `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --allow-pilot-hold-for-beta --due-date 2026-03-04 && python scripts/run_sheetbook_sample_gap_summary.py --days 14`
- [sample_gap] 파일럿 이벤트 추가 확보: workspace_home_opened 5건, home_source_sheetbook_created 5건: `python scripts/run_sheetbook_release_readiness.py --days 14`
- [sample_gap] 로컬 리허설용 표본 생성(운영 판정 분리): workspace_home_opened 5건, home_source_sheetbook_created 5건: `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --clear-before --home-count 5 --create-count 5 --archive-event-count 0`
- [sample_gap] 아카이브 이벤트 5건 추가 확보 후 품질 판정 재확인: `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- [sample_gap] 로컬 리허설용 아카이브 이벤트 5건 생성(운영 판정 분리): `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --home-count 0 --create-count 0 --archive-event-count 5`
- [sample_gap] 표본 수집 후 gap summary 재생성: `python scripts/run_sheetbook_sample_gap_summary.py --days 14`
- [decision] 게이트 상태 최신화 후 판정 재생성: `python scripts/run_sheetbook_release_readiness.py --days 14 && python scripts/run_sheetbook_signoff_decision.py`
