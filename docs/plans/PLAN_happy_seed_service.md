# Implementation Plan: 행복의 씨앗 (v1)

Status: Draft  
Date: 2026-02-17  
Scope Declaration: `app-level` (신규 앱 중심) + 최소 `global` 변경(서비스 라우팅 분기 1곳)

## 1) 기준 문서 반영 사항

- `CLAUDE.md`, `SERVICE_INTEGRATION_STANDARD.md`, `codex/SKILL.md` 기준을 우선 적용.
- 신규 서비스는 독립 Django app으로 분리.
- `product.title` SSOT 유지(대시보드 라우팅 분기와 ensure 커맨드 문자열 100% 일치).
- 새 서비스에는 `ServiceManual` + `ManualSection` 3개 이상 필수.
- 한글 파일은 UTF-8 유지, 광역 재인코딩 금지.
- 배포 동기화 4종 필수: `INSTALLED_APPS`, `Procfile`, `nixpacks.toml`, `settings_production.py` startup task.

## 2) 서비스 SSOT

- 앱명: `happy_seed`
- Product title(고정): `행복의 씨앗`
- URL namespace: `happy_seed`
- 진입 URL: `/happy-seed/`
- 서비스 성격: 교실 운영형(교사 주도), 학생 공개 대시보드 포함
- 비범위 고정:
  - 학부모 리포트/포털 없음
  - 벌점/확률 하락/자동 처벌 없음
  - 문제행동 즉시 보상 없음

## 3) 단계별 구현 로드맵

## Phase 0. 뼈대/통합 (MVP 착수 전 필수)

- `happy_seed` 앱 생성: `models.py`, `views.py`, `urls.py`, `admin.py`, `tests.py`.
- `config/urls.py`에 namespace 라우팅 등록.
- `products/templates/products/partials/preview_modal.html`에 `행복의 씨앗` 분기 추가.
- `products/management/commands/ensure_happy_seed.py` 추가:
  - Product 생성/보장
  - ProductFeature 최소 3개
  - ServiceManual + ManualSection 3개 이상 생성
- 배포 동기화 4종 반영.

## Phase 1. 도메인 모델 (MVP-1 핵심)

- 교실/학생/설정:
  - `HSClassroom`(교사 소유)
  - `HSStudent`
  - `HSClassroomConfig`(base_prob, seed_target_n, prize 정책, balance mode 설정)
- 동의:
  - `HSGuardianConsent`(학생별 동의 상태, 서명 링크/서명 시각/증빙 메타)
- 보상/기록:
  - `HSPrize`
  - `HSTicketLedger`(꽃피움 1회권 원장)
  - `HSSeedLedger`(씨앗 원장: 특별 긍정행동/회복/미당첨 보정)
  - `HSBloomDraw`(추첨 결과 로그)
  - `HSInterventionLog`(교사 개입 로그, 학생 비공개)
- 행동 카테고리:
  - `HSBehaviorCategory`(기본 5종 + 교사 커스텀)
- 마이그레이션 생성 + 관리자 등록.

## Phase 2. 엔진 규칙 구현

- 꽃피움 실행 로직:
  - 입력: 학생, 티켓 1개 사용, classroom config
  - 출력: 당첨(보상) 또는 미당첨(+씨앗 1)
- 씨앗 전환:
  - 누적 N 도달 시 티켓 자동 +1
  - 씨앗은 확정 보상 금지(항상 기회만 제공)
- 우수 성취/성실 참여 지급:
  - 성실 참여: 티켓 +1
  - 우수 성취: 교사 기준 충족 시 티켓 추가 지급
- 따뜻한 균형 모드(옵션):
  - OFF 기본
  - ON 시 최근 기간 지표 기반 미세보정 `epsilon`
- 교사 개입:
  - 즉시 당첨 / 다음 회차 강제 당첨
  - 교사 전용 로그 필수.

## Phase 3. 교사용 운영 UI (MVP-1 완료선)

- 반 생성/학생 등록/활성화(동의 완료자만 활성).
- 운영 액션:
  - 성실 참여 지급
  - 우수 성취 추가 지급
  - 씨앗 수동 지급(특별행동/회복)
  - 꽃피움 실행
  - 모둠 성공 시 모둠 내 랜덤 1~2명 지급
- 설정 화면:
  - base 확률, N, 보상 텍스트, 카테고리, 균형모드, 개입 허용.
