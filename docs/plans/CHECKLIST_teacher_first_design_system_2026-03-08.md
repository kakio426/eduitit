# Teacher-First Design System Checklist

작성일: 2026-03-08

## Status
- 현재 상태: 완료
- 메모: `noticegen / reservations / parentcomm / hwpxchat / textbooks / consent / slidesmith / happy_seed` 샘플 롤아웃 이후 `service_guide_detail / tool_guide / service_guide_list / product_list / mini_card`까지 작업명 우선 카드 문법과 설명 밀도 축소 반영
- 선행 조건: 발견성 구조 고정
- 다음 작업 단위: 다음 전사 디자인 적용 범위 결정

## Goal
- 설명형 UI를 줄이고 전사 UI 문법을 통일한다.
- 서비스가 달라도 한 제품처럼 보이게 만든다.

## Locked Decisions
- 전사 UI 문법은 `설명보다 구조`
- 버튼 hierarchy, 카드 여백, 상태 색상, 모달/드로어 패턴은 공통 토큰으로 정의
- 브랜드명은 보조, 작업명은 전면
- 긴 설명 박스는 최종 구조에서 금지

## Implementation Checklist
- [x] 설명 카드 전수 조사표 작성
- [x] teacher-first UI token 정의
- [x] primary/secondary/tertiary button 규칙 정의
- [x] 카드 spacing 규칙 정의
- [x] 상태 색상 규칙 정의
- [x] 모달/드로어 패턴 정의
- [x] empty state/success/error 패턴 정의
- [x] 작업명 우선 표기 규칙을 홈/카탈로그/서비스 카드에 반영
- [x] 서비스별 예외 패턴 제거 목록 작성
- [x] 최소 3개 서비스에 공통 패턴 샘플 적용 후 전사 확장

## Validation
- [x] 토큰/패턴 문서화
- [x] 샘플 서비스 UI 계약 테스트
- [x] 설명 카드 감소 전후 수동 리뷰
- [x] 브라우저 스모크에서 중복 CTA/과한 설명 0건 확인

## References
- [TOKENS_teacher_first_ui_2026-03-09.md](/C:/Users/kakio/eduitit/docs/plans/TOKENS_teacher_first_ui_2026-03-09.md)
- [AUDIT_teacher_first_explanatory_ui_2026-03-09.md](/C:/Users/kakio/eduitit/docs/plans/AUDIT_teacher_first_explanatory_ui_2026-03-09.md)

## Exit Criteria
- 서비스가 달라도 한 제품처럼 보인다.
- 설명을 읽어야 이해되는 구조가 눈에 띄게 줄어든다.

## Next After This
- [CHECKLIST_teacher_first_mobile_release_gate_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_mobile_release_gate_2026-03-08.md)
