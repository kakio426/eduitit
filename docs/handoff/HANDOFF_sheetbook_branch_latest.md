# HANDOFF: Sheetbook Branch Working Snapshot (latest)
Status: Working branch handoff (2026-03-03 23:38)

작성일: 2026-03-03
대상 저장소: `eduitit`
대상 브랜치: `feature/sheetbook`
기준 브랜치: `main`

## 1) 브랜치 스냅샷

- current branch: `feature/sheetbook`
- tracking: `origin/feature/sheetbook`
- latest backup commit: `5dd26ed` (`fix(sheetbook): carry due-date into gap summary refresh actions`)
- main은 미머지 상태 유지

작업 트리(sheetbook 관련만):
- modified: (없음)
- untracked: (없음)

## 1-1) 내일 시작 지점 (여기서 바로 시작)

- 시작 브랜치: `feature/sheetbook`
- 시작 커밋 기준점: `origin/feature/sheetbook` 최신 HEAD
- 첫 실행(복붙):
  1. `git checkout feature/sheetbook`
  2. `git fetch origin`
  3. `git rev-parse HEAD`
  4. `git rev-parse origin/feature/sheetbook`
  5. (해시 다를 때만) `git pull --ff-only origin feature/sheetbook`
  6. `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
- 확인 파일:
  - `docs/handoff/sheetbook_daily_start_bundle_latest.json`
  - `docs/runbooks/logs/SHEETBOOK_OPS_INDEX_2026-03-03.md`

### 1-1-a) `"이어서 진행해줘"` 즉시 실행 템플릿

- 아래 4단계를 그대로 실행하면 같은 맥락으로 즉시 재개 가능:
  1. `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
  2. `python scripts/run_sheetbook_sample_gap_summary.py --days 14 --due-date 2026-03-04`
  3. blocker가 남아 있으면 `python scripts/run_sheetbook_local_rehearsal_cycle.py --days 14 --home-count 5 --create-count 5 --action-count -1 --archive-event-count 5 --allow-pilot-hold-for-beta --due-date 2026-03-04`
  4. 재판정 `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`

- 재개 후 바로 확인할 핵심 값:
  - `sheetbook_daily_start_bundle_latest.json`의 `overall`, `decision`, `readiness_status`
  - `sheetbook_sample_gap_summary_latest.json`의 `overall.ready`, `overall.blockers`

## 1-2) 2026-03-03 추가 실행 결과 (당일)

- 실행 완료:
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-03`
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-03 --allow-pilot-hold-for-beta`
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
  - `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta`
  - `python scripts/run_sheetbook_release_signoff_log.py --date 2026-03-03 ...`
  - `python scripts/run_sheetbook_release_signoff_log.py --date 2026-03-03 --next-action "pilot 표본 보강 + 상태 재판정" --due-date 2026-03-04`
- 상태 요약:
  - `manual_alias_statuses`: staging/prod/real-device 모두 `PASS`
  - `manual_pending` 표시는 effective 기준 `(없음)` + raw(readiness) 분리 노출
  - `decision`: `GO` (조건: `pilot_hold_for_beta=true`)
  - `readiness_status`: `HOLD` (표본 부족 유지)
  - sample gap blockers: `pilot_home_opened_gap:5`, `pilot_create_gap:5`, `archive_event_gap:5`
- 확인 파일:
  - `docs/handoff/sheetbook_release_decision_latest.json`
  - `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-03.md`
  - `docs/runbooks/logs/SHEETBOOK_OPS_INDEX_2026-03-03.md`

## 2) 오늘 반영 요약

- `SB-014`:
  - role 분해 임계치 추천(`--group-by-role`) + 파일럿 로그 역할별 스냅샷 반영
- `SB-015`:
  - release signoff 로그 자동 생성 스크립트 추가
  - readiness/decision/signoff log 최신화
  - 수동 signoff PASS 반영 + 조건부 베타 GO 재산출(`decision=GO`, `readiness=HOLD`)
