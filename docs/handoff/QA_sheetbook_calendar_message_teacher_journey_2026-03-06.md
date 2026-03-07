# Sheetbook / Calendar / Message 교사 여정 QA 체크리스트 (2026-03-06)

## 범위
- 대상 서비스: `sheetbook`, `classcalendar`
- 연계 흐름: `sheetbook -> calendar`, `message capture -> calendar event`, `sheetbook action -> consent/signature/notice`
- 기준 문서: `docs/plans/PLAN_sheetbook_calendar_message_enterprise_rebuild_2026-03-06.md`
- 엔터프라이즈 가드:
  - 다음 행동 가시성
  - 무반응처럼 느껴지는 버튼 제거
  - 키보드/포커스/모달 닫기 계약 유지
  - 권한 경계와 감사 가능한 액션 기록
  - 로그/스모크/회귀 테스트로 추적 가능

## 자동 점검 결과
1. Django 기본 점검
- 명령: `python manage.py check`
- 결과: PASS

2. 핵심 연계 계약 테스트
- 명령: `python manage.py test tests.test_sheetbook_navigation_contracts classcalendar.tests.test_sheetbook_bridge classcalendar.tests.test_message_capture_api`
- 결과: PASS

3. sheetbook 그리드 핵심 UI 계약 테스트
- 명령:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_includes_mobile_row_editor_controls`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_includes_selection_recommendation_parser_script`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_search_focus_params_are_embedded_in_grid_editor`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_search_returns_tab_cell_action_results`
- 결과: PASS

4. 브라우저 스모크
- 명령:
  - `python scripts/run_sheetbook_grid_smoke.py`
  - `python scripts/run_sheetbook_consent_smoke.py`
- 결과: PASS
- 메모: 2026-03-07 최종 재실행 기준 grid smoke desktop/tablet PASS, consent smoke PASS, 콘솔 `ReferenceError` 0건, 렌더 경고 없음

5. 인라인 스크립트 문법 점검
- 명령: `node --check` on `sheetbook/templates/sheetbook/detail.html` inline script
- 결과: PASS

6. 전체 `sheetbook.tests` 상태
- 명령: `python manage.py test sheetbook.tests --failfast`
- 결과: PASS
- 메모: 2026-03-07 기준 `225 passed, 59 skipped`

## 교사 핵심 시나리오 확인 포인트
1. `sheetbook -> calendar`
- 표에 일정 데이터를 넣고 달력 반영 버튼을 눌렀을 때 다음 화면 또는 결과가 즉시 보여야 한다.
- 축약 달력에서도 선택 날짜 일정, 첨부 유무, 원본 화면 이동이 보여야 한다.

2. `message capture -> calendar event`
- 메시지를 붙여넣으면 일정이 생성되고, 생성 직후 상세에서 제목/메모/첨부를 다시 확인할 수 있어야 한다.
- 첨부가 있다면 다운로드 또는 열기 동선이 보여야 한다.

3. `sheetbook action -> consent/signature/notice`
- 버튼 라벨만 보고도 "바로 완료"인지 "다음 화면 열기"인지 이해돼야 한다.
- 성공 후 최근 기록에만 남지 말고, 실제 결과 화면으로 바로 이어져야 한다.

4. `sheetbook 내부 작업`
- 검색은 탭/칸/실행 기록을 한 번에 찾고, 눌렀을 때 해당 위치나 결과로 이동해야 한다.
- 모바일 또는 차단 상황에서는 왜 지금 수정이 안 되는지와 다음 행동이 보여야 한다.

## 접근성/운영 가드 점검
1. 키보드 경로
- 검색창 진입, 검색 결과 링크 이동, 주요 액션 버튼 포커스 이동이 자연스러운지 확인
- 합격 기준: 마우스 없이도 핵심 흐름 1회 수행 가능

2. 포커스/모달 계약
- 미리보기/확인 모달이 ESC 또는 닫기 버튼으로 닫히고, 닫은 뒤 원래 작업 위치로 복귀하는지 확인
- 합격 기준: 포커스 유실이나 배경 클릭 무반응 체감 없음

3. 권한 경계
- 비소유자, 모바일 읽기 모드, 차단 상태에서 403/안내 메시지가 일관되게 보이는지 확인
- 합격 기준: "왜 안 되는지"가 사용자 문구로 노출

4. 관측성
- 주요 액션 실패 시 `sheetbook_metric` 또는 요청 로그로 추적 가능한지 확인
- 합격 기준: 실패 원인 파악에 필요한 이벤트/상태 코드 확인 가능

## 실기기 수동 점검 프로토콜 (교사 1명 기준, 15~20분)
1. PC(Chrome, 1280px)에서 `sheetbook` 상세 진입 후 검색, 셀 선택, 달력 등록을 1회 수행한다.
- 합격 기준: 검색 결과가 즉시 보이고, 선택 액션 버튼이 보이며, 결과가 새 화면 또는 같은 화면에서 즉시 확인된다.

2. `message capture`로 메시지 붙여넣기 후 일정 생성, 첨부 확인을 수행한다.
- 합격 기준: 생성 완료 후 일정 상세에서 제목/메모/첨부 동선이 모두 보인다.

3. `동의서/서명/안내문` 액션을 각각 1회 눌러 다음 화면으로 이어지는지 확인한다.
- 합격 기준: 버튼 무반응 체감 없음, 최근 기록과 실제 이동 결과가 일치한다.

4. 모바일(360~390px)에서 `sheetbook` 진입 후 읽기/편집 제한 안내를 확인한다.
- 합격 기준: 막힌 이유와 PC/태블릿 권장 안내가 분명하다.

5. 실패 상황 1회 만들기(잘못된 입력/권한 없는 상태/필수값 누락).
- 합격 기준: 실패 알림이 보이고 다음 행동이 문장으로 안내된다.

## 현재 남은 리스크
- 360px급 실기기에서 모바일 행 편집 패널의 터치 체감은 별도 확인이 필요하다.
- 명시적 연결 설정 UI는 도입됐지만, 실제 교사 사용 데이터로 자동 추천 fallback을 더 줄일지 판단이 필요하다.

## 실기기 결과 기록표 (작성용)
| 항목 | 기기/브라우저 | 결과(PASS/FAIL) | 메모 |
|---|---|---|---|
| 검색 -> 결과 이동 -> 셀 포커스 | PC / Chrome |  |  |
| sheetbook -> calendar 반영/확인 | PC / Chrome |  |  |
| message capture -> 일정 생성/첨부 확인 | PC / Chrome |  |  |
| 동의서/서명/안내문 다음 화면 이동 | PC / Chrome |  |  |
| 모바일 읽기 제한/다음 행동 안내 | Mobile / Safari |  |  |
| 모바일 행 편집 패널 조작성 | Mobile / Safari |  |  |
| 실패 상황 알림/다음 행동 안내 | PC / Chrome |  |  |
