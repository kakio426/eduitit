# Sheetbook Beta Rollout Runbook

작성일: 2026-02-28

## 1) 환경변수 설정

필수:

- `SHEETBOOK_ENABLED=False`

내부 베타 계정 allowlist(콤마 구분):

- `SHEETBOOK_BETA_USERNAMES=teacher_a,teacher_b`
- `SHEETBOOK_BETA_EMAILS=teacher_a@school.kr,teacher_b@school.kr`
- `SHEETBOOK_BETA_USER_IDS=101,102`
- `SHEETBOOK_ENABLED=False` 상태에서 `check_sheetbook_rollout --strict`를 통과하려면 allowlist 1개 이상이 필요

운영 지표 임계치(파일럿 데이터 기준으로 조정):

- `SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE=60`
- `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE=50`
- `SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE=5`
- `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE=5`

파일럿 이벤트 기반 추천값 산출(선택):

- `python manage.py recommend_sheetbook_thresholds --days 14`
- `python manage.py recommend_sheetbook_thresholds --days 14 --group-by-role`
- 출력된 `SHEETBOOK_WORKSPACE_*` 권장값을 env에 반영한 뒤 `check_sheetbook_rollout --strict`로 재검증
- role별 편차가 크면 전체 권장값 반영 전에 파일럿 운영 대상(role/학교군) 기준으로 재해석
- 파일럿 수집 체크리스트: `docs/runbooks/SHEETBOOK_PILOT_DATA_CHECKLIST.md`
- 파일럿 운영 로그 템플릿: `docs/runbooks/SHEETBOOK_PILOT_EVENT_LOG_TEMPLATE.md`
- 파일럿 운영 로그 자동 스냅샷: `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`

교시 표기 사용 시:

- `SHEETBOOK_PERIOD_FIRST_CLASS_HOUR=9`
- `SHEETBOOK_ROLLOUT_STRICT_STARTUP=True` (부팅 시 경고도 실패 처리하려면)
- `SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP=False` (부팅 시 임계치 추천 출력 활성화 여부)
- `SHEETBOOK_ROLLOUT_RECOMMEND_DAYS=14` (추천 집계 기간)
- `SHEETBOOK_PREFLIGHT_STRICT=True` (pre-deploy 스크립트에서 strict 점검을 강제하려면)

## 2) 배포 전 점검

아래 명령을 순서대로 실행:

```bash
python manage.py migrate --noinput
python manage.py check_sheetbook_preflight --strict --recommend-days 14
python manage.py check
python manage.py test sheetbook.tests
```

모두 통과하면 베타 배포 진행.

보조 스크립트:

- Linux/macOS: `bash scripts/pre_deploy_check.sh`
- Windows PowerShell: `.\scripts\pre_deploy_check.ps1`
- 수동 체감 점검(권장): `docs/runbooks/SHEETBOOK_GRID_1000_SMOKE.md` 기준으로 `grid_limit=1000` 스모크 1회
- 수신자 편집 점검(권장): `docs/runbooks/SHEETBOOK_CONSENT_RECIPIENTS_SMOKE.md` 기준으로 대량 수신자 스모크 1회
- allowlist 접근 게이트 점검(권장): `python scripts/run_sheetbook_allowlist_smoke.py`
  - 상세 runbook: `docs/runbooks/SHEETBOOK_ALLOWLIST_ACCESS_SMOKE.md`
- 출시 준비도 집계(권장): `python scripts/run_sheetbook_release_readiness.py --days 14`
  - 상세 runbook: `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
- 최종 의사결정 집계(권장): `python scripts/run_sheetbook_signoff_decision.py`
  - alias 예시: `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:ok --set production_real_account_signoff=PASS:ok --set real_device_grid_1000_smoke=PASS:ok`
  - 현재 정책: 실기기 항목은 기본 면제(auto PASS). 필요 시 `--no-waive-real-device-smoke`로 해제
  - 파일럿 샘플 부족 상태에서 베타 공개를 진행하려면 `--allow-pilot-hold-for-beta`를 명시해 조건부 GO 판정 사용
- signoff 로그 문서 자동 생성(권장): `python scripts/run_sheetbook_release_signoff_log.py --author sheetbook-ops`

Windows one-command(strict) 예시:

1. 베타 경로(`SHEETBOOK_ENABLED=False`, allowlist 사용):
   - `$env:SHEETBOOK_ENABLED='False'`
   - `$env:SHEETBOOK_BETA_USERNAMES='teacher_a'`
   - `$env:SHEETBOOK_BETA_EMAILS='teacher_a@school.kr'`
   - `$env:SHEETBOOK_PREFLIGHT_STRICT='True'`
   - `.\scripts\pre_deploy_check.ps1`
2. 전체 공개 경로(`SHEETBOOK_ENABLED=True`):
   - `$env:SHEETBOOK_ENABLED='True'`
   - `$env:SHEETBOOK_PREFLIGHT_STRICT='True'`
   - `.\scripts\pre_deploy_check.ps1`

## 3) 배포 후 확인

관리자 계정으로 아래 확인:

1. `/sheetbook/metrics/?days=7` 열림 여부
2. `홈에서 새 수첩 만들기` / `홈에서 기능 실행 시작` 수치 집계 여부
3. 베타 계정은 접근 가능, 비 allowlist 계정은 404 차단 여부

## 4) 롤백

즉시 차단:

1. `SHEETBOOK_ENABLED=False` 유지
2. `SHEETBOOK_BETA_USERNAMES`, `SHEETBOOK_BETA_EMAILS`, `SHEETBOOK_BETA_USER_IDS` 값을 빈 문자열로 변경
3. 재배포 후 `/sheetbook/` 접근 차단 확인

전체 공개 전환:

1. `SHEETBOOK_ENABLED=True`
2. allowlist 값은 유지하거나 비워도 됨(플래그 ON이면 전체 허용)
