# Sheetbook Release Signoff (2026-03-01)

작성일: 2026-03-01  
작성자: codex-local

## 1) 자동 게이트 스냅샷

- 실행 명령:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
- 출력 파일:
  - `docs/handoff/sheetbook_release_readiness_latest.json`
  - `docs/handoff/sheetbook_manual_signoff_latest.json`
  - `docs/handoff/sheetbook_release_decision_latest.json`
- 집계 시각:
  - 2026-03-01 13:01:39
- `overall.status`:
  - `HOLD`
- `release_decision`:
  - `HOLD`
- `blocking_reasons`:
  - 없음(자동 게이트 통과)
- `manual_pending`:
  - `staging_real_account_signoff`
  - `production_real_account_signoff`
- `waived_manual_checks`:
  - `real_device_grid_1000_smoke`
- `beta_conditional_go_option`:
  - `--allow-pilot-hold-for-beta` 사용 가능 (현재 기본 미적용)

## 2) 자동 게이트 요약

| check | result | notes |
|---|---|---|
| preflight(beta strict) | PASS | allowlist 포함 strict 통과 |
| preflight(global strict) | PASS | `SHEETBOOK_ENABLED=True` strict 통과 |
| smoke_grid_1000 | PASS | `evaluation.pass=true` |
| smoke_consent_recipients | PASS | `evaluation.pass=true` + 미니맵 다중 점프/밀집 lane 분산 검증 통과 |
| smoke_consent_recipients_300 | PASS | `evaluation.pass=true` + 300줄 밀집 마커 클릭 정확도 통과 |
| smoke_allowlist_access | PASS | `evaluation.pass=true` |
| pilot_recalibration_readiness | HOLD | 최근 14일 샘플 0건(최소 샘플 미충족) |

## 3) 수동 게이트 점검 (미완료)

| check_id | env | account_type | result(PASS/HOLD/FAIL) | notes |
|---|---|---|---|---|
| staging_real_account_signoff | staging | allowlisted | HOLD | 실행 대기 |
| staging_real_account_signoff | staging | non_allowlisted | HOLD | 실행 대기 |
| production_real_account_signoff | production | allowlisted | HOLD | 실행 대기 |
| production_real_account_signoff | production | non_allowlisted | HOLD | 실행 대기 |
| real_device_grid_1000_smoke | real-device | teacher | PASS(waived) | device-unavailable 정책 면제 |

## 4) 현재 판정

- decision: `HOLD`
- owner: 운영 담당
- next_action:
  - staging/production 실계정 동선 점검 1회씩 수행
  - 파일럿 샘플 누적 후 임계치 재보정 재실행

## 5) 추가 갱신 (2026-03-01 19:48)

- 실행 명령:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
  - `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
  - `python manage.py recommend_sheetbook_thresholds --days 14`
- 최신 집계:
  - readiness `generated_at`: `2026-03-01 19:48:13`
  - decision `generated_at`: `2026-03-01 19:48:11`
  - `overall.status`: `HOLD`
  - `release_decision`: `HOLD`
  - `manual_pending`: `staging_real_account_signoff`, `production_real_account_signoff`
  - `waived_manual_checks`: `real_device_grid_1000_smoke`
- 파일럿 관측/재보정:
  - 최근 14일 관측치 0건으로 `pilot.status=HOLD` 유지
  - 권장 임계치 변화 없음(60/50, min sample 5/5)
- strict preflight 메모:
  - 기본 로컬 env(`SHEETBOOK_ENABLED=False`, beta allowlist 미설정)에서는 strict 경고로 실패
  - 베타 운영 가정 env(`SHEETBOOK_ENABLED=True`, `SHEETBOOK_BETA_USERNAMES=beta_teacher`)에서는 strict 통과

## 6) 조건부 GO 재검증 + 상태 복구 (2026-03-01 19:51)

- 실행 명령:
  - `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta --set staging_real_account_signoff=PASS:beta-ready-check-20260301 --set production_real_account_signoff=PASS:beta-ready-check-20260301`
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`
- 결과:
  - 1차(검증): `decision=GO`
    - `readiness_status=HOLD`, `automated_gate_pass=true`, `pilot_hold_for_beta=true`
  - 2차(복구): `decision=HOLD`
    - 수동 실계정 항목을 `HOLD:pending`으로 복귀
    - 실기기 항목은 정책상 `PASS(waived_by_policy)` 유지
