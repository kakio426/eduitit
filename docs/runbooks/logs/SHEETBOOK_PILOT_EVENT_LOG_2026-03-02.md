# Sheetbook Pilot Event Log (2026-03-02)

기록 시각: 2026-03-02 22:48  
기준 명령: `python manage.py recommend_sheetbook_thresholds --days 14`

## 1) 일일 기록 표

| date | school_or_group | class_scope | active_teachers | workspace_home_opened | home_source_sheetbook_created | home_source_action_execute_requested | home_to_create_rate(%) | create_to_action_rate(%) | blockers | next_action |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 2026-03-02 | local-pilot-baseline | baseline | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 파일럿 실사용 트래픽 미유입 | 파일럿 계정 3개 학급 대상 홈 진입/수첩 생성/기능 실행 안내(운영자, 03-02) |

## 2) 주간 스냅샷

- 기간: 최근 14일
- 누적 `workspace_home_opened`: 0
- 누적 `sheetbook_created(entry_source=workspace_home*)`: 0
- 누적 `action_execute_requested(entry_source=workspace_home*)`: 0
- 누적 홈->수첩 생성 전환율: 0.0%
- 누적 수첩 생성->기능 실행 전환율: 0.0%
- 주요 이슈: 샘플 부족
- 다음 주 액션: 파일럿 계정 3개 학급 대상 홈 진입/수첩 생성/기능 실행 안내(운영자, 03-02)

## 3) 역할별 스냅샷 참고
- role 데이터 없음

## 4) 재보정 실행 기록

### Output Snapshot

- 실행일: 2026-03-02
- 추천 목표(`SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE`): 60.0 (샘플 부족(0 < 5))
- 추천 목표(`SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE`): 50.0 (샘플 부족(0 < 5))
- 추천 샘플(`SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE`): 5
- 추천 샘플(`SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE`): 5
- 반영 여부(YES/NO): NO
- 반영 사유: 파일럿 데이터 부족으로 기본값 유지