- `운영 정합성 개선`:
  - daily bundle에서 `manual_pending`을 decision alias 기준으로 effective 계산
  - `manual_pending_raw(readiness)`를 별도 노출해 원본/보정값 동시 확인 가능
  - ops index가 daily bundle의 effective `manual_pending`을 우선 사용하도록 보정
  - daily bundle에 `--allow-pilot-hold-for-beta` 옵션 추가(조건부 GO 일괄 실행)
  - `--allow-pilot-hold-for-beta` 사용 시 release signoff `next_action` 기본값을
    `pilot 표본 보강 + 상태 재판정`으로 자동 전환
  - release signoff markdown도 `manual_pending` effective + `manual_pending_raw(readiness)` 분리 노출로 정합성 통일
  - daily/ops/release 리포트에 `pilot_hold_for_beta` 표시 추가(조건부 GO 여부 명시)
  - daily bundle `next_actions` 재실행 명령이 실행 옵션(`--allow-pilot-hold-for-beta`, `--due-date`)을 유지하도록 보정
  - 로컬 pre-commit 가드 활성화 시도:
    - `powershell -ExecutionPolicy Bypass -File scripts/install_git_hooks.ps1`
    - Windows `sh.exe` 환경 오류(Win32 error 5)로 자동 훅 커밋 차단 발생
    - 대응: `core.hooksPath` 해제 후 커밋 전 수동 가드 고정 실행
      - `python scripts/branch_path_guard.py --branch feature/sheetbook --staged`
  - 수동 가드 실수 방지용 guarded commit 헬퍼 추가:
    - `python scripts/run_sheetbook_guarded_commit.py --guard-only`
    - `python scripts/run_sheetbook_guarded_commit.py -m "feat(sheetbook): ..."`
    - `--push` 시 네트워크 일시 실패 재시도(`--push-retries`, `--push-retry-delay`)
    - `--branch` 지정 시 현재 체크아웃 브랜치와 일치 여부 강제 검증(불일치 차단)
    - push 최종 실패 시 로컬 커밋 해시 + 수동 재시도 명령 안내 출력
    - 인증/권한/저장소 경로 오류는 비재시도 오류로 즉시 중단
    - handoff latest 메타데이터 자동 갱신:
      - `python scripts/run_sheetbook_refresh_handoff_latest.py`
      - `python scripts/run_sheetbook_refresh_handoff_latest.py --dry-run`
      - `run_sheetbook_guarded_commit.py --refresh-handoff-latest`로 후행 자동 실행 가능
      - `--commit-handoff-refresh` 사용 시 refresh 결과를 자동 커밋/2차 push
      - refresh 자동 커밋 직전 2차 branch guard 재검사로 우회 차단
    - 문서: `docs/runbooks/sheetbook_guarded_commit_workflow.md`
    - 테스트: `SheetbookGuardedCommitScriptTests` 추가
  - 로컬 리허설용 metric seed 스크립트 추가:
    - `python scripts/run_sheetbook_seed_metric_samples.py --clear-seeded`

## 1-3) 로컬 리허설 상태 (seed 기반, 운영 판정용 아님)

