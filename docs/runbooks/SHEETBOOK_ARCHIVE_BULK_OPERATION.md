# SHEETBOOK 아카이브/복구 다건 운영 가이드

## 1. 목적
- 교무수첩 목록에서 여러 수첩을 한 번에 `아카이브` 또는 `활성 복구`할 때,
  실수 없이 처리하고 결과를 운영 지표로 검증한다.

## 2. 적용 범위
- 화면: `교무수첩 > 내 교무수첩` 목록
- 기능: `체크한 수첩 일괄 처리` 폼
- 엔드포인트: `POST /sheetbook/bulk-archive/`

## 3. 사전 확인
1. 대상 계정이 시트북 접근 권한을 가지고 있는지 확인한다.
2. 필터(`활성/아카이브/전체`)를 업무 목적에 맞게 선택한다.
3. 현재 페이지에서만 선택이 적용됨을 확인한다.

## 4. 표준 처리 절차
1. 목록에서 처리 대상 수첩을 체크한다.
2. 필요하면 `전체 선택`으로 현재 페이지 전체를 선택한다.
3. `아카이브` 또는 `활성으로 되돌리기`를 선택한다.
4. `선택 적용` 버튼을 눌러 처리한다.
5. 성공 메시지의 수량을 확인한다.
   - 변경 수량(`N개 수첩을 ...`)
   - 이미 동일 상태 수량(`이미 아카이브/이미 활성`)
   - 제외 수량(`접근 불가·삭제됨 N개 제외`)

## 5. 메시지 해석 기준
- `선택된 수첩이 없어요...`
  - 체크된 항목이 없는 상태에서 제출된 경우
- `... 접근 불가·삭제됨 N개 제외`
  - 선택 목록에 타 사용자 수첩 id 또는 삭제된 id가 포함된 경우
- `선택한 수첩을 찾을 수 없어요...`
  - 선택된 id가 모두 무효하거나 접근 불가인 경우

## 6. 운영 지표 확인
관리자 지표(`교무수첩 사용 지표`)의 `아카이브/복구` 카드에서 아래를 확인한다.

- 단건 이벤트:
  - `sheetbook_archived_count`
  - `sheetbook_unarchived_count`
- 다건 이벤트:
  - `sheetbook_archive_bulk_updated_count` (실행 횟수)
  - `sheetbook_bulk_archive_changed_count` (다건 보관 변경 건수)
  - `sheetbook_bulk_unarchive_changed_count` (다건 복구 변경 건수)

## 7. 운영 체크리스트
- 매일:
  - 대량 정리 후 지표 카드에서 다건 처리 횟수와 변경 건수 확인
- 주간:
  - 제외(`ignored`) 발생이 반복되면 권한/선택 절차 안내 강화
  - 이미 동일 상태 비율이 높으면 필터 기준 재안내(활성/아카이브 구분)

## 8. 품질 스냅샷 명령
최근 다건 처리 품질 비율을 JSON으로 저장:

```bash
python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14
```

임계치/표본 기준을 조정해 재판정하려면:

```bash
python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14 --min-events 5 --ignored-rate-threshold 10 --unchanged-rate-threshold 50
```

기본 출력:
- `docs/handoff/sheetbook_archive_bulk_snapshot_latest.json`

확인 포인트:
- `quality.has_enough_samples` (표본 5회 이상 여부)
- `quality.sample_gap_count` (목표 표본까지 남은 이벤트 수)
- `rates.ignored_rate_pct`
- `rates.unchanged_rate_pct`
- `quality.needs_attention` + `attention_reasons`
- `quality.thresholds` (이번 판정에 사용한 기준값)
- `quality.next_step` (`collect_more_samples` / `investigate_bulk_flow` / `continue_monitoring`)
