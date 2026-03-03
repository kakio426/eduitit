# Sheetbook Local Rehearsal Cycle Workflow

작성일: 2026-03-03  
대상 브랜치: `feature/sheetbook`

## 목적

- 표본 gap 해소 리허설을 한 번의 명령으로 실행한다.
- 실행 순서:
  1. 표본 수집(clear-before)
  2. bundle/gap 재집계
  3. 수집 데이터 clear-only
  4. bundle/gap 재집계(복구 상태 확인)

## 기본 실행

```bash
python scripts/run_sheetbook_local_rehearsal_cycle.py \
  --days 14 \
  --home-count 5 \
  --create-count 5 \
  --action-count 3 \
  --archive-event-count 5 \
  --allow-pilot-hold-for-beta \
  --due-date 2026-03-04
```

## 출력 파일

- cycle 요약:
  - `docs/handoff/smoke_sheetbook_local_rehearsal_cycle_latest.json`
- 수집 단계:
  - `docs/handoff/smoke_sheetbook_collect_samples_bundle_latest.json`
- clear 단계:
  - `docs/handoff/smoke_sheetbook_collect_samples_bundle_clear_latest.json`
- 후속 재집계 결과:
  - `docs/handoff/sheetbook_daily_start_bundle_latest.json`
  - `docs/handoff/sheetbook_sample_gap_summary_latest.json`

## 참고

- `collect_samples_local_rehearsal` next action은 이제 위 스크립트를 직접 호출한다.
- `--due-date`가 비정상 형식이면 내부에서 생략 처리되고 `warnings`에 기록된다.
