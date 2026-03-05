# CHECKLIST: Message Capture MVP (SBMSG-01~05)

작성일: 2026-03-04  
대상: `classcalendar` 메시지 기반 일정 자동등록 MVP 1단계  
범위: `SBMSG-01` ~ `SBMSG-05`

## 0) 목표

- 교사가 `복사+붙여넣기`와 `파일 드래그`만으로 일정 등록 직전(확인 카드)까지 도달할 수 있게 한다.
- 저장 전 자동 파싱 결과를 1회 확인해 오인식으로 인한 누락을 막는다.

## 1) 선행 조건

1. `PLAN_message_capture_calendar_sheetbook_2026-03-04.md` 최신본 확인
2. 기능 플래그 준비:
   - `FEATURE_MESSAGE_CAPTURE_ENABLED=False` (기본)
   - 내부 계정 allowlist만 ON
3. M1 스키마 적용 가능 상태:
   - `classcalendar` migration `0011_calendarmessagecapture_and_more.py`

## 2) 구현 체크리스트

### SBMSG-01: 진입 버튼

- [x] 캘린더 화면 상단에 `메시지 바로 등록` 버튼 추가
- [x] 클릭 시 등록 모달(또는 패널) 오픈
- [x] 권한/플래그 OFF 시 버튼 숨김 또는 비활성
- [x] 라벨/문구 컴맹 친화 문장 적용

완료 기준:

- [x] 어디서 시작할지 헷갈리지 않게 1클릭 진입 가능

### SBMSG-02: 입력 UI(복붙+드래그)

- [x] 텍스트 붙여넣기 영역 추가
- [x] 파일 드래그 앤 드롭 영역 추가
- [x] 파일 선택 버튼 폴백 추가
- [x] 첨부 목록(파일명/크기/삭제) 미리보기 추가
- [x] 용량/형식 제한 초과 시 즉시 안내

완료 기준:

- [x] 텍스트만/파일만/동시 입력 모두 처리 가능

### SBMSG-03: 메시지 파싱 API v1

- [x] API 엔드포인트 추가: `message-captures/parse`
- [x] 추출 항목: 제목/날짜/시간/할일요약/우선도/파싱근거
- [x] 상태값: `parsed`, `needs_review`, `failed`
- [x] 골든 메시지 샘플 기반 기본 규칙 반영
- [x] 응답 스키마 문서화

완료 기준:

- [x] 날짜/시간 추출 정확도 기준치(내부 골든셋) 충족

### SBMSG-04: 신뢰도 점수 + 확인 필요

- [x] 파싱 결과에 `confidence_score` 계산
- [x] 임계치 기준 high/medium/low 분류
- [x] low는 저장 전 강제 확인 처리
- [x] UI에 `확인 필요` 배지 노출

완료 기준:

- [x] 모호한 날짜/시간 케이스에서 무조건 검토 단계 거침

### SBMSG-05: 저장 전 확인 카드

- [x] 확인 카드 구성: 제목/날짜/시간/요약/첨부
- [x] 즉시 수정 가능 필드 제공
- [x] CTA 2개만 제공: `이대로 저장`, `다시 붙여넣기`
- [x] 필수값 누락 시 필드 강조 + 단일 에러 문구

완료 기준:

- [x] 저장 직전 검토를 1화면에서 완료 가능

## 3) API 계약 초안 (SBMSG-01~05 범위)

1. `POST /classcalendar/api/message-captures/parse/`
   - 입력: `raw_text`, `files[]`, `source_hint`, `idempotency_key`
   - 출력: `capture_id`, `parse_status`, `confidence_score`, `draft_event`, `attachments[]`, `warnings[]`
2. `POST /classcalendar/api/message-captures/{capture_id}/commit/`
   - 입력: 확인 카드 수정값 + `selected_attachment_ids`
   - 출력: `event`, `attachments`, `sheetbook_sync`

### 3-1) 구현 응답 스키마 요약 (2026-03-05 반영)

1. parse 응답 핵심 필드
   - `capture_id`, `parse_status`, `confidence_score`, `confidence_label`
   - `draft_event`: `title`, `start_time`, `end_time`, `is_all_day`, `todo_summary`, `priority`, `needs_confirmation`, `parse_evidence`
   - `attachments[]`, `warnings[]`, `reused`
2. commit 응답 핵심 필드
   - `event`(생성된 캘린더 이벤트 직렬화)
   - `attachments`(이벤트 첨부로 복사된 목록)
   - `warnings`(첨부 복사 실패 등 경고)
   - `sheetbook_sync`(현재 `pending`/`enabled` 메타 반환)

## 4) 1인 개발 검증 체크리스트

### 단위 테스트

- [x] 날짜 파싱(절대/상대/한국어 표현)
- [x] 시간 파싱(단일/범위/종일)
- [x] 신뢰도 분류 임계치
- [x] idempotency 중복 처리

### 통합 테스트

- [x] parse API 정상/부분/실패
- [x] parse -> 확인 카드 데이터 매핑
- [x] commit 전 필수값 검증

### E2E 테스트

- [x] 복붙 -> 드래그 -> 확인 카드까지 한 번에 진행
- [x] 날짜 모호 케이스에서 `확인 필요` 노출
- [x] 파일 초과/형식 오류 처리

### 4-1) 2026-03-05 실행 로그

1. `python manage.py check` 통과
2. `python manage.py test classcalendar.tests.test_message_capture_parser classcalendar.tests.test_message_capture_api` 통과 (15 tests)
3. 템플릿 inline JS는 Django 템플릿 태그 제거본으로 `node --check` 통과
4. `python scripts/run_message_capture_golden_eval.py --case-count 150 --output docs/handoff/message_capture_golden_eval_latest.json` 통과
   - `parse_status_accuracy=1.0000`, `datetime_accuracy=1.0000`, `title_accuracy=1.0000`, `evaluation.pass=true`

### 4-2) 골든셋 산출물

1. 결과 파일: `docs/handoff/message_capture_golden_eval_latest.json`
2. 케이스 구성: 총 150건 (`parsed` 60 / `needs_review` 60 / `failed` 30)

## 5) 운영 로그 항목

- [x] parse 성공/부분/실패 카운트
- [x] 평균 처리시간(입력 시작 -> 확인 카드 도달)
- [x] 수동 수정률(자동값 대비)
- [x] 첨부 업로드 실패율

## 6) 배포 가드

- [x] 기능 플래그 OFF 기본 유지
- [x] 내부 allowlist 계정만 ON
- [x] 장애 시 즉시 OFF 가능한 운영 절차 확인

### 6-1) 즉시 OFF 절차 (2026-03-05 확인)

1. 환경변수 `FEATURE_MESSAGE_CAPTURE_ENABLED=False`로 변경
2. 필요 시 allowlist(`FEATURE_MESSAGE_CAPTURE_ALLOWLIST_*`) 비우기
3. 앱 재시작 후 `/classcalendar/legacy/`에서 버튼 비노출 확인
4. API `/classcalendar/api/message-captures/parse/` 403(`feature_disabled`) 확인

## 7) 완료 선언 조건

- [x] SBMSG-01~05 구현 완료
- [x] 단위/통합/E2E 기본 세트 통과
- [x] 문서(계획 + 체크리스트 + API 스펙) 최신화
- [x] 운영 플래그/롤백 경로 검증 완료
