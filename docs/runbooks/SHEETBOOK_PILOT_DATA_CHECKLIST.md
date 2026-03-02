# Sheetbook Pilot Data Checklist

작성일: 2026-03-01  
대상: `SB-014` 퍼널 임계치 재보정을 위한 파일럿 데이터 수집

## 1) 수집 목표

- 임계치 재보정에 필요한 이벤트 샘플을 먼저 확보한다.
- 최소 수집 기준(권장):
  - `workspace_home_opened` 20건 이상
  - `sheetbook_created(entry_source=workspace_home*)` 10건 이상
  - `action_execute_requested(entry_source=workspace_home*)` 5건 이상

## 2) 이벤트 확인 명령

아래 명령으로 최근 14일 이벤트를 점검:

```bash
python manage.py recommend_sheetbook_thresholds --days 14
```

샘플 부족 문구가 사라질 때까지 파일럿 사용 데이터를 누적한다.

기록 템플릿:

- Markdown: `docs/runbooks/SHEETBOOK_PILOT_EVENT_LOG_TEMPLATE.md`
- CSV: `docs/runbooks/templates/sheetbook_pilot_event_log_template.csv`

자동 스냅샷(권장):

```bash
python scripts/run_sheetbook_pilot_log_snapshot.py --days 14
```

- 기본 출력:
  - `docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_<YYYY-MM-DD>.md`
  - `docs/runbooks/logs/sheetbook_pilot_event_log_<YYYY-MM-DD>.csv`

## 3) 파일럿 운영 체크 포인트

1. 홈에서 교무수첩 진입(목록 열기) 경로로 실제 사용 유도
2. 홈 진입 후 `새 수첩` 또는 `이어쓰기` 실행 유도
3. 생성 직후 기능 1개 이상(달력/수합/동의서/배부/안내문) 실행 유도
4. 최소 3개 학급/학년 단위로 분산 수집
5. 일일 기록표에 blockers/next_action까지 함께 기록

## 4) 재보정 실행 절차

1. 추천값 산출:
  - `python manage.py recommend_sheetbook_thresholds --days 14`
2. 권장값을 env에 반영:
  - `SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE`
  - `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE`
  - `SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE`
  - `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE`
3. strict 재검증:
  - `python manage.py check_sheetbook_preflight --strict --recommend-days 14`

## 5) 판정 기준

- `PASS`
  - 추천 커맨드에서 샘플 부족이 아니고 권장값이 산출됨
  - env 반영 후 strict preflight 통과
- `HOLD`
  - 샘플 부족으로 현재 설정 유지 문구가 출력됨
  - 파일럿 수집 기간을 연장하고 동일 절차 재실행
