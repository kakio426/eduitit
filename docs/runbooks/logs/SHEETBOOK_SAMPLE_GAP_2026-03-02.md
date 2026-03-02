# Sheetbook Sample Gap Summary (2026-03-02 22:48:27)

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
- 홈 진입 이벤트(workspace_home_opened) 5건 추가 확보: `python scripts/run_sheetbook_release_readiness.py --days 14`
- 홈에서 수첩 생성 이벤트(home_source_sheetbook_created) 5건 추가 확보: `python scripts/run_sheetbook_release_readiness.py --days 14`
- 아카이브 이벤트 5건 추가 확보 후 품질 판정 재확인: `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- 표본 수집 후 gap summary 재생성: `python scripts/run_sheetbook_sample_gap_summary.py`
