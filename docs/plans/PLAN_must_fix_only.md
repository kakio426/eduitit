# Must-Fix Only Plan (Confirmed Issues)

Status: Ready  
Created: 2026-02-18  
Last Updated: 2026-02-18  
Scope: `confirmed bug/security/accessibility regressions only`

## Analysis Trail

- Continuation plan: `docs/plans/PLAN_ux_rollout_continuation_2026-02-18.md`
- Progress snapshot: `docs/handoff/HANDOFF_ux_rollout_snapshot_2026-02-18.md`

## Purpose

이 문서는 "무조건 잘못된 것"만 빠르게 고치기 위한 실행 백로그다.  
단, 사용자 이탈/전환에 직접 영향을 주는 UX 결함은 정책 이슈와 분리해 별도 우선순위로 즉시 처리한다.

## Operation Rule

1. 재개 시 맨 위 `TODO` 1개만 처리한다.
2. 처리 후 상태를 `DOING -> DONE`으로 바꾼다.
3. 완료 시 검증 명령을 실행하고 결과를 기록한다.
4. 커밋 메시지에 이슈 ID를 포함한다. 예: `fix(reservations): block anonymous delete (C-01)`

## Backlog

| ID | Status | Issue | Evidence | Done Condition | Validation Command |
|---|---|---|---|---|---|
| C-01 | DONE | 예약 삭제가 비로그인에서도 가능 | `reservations/views.py:416`, `reservations/urls.py:20` | 익명/타사용자 삭제 요청이 403 또는 차단됨 | `python manage.py test reservations -v 2` |
| H-03 | DONE | 홈 V1 카드 클릭 이벤트 중복 바인딩 | `core/templates/core/home.html:167`, `core/templates/core/home.html:367` | 1회 클릭당 preview 요청 1회만 발생 | `python manage.py test products.tests.test_modal_consistency -v 2` |
| H-06 | DONE | `target="_blank"` 링크에 `rel` 누락 | 예: `products/templates/products/detail.html:183` | 누락 0건 | `rg -n "target=\"_blank\"" -S core products collect consent` |
| H-07 | DONE | 모달 `aria-labelledby` 대상 ID 불일치 | `core/templates/base.html:546`, `core/templates/base.html:583` | 모달 제목 ID와 참조가 일치, 키보드 열기/닫기 정상 | `python manage.py test products.tests.test_dashboard_modals -v 2` |
| T-01 | DONE | UI 핵심 테스트 7개 실패 상태 | `products/tests/test_modal_consistency.py`, `products/tests/test_dashboard_modals.py`, `core/tests/test_ui_auth.py` | 기존 실패 7개가 모두 green | `python manage.py test products.tests.test_modal_consistency products.tests.test_dashboard_modals core.tests.test_ui_auth -v 2` |

## UX Priority Matrix (2026-02-18)

| ID | Priority | Item | Impact | Difficulty | Owner | Status |
|---|---|---|---|---|---|---|
| UX-01 | P0 | iPad/태블릿 오판정 차단 제거 | High (이탈 감소) | Low | Web | DONE |
| UX-02 | P0 | 모바일 미지원 페이지 대체 경로 제공(PC 열기/축소 기능/문의) | High (이탈 감소) | Medium | Web | DONE |
| UX-03 | P1 | 댓글/액션 터치 접근성 개선(hover 의존 제거) | Low-Med | Low | Web | DONE |
| UX-04 | P1 | V2 플래그 의존성 정리(배포 기본값/롤백 규칙) | High | Medium | Web+Ops | DONE |
| UX-05 | P2 | 서비스 라우팅 title 문자열 매칭 제거(route 필드화) | Med (장애 예방) | Medium | Web | DONE |
| UX-06 | P2 | 768~1024 레이아웃 재설계(사이드바/메인 폭) | Med | High | Web | DONE |
| UX-07 | P3 | IA 단순화(핵심 시나리오 1차 노출 강화) | High (전환 개선) | High | Product | DOING |

### Execution Rule (UX Track)

1. `Impact/effort` 기준으로 `P0 -> P1 -> P2 -> P3` 순서 처리.
2. `UX-04`(V2 플래그 기준) 없이는 IA/레이아웃 대형 변경(`UX-06`, `UX-07`)을 머지하지 않는다.
3. 각 항목은 `Done Condition + Validation`을 동일 PR 본문에 기록한다.

## Validation Result (2026-02-18)

- `python manage.py test products.tests.test_modal_consistency products.tests.test_dashboard_modals core.tests.test_ui_auth reservations.tests.ReservationsViewTest -v 1` -> `OK (15 passed)`
- tracked HTML 기준 `target="_blank"` + `rel` 누락 검사 -> `TOTAL_MISSING=0`
- `python manage.py test products.tests.test_views -v 2` -> `OK (10 passed)` (phone 차단, iPad 허용, force_desktop 우회, tablet rollback flag 검증)
- `python manage.py test products.tests.test_views core.tests.test_home_view products.tests.test_dashboard_modals core.tests.test_ui_auth -v 1` -> `OK (39 passed)` (검색 플래그 분리 포함)

## Decision Log

- 2026-02-18: 세션 만료 정책을 편의성 기준으로 확정하고 코드 반영
  - backend 세션 설정값과 frontend auto logout 타이머를 동일 기준으로 정합화
- 2026-02-18: large-screen 서비스 접근 정책을 "phone 기본 차단 + force_desktop 우회 + ALLOW_TABLET_ACCESS 롤백 플래그"로 적용
- 2026-02-18: Ctrl+K 검색 컨텍스트를 V2 의존에서 분리(`GLOBAL_SEARCH_ENABLED`)하여 환경별 기능 편차 완화

## Deferred (Policy Decision Needed)

- 세션 정책 불일치(24h vs 60m): 정책 확정 후 반영.
- 서비스 실행 라우팅 스키마화(title 매칭 제거): 2주 구조개선 트랙으로 분리.
