# Happy Seed 기반 문제풀이 플랫폼 설계 핸드오프

기준 코드베이스: `C:\Users\kakio\eduitit`  
작성일: 2026-02-21  
용도: 다른 AI/개발자에게 현재 구조를 정확히 전달하고, `행복의 씨앗`과 결합되는 문제풀이 플랫폼 구현에 바로 착수하기 위한 문서

## 1. 한 줄 요약
- `happy_seed`는 "학급 운영/보상 엔진"이고, 문제풀이는 별도 앱으로 분리한 뒤 `grant_tickets()`/`add_seeds()`를 호출해 결합하는 방식이 가장 안전하다.

## 2. 프로젝트 전체 구조

### 2.1 아키텍처
- Django 멀티앱 모놀리식 구조
- 메인 라우팅: `config/urls.py`
- 핵심 앱
- `core`: 홈, 공통 UI, 사용량 계측, 운영 미들웨어
- `products`: 서비스 카탈로그/런치 라우팅
- `consent`: 전자 동의서 생성/서명/결과 관리
- `happy_seed`: 학급 보상 도메인(씨앗/티켓/추첨/동의 게이트)

### 2.2 공통 프론트엔드 패턴
- 공통 베이스 템플릿: `core/templates/base.html`
- 서버 렌더링 + HTMX partial 갱신 + Alpine.js 상호작용
- 홈 V2: `core/templates/core/home_authenticated_v2.html`, `core/templates/core/home_v2.html`
- 서비스 진입은 Product 모달/런치 URL 규칙을 따름

### 2.3 서비스 런치 규칙
- 카탈로그 모델: `products/models.py` 의 `Product`
- 런치 우선순위
- `external_url` 우선
- 없으면 `launch_route_name`
- 둘 다 없으면 `product_detail`
- 구현 참조: `core/views.py` 의 `_resolve_product_launch_url()`

## 3. Happy Seed 도메인 구조 (핵심)

### 3.1 모델
파일: `happy_seed/models.py`

- `HSClassroom`: 반/교실 단위 루트
- `HSClassroomConfig`: 반 설정(씨앗 전환 기준, 기본 당첨률, 균형모드 등)
- `HSStudent`: 학생 상태(씨앗/티켓/당첨누적/개입예약)
- `HSGuardianConsent`: 보호자 동의 상태(approved/pending/rejected/withdrawn 등)
- `HSPrize`: 보상 풀(가중치/재고)
- `HSTicketLedger`: 티켓 원장
- `HSSeedLedger`: 씨앗 원장
- `HSBloomDraw`: 추첨 로그(확률 입력/보정/최종확률/멱등키/축하토큰)
- `HSClassEventLog`: 분석/감사용 표준 이벤트 로그

### 3.2 엔진/비즈니스 로직
파일: `happy_seed/services/engine.py`

- `execute_bloom_draw(student, classroom, created_by, request_id)`
- 멱등 처리: 같은 `request_id` 재요청 시 기존 draw 반환
- 동시성 처리: `select_for_update` + transaction
- 동의 게이트: `consent.status == approved` 아니면 예외
- 티켓 차감, 보상 가중 랜덤 선택, 재고 원자적 차감
- 미당첨 시 씨앗 +1 및 자동 전환 처리
- `add_seeds(...)`
- 씨앗 원장 기록 + 임계치(`seeds_per_bloom`) 도달 시 티켓 자동 전환
- `grant_tickets(...)`
- 동의 게이트 후 티켓 부여
- `log_class_event(...)`
- 주요 액션 이벤트 표준화 기록

## 4. 동의서(consent) 연동 구조

### 4.1 왜 중요함?
- Happy Seed의 대부분 핵심 동작은 동의 완료 상태를 전제로 함
- 즉, 문제풀이 플랫폼도 동일한 동의 게이트를 재사용하는 게 일관성/정책 측면에서 유리함

### 4.2 현재 자동 생성 플로우
파일: `happy_seed/views.py`, `happy_seed/templates/happy_seed/consent_manage.html`

- 교사는 학부모 명단(텍스트/CSV)만 입력
- 서버가 자동 수행
- 명단 파싱/검증(인코딩, 중복, 미매칭)
- 안내문 PDF 생성: `_build_happy_seed_notice_pdf()`
- `consent` 앱의 `SignatureDocument`, `SignatureRequest`, `SignatureRecipient` 생성
- 학생별 서명 URL을 `HSGuardianConsent.external_url`에 연결
- 이후 `consent_sync_from_sign_talk()`로 응답 결과를 `approved/rejected` 반영

### 4.3 consent 앱 핵심 엔티티
파일: `consent/models.py`

- `SignatureDocument`: 원본 안내문(PDF/이미지)
- `SignatureRequest`: 동의 요청 묶음
- `SignatureRecipient`: 학생별 보호자 수신자/토큰/결정/서명
- `ConsentAuditLog`: 검증/서명/요청 이벤트 로그

