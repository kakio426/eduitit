# Eduitit Teacher-First Execution Checklist v2

작성일: 2026-03-08
기준 브랜치: `codex/teacher-first-home-ia`

## 역할
- 이 문서는 `전체 진행 현황 요약`만 관리한다.
- 상세 구현 항목은 단계별 체크리스트 문서에서 관리한다.
- canonical contract는 계약 문서를 우선 기준으로 본다.

## Canonical Docs
- [CONTRACT_teacher_first_product_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CONTRACT_teacher_first_product_2026-03-08.md)
- [CONTRACT_workflow_bundle_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CONTRACT_workflow_bundle_2026-03-08.md)

## Detailed Checklists
- [CHECKLIST_teacher_first_service_shell_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_service_shell_2026-03-08.md)
- [CHECKLIST_workflow_bundle_d2_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_workflow_bundle_d2_2026-03-08.md)
- [CHECKLIST_teacher_first_workbench_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_workbench_2026-03-08.md)
- [CHECKLIST_teacher_first_discovery_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_discovery_2026-03-08.md)
- [CHECKLIST_teacher_first_design_system_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_design_system_2026-03-08.md)
- [CHECKLIST_teacher_first_mobile_release_gate_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_mobile_release_gate_2026-03-08.md)

## Current Status
- Phase A: 완료
- Phase B: 완료
- Phase C: 우선 서비스군 완료
- Phase D1: 완료
- Phase D2: 완료
- Phase E: 완료
- Phase F: 완료
- Phase G: 완료
- 메모: signatures/maker의 보관함 안내와 복귀 라벨도 작업 우선 구조에 맞게 축소
- 메모: parentcomm는 `오늘 할 일 / 쪽지 / 상담`만 전면에 두고 `알림장 / 연락처`를 보조 메뉴로 내려 탭 과밀을 줄임
- Phase H: 완료

## Phase Map
### Phase A. 기준선 잠금
상태: 완료

- `home/catalog baseline` 문서 상태 표시 완료
- `service shell baseline` 문서 상태 표시 완료
- same-source-of-truth 문서 고정 완료
- 기준선 구현은 이후 단계의 출발점으로 잠금

### Phase B. 전역 진입 구조 마감
상태: 완료

- 홈, 전체 서비스, 이용방법, 가이드 역할 분리 완료
- `하려는 일` 중심 탐색 구조 반영 완료
- `내 작업대`, `새로 써보기`, `핵심 업무`, `더 많은 도구` 계층 반영 완료

### Phase C. 공통 서비스 셸 전사 확장
상태: 우선 서비스군 + 남은 후보 완료

- 완료 서비스: `sheetbook`, `classcalendar`, `noticegen`, `timetable`, `parentcomm`, `reservations`, `consent`, `signatures`, `hwpxchat`, `textbooks`, `slidesmith`, `happy_seed`
- 남은 후보 없음
- 상세 기준: [CHECKLIST_teacher_first_service_shell_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_service_shell_2026-03-08.md)

### Phase D. 핵심 워크플로우 묶음 통합
상태: D1 완료, D2 완료

- D1 완료: `noticegen -> consent`, `noticegen -> signatures`
- D2 완료: `reservations -> noticegen`, `reservations -> parentcomm`
- 상세 기준: [CHECKLIST_workflow_bundle_d2_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_workflow_bundle_d2_2026-03-08.md)

### Phase E. 내 작업대 고도화
상태: 완료

- 즐겨찾기를 `개인 작업대`로 완성하는 단계
- 작업대 접근성 정적 계약과 브라우저 smoke가 release gate에서 함께 통과했다
- 완료 범위: `최근 이어서` 분리, `업무 조합` 저장/적용, 추천 카드 `작업대에 추가`, 기본 슬롯 4칸, 조합 card화, 조합 삭제, task-first 미리보기, 키보드/모바일 순서 버튼 정리
- 상세 기준: [CHECKLIST_teacher_first_workbench_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_workbench_2026-03-08.md)

### Phase F. 발견성 고도화
상태: 완료

- 메인 업무를 방해하지 않는 추천/발견 구조 설계 단계
- 완료: `같이 쓰면 좋은 도구`, `이번 주 많이 쓰는 조합`, 추천 이유 라벨, 최대 카드 수 제한, 최근 사용 흐름 기반 추천 룰 문서화
- 상세 기준: [CHECKLIST_teacher_first_discovery_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_discovery_2026-03-08.md)

### Phase G. 설명 제거 + 디자인 시스템
상태: 완료

- 설명형 UI 감사표와 공통 token 문서를 잠근 뒤, `noticegen / reservations / parentcomm / hwpxchat / textbooks / consent / slidesmith / happy_seed` 샘플 롤아웃, `홈 / 카탈로그 / 빠른 사용 안내` 작업명 우선 카드 문법, `service_guide_detail / tool_guide` 설명 밀도 축소까지 반영 완료
- 상세 기준: [CHECKLIST_teacher_first_design_system_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_design_system_2026-03-08.md)

### Phase H. 모바일 + 운영 가드
상태: 완료

- 모바일 정책 문서, 접근성/console/release gate 기준 문서, smoke 목록을 고정했고 `check_teacher_first_release_gate.py` full run까지 실제 통과했다.
- 정적 계약 검사 스크립트, 홈 작업대 접근성 계약, teacher-first 복사 CTA 실패 피드백 계약, 공통 모바일 차단 화면 축소가 모두 gate 범위에 포함되어 PASS 상태다.
- 상세 기준: [CHECKLIST_teacher_first_mobile_release_gate_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_mobile_release_gate_2026-03-08.md)

## Next Order
1. 현재 기준선 유지
2. 다음 전사 UX 묶음 선정
3. 필요한 경우 동일 gate 재실행
4. main 반영 전 범위별 검증 유지
5. 통합 회귀 + main 반영 잠금
6. 다음 후보 서비스/워크플로우 확장
7. 반복
