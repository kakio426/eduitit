# PLAN: UX Rollout Continuation (2026-02-18)

## 1) 목적
- 현재 진행 중인 UX 개선(UX-04 ~ UX-07)을 안전하게 이어가기 위한 실행 계획을 고정한다.
- 문제 발생 시 즉시 롤백할 수 있도록 플래그/검증 기준을 문서화한다.

## 2) 현재 확정 상태 (Snapshot)
- 완료:
  - UX-01: iPad/태블릿 차단 정책 개선
  - UX-02: 모바일 미지원 페이지 대체 경로 추가
  - UX-03: 댓글/액션 터치 접근성 개선
  - UX-04: V2 플래그 의존성 정리 (기본값 True + 롤백 규칙 문서화)
  - UX-05: route 필드화 (모델/마이그레이션/백필 + title fallback 제거)
  - UX-06: 768~1024 레이아웃 재설계 (SNS 분기점 `xl` 전환)
- 진행 중:
  - UX-07: IA 단순화 (섹션 preview cap 적용 완료, 추가 구조 단순화 잔여)

## 3) 이미 반영된 운영 라인
- 디바이스/롤백 플래그
  - `config/settings.py:432` `ALLOW_TABLET_ACCESS`
  - `config/settings_production.py:548` `ALLOW_TABLET_ACCESS`
- 검색 플래그 분리
  - `config/settings.py:433` `GLOBAL_SEARCH_ENABLED`
  - `config/settings_production.py:549` `GLOBAL_SEARCH_ENABLED`
  - `core/context_processors.py:75` (`HOME_V2_ENABLED` 의존 제거)
- 대화면 서비스 진입 정책
  - `products/views.py:10` `_is_phone_user_agent`
  - `products/views.py:31` `_is_force_desktop`
  - `products/views.py:36` `_should_block_for_large_screen_service`
  - `products/views.py:88`, `products/views.py:102` (`continue_url`)
- 차단 페이지 대체 경로
  - `products/templates/products/mobile_not_supported.html:34`
- 터치 접근성
  - `core/templates/core/partials/comment_item.html:22`

## 4) 다음 실행 순서
1. UX-04 마무리(운영 기준 확정)
- `HOME_V2_ENABLED` 기본값 운영/스테이징 기준 확정
- 플래그 롤백 역할 확정:
  - `HOME_V2_ENABLED`
  - `GLOBAL_SEARCH_ENABLED`
  - `ALLOW_TABLET_ACCESS`
- 배포 문서 반영

2. UX-05 이후 구조 개선
- 목표: `title` 문자열 분기 제거
- 방식: `Product`의 명시적 launch route 필드 기반 라우팅
- 호환 기간을 두고 기존 분기 완전 제거

3. UX-06 태블릿 레이아웃 안정화
- 범위: `768~1024` 구간
- 목표: SNS 사이드바와 메인 콘텐츠 충돌 제거

4. UX-07 IA 단순화 완료
- 핵심 사용자 시나리오를 첫 화면 1차 노출
- 보조 기능은 접기/2차 진입으로 이동

## 5) 검증 게이트 (각 단계 공통)
- 필수 명령:
  - `python manage.py check`
  - 단계별 관련 테스트
- 최소 스모크 테스트:
  - `python manage.py test products.tests.test_views core.tests.test_home_view products.tests.test_dashboard_modals core.tests.test_ui_auth -v 1`
- 배포 전 확인:
  - phone / iPad / desktop 진입 정책
  - 검색 모달 노출/비노출 (`GLOBAL_SEARCH_ENABLED`)
  - 모달 열기/닫기 및 주요 플로우

## 6) 장애 시 롤백
- 태블릿 정책 이슈: `ALLOW_TABLET_ACCESS=False/True` 즉시 전환
- 검색/IA 이슈: `GLOBAL_SEARCH_ENABLED=False`로 검색 기능만 분리 비활성화
- V2 레이아웃 이슈: `HOME_V2_ENABLED=False`로 V1 즉시 복귀

## 7) 분석 및 기록 규칙
- 모든 변경은 `docs/handoff/HANDOFF_ux_rollout_snapshot_2026-02-18.md`에 추적 기록
- 테스트는 "명령 + 통과 여부" 형식으로 기록
- 재현 조건(UA, 플래그 값, URL 파라미터)을 함께 남긴다
