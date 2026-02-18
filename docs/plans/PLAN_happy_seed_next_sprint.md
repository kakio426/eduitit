# 행복의 씨앗 다음 스프린트 계획 (실행안)

작성일: 2026-02-18  
기준: 현재 `happy_seed` 구현 상태(라이브/디스플레이 분리, 보상 상대비율, 동의 수동승인, 모둠 편성/지급, 활동/분석 확장 반영)

## 1) 현재 상태 요약

### 이미 반영됨
- 보상 상대비율(`win_rate_percent`) 기반 보상 선택
- 라이브/디스플레이 분리(디스플레이 종료 버튼 제거)
- 동의: 서명톡 링크 생성/재발송/동기화 + 미일치 수동승인
- 모둠: 편성 UI + 모둠 성공 랜덤 1~2명 지급
- 활동: 성실참여 + 점수기반 추가 + 수동 보너스 체크
- 분석: 장기 미당첨/편중/정체 알림, 교사 개입 예약
- 이벤트 로그: `HSClassEventLog`
- 저위험 API 추가:
  - `/api/v1/classes/{class_id}/live:execute-draw`
  - `/api/v1/classes/{class_id}/live:group-mission-success`
  - `/api/v1/classes/{class_id}/consents:sync-sign-talk`

### 부분 반영
- 이벤트명 `EV_*` 완전 통일(현재 `meta.event_code` 병행)
- 에러코드 표준 일부 적용
- 컴포넌트 ID 규칙 일부 적용

### 미반영
- OpenAPI YAML 정식 SSOT
- SSE/WebSocket 실시간 스트림
- 전체 API 표준 전환

## 2) 우선순위 백로그

### P0 (즉시, 저리스크)
1. OpenAPI v1 문서화
2. 에러코드 표준 전면 적용(핵심 API 우선)
3. 이벤트명 표준 alias 정책 고정(`EV_*`)
4. 컴포넌트 ID 핵심 화면 100% 부여(LIVE/DISPLAY/CONSENT)

### P1 (다음)
1. Consent webhook 정식 엔드포인트
2. 분석/로그 API 추가 (`events`, `analytics:summary`)
3. 활동 apply API 분리

### P2 (후속)
1. SSE 스트림 도입
2. UI 효과/애니메이션 고도화
3. 디자인 시스템 정리

## 3) 작업 상세 스펙

### 작업 A. OpenAPI v1 작성
- 목적: FE/BE/QA 공통 SSOT 확립
- 변경 파일:
  - `docs/api/happy_seed_openapi_v1.yaml` (신규)
- API/이벤트/에러 영향: 문서화만(런타임 무영향)
- DoD:
  - 기존 3개 API + 예정 핵심 API 스키마 포함
  - Envelope/Error schema 공통화
- 테스트:
  - OpenAPI lint 통과
- 롤백:
  - 문서 제거/이전 버전 복원

### 작업 B. 에러코드 표준 적용
- 목적: 프론트 분기/번역/알림 처리 단순화
- 변경 파일:
  - `happy_seed/views.py` (API 응답 헬퍼 확장)
- API/이벤트/에러 영향:
  - JSON 에러를 `ERR_*`로 통일
- DoD:
  - 핵심 API에서 에러코드 누락 없음
- 테스트:
  - 에러 경로 단위 테스트
- 롤백:
  - 헬퍼 우회 + 기존 메시지 방식

### 작업 C. 이벤트 표준 alias 고정
- 목적: 로그/디스플레이/분석 이벤트명 일관화
- 변경 파일:
  - `happy_seed/services/engine.py`
- API/이벤트/에러 영향:
  - `meta.event_code`를 `EV_*`로 고정
- DoD:
  - 모든 이벤트 레코드에 `event_code` 존재
- 테스트:
  - 이벤트 생성 테스트
- 롤백:
  - alias 주입 제거

### 작업 D. 컴포넌트 ID 핵심 화면 정리
- 목적: E2E 자동화/클릭 추적 안정성 확보
- 변경 파일:
  - `happy_seed/templates/happy_seed/bloom_run.html`
  - `happy_seed/templates/happy_seed/garden_public.html`
  - `happy_seed/templates/happy_seed/partials/garden_flowers.html`
  - `happy_seed/templates/happy_seed/consent_manage.html` (후속 확장)
- API/이벤트/에러 영향: 없음(DOM 식별자만 추가)
- DoD:
  - 핵심 버튼/영역 ID 규칙 적용 완료
- 테스트:
  - 렌더 + 수동 클릭 스모크
- 롤백:
  - ID 속성 제거

## 4) 2주 스프린트 계획

### 1주차
- OpenAPI v1 초안 작성 및 합의
- 핵심 API 에러코드 통일
- 이벤트 alias 규칙 반영

### 2주차
- 컴포넌트 ID 핵심 화면 완성
- Consent webhook 초안 구현
- 로그/분석 API 1차 공개
- 배포/롤백 리허설

## 5) 리스크와 완화

### 리스크
- API 표준화 중 기존 화면 흐름 회귀
- 이벤트명 변경으로 분석 대시보드 단절
- 동의 자동화 오승인

### 완화
- 기존 화면 로직은 유지, API는 additive 방식
- 기존 type 보존 + `meta.event_code` 병행
- 정확일치 자동승인 + 미일치 수동승인 유지

## 6) 산출물 템플릿

### OpenAPI YAML 최소 구성
- `paths`:
  - `live:execute-draw`
  - `live:group-mission-success`
  - `consents:sync-sign-talk`
- `components.schemas`:
  - `EnvelopeSuccess`
  - `EnvelopeError`
  - `DrawResult`
  - `GroupMissionResult`

### 이벤트 CSV 컬럼
- `timestamp,event_type,event_code,class_id,student_id,group_id,request_id,meta_json`