- 축하 화면:
  - 큰 애니메이션(핵심 5초 내)
  - 자동 종료 금지, 교사 수동 종료
  - 철학 문구 고정 노출.

## Phase 4. 학생 공개 대시보드 (MVP-1 완료선)

- 꽃밭 1차: 그리드 기반 + 미세 랜덤 오프셋.
- 학생별 1 flower object:
  - 이름(작게)
  - 씨앗 진행도 색/채움 변화
- 단계 시각화:
  - 0~3 씨앗, 4~7 새싹, 8~9 봉오리, N 완성.
- 서열/랭킹/배지 미제공.

## Phase 5. 동의 연동 (MVP-1 필수)

- 1차 권장: 기존 `signatures` 앱 패턴 재사용하여 보호자 온라인 서명 흐름 연결.
- 학생 활성화 가드:
  - 동의 미완료 학생은 기록 저장/보상 지급 불가.
- 감사 추적:
  - 동의 요청 시각, 완료 시각, 처리자 로깅.

## Phase 6. 분석/개입/균형모드 (MVP-2)

- 교사용 분석:
  - 학생별 당첨 횟수(기간 필터)
  - 장기 미당첨 감지
  - 편중 감지
  - 씨앗 정체 감지
- 교사 개입 로그 UI.
- 균형 모드 상태/작동 근거 표시(교사 전용).
- 학생 개인 기록 화면:
  - 씨앗 사유 타임라인, 주/월 참여 횟수, 행동유형 비율.

## Phase 7. 품질 게이트/릴리즈

- 필수 체크:
  - `python manage.py makemigrations`
  - `python manage.py migrate`
  - `python manage.py check`
- 테스트 최소 세트:
  - 엔진 단위 테스트(확률, 씨앗 전환, 개입, 균형모드)
  - 권한 테스트(교사/학생/비로그인)
  - 핵심 플로우 통합 테스트(수업 중 지급 -> 꽃피움 -> 로그 반영)
- 수동 검증:
  - 대시보드 -> 모달 -> 서비스 실행 경로
  - 모달 닫기/ESC/포커스 복귀.

## 4) 파일 단위 작업 목록

- 신규:
  - `happy_seed/models.py`
  - `happy_seed/views.py`
  - `happy_seed/urls.py`
  - `happy_seed/admin.py`
  - `happy_seed/services/engine.py`
  - `happy_seed/services/analytics.py`
  - `happy_seed/templates/happy_seed/*.html`
  - `happy_seed/static/happy_seed/*`
  - `happy_seed/tests/test_engine.py`
  - `happy_seed/tests/test_views.py`
  - `happy_seed/tests/test_permissions.py`
  - `products/management/commands/ensure_happy_seed.py`
- 수정:
  - `config/urls.py`
  - `config/settings.py`
  - `config/settings_production.py`
  - `products/templates/products/partials/preview_modal.html`
  - `Procfile`
  - `nixpacks.toml`

## 5) 미결정 5건 기본안(권장값)

- 미당첨 문구 톤: `이번엔 씨앗이 자랐어요. 다음 꽃피움을 준비했어요.`
- 꽃밭 레이아웃: MVP는 `그리드 기반` 채택.
- 모둠 랜덤 UX: 모둠원 체크 -> `1명/2명 자동 추첨` 버튼.
- 보상 선택 UI: 텍스트 리스트 + 당첨 시 랜덤 1개.
- 균형모드 기본 `epsilon`: `0.05` 권장(최소 체감).

## 6) 완료 정의 (DoD)

- MVP-1 범위 기능이 모두 동작하고, 비범위 항목이 코드에 유입되지 않음.
- 교사만 확률/균형/개입을 확인 가능하고 학생 화면에는 비공개 유지.
- 씨앗 누적은 항상 기회(티켓)로만 전환되고 확정 보상으로 사용되지 않음.
- 축하 화면 자동 종료가 없고 철학 문구가 고정 노출됨.
- 서비스 카드에서 `행복의 씨앗` 클릭 시 홈으로 튕기지 않고 정상 진입.

## 7) 권한 경계 매트릭스

