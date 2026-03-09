# Teacher-First Mobile + Release Gate Checklist

작성일: 2026-03-08

## Status
- 현재 상태: 완료
- 메모: 공통 모바일 차단 화면을 큰 설명 박스 대신 짧은 이유 + 다음 행동 2개 구조로 축소
- 선행 조건: 전사 UI 문법 초안 고정
- 다음 작업 단위: 브라우저 smoke를 허용하는 로컬/배포 전 검증 환경에서 최종 재확인

## Goal
- 엔터프라이즈급 기준으로 모바일 정책과 운영 검증을 잠근다.
- 배포 전 통과/실패를 문서만 보고 판단할 수 있게 만든다.

## Locked Decisions
- 모바일은 `제한 편집` 원칙
- 허용: 단건 입력, 확인, 간단 수정
- 비허용: 대량 입력, 복잡한 구조 변경
- 무반응 버튼은 금지
- 배포 기준은 smoke, 접근성, console, rollback 포함

## Implementation Checklist
- [x] 모바일 공통 정책 문서화
- [x] 서비스별 safe/unsafe action 분류표 작성
- [x] 막힌 기능은 비활성/짧은 이유 표시로 통일
- [x] 무반응 버튼 전수 점검
- [x] 주요 서비스 smoke 스위트 목록 확정
- [x] 접근성 계약 정의
- [x] focus
- [x] dialog
- [x] keyboard only
- [x] aria-live
- [x] console error 0 기준 문서화
- [x] 이벤트 로깅/실패 로그 기준 정의
- [x] rollback checklist 작성
- [x] release gate 문서 작성
- [x] 정적 계약 검사 스크립트 추가

## Validation
- [x] 모바일 경로 smoke
- [x] 접근성 smoke
- [x] console `ReferenceError` 0
- [x] release gate dry-run
- [x] 정적 계약 검사 실행
- [x] 홈 작업대 접근성 정적 계약 포함
- [x] 복사 CTA 실패 피드백 정적 계약 포함
- [x] smoke-only blocked 분류 확인

## Current Notes
- 2026-03-09 local escalated run 기준으로 브라우저 smoke와 full gate가 실제 통과했다.
- 권한이 제한된 환경에서는 같은 명령이 다시 `blocked`로 기록될 수 있으므로, 그 경우에는 코드 실패와 환경 실패를 구분해서 본다.
- SQLite 환경에서는 smoke를 병렬로 돌리면 `database is locked`가 날 수 있으므로 반드시 순차 실행한다.

## References
- [POLICY_teacher_first_mobile_2026-03-09.md](/C:/Users/kakio/eduitit/docs/plans/POLICY_teacher_first_mobile_2026-03-09.md)
- [RELEASE_GATE_teacher_first_2026-03-09.md](/C:/Users/kakio/eduitit/docs/plans/RELEASE_GATE_teacher_first_2026-03-09.md)

## Exit Criteria
- 배포 전 통과/실패를 문서만 보고 판단할 수 있다.
- 모바일에서 왜 안 되는지 설명보다 구조로 이해된다.

## Next After This
- 마스터 체크리스트 [CHECKLIST_eduitit_teacher_first_execution_v2_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_eduitit_teacher_first_execution_v2_2026-03-08.md) 상태를 완료로 유지한다.
- 이후 대형 UX 변경이 생기면 같은 gate를 다시 실행한다.
