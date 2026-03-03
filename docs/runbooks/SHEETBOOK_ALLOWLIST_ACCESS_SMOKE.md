# Sheetbook Allowlist Access Smoke Runbook

작성일: 2026-03-01  
대상: `SB-015` 베타 allowlist 접근 게이트 동작 검증

## 1) 목적

- `SHEETBOOK_ENABLED=False`에서 allowlisted 계정만 접근 가능한지 확인한다.
- `SHEETBOOK_ENABLED=True`에서 비 allowlisted 계정도 접근 가능한지 확인한다.
- index/create/detail 핵심 동선의 상태코드를 자동 검증해 운영 전 게이트 회귀를 빠르게 탐지한다.

## 2) 실행 명령

```bash
python scripts/run_sheetbook_allowlist_smoke.py
```

산출물:

- `docs/handoff/smoke_sheetbook_allowlist_latest.json`

## 3) 검증 시나리오

1. 베타 전용 경로(`SHEETBOOK_ENABLED=False`, allowlist 설정)
- allowlisted 사용자:
  - `GET /sheetbook/` -> `200`
  - `POST /sheetbook/create/` -> `302`
  - `GET /sheetbook/<created_id>/` -> `200`
- 비 allowlisted 사용자:
  - `GET /sheetbook/` -> `404`
  - `POST /sheetbook/create/` -> `404`

2. 전체 공개 경로(`SHEETBOOK_ENABLED=True`, allowlist 비움)
- 비 allowlisted 사용자:
  - `GET /sheetbook/` -> `200`
  - `POST /sheetbook/create/` -> `302`
  - `GET /sheetbook/<created_id>/` -> `200`

## 4) 합격 기준

- `PASS`
  - 출력 JSON의 `evaluation.pass=true`
  - `evaluation.reasons`가 빈 배열
- `FAIL`
  - 상태코드 기대치 불일치
  - create/detail 동선 중 하나라도 실패

## 5) 운영 적용 메모

- 베타 배포 직전에는 아래 순서로 함께 실행:
  1. `python manage.py check_sheetbook_preflight --strict --recommend-days 14`
  2. `python scripts/run_sheetbook_allowlist_smoke.py`
- FAIL 시 우선 점검 항목:
  - `SHEETBOOK_ENABLED`
  - `SHEETBOOK_BETA_USERNAMES`, `SHEETBOOK_BETA_EMAILS`, `SHEETBOOK_BETA_USER_IDS`