| 역할 | 접근 범위 | 허용 액션 | 금지 액션 |
| :-- | :-- | :-- | :-- |
| 교사(로그인) | 교사 대시보드, 반/학생/설정, 운영 로그 | 지급/추첨/개입/설정 변경/분석 조회 | 타 교사 반 데이터 접근 |
| 학생(교실/학생 화면) | 공개 꽃밭, 본인 기록(허용 시) | 결과 확인, 본인 진행도 확인 | 확률/균형모드/개입 로그 열람, 설정 변경 |
| 보호자(서명 링크) | 동의 서명 화면 | 동의 제출/재제출 | 반 운영 데이터 조회 |
| 비로그인 일반 사용자 | 공개되지 않은 내부 화면 접근 불가 | 없음 | 서비스 운영 화면 접근 |

## 8) 상태 전이/원자성 규칙

- 엔티티 상태:
  - `ticket_count` (꽃피움권)
  - `seed_count` (씨앗)
  - `pending_intervention` (다음 회 강제당첨 예약)
- 이벤트별 전이:
  - 성실참여 인정 -> `ticket_count +1`
  - 우수성취 인정 -> `ticket_count +N` (교사 설정)
  - 추첨 실행:
    - 공통: `ticket_count -1` 선차감
    - 당첨: `win_log` 기록
    - 미당첨: `seed_count +1`, N 도달 시 `ticket_count +1` 자동
  - 교사개입 예약 -> `pending_intervention=True`
  - 예약 개입 소진 추첨 -> 당첨 처리 후 `pending_intervention=False`
- 중복 클릭/재시도:
  - 추첨/지급 API는 멱등 키(`request_id`) 사용
  - 동일 키 재요청은 최초 결과 재반환
- 트랜잭션:
  - 지급/추첨/씨앗전환은 단일 DB 트랜잭션으로 처리
  - 학생 단위 row lock(`select_for_update`) 적용

## 9) 랜덤성/감사 로그 규칙

- RNG:
  - 서버측 RNG만 사용, 클라이언트 RNG 금지
  - 기본 `base_prob`에서 균형모드 보정 후 최종 확률 계산
- 감사 로그(교사용):
  - 실행 시각, 실행자, 대상 학생, 입력 확률, 보정값, 결과(당첨/미당첨), 적용 보상
  - 교사개입 적용 여부(즉시/다음회), 사유
- 재현성 정책:
  - 보안상 seed 값은 노출하지 않음
  - 감사 목적의 결과 검증용 요약 해시를 로그에 보관

## 10) 동의/데이터 수명주기/운영 가드레일

- 동의 예외 시나리오:
  - 미동의: 학생 비활성, 기록 저장/보상 지급 불가
  - 동의철회: 즉시 비활성 + 신규 기록 차단
  - 재동의: 교사 승인 후 재활성
- 데이터 보관:
  - 학년 종료 기본 정책: `hard delete` (교사 변경 가능)
  - 옵션: 지정 기간 `soft delete` 후 자동 영구삭제
  - 교사 계정 삭제 시 연계 데이터 파기 옵션 필수 표시
- 알림 임계값 기본값(초안):
  - 장기 미당첨: 최근 30일 또는 최근 10회 중 0회 당첨
  - 편중: 상위 20% 학생의 당첨 비율이 전체의 50% 초과
  - 씨앗 정체: 14일 이상 씨앗 증분 없음
- 교사개입 가드레일:
  - 개입 시 사유 입력 권장(빈도 높을 때 경고 배지)
  - 월간 개입 횟수/비율 리포트 제공(교사 본인만)

## 11) 접근성/교실 디스플레이 기준

- 최소 글자 크기:
  - 프로젝터 모드 본문 `>= 20px`, 핵심 수치 `>= 28px`
- 색 대비:
  - 텍스트 대비 WCAG AA 이상 권장
- 터치 타깃:
  - 버튼/카드 최소 `44x44px`
- 애니메이션:
  - 핵심 연출 5초 이내
  - 저자극 모드(모션 감소) 옵션 제공

## 12) 운영 장애 대응 및 수치형 수용 기준

- 장애 대응:
  - 네트워크 불안정 시 로컬 큐 적재 후 재전송
  - 재전송 충돌은 멱등 키로 중복 반영 방지
  - 실패 건은 교사 화면에서 수동 재처리 가능
- MVP-1 수치형 수용 기준:
  - 핵심 API(P95) 응답시간: 700ms 이하
  - 핵심 플로우 성공률: 99% 이상(지급->추첨->로그)
  - 치명 오류율(5xx): 0.5% 미만
  - 필수 테스트:
    - 엔진 단위 테스트 20개 이상
    - 권한/보안 테스트 10개 이상
    - 통합/E2E 시나리오 8개 이상
