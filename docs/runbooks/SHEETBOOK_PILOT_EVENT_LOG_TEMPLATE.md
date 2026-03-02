# Sheetbook Pilot Event Log Template

작성일: 2026-03-01  
용도: `SB-014` 임계치 재보정을 위한 파일럿 운영 기록

## 1) 사용 방법

1. 아래 일일 기록 표를 복사해 날짜별로 채운다.
2. 최소 3개 학급/학년 단위로 기록한다.
3. 주 1회 `recommend_sheetbook_thresholds` 결과를 붙이고 재보정 여부를 결정한다.

## 2) 일일 기록 표

| date | school_or_group | class_scope | active_teachers | workspace_home_opened | home_source_sheetbook_created | home_source_action_execute_requested | home_to_create_rate(%) | create_to_action_rate(%) | blockers | next_action |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 2026-03-01 | 예시초 파일럿A | 3학년 1~3반 | 4 | 18 | 7 | 4 | 38.9 | 57.1 | 동의서 수신자 정리 시간 필요 | 동의서 seed 예시 템플릿 배포(운영자, 03-02) |
| YYYY-MM-DD |  |  |  |  |  |  |  |  |  |  |

## 3) 주간 스냅샷

- 기간:
- 누적 `workspace_home_opened`:
- 누적 `sheetbook_created(entry_source=workspace_home*)`:
- 누적 `action_execute_requested(entry_source=workspace_home*)`:
- 누적 홈->수첩 생성 전환율:
- 누적 수첩 생성->기능 실행 전환율:
- 주요 이슈:
- 다음 주 액션:

## 4) 재보정 실행 기록

### Command

```bash
python manage.py recommend_sheetbook_thresholds --days 14
python manage.py check_sheetbook_preflight --strict --recommend-days 14
```

### Output Snapshot

- 실행일:
- 추천 목표(`SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE`):
- 추천 목표(`SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE`):
- 추천 샘플(`SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE`):
- 추천 샘플(`SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE`):
- 반영 여부(YES/NO):
- 반영 사유:
