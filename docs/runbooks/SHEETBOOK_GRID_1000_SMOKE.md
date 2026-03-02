# Sheetbook 1000-Row Browser Smoke Runbook

작성일: 2026-03-01  
대상: `SB-006` 1,000행 그리드 체감 성능 검증

## 1) 목적

- 데스크톱/태블릿에서 `?grid_limit=1000` 로딩 시 교사 사용 맥락(조회/스크롤/편집)에서 체감 성능을 확인한다.
- 콘솔 성능 로그(`render_ms`, `mode`, `chunks`, `chunk_size`)와 실제 체감(입력 지연, 스크롤 끊김)을 함께 기록한다.
- 병목이 보이면 다음 조치(청크 튜닝 유지 vs 가상 스크롤 착수)를 결정한다.

## 2) 사전 조건

- 최신 코드 반영 후 아래 점검 통과:
  - `python manage.py check`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_grid_uses_sanitized_grid_limit_for_smoke sheetbook.tests.SheetbookGridApiTests.test_grid_data_limit_is_capped_to_1000 sheetbook.tests.SheetbookGridApiTests.test_detail_grid_renders_action_layer_ui`
- 테스트용 교무수첩에 그리드 탭 데이터 1,000행 준비
- 브라우저 개발자도구 Console 열어 성능 로그 수집 가능 상태

## 3) 실행 절차

### 자동 실행(권장 1회)

- 명령:
  - `python scripts/run_sheetbook_grid_smoke.py`
- 옵션(환경 편차 보정):
  - `--max-final-render-ms` (기본 2000, PASS 하드 기준)
  - `--warn-initial-render-ms` (기본 3000, 경고 기준)
- 산출물:
  - `docs/handoff/smoke_sheetbook_grid_1000_latest.json`
- 참고:
  - 데스크톱 + 태블릿(iPad Pro 11 에뮬레이션)까지 한 번에 측정된다.

### A. 데스크톱 시나리오(필수)

1. 교무수첩 상세 진입:
   - URL 예시: `/sheetbook/<sheetbook_id>/?tab=<grid_tab_id>&grid_limit=1000`
2. 초기 렌더 확인:
   - 첫 화면 표시까지의 체감 대기 시간 기록
   - 콘솔 로그에서 `render_ms`, `mode(sync|chunked)` 기록
3. 스크롤 시나리오:
   - 상단 -> 중간(약 500행) -> 하단(1000행 근처) 이동
   - 끊김/튐/지연 여부를 5점 척도로 기록
4. 편집 시나리오:
   - 상단/중간/하단에서 각 5셀 수정 후 저장 반응 확인
   - 입력 반영 지연(ms 체감)과 실패/재시도 UI 여부 기록
5. 액션바 영향 확인:
   - 범위 선택 후 액션바 노출/해제 시 프레임 저하 체감 기록

### B. 태블릿 시나리오(필수)

1. 동일 URL로 진입(`grid_limit=1000`)
2. 손가락 스크롤 연속 3회(상/중/하 왕복) 수행
3. 셀 탭-편집-저장 10회 반복
4. 키보드 표시/숨김 전환 시 하단 UI 겹침/밀림 여부 기록

## 4) 합격 기준(Pass/Fail)

- `PASS`
  - 콘솔 `final_render_log.render_ms`가 기준 이하(기본 2000ms)
  - `initial_render_ms`는 경고 항목으로 분리(기본 3000ms 초과 시 warning)
  - 스크롤/편집이 반복적으로 멈추지 않음(치명 끊김 없음)
  - 입력 후 저장/반영이 안정적으로 완료됨
  - 콘솔 오류 없음
- `FAIL`
  - `final_render_log.render_ms` 기준 초과 또는 1000행 로딩 미완료
  - 데스크톱 또는 태블릿에서 반복 재현되는 심각 끊김
  - 편집 반영 지연이 지속적으로 커서 실사용이 어려움
  - UI 겹침/오작동으로 교정 동선이 막힘

## 5) 기록 템플릿

아래 형식으로 결과를 handoff 또는 이슈 코멘트에 남긴다.

```text
[SB-006 1000-row smoke]
date:
env: (local/staging/prod-like)
browser/device:
url: /sheetbook/<id>/?tab=<id>&grid_limit=1000

console:
- mode:
- render_ms:
- chunks/chunk_size:
- errors:

desktop:
- initial_load_feel:
- scroll_feel(1~5):
- edit_delay_feel:
- blockers:

tablet:
- scroll_feel(1~5):
- edit_delay_feel:
- keyboard_layout_issues:
- blockers:

decision:
- keep current chunk tuning / tune chunk size / start virtual scroll
- next action owner + due date
```

## 6) 병목 대응 가이드

- 경미한 저하(일부 구간만 지연): 청크 크기/분할 조건 튜닝 우선
- 중간 수준 저하(반복 편집 지연): 렌더 타이밍 + DOM 업데이트 구간 계측 추가
- 심각 저하(교실 사용 불가): 가상 스크롤 설계 착수 이슈 즉시 생성
