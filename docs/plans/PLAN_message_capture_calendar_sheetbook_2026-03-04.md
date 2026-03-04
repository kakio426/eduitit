# PLAN: 메시지 기반 일정 자동등록 + 캘린더 첨부 + Sheetbook 연동

작성일: 2026-03-04  
대상 서비스: `classcalendar`, `sheetbook`  
대상 사용자: 교사(컴퓨터 숙련도 낮은 사용자 포함)

## 1) 문제 정의

- 학교 메신저 공지가 빈번하고, 일정/준비물/마감이 혼재되어 있어 놓침 불안이 큼.
- 현재는 공지 내용을 수동으로 다시 정리해야 하므로 인지 부담이 큼.
- 목표는 "복붙 + 드래그"만으로 일정 등록까지 끝내는 것.

핵심 사용자 문장:

- "메신저 내용을 붙여넣고 파일만 놓으면, 해야 할 일이 일정으로 정리되면 좋겠다."

## 2) 목표 / 비목표

목표:

1. 메시지 원문에서 일정 후보(제목/날짜/시간/할 일)를 자동 추출한다.
2. 첨부파일을 일정과 함께 저장하고 열람/다운로드 가능하게 한다.
3. 저장된 일정을 필요 시 Sheetbook 일정 탭으로 자동 연동한다.
4. 컴퓨터 초보 교사도 20초 내 등록 가능한 UX를 만든다.

비목표(초기):

1. 구글시트급 함수/피벗/차트 제공
2. 메신저 서비스별 공식 API 직접 연동
3. 대규모 협업 워크플로 엔진화

## 3) 현재 시스템 진단

현재 확인 결과(코드 기준):

1. 캘린더 일정 생성/수정은 `title`, `note`, `time` 중심으로 동작  
   - `classcalendar/forms.py`의 `CalendarEventCreateForm`  
   - `classcalendar/views.py`의 `api_create_event`, `api_update_event`
2. `EventPageBlock`에 `block_type='file'` 주석은 있으나 첨부 업로드/다운로드 API와 UI는 미구현 상태
3. Sheetbook은 표 입력/CSV,XLSX 입출력/달력 반영/후속 액션(동의서, 서명, 안내문 등) 흐름이 있음

결론:

- 캘린더 첨부 구조는 새로 구현하는 것이 맞다.
- 메시지 자동등록 기능은 캘린더 중심으로 먼저 구현하고 Sheetbook 연동을 붙이는 것이 적합하다.

## 4) 벤치마크(유사 사례)

1. Google Calendar: Gmail 메일 일정 자동 인식
2. Gmail + Gemini: 메일에서 Add to calendar
3. Outlook Copilot: 메일 기반 일정 생성
4. Teams: 메시지에서 Task 생성
5. Slack: 메시지 기반 리마인더 생성

적용 관점:

- 외부 사례의 핵심은 "입력 최소화 + 자동 제안 + 1회 확인"이다.
- eduitit도 동일하게 "자동 초안 + 1회 확인 카드"를 표준 플로우로 채택한다.

## 5) 사용자 플로우(최종)

```text
[메시지 바로 등록]
-> [메시지 붙여넣기 + 파일 드래그]
-> [자동 파싱(제목/날짜/시간/할일/우선도)]
-> [저장 전 확인 카드 1회]
-> [이대로 저장]
-> [캘린더 일정 생성 + 첨부 연결 + 원문 스냅샷 저장]
-> [옵션: Sheetbook 일정 탭 동기화]
-> [완료: 캘린더 보기 / 다음 메시지 등록]
```

예외 플로우:

1. 날짜 모호: `확인 필요` 배지 + 빠른 날짜 선택(오늘/내일/직접)
2. 중복 감지: `기존 업데이트` vs `새 일정`
3. 첨부 일부 실패: 일정 저장 성공 유지 + 실패 파일 재시도
4. 파싱 실패: 최소 입력 모드(제목+날짜)로 저장 가능

## 6) UX 원칙(컴맹 친화 고정)

