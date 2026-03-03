# Sheetbook Sample Gap Summary (2026-03-03 21:29:41)

- days: `14`
- overall_ready: `False`
- blockers: pilot_home_opened_gap:5, pilot_create_gap:5, archive_event_gap:5
- json_output: `C:\Users\kakio\eduitit\docs\handoff\sheetbook_sample_gap_summary_latest.json`

## Pilot
- workspace_home_opened: `0`
- home_source_sheetbook_created: `0`
- home_source_action_execute_requested: `0`
- workspace_home_opened_gap: `5`
- home_source_sheetbook_created_gap: `5`

## Archive
- event_count: `0`
- event_gap: `5`
- next_step: `collect_more_samples`

## Next Actions
- 파일럿 이벤트 추가 확보: workspace_home_opened 5건, home_source_sheetbook_created 5건: `python scripts/run_sheetbook_release_readiness.py --days 14`
- 로컬 리허설용 표본 생성(운영 판정 분리): workspace_home_opened 5건, home_source_sheetbook_created 5건: `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --clear-before --home-count 5 --create-count 5 --action-count 3 --archive-event-count 0`
- 아카이브 이벤트 5건 추가 확보 후 품질 판정 재확인: `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- 로컬 리허설용 아카이브 이벤트 5건 생성(운영 판정 분리): `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --home-count 0 --create-count 0 --archive-event-count 5`
- 표본 수집 후 gap summary 재생성: `python scripts/run_sheetbook_sample_gap_summary.py --days 14`