## 5. API/응답 패턴

### 5.1 Happy Seed API v1
파일: `happy_seed/urls.py`, `happy_seed/views.py`

- 예시
- `api/v1/classes/<classroom_id>/live:execute-draw`
- `api/v1/classes/<classroom_id>/live:group-mission-success`
- `api/v1/classes/<classroom_id>/consents:sync-sign-talk`

### 5.2 응답 envelope 규약
- `{"ok": true/false, "data": ..., "error": ..., "request_id": "..."}`
- 확장 앱에서도 같은 형태를 쓰면 운영/디버깅 일관성이 높음

## 6. 운영/배포 구조에서 반드시 알아야 할 점

### 6.1 런타임 부트스트랩
파일: `core/management/commands/bootstrap_runtime.py`

- 서버 시작 시 실행
- `migrate`, `check_consent_schema`, `ensure_*` 명령 순차 수행

### 6.2 신규 서비스 등록 규칙
- `products/management/commands/ensure_<app>.py` 생성
- `Product` + `ProductFeature` + `ServiceManual` + `ManualSection(3+)` 동시 보장
- 예시 참조
- `products/management/commands/ensure_happy_seed.py`
- `products/management/commands/ensure_consent.py`

### 6.3 실행 커맨드
- `Procfile`, `nixpacks.toml`에서 `bootstrap_runtime` 호출

## 7. 문제풀이 플랫폼 설계 권장안

### 7.1 권장 방식
- 새 앱 생성(예: `seed_quiz`) 후 Happy Seed와 서비스 레벨 연동
- 이유
- 도메인 경계 명확
- 기존 운영 흐름 최소 침범
- 롤백/테스트/배포 단위 분리 용이

### 7.2 권장 최소 모델
- `QuizSet`: 문제 세트
- `QuizItem`: 문제
- `QuizChoice`: 선택지
- `QuizAssignment`: 반/학생 할당
- `QuizAttempt`: 제출 시도(멱등키 포함)
- `QuizAttemptItem`: 문항별 응답
- `QuizResultSummary`: 채점 요약/보상 적용 결과

### 7.3 채점-보상 트랜잭션 권장 흐름
1. 제출 수신 (`idempotency_key` 검증)
2. 채점 계산
3. 동의 게이트 확인 (`HSGuardianConsent.approved`)
4. 점수/규칙에 따라 `grant_tickets()` 또는 `add_seeds()` 호출
5. 이벤트 로그 기록 (`HSClassEventLog`)
6. envelope 응답 반환

### 7.4 프론트엔드 권장 흐름
- 교사용
- 문제세트 생성/배포/결과 요약 대시보드
- HTMX partial 갱신(리스트/상태 테이블)
- 학생용
- 모바일 우선 단순 단계
- 큰 버튼, 짧은 한 화면 입력, 즉시 피드백

## 8. 불변 조건(이 프로젝트에서 깨면 안 되는 것)
- 동의 없는 학생에게 보상 지급 금지
- 멱등키 없는 보상 지급 API 금지
- 보상/재고 갱신은 트랜잭션 없이 수행 금지
- 서비스 등록 시 ensure/manual 누락 금지
- 기존 서비스 공통 UI를 불필요하게 전역 변경 금지

## 9. 다른 AI에게 바로 전달할 프롬프트

```text
You are implementing a new quiz-solving platform integrated with Eduitit's Happy Seed domain.

Project architecture:
- Django monolith with multiple apps.
- Core apps: core, products, consent, happy_seed.
- Service launch must follow Product.external_url -> Product.launch_route_name -> product_detail fallback.

Happy Seed domain:
- Models in happy_seed/models.py: classroom, student, guardian consent, prize, ticket/seed ledgers, bloom draw, class event log.
- Engine logic in happy_seed/services/engine.py:
  - execute_bloom_draw is idempotent and transactional with select_for_update.
  - grant_tickets/add_seeds enforce consent and update ledgers.

Consent integration:
- happy_seed/views.py automatically creates consent request + notice PDF from guardian roster.
- consent/models.py handles SignatureDocument, SignatureRequest, SignatureRecipient, ConsentAuditLog.
- Student consent status is synchronized back to HSGuardianConsent.

Implementation requirements for the new quiz app:
1) Create a separate Django app (do not over-expand happy_seed directly).
2) Use idempotency_key for submission/reward APIs.
3) Reuse HSGuardianConsent as the reward gate.
4) Reward by calling happy_seed engine functions (grant_tickets/add_seeds).
5) Log key actions into HSClassEventLog.
6) Keep API response envelope: ok/data/error/request_id.
7) Add ensure_<app>.py for Product + ProductFeature + ServiceManual + 3+ ManualSection.
```

