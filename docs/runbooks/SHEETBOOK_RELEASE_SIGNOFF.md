# Sheetbook Release Signoff Runbook

작성일: 2026-03-01  
대상: P0 베타 공개 전 최종 승인(`SB-014`, `SB-015`, `SB-006` 포함)

## 1) 목적

- 자동 게이트(preflight + smoke)와 수동 게이트(실계정/실기기)를 한 화면에서 판정한다.
- 배포 승인/보류/차단 결정을 기록 가능한 형태로 남긴다.

## 2) 자동 게이트 실행

```bash
python scripts/run_sheetbook_release_readiness.py --days 14
```

실기기 면제 정책(기본 적용):

- 기본값으로 `real_device_grid_1000_smoke`는 면제 처리된다.
- 면제를 해제하고 수동 대기 항목으로 다시 포함하려면:

```bash
python scripts/run_sheetbook_release_readiness.py --days 14 --no-waive-real-device-smoke
```

산출물:

- `docs/handoff/sheetbook_release_readiness_latest.json`

판정 규칙:

- `overall.status=PASS`
  - 자동 게이트 통과 + 파일럿 샘플 기준 충족
- `overall.status=HOLD`
  - 자동 게이트는 통과했지만 파일럿 샘플 부족 또는 수동 점검 대기
- `overall.status=FAIL`
  - preflight/smoke 중 하나라도 실패

자동 smoke 집계 항목:

- `smoke_sheetbook_grid_1000_latest.json`
- `smoke_sheetbook_consent_recipients_latest.json`
- `smoke_sheetbook_consent_recipients_300_latest.json` (존재 시 함께 판정)
- `smoke_sheetbook_allowlist_latest.json`
- `sheetbook_consent_freeze_snapshot_latest.json` (선택: freeze diff 참고)

`smoke_sheetbook_consent_recipients*`는 밀집 문제 줄 구간에서 아래를 함께 검증한다.

- 미니맵 lane 분산(`minimap_lane_count>=2`)
- 중복 marker 위치 없음(`minimap_duplicate_lane_top_count=0`)
- 미니맵 점프 다중 샘플 정확도(`line_jump_by_minimap.checked_count>=3`, `ok=true`)

freeze 기준선 diff를 함께 남기려면:

```bash
python scripts/run_sheetbook_consent_freeze_snapshot.py
```

## 3) 수동 점검 상태 + 최종 의사결정

수동 점검 상태를 파일로 관리하고 최종 `GO/HOLD/STOP`를 계산:

```bash
python scripts/run_sheetbook_signoff_decision.py
```

입력/출력 파일:

- 입력(자동): `docs/handoff/sheetbook_release_readiness_latest.json`
- 입력/갱신(수동 상태): `docs/handoff/sheetbook_manual_signoff_latest.json`
- 출력(최종 판정): `docs/handoff/sheetbook_release_decision_latest.json`
- 출력(운영 로그, 권장): `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_<YYYY-MM-DD>.md`
- 출력의 `next_actions`:
  - 현재 상태에서 바로 실행 가능한 다음 명령을 자동 추천
  - 예: `staging_real_account_signoff`/`production_real_account_signoff` PASS 반영 명령
- 출력의 `decision_context.manual_alias_statuses`:
  - 수동 점검 alias 단위 집계 상태를 함께 제공
  - 예: `staging_real_account_signoff`, `production_real_account_signoff`, `real_device_grid_1000_smoke`

기본값으로 실기기 항목은 자동 `PASS(waived_by_policy)` 처리된다.  
해제하려면:

```bash
python scripts/run_sheetbook_signoff_decision.py --no-waive-real-device-smoke
```

베타 운영에서 파일럿 샘플 부족(`readiness=HOLD`)을 조건부 허용하려면:

```bash
python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta
```

검증 후 운영 상태를 HOLD로 복구:

```bash
python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending
```

조건:

- `readiness_overall.automated_gate_pass=true`
- 수동 점검(실기기 면제 포함) 항목이 모두 `PASS`
- 위 조건이면 `decision=GO`로 계산

`--set` 옵션으로 수동 점검 상태를 바로 반영 가능:

```bash
python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:ok
```

staging/prod를 한 번에 반영:

```bash
python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok
```

지원 key:

- `staging_allowlisted`
- `staging_non_allowlisted`
- `production_allowlisted`
- `production_non_allowlisted`
- `real_device_grid_1000`
- `staging_real_account_signoff` (alias: `staging_allowlisted` + `staging_non_allowlisted`)
- `production_real_account_signoff` (alias: `production_allowlisted` + `production_non_allowlisted`)
- `real_device_grid_1000_smoke` (alias: `real_device_grid_1000`)

판정 파일 기반 운영 로그를 자동 생성하려면:

```bash
python scripts/run_sheetbook_release_signoff_log.py --author sheetbook-ops
```

## 4) 수동 게이트 체크리스트

아래 항목은 자동 스크립트가 대체하지 못하므로 운영자가 직접 체크한다.

1. `staging_real_account_signoff`
- allowlisted 교사 계정으로 `index/create/detail` 동선 1회
- 비 allowlisted 교사 계정 차단(베타 경로) 1회
- 결과: `PASS/HOLD/FAIL` 기록

2. `production_real_account_signoff`
- 운영 실계정(allowlisted) 동선 점검 1회
- 차단 계정 1회 점검
- 결과: `PASS/HOLD/FAIL` 기록

3. `real_device_grid_1000_smoke`
- 실기기에서 `grid_limit=1000` 체감/편집/저장 확인
- 참조: `docs/runbooks/SHEETBOOK_GRID_1000_SMOKE.md`
- 결과: `PASS/HOLD/FAIL` 기록

## 5) 승인 기준

- `GO`
  - 자동 게이트 `PASS`
  - 수동 게이트 3개 모두 `PASS`
- `HOLD`
  - 자동 게이트 `HOLD` 또는 수동 게이트 일부 미완료
- `STOP`
  - 자동 게이트 `FAIL` 또는 수동 게이트 `FAIL` 발생

## 6) 기록 템플릿

템플릿 파일:

- `docs/runbooks/templates/sheetbook_release_signoff_template.md`

일일 로그 예시:

- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_<YYYY-MM-DD>.md`

자동 생성(권장):

- `python scripts/run_sheetbook_release_signoff_log.py --author <작성자>`
