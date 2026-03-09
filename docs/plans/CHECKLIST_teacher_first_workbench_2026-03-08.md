# Teacher-First Workbench Checklist

작성일: 2026-03-08

## Status
- 현재 상태: 완료
- 메모: 정적 접근성 계약은 release gate에 포함
- 메모: 저장한 조합 card화, 조합 삭제, task-first 미리보기, 모바일 순서 변경 버튼 가시성 개선 반영
- 선행 조건: 홈/카탈로그 baseline 완료
- 다음 작업 단위: 다음 전사 UX 묶음 착수

## Goal
- 즐겨찾기를 단순 별표가 아니라 교사별 `개인 작업대`로 완성한다.
- `최근 사용`과 `내 작업대` 역할을 분리한다.
- 교사마다 다른 워크플로우를 홈에 반영한다.

## Locked Decisions
- 즐겨찾기는 홈에서 `내 작업대`로만 보인다.
- `최근 사용`과 `내 작업대`는 별도 섹션으로 유지한다.
- 모바일은 드래그 대신 단순 순서 변경만 허용한다.
- 기존 `reorder_product_favorites` 계약은 유지한다.
- 업무 조합은 `bundle` 개념으로 별도 저장한다.

## Implementation Checklist
- [x] `내 작업대` 정보구조 고정
- [x] 고정 슬롯 개수 확정
- [x] `최근 사용` 자동 정렬 로직과 `내 작업대` 수동 정렬 로직 분리
- [x] 추천 카드에서 `작업대에 추가` CTA 추가
- [x] `업무 조합` 저장 모델/API 설계
- [x] `업무 조합` 불러오기/적용 UX 설계
- [x] 키보드 정렬 접근성 정의
- [x] 모바일 순서 변경 UX 정의
- [x] 빈 작업대 empty state 문구 최소화
- [x] 홈에서 `공용 대문` 느낌 대신 `개인 작업대`가 먼저 보이도록 hierarchy 고정

## Validation
- [x] 재정렬 테스트
- [x] bundle 저장/불러오기 테스트
- [x] 추천 카드 추가 테스트
- [x] 빈 상태/첫 사용 상태 UI 계약 테스트
- [x] 정적 접근성 계약 실행
- [x] 접근성 smoke

## Exit Criteria
- 교사마다 다른 워크플로우가 홈에 반영된다.
- 최근 사용과 즐겨찾기가 서로 역할을 침범하지 않는다.

## Next After This
- [CHECKLIST_teacher_first_discovery_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_discovery_2026-03-08.md)
