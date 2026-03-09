# Teacher-First Workflow Bundle D2 Checklist

작성일: 2026-03-08

## Status
- 현재 상태: 완료
- 선행 조건: `D1 noticegen -> consent/signatures` 완료
- 다음 작업 단위: `내 작업대 고도화 (Phase E)`

## Goal
- `예약 -> 결과 확인 -> 안내문/학부모 소통` 흐름을 하나의 교사 업무처럼 연결한다.
- 예약 결과가 후속 작업 seed로 자연스럽게 전달되게 한다.
- 출발 화면이 달라도 결과 복귀 구조를 동일하게 만든다.

## Locked Decisions
- canonical entry는 `reservations`
- 후속 흐름은 `예약 -> 결과 확인 -> 안내문/학부모 소통`
- 대상 연결은 `reservations -> noticegen`, `reservations -> parentcomm`
- seed 계약은 기존 `workflow_action_seeds`를 확장해서 사용
- 예약 관리자 기능은 계속 2차 위치 유지

## Implementation Checklist
- [x] `reservations -> noticegen` 후속 CTA 위치 결정
- [x] `reservations -> parentcomm` 후속 CTA 위치 결정
- [x] `origin_service`, `origin_url`, `origin_label`, `action_type`, `prefill_payload` seed shape 고정
- [x] `noticegen`가 예약 결과를 안내문 seed로 읽도록 연결
- [x] `parentcomm`가 예약 결과를 메시지/상담 seed로 읽도록 연결
- [x] 결과 화면에서 원본 예약 화면 복귀 링크 통일
- [x] 버튼 문구를 `안내문으로 이어서 만들기`, `학부모 연락으로 이어서 하기`로 통일
- [x] 관리자용 버튼과 교사용 후속 버튼 분리
- [x] legacy/empty seed 실패 시 무반응 없이 fallback 처리

## Validation
- [x] `reservations -> noticegen` 통합 테스트
- [x] `reservations -> parentcomm` 통합 테스트
- [x] 복귀 링크 테스트
- [x] seed 없는 직접 진입 fallback 테스트
- [x] `python manage.py check`
- [x] 대상 앱 테스트
- [x] 관련 JS `node --check` (이번 단계는 JS 파일 변경 없음, 템플릿/서버 계약만 변경)

## Exit Criteria
- 예약은 더 이상 독립 도구가 아니라 후속 업무 출발점으로 느껴진다.
- 출발이 예약이든 후속 화면이든 결과 복귀 구조가 같다.

## Next After This
- [CHECKLIST_teacher_first_workbench_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_workbench_2026-03-08.md)