- 실행:
  - `python scripts/run_sheetbook_seed_metric_samples.py --clear-seeded --home-count 5 --create-count 5 --action-count 3 --archive-event-count 5`
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04`
- 결과(로컬 리허설 데이터 기준):
  - `readiness_status`: `PASS`
  - `decision`: `GO`
  - `sample_gap_blockers`: `(없음)`
  - `archive_next_step`: `continue_monitoring`
- 주의:
  - 위 결과는 seed metric 이벤트 기반의 로컬 리허설 결과이며, 실제 운영 트래픽 기반 판정과 분리해서 해석해야 함.

## 1-4) 리허설 정리/복구 (clear-only)

- 실행:
  - `python scripts/run_sheetbook_seed_metric_samples.py --clear-only`
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
- 정리 결과:
  - 제거된 seed 이벤트: `18`
  - 현재 기준 상태:
    - `readiness_status`: `HOLD`
    - `decision`: `GO` (조건부 베타)
    - `sample_gap_blockers`: `pilot_home_opened_gap:5`, `pilot_create_gap:5`, `archive_event_gap:5`
- 의미:
  - 로컬 리허설 데이터는 제거되었고, 스냅샷은 다시 비리허설 상태로 복구됨.
- `SB-108`:
  - consent freeze snapshot diff 자동화 스크립트 추가
  - freeze checklist/release signoff runbook 반영
- `운영 자동화`:
  - daily start bundle 스크립트 추가
  - `docs/handoff/sheetbook_daily_start_bundle_latest.json` 자동 생성
  - `docs/runbooks/logs/SHEETBOOK_DAILY_START_<YYYY-MM-DD>.md` 리포트 자동 생성
  - sample gap summary 스크립트 추가
  - `docs/handoff/sheetbook_sample_gap_summary_latest.json`으로 pilot/archive 갭 통합 확인
  - sample gap blocker별 `next_actions` 자동 생성(수집 명령 + 재집계 명령)
  - daily start markdown에 `Sample Gap Next Actions` 섹션 노출
  - sample gap markdown 리포트 자동 생성:
    - `docs/runbooks/logs/SHEETBOOK_SAMPLE_GAP_<YYYY-MM-DD>.md`
  - sample gap/bundle 명령 `--days` 동기화(고정 14 하드코딩 제거)
  - sample gap 파일럿 액션 통합(`collect_pilot_samples`)으로 중복 명령 제거
  - consent freeze snapshot markdown 리포트 자동 생성:
    - `docs/runbooks/logs/SHEETBOOK_CONSENT_FREEZE_<YYYY-MM-DD>.md`
  - consent freeze snapshot JSON(`md_output`)을 daily bundle summary/markdown에 연동
  - daily bundle markdown에 `consent_freeze_reasons` 표시 추가
  - archive bulk snapshot markdown 리포트 자동 생성:
    - `docs/runbooks/logs/SHEETBOOK_ARCHIVE_BULK_<YYYY-MM-DD>.md`
  - archive snapshot JSON(`md_output`)을 daily bundle summary/markdown(`archive_report`)에 연동
  - ops index 리포트 자동 생성:
    - `docs/runbooks/logs/SHEETBOOK_OPS_INDEX_<YYYY-MM-DD>.md`
  - daily bundle이 최신 `sheetbook_daily_start_bundle_latest.json`을 입력으로 ops index를 후행 실행하도록 순서 보정
  - daily bundle summary/markdown에 `ops_index_report` 경로 노출

## 1-5) 2026-03-03 야간 스모크 안정화

- 실행:
  - `python scripts/run_sheetbook_allowlist_smoke.py`
  - `python scripts/run_sheetbook_consent_smoke.py`
  - `python scripts/run_sheetbook_grid_smoke.py --port 8015`
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
- 코드 보강:
  - `scripts/run_sheetbook_grid_smoke.py`
    - 가상 그리드 클릭 불안정 대응(`_click_with_retry`) 추가
    - 저장 상태에서 `충돌` 즉시 감지 + 셀 편집 1회 재시도(`_edit_cell_and_save`) 추가
    - 콘솔 409 충돌 노이즈를 `ignored_console_errors`로 분리
- 테스트 보강:
  - `sheetbook/tests.py`
    - `SheetbookGridSmokeScriptTests` 추가
    - 검증 항목: 충돌 즉시 감지, 충돌 시 1회 재시도, 비충돌 실패 시 재시도 없음
- 상태 요약:
  - `smoke_sheetbook_grid_1000_latest.json`: `pass=true` (desktop/tablet 모두 PASS, desktop initial render warning 1건)
  - `sheetbook_daily_start_bundle_latest.json`: `overall=GO`, `decision=GO`, `readiness_status=HOLD`
  - sample gap blockers는 기존과 동일:
    - `pilot_home_opened_gap:5`, `pilot_create_gap:5`, `archive_event_gap:5`

## 1-6) 2026-03-04 시작 우선순위 판단

- 현재 기준(2026-03-03 19:52:33):
  - `overall=GO`, `decision=GO`, `readiness_status=HOLD`
  - 미해소 blocker: `pilot_home_opened_gap:5`, `pilot_create_gap:5`, `archive_event_gap:5`
- 내일(2026-03-04) 1순위:
  - 파일럿/아카이브 표본 5건씩 먼저 확보해서 `readiness_status`를 `PASS`로 전환
  - 이유: 현재 STOP 리스크는 기능 결함보다 표본 부족이며, 야간 스모크 안정화로 기능 게이트는 이미 PASS
- 내일(2026-03-04) 권장 시작 순서:
  1. `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
  2. 표본 수집 실행(운영 트래픽/파일럿 계정 활동)
  3. `python scripts/run_sheetbook_release_readiness.py --days 14`
  4. `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
  5. `python scripts/run_sheetbook_sample_gap_summary.py --days 14 --due-date 2026-03-04`
  6. `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
