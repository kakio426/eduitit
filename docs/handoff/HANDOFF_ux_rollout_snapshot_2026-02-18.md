# Handoff: UX Rollout Snapshot (2026-02-18)

## 1. 요약
- 본 문서는 UX 개선 작업의 "현재 진행 상황 + 재현 정보"를 저장한 스냅샷이다.
- 문제 발생 시 이 문서와 `docs/plans/PLAN_ux_rollout_continuation_2026-02-18.md`를 기준으로 원인 분석을 시작한다.

## 2. 이번 턴 반영 범위
- 정책/플래그
  - `ALLOW_TABLET_ACCESS` 추가
  - `GLOBAL_SEARCH_ENABLED` 추가
- 서비스 접근 정책
  - phone 차단 + `force_desktop=1` 우회
  - 태블릿 롤백 가능 구조
- UI
  - 모바일 미지원 화면에 "그래도 계속 진행" 경로 추가
  - 댓글 액션 터치 접근성 개선
- 테스트
  - device policy/force_desktop/플래그 분기 테스트 추가
  - V1 검색 컨텍스트 테스트 추가

## 3. 핵심 변경 파일 (추적 대상)
- `products/views.py`
- `products/templates/products/mobile_not_supported.html`
- `products/tests/test_views.py`
- `config/settings.py`
- `config/settings_production.py`
- `core/context_processors.py`
- `core/templates/core/partials/comment_item.html`
- `core/tests/test_home_view.py`
- `docs/plans/PLAN_must_fix_only.md`
- `docs/plans/PLAN_ux_rollout_continuation_2026-02-18.md`
- `claude.md`
- `codex/SKILL.md`

## 4. 라인 레퍼런스 (빠른 트리아지)
- 플래그:
  - `config/settings.py:432`
  - `config/settings.py:433`
  - `config/settings_production.py:548`
  - `config/settings_production.py:549`
  - `core/context_processors.py:75`
- 디바이스 정책:
  - `products/views.py:10`
  - `products/views.py:31`
  - `products/views.py:36`
  - `products/views.py:81`
  - `products/views.py:95`
- 우회 경로 UI:
  - `products/templates/products/mobile_not_supported.html:34`
- 터치 접근성:
  - `core/templates/core/partials/comment_item.html:22`
- 테스트:
  - `products/tests/test_views.py:100`
  - `core/tests/test_home_view.py:47`
  - `core/tests/test_home_view.py:52`

## 5. 실행/검증 로그
- 실행 명령 1:
  - `python manage.py test products.tests.test_views -v 2`
  - 결과: `OK (10 passed)`
- 실행 명령 2:
  - `python manage.py test products.tests.test_views core.tests.test_home_view products.tests.test_dashboard_modals core.tests.test_ui_auth -v 1`
  - 결과: `OK (39 passed)`

## 6. 현재 상태 (UX 매트릭스 기준)
- DONE: UX-01, UX-02, UX-03
- DOING: UX-04 (검색 플래그 분리 완료, `HOME_V2_ENABLED` 운영 기본값 확정 필요)
- TODO: UX-05, UX-06, UX-07

## 7. 즉시 롤백 포인트
- 태블릿 이슈 발생 시:
  - `ALLOW_TABLET_ACCESS=False` 적용
- 검색/공통 노출 이슈 발생 시:
  - `GLOBAL_SEARCH_ENABLED=False` 적용
- V2 화면 이슈 발생 시:
  - `HOME_V2_ENABLED=False` 적용

## 8. 분석 시작 순서 (장애 발생 시)
1. 증상 재현:
- 사용자 UA/해상도/URL 파라미터(`force_desktop`) 확인
2. 플래그 확인:
- `HOME_V2_ENABLED`, `GLOBAL_SEARCH_ENABLED`, `ALLOW_TABLET_ACCESS`
3. 라우팅/렌더 확인:
- `products/views.py` 분기 + 템플릿 컨텍스트
4. 테스트 재실행:
- 섹션 5의 두 명령 우선 실행

## 9. 워크트리 주의사항
- 현재 저장소는 기존 미커밋 변경이 다수 존재한다.
- 본 스냅샷은 위 "핵심 변경 파일"만 분석 대상으로 삼는다.
