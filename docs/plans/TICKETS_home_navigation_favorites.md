# 홈 탐색 구조 + 즐겨찾기 구현 티켓

작성일: 2026-02-25
기준 문서: `CLAUDE.md`, `SERVICE_INTEGRATION_STANDARD.md`

## 범위 선언
- `target_app`: `core` (home/search/api), `core/templates/core/*`
- `do_not_touch_apps`: `products/dutyticker*`, `classcalendar`, 기타 개별 서비스 앱
- 공용 전역 레이아웃(`base.html`)은 변경하지 않는다.

## 레이아웃/폰트 비회귀 가드레일
- 기존 Tailwind 유틸 클래스 체계를 유지하고, 카드 폭/패딩/폰트 패밀리 변경 금지
- 홈 템플릿의 레이아웃 핵심 클래스 유지:
  - `xl:flex-row xl:gap-6`
  - `flex-1 min-w-0`
  - SNS 사이드바 `hidden xl:block` / 모바일 `block xl:hidden`
- 새 UI는 기존 카드 내부에 "작은 액션(별 토글)"만 추가하고 카드 크기/타이포 스케일은 유지
- "색/그림자/폰트" 전역 스타일 변경 금지

## Ticket 0 (완료)
- [x] 작업 티켓 문서화
- [x] 구현 범위 고정(target_app/do_not_touch_apps)
- [x] 레이아웃/폰트 비회귀 가드레일 확정

---

## Ticket 1: 홈 분류 엔진 개편 (메인 4 + 보조 3)
목표: 서비스가 많아도 찾기 쉽게 홈 분류를 목적 중심으로 재구성

구현 항목
- [ ] `core/views.py` 분류 상수 재정의
  - 메인: `수합·서명`, `문서·작성`, `수업·학급 운영`, `교실 활동`
  - 보조: `상담·리프레시`, `가이드·인사이트`, `외부 서비스`
- [ ] 서비스별 분류 함수 추가 (서비스명/route/타입 기반 우선순위 매핑)
- [ ] 기존 `sections` 컨텍스트는 유지(호환), `aux_sections` 추가
- [ ] `별빛 추첨기`가 반드시 `수업·학급 운영`으로 분류되도록 고정 규칙 추가
- [ ] `home_v2`, `home_authenticated_v2`에서 보조 섹션 렌더링 추가(간단 카드 재사용)

완료 조건
- [ ] 홈에서 메인 4개 목적 섹션이 우선 노출된다
- [ ] 보조 3개 섹션이 별도 영역으로 표시된다
- [ ] 기존 반응형 분기(`xl`)가 그대로 유지된다

---

## Ticket 2: 아이디별 즐겨찾기 데이터/백엔드
목표: 사용자별 즐겨찾기 영속 저장 + API 제공

구현 항목
- [ ] `core/models.py`에 `ProductFavorite` 모델 추가
  - 필드: `user`, `product`, `pin_order`, `created_at`
  - 제약: `(user, product)` unique
  - 인덱스: `(user, pin_order)`, `(user, created_at)`
- [ ] 마이그레이션 생성
- [ ] API 추가 (`core/views.py`, `core/urls.py`)
  - `POST /api/favorites/toggle/`
  - `GET /api/favorites/`
- [ ] 응답 표준화(성공/오류 코드, 권한 체크)
- [ ] `fetch` 실패 시 사용자 피드백 메시지 반환/표시 가능 구조 유지

완료 조건
- [ ] 로그인 사용자마다 즐겨찾기가 분리 저장된다
- [ ] 같은 서비스 중복 즐겨찾기가 생성되지 않는다
- [ ] 비로그인은 401/ignored 정책이 일관되게 동작한다

---

## Ticket 3: 홈 V2 UI 즐겨찾기 통합
목표: 레이아웃을 깨지 않고 즐겨찾기 사용성을 추가

구현 항목
- [ ] 홈 카드(`mini_card`)에 별 토글 버튼 추가
  - 카드 클릭과 이벤트 충돌 방지 (`stopPropagation`)
- [ ] 로그인 홈(`home_authenticated_v2`)에 `내 즐겨찾기` 스트립 섹션 추가
- [ ] 퀵 액션 계산 시 즐겨찾기 우선 반영, 이후 사용기록 보완
- [ ] 초기 즐겨찾기 ID를 JSON으로 주입해 렌더 시 즉시 상태 반영
- [ ] 토글 액션 후 토스트/피드백 표시

완료 조건
- [ ] 별 토글 시 카드 레이아웃(높이/비율/폰트)이 깨지지 않는다
- [ ] 새로고침 후에도 즐겨찾기 상태가 유지된다
- [ ] 퀵 액션에서 즐겨찾기 우선순위가 반영된다

---

## Ticket 4: 검증/테스트
구현 항목
- [ ] 단위/통합 테스트 추가
  - 분류 엔진 테스트
  - 즐겨찾기 API 테스트
  - 홈 컨텍스트(quick_actions/favorites) 테스트
- [ ] 기존 홈 V2 테스트 기대값 업데이트
- [ ] `python manage.py check`
- [ ] 변경된 테스트 실행

완료 조건
- [ ] 체크 명령 통과
- [ ] 핵심 테스트 통과
- [ ] 변경 요약과 남은 리스크 문서화

---

## 배포/운영 메모
- feature flag가 필요하면 `HOME_V2_ENABLED` 흐름 안에서만 조건 분기
- 기존 `ProductUsageLog` 로직과 충돌하지 않도록 즐겨찾기 로직은 별도 모델로 분리
- 기존 공용 CSS/폰트/전역 nav는 수정하지 않는다
