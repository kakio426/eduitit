# Teacher-First Discovery Checklist

작성일: 2026-03-08

## Status
- 현재 상태: 완료
- 선행 조건: `내 작업대` 구조 고정
- 다음 작업 단위: 추천/발견성 계층 설계

## Goal
- 새 기능이 `광고판`처럼 보이지 않으면서도 계속 발견되게 만든다.
- 발견성은 유지하되 메인 업무 집중을 깨지 않는다.

## Locked Decisions
- 발견성은 `광고판`이 아니라 `맥락 기반 추천`으로만 제공
- 추천은 메인 CTA보다 앞에 나오지 않는다
- 한 번에 보이는 추천 카드 수는 제한한다
- 서비스명보다 `어떤 일에 쓰는지`를 먼저 보여준다

## Implementation Checklist
- [x] `새로 써보기` 노출 기준 정의
- [x] `같이 쓰면 좋은 도구` 섹션 설계
- [x] `이번 주 많이 쓰는 조합` 섹션 설계
- [x] 최근 사용 흐름 기반 추천 룰 문서화
- [x] 추천 이유 라벨 정의
- [x] 추천 카드 최대 개수 고정
- [x] 홈에서 추천 영역이 `오늘 바로 시작`과 `내 작업대`를 밀지 않게 hierarchy 조정
- [x] 추천에서 바로 `작업대에 추가` 연결
- [x] 추천이 없는 경우 fallback UI 정의

## Validation
- [x] 홈 추천 섹션 렌더 테스트
- [x] 추천 이유 라벨 테스트
- [x] 최대 카드 수 테스트
- [x] 추천 영역이 메인 섹션보다 먼저 오지 않는 UI 계약 테스트


## Recommendation Rule
- 추천 seed는 `내 작업대`, `최근 이어서`, `오늘 바로 시작`에서 이미 쓰고 있는 도구를 우선 사용한다.
- `같이 쓰면 좋은 도구`는 `HOME_COMPANION_SECTION_MAP` 기준으로만 이어 붙이고, 이미 작업대나 최근 사용에 있는 도구는 제외한다.
- 추천 카드는 최대 3개까지만 보여주고, 이유 라벨은 `지금 하는 일 + 같이 쓰기` 방식으로 짧게 유지한다.
- `새로 써보기`는 추천/작업대/최근 사용에 이미 나온 도구를 다시 노출하지 않는다.
## Exit Criteria
- 새 도구를 발견할 수 있지만, 메인 업무 집중은 깨지지 않는다.

## Next After This
- [CHECKLIST_teacher_first_design_system_2026-03-08.md](/C:/Users/kakio/eduitit/docs/plans/CHECKLIST_teacher_first_design_system_2026-03-08.md)