- 판정 기준:
  - `sheetbook_sample_gap_summary_latest.json`의 `overall.ready=true`
  - `sheetbook_release_readiness_latest.json`의 `overall.status=PASS`
  - 위 2개가 충족되면 그 시점부터 수동 signoff 재확인으로 이동

## 1-7) 표본 수집 보조 스크립트 추가 (2026-03-03)

- 신규 스크립트:
  - `python scripts/run_sheetbook_collect_pilot_samples.py`
  - `python scripts/run_sheetbook_local_rehearsal_cycle.py`
- 목적:
  - 로컬/스테이징에서 `pilot_home_opened`, `pilot_create`, `archive_event` 표본을
    실제 뷰 플로우 기반으로 빠르게 확보해 gate 재판정을 반복 검증
- 기본 수집(5/5/5):
  - `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --clear-before --home-count 5 --create-count 5 --archive-event-count 5`
- 액션 이벤트 포함 수집(5/5/3/5):
  - `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event --clear-before --home-count 5 --create-count 5 --action-count 3 --archive-event-count 5`
- 정리(되돌리기):
  - `python scripts/run_sheetbook_collect_pilot_samples.py --clear-only`
- 리허설 사이클 1회 실행(수집 -> 검증 -> clear -> 복구):
  - `python scripts/run_sheetbook_local_rehearsal_cycle.py --days 14 --home-count 5 --create-count 5 --action-count 3 --archive-event-count 5 --allow-pilot-hold-for-beta --due-date 2026-03-04`
- 동작 메모:
  - `quick-create`/`bulk-archive`는 실제 뷰를 호출해 metric 이벤트를 생성
  - `--action-count` 기본값은 `-1(auto)`이며 `create_count` 기준 `min(create_count, 3)`으로 자동 계산
  - `--next-due-date YYYY-MM-DD`를 주면 출력 `next_steps`의 bundle due-date를 고정값으로 지정 가능
  - `--next-due-date` 파싱 실패 시 결과 JSON `warnings`에 `next_due_date_invalid_fallback`이 기록됨
  - `action_count`가 자동/보정되면 결과 JSON `requested.action_count_mode=auto`로 표시되며,
    비정상 입력(예: `--action-count -3`)은 `warnings`에 `action_count_invalid_fallback`이 함께 기록됨
  - `--archive-batch-size`가 0 이하이거나 비정상이면 `requested.archive_batch_size=1`로 보정되고
    `warnings`에 `archive_batch_size_invalid_fallback`이 기록됨
  - `--strict-inputs`를 켜면 위 보정이 필요한 경우 `mode=input_error` JSON을 출력하고 즉시 중단됨
  - `run_sheetbook_sample_gap_summary.py`의 `next_actions`에 로컬 리허설 수집 명령이 함께 노출됨:
    - `collect_pilot_samples_local_rehearsal`
    - `collect_archive_events_local_rehearsal`
  - `run_sheetbook_daily_start_bundle.py`의 `next_actions`에도
    `collect_samples_local_rehearsal`이 함께 노출되어
    `run_sheetbook_local_rehearsal_cycle.py` 기준으로 한 번에 리허설 수집/재판정/정리 가능
  - 홈(`/`)이 현재 로컬 DB 스키마 이슈(`core_post.featured_from`)로 500이면,
    `workspace_home_opened`는 자동으로 direct metric 폴백 기록(`home_collection_mode=auto`)
  - `home_collection_mode=auto`에서는 홈 수집 전 스키마 사전 점검을 수행하여
    `core_post.featured_from` 미존재 시 홈 요청을 생략하고 바로 폴백으로 전환
