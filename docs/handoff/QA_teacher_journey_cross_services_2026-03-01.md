# 교사 여정 크로스 서비스 QA 체크리스트 (2026-03-01)

## 범위
- 대상 서비스: `reservations`, `happy_seed`, `core(SNS)`, `sheetbook`
- 연계 점검: `collect`, `classcalendar` (새 탭 명시성)
- 기준: `CLAUDE.md`의 교사 여정 UX 가드레일
  - 다음 행동 가시성
  - 처리중 피드백/중복 클릭 방지
  - 오류 피드백
  - 새 탭/외부 이동 명시

## 자동 점검 결과
1. P0 4개 서비스의 `hx-post` 파일에 `hx-indicator`, `hx-disabled-elt` 누락이 없다.
- 결과: PASS

2. 핵심 액션에 `hx-on::response-error`가 연결되어 실패 인지가 가능하다.
- 결과: PASS

3. 새 탭 이동 라벨 `(새 탭)`이 사용자 텍스트로 노출된다.
- 대상: `reservations`, `happy_seed`, `collect`, `classcalendar`, `core(post news link)`
- 결과: PASS

4. Django 기본 점검
- 명령: `python manage.py check`
- 결과: PASS (0 issues)

5. UI 계약 테스트
- 명령: `python manage.py test tests.test_teacher_journey_ui_contracts`
- 결과: PASS

6. 서비스 플로우 회귀 테스트
- 명령:
  - `python manage.py test reservations.tests happy_seed.tests.test_flow collect.tests.test_collect_flow classcalendar.tests.test_integration_links_and_settings`
  - `python manage.py test sheetbook.tests.SheetbookOwnershipTests core.tests.test_home_view`
- 결과: PASS (총 103 tests)

## 서비스별 확인 포인트 (교사 기준)
1. `reservations`
- 관리자 대시보드: `예약 현황판 (새 탭)` 문구 확인
- 특별실/블랙아웃/설정 저장: 클릭 시 스피너 노출 + 버튼 중복 클릭 방지
- 예약 취소/강제삭제(PC/모바일): 클릭 후 처리중 상태 노출

2. `happy_seed`
- 교실 상세: `꽃밭 대시보드 (새 탭)` 문구 확인
- 학생 추가/씨앗 지급/동의 상태 변경: 처리중 스피너와 클릭 잠금 확인
- 동의 링크: `열기 (새 탭)` 문구 확인

3. `core` SNS
- 게시글 작성(PC/모바일): 등록 버튼 처리중 표시 + 중복 클릭 방지
- 좋아요/댓글 작성/댓글 신고/수정 저장: 처리중 표시 + 실패 알림
- 뉴스 링크 카드: `원문 보기 (새 탭)` 문구 확인

4. `sheetbook`
- 탭 추가/이름변경/위로/아래로/삭제: 처리중 표시 + 클릭 잠금
- 삭제 확인창 이후 요청중 인지가 가능한지 확인

5. `collect` / `classcalendar`
- 다운로드/외부 이동 버튼에 `(새 탭)` 표기가 유지되는지 확인

## 실기기 수동 점검 프로토콜 (PC + 모바일, 12~15분)
1. PC(Chrome 1280px)에서 각 서비스 핵심 액션 1회씩 클릭
- 합격 기준: 버튼이 즉시 처리중 상태로 바뀌고, 같은 버튼 연타가 차단된다.

2. 의도적으로 실패 상황 1회 만들기(필수값 누락/잘못된 입력 등)
- 합격 기준: 오류 인지 가능(알림/영역 업데이트)하고 다음 행동이 명확하다.

3. 새 탭 링크 1회 클릭
- 합격 기준: 라벨에 `(새 탭)`이 보이며 실제 새 탭으로 열린다.

4. 모바일(360~390px, Safari/Chrome)에서 동일 핵심 액션 반복
- 합격 기준: 버튼 높이/가독성 유지, 라벨 줄바꿈으로 의미 손실 없음.

## 잔여 리스크
- 브라우저별 alert 체감 차이(특히 iOS Safari) 확인 필요
- 저사양 모바일에서 스피너 가시성/터치 반응성은 실기기 확인 필요

## 실기기 결과 기록표 (작성용)
| 항목 | 기기/브라우저 | 결과(PASS/FAIL) | 메모 |
|---|---|---|---|
| reservations 저장/삭제 처리중 인지 | PC / Chrome |  |  |
| happy_seed 학생/동의 액션 처리중 인지 | PC / Chrome |  |  |
| core SNS 작성/좋아요/댓글 처리중 인지 | PC / Chrome |  |  |
| sheetbook 탭 액션 처리중 인지 | PC / Chrome |  |  |
| collect/classcalendar 새 탭 표기 + 동작 | PC / Chrome |  |  |
| 핵심 액션 처리중 인지 | Mobile / Safari |  |  |
| 새 탭 표기 + 동작 | Mobile / Safari |  |  |
| 버튼 가독성/터치성(줄바꿈/높이) | Mobile / Safari |  |  |