1. 화면당 결정 1개
2. 버튼 문구는 동사형 단문
3. 기술 용어 노출 금지
4. 자동값 기본 채움, 사용자는 확인 위주
5. 실패 안내는 "이유 1줄 + 다음 행동 1버튼"
6. 저장 전 확인 카드 필수(완전 자동 저장 금지)

권장 문구:

- 버튼: `메시지 바로 등록`
- 안내: `메신저 내용을 붙여넣고 파일을 놓아주세요`
- 확인: `자동으로 읽었어요. 틀리면 여기만 고쳐주세요`
- 저장: `이대로 일정 만들기`
- 완료: `일정이 저장됐어요`

## 7) 실행 로드맵(티켓 20개)

P0 (필수):

1. SBMSG-01 진입 버튼
2. SBMSG-02 붙여넣기+드래그 입력 UI
3. SBMSG-03 메시지 파싱 API v1
4. SBMSG-04 날짜/시간 신뢰도 점수
5. SBMSG-05 저장 전 확인 카드
6. SBMSG-06 캘린더 이벤트 생성 파이프라인
7. SBMSG-07 캘린더 첨부 데이터모델
8. SBMSG-08 첨부 업로드/다운로드 API+권한
9. SBMSG-09 캘린더 상세 첨부 UI
10. SBMSG-10 Sheetbook 일정 탭 자동 연동

P1 (권장):

11. SBMSG-11 중복 일정 감지
12. SBMSG-12 날짜 미확정 빠른 선택
13. SBMSG-13 파싱 실패 최소 입력 모드
14. SBMSG-14 첨부 실패 재시도
15. SBMSG-15 원문/파싱/최종수정 이력 저장
16. SBMSG-16 초간단 도움말

P2 (후속):

17. SBMSG-17 메신저 유형 프리셋
18. SBMSG-18 이미지/PDF OCR
19. SBMSG-19 놓침 방지 리마인드 추천
20. SBMSG-20 운영 대시보드

## 8) 1인 개발 검증 전략

실교사 파일럿이 어려운 조건에서 다음으로 대체한다.

1. 골든 메시지 세트 구축(150~300건)
2. 자동 회귀(정답 라벨 비교)
3. 시나리오 E2E 자동화
4. 섀도우 모드(실저장 없이 파싱 로그 관찰)
5. 기능 플래그 점진 활성화 + 즉시 OFF 스위치

품질 기준:

1. 날짜/시간 추출 정확도 >= 85%
2. 필수 필드 추출 실패율 <= 5%
3. 중복 생성 0건
4. 미처리 예외 0건

## 9) DB 스키마 초안

### 9-1) calendar_message_capture

용도: 메시지 캡처/파싱/커밋 상태 저장

- `id` UUID PK
- `author` FK(User)
- `raw_text` TEXT
- `normalized_text` TEXT
- `source_hint` VARCHAR(30)
- `parse_status` VARCHAR(20) (`parsed`, `needs_review`, `failed`)
- `confidence_score` DECIMAL(5,2)
- `extracted_title` VARCHAR(200)
- `extracted_start_time` DATETIME NULL
- `extracted_end_time` DATETIME NULL
- `extracted_is_all_day` BOOL
- `extracted_priority` VARCHAR(10) NULL
- `extracted_todo_summary` TEXT
- `parse_payload` JSON
- `idempotency_key` VARCHAR(64)
- `committed_event` FK(CalendarEvent) NULL
- `committed_at` DATETIME NULL
- `created_at`, `updated_at`

인덱스/제약:

- INDEX `(author_id, created_at)`
- INDEX `(author_id, parse_status, created_at)`
- UNIQUE `(author_id, idempotency_key)`

### 9-2) calendar_message_capture_attachment

용도: 커밋 전 임시 첨부

- `id` UUID PK
- `capture` FK(calendar_message_capture)
- `uploaded_by` FK(User)
- `file` FileField
- `original_name` VARCHAR(255)
- `mime_type` VARCHAR(120)
- `size_bytes` BIGINT
- `checksum_sha256` CHAR(64)
- `is_selected` BOOL default true
- `created_at`