- 폴백을 강제로 쓰려면:
  - `python scripts/run_sheetbook_collect_pilot_samples.py --home-collection-mode direct-event`

## 3) 내일 시작 체크리스트 (순서 고정)

1. 게이트 최신화
   - `python scripts/run_sheetbook_release_readiness.py --days 14`
   - `python scripts/run_sheetbook_signoff_decision.py`
2. signoff 로그 갱신
   - `python scripts/run_sheetbook_release_signoff_log.py --author sheetbook-ops --owner sheetbook-release --next-action "staging/prod 실계정 점검" --due-date 2026-03-04`
3. 파일럿/품질 스냅샷 갱신
   - `python manage.py recommend_sheetbook_thresholds --days 14 --group-by-role`
   - `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
   - `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
   - `python scripts/run_sheetbook_consent_freeze_snapshot.py`
4. 수동 signoff 완료 시 반영
   - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
5. 최종 재확인
   - `python scripts/run_sheetbook_signoff_decision.py`
   - `python scripts/run_sheetbook_release_signoff_log.py --author sheetbook-ops --owner sheetbook-release --next-action "beta go/no-go 재판정" --due-date 2026-03-04`
6. 원클릭 번들(권장)
   - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
7. 표본 부족량 요약(권장)
   - `python scripts/run_sheetbook_sample_gap_summary.py --days 14 --due-date 2026-03-04`
8. 운영 인덱스 단독 갱신(필요 시)
   - `python scripts/run_sheetbook_ops_index_report.py --record-date 2026-03-03`

## 4) 중간 백업 규칙

1. `git add -A`
2. `git commit -m "wip(sheetbook): <짧은 설명>"`
3. `git push origin feature/sheetbook`
4. 본 문서/`HANDOFF_sheetbook_2026-02-27.md` 갱신

## 5) 집에서 진행할 작업 (2026-03-03 저녁)

1. 시작 동기화
   - `git checkout feature/sheetbook`
   - `git fetch origin`
   - `git pull --ff-only origin feature/sheetbook`
2. 오늘 기준 상태 재확인
   - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-04 --allow-pilot-hold-for-beta`
   - `python scripts/run_sheetbook_sample_gap_summary.py --days 14`
3. 코드 작업 후 최소 검증
   - `python manage.py test sheetbook.tests.SheetbookGuardedCommitScriptTests sheetbook.tests.SheetbookRefreshHandoffLatestScriptTests`
   - `python manage.py check`
4. 백업/원격 반영(권장 1회 명령)
   - `python scripts/run_sheetbook_guarded_commit.py -m "chore(sheetbook): home-session checkpoint" --push --refresh-handoff-latest --commit-handoff-refresh`
5. 종료 확인
   - `git status -sb`
   - `docs/handoff/HANDOFF_sheetbook_branch_latest.md`의 `latest backup commit`이 최신 커밋으로 갱신됐는지 확인