인덱스:

- INDEX `(capture_id, created_at)`

### 9-3) calendar_event_attachment

용도: 이벤트 최종 첨부

- `id` UUID PK
- `event` FK(CalendarEvent)
- `uploaded_by` FK(User)
- `source_capture_attachment` FK(temp_attachment) NULL
- `file` FileField
- `original_name` VARCHAR(255)
- `mime_type` VARCHAR(120)
- `size_bytes` BIGINT
- `checksum_sha256` CHAR(64)
- `sort_order` INT
- `created_at`

인덱스/제약:

- INDEX `(event_id, sort_order)`
- UNIQUE `(event_id, checksum_sha256, original_name)` 권장

### 9-4) calendar_event_sync_task

용도: 캘린더 -> Sheetbook 동기화 재시도

- `id` UUID PK
- `event` FK(CalendarEvent)
- `target_type` VARCHAR(30) (`sheetbook_schedule`)
- `status` VARCHAR(20) (`pending`, `success`, `failed`)
- `retry_count` INT
- `target_ref` JSON
- `last_error` TEXT NULL
- `created_at`, `updated_at`, `completed_at`

인덱스/제약:

- INDEX `(status, updated_at)`
- UNIQUE `(event_id, target_type)` 권장

## 10) API 초안

기존 namespace를 따라 `classcalendar/api/...` 하위로 확장한다.

1. `POST /classcalendar/api/message-captures/parse/`
2. `POST /classcalendar/api/message-captures/{capture_id}/commit/`
3. `POST /classcalendar/api/events/{event_id}/attachments/upload/`
4. `GET /classcalendar/api/events/{event_id}/attachments/`
5. `GET /classcalendar/api/events/{event_id}/attachments/{attachment_id}/download/`
6. `DELETE /classcalendar/api/events/{event_id}/attachments/{attachment_id}/`
7. `POST /classcalendar/api/events/{event_id}/sheetbook-sync/retry/`

표준 에러 코드:

- `validation_error` (400)
- `permission_denied` (403)
- `duplicate_request` (409)
- `needs_confirmation` (422)
- `file_too_large` (413)

## 11) 마이그레이션 순서 (실행용)

원칙: Expand -> Dual Write/Read -> Contract

### Phase M1: 테이블 추가(비파괴)

1. 신규 모델 추가:
   - `calendar_message_capture`
   - `calendar_message_capture_attachment`
   - `calendar_event_attachment`
   - `calendar_event_sync_task`
2. 기존 테이블에 변경이 필요하면 nullable로 먼저 추가
3. 인덱스/기본 제약 추가

배포:

1. migration 배포
2. 앱 코드는 아직 신규 테이블 쓰지 않음(호환성 유지)

### Phase M2: 읽기 API 도입(쓰기 없음)

1. 첨부 목록/다운로드 read API 먼저 배포
2. UI는 fallback 유지(첨부 없으면 기존 화면)

### Phase M3: 쓰기 API 도입 + 기능 플래그

1. `message_capture parse/commit` API 배포
2. 첨부 업로드 API 배포
3. `FEATURE_MESSAGE_CAPTURE_ENABLED` 기본 OFF
4. 본인 계정 allowlist만 ON

### Phase M4: Dual Write 안정화

1. 이벤트 저장 시:
   - 기존 `note` 저장 유지
   - 신규 capture/attachment 동시 저장
2. 실패 분리:
   - 이벤트 저장 성공 + 첨부 실패 허용
   - 실패 첨부는 재시도 큐 적재

### Phase M5: Sheetbook 동기화 연결

1. commit 성공 후 `calendar_event_sync_task` enqueue
2. 동기화 성공 시 매핑 정보 `target_ref` 저장
3. 실패 시 지수 백오프 재시도

### Phase M6: 데이터 백필(필요 시)

1. 과거 이벤트의 `EventPageBlock(file)`가 존재하면 `calendar_event_attachment`로 이관 스크립트 실행
2. dry-run -> 샘플 검증 -> 실제 이관
3. 이관 결과 리포트 저장

### Phase M7: 제약 강화

1. 운영 안정화 후 unique/check 제약 강화
2. 성능 인덱스 튜닝

### Phase M8: 정리(Contract)

1. 사용하지 않는 구 경로/임시 필드 제거
2. 문서/운영런북 확정

Rollback 가이드:

1. 기능 플래그 OFF로 즉시 차단
2. 신규 테이블은 보존(데이터 손실 방지)
3. API 라우팅만 구버전으로 회귀

## 12) 테스트 케이스 목록

### 12-1) 단위 테스트 (파서/도메인)

1. 날짜 파싱: 절대날짜(`2026-03-15`), 한국식(`3월 15일`), 상대날짜(`내일`)
2. 시간 파싱: 단일 시간, 시간 범위, 종일 이벤트
3. 우선도 파싱: 긴급/마감/필수 키워드
4. 제목 생성 규칙: 제목 비어 있을 때 fallback
5. 신뢰도 점수: high/medium/low 분류 경계값
6. idempotency key 중복 처리
7. 파일 검증: mime/확장자/용량 초과
8. checksum 생성/중복 감지

### 12-2) 모델 테스트

1. capture 생성/수정/커밋 필드 검증
2. attachment FK cascade 동작
3. unique 제약(`author+idempotency`)
4. sync_task 상태 전이(`pending -> success/failed`)

### 12-3) API 통합 테스트

1. parse 성공 응답 구조
2. parse 실패/부분 인식 응답 구조
3. commit 성공(이벤트 생성 + 첨부 연결)
4. commit 중복 요청(409)
5. 첨부 업로드 성공/실패 혼합
6. 첨부 목록 조회 권한
7. 첨부 다운로드 권한
8. 첨부 삭제 권한
9. Sheetbook sync retry API 동작

### 12-4) 권한/보안 테스트

1. 타인 이벤트 첨부 접근 차단(403)
2. 임의 event_id/attachment_id 탐색 차단
3. 파일명 경로 주입 차단
4. 허용되지 않은 파일 형식 차단

### 12-5) E2E 시나리오 테스트

1. 정상: 복붙+드래그 -> 확인카드 -> 저장 -> 캘린더 표시
2. 날짜 모호: 확인 필요 -> 날짜 선택 -> 저장
3. 첨부 일부 실패: 일정 저장 유지 + 첨부 재시도
4. 중복 저장 버튼 연타: 일정 1건만 생성
5. sheetbook_sync ON: 일정 + 수첩행 생성
6. sheetbook_sync 실패: 일정 성공 + 재시도 큐 등록

### 12-6) 회귀 테스트

1. 기존 `api_create_event` 수동 생성 경로 무영향
2. 기존 캘린더 조회/API 성능 퇴화 여부
3. 기존 integration locked event 수정/삭제 차단 동작 유지

### 12-7) 성능/안정성 테스트

1. parse API p95 latency 측정
2. 첨부 업로드 동시성(다중 파일)
3. 재시도 큐 누적 시 처리율/지연

## 13) 운영 관측 지표

필수 KPI:

1. 등록 완료까지 소요시간(중앙값)
2. 자동 인식값 수동 수정률
3. parse 성공/부분/실패 비율
4. 첨부 업로드 실패율
5. 중복 생성 차단 횟수
6. sheetbook 동기화 성공률

알람 기준 예시:

1. parse 실패율 > 10% (1시간)
2. 첨부 실패율 > 5% (1시간)
3. sync_task 실패 누적 > 50건

## 14) 단계별 릴리즈 전략

1. 내부(본인) 계정 ON
2. 소수 allowlist ON
3. 전체 공개 ON
4. 문제 시 즉시 OFF + 사후 분석

## 15) 즉시 실행 TODO

1. `SBMSG-01~05` 먼저 구현
2. 동시에 M1 마이그레이션 설계/생성
3. 골든 메시지 세트 초기 150건 구축
4. E2E 자동화 10개 시나리오 우선 작성

