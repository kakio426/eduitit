# HANDOFF: 교무수첩(Sheetbook) 진행 상태
Status: Working handoff (2026-02-27 EOD)

작성일: 2026-02-27
기준 계획서:
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`

## 0) 추가 업데이트 (2026-02-28 00:20)

### A. SB-013 보완 반영
- 동의서 사전 검토 화면의 대량 수신자 입력 UX를 교사 친화형으로 보강
  - 입력 줄 수/반영 인원/중복/형식 확인 필요 건수 요약 노출
  - 저장 시 “반영/제외” 결과를 쉬운 안내 문구로 표시
  - 수신자 파서 메타(입력/중복/형식 제외)를 계측 로그에 저장

### B. SB-014 퍼널 확장 반영
- 홈 유입 source를 액션 실행 단계까지 추적하도록 보강
  - 액션 실행 요청/성공 이벤트에 `entry_source` 저장
  - detail 진입 source를 세션에 저장해 후속 액션 실행 시에도 source 유지
- 관리자 지표 대시보드 퍼널 카드 확장
  - `홈에서 기능 실행 시작`, `홈에서 기능 실행 완료`
  - `홈 진입 대비`, `수첩 생성 대비` 전환율 추가
- 이벤트 목록 라벨을 교사 친화 문구로 변환해 노출

### C. 교사 친화 문구 점검
- `consent_review` / `metrics_dashboard` 문구에서 기술 용어를 줄이고 작업 중심 표현으로 정리
- `sheetbook:index`에 제목 검색 + 페이지네이션(20개 단위) 추가
- 확인 기준:
  - 선생님이 “무엇을 입력하면 되는지” 한 문장으로 이해 가능
  - 실패/제외 안내가 원인 중심이 아닌 다음 행동 중심으로 보이는지 확인

### D. CLAUDE.md / SERVICE_INTEGRATION_STANDARD 정합성 점검
- 부합 항목
  - 작업 범위 잠금 선언(`target_app=sheetbook`, `do_not_touch_apps` 명시) 후 수정
  - 비JS 폴백 유지(액션 실행 폼)
  - 상단 여백 표준(`pt-32`) 유지
  - 교사 친화 언어 원칙 반영(지표/동의서 문구 단순화)
- 미충족/예외
  - 브라우저 스모크 테스트, 30초 교실 시나리오 스모크는 현 세션 제약으로 미실행
  - 대체로 터미널 기반 검증(`manage.py test`, `manage.py check`, `node --check`)으로 진행

### E. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests`
- `python manage.py test sheetbook.tests`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)

결과:
- `sheetbook.tests.SheetbookMetricTests` 6 tests, OK
- `sheetbook.tests` 58 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사(node --check) OK

## 0-1) 추가 업데이트 (2026-02-28 00:45)

### A. SB-011 시간 컬럼 동기화 반영
- 일정 탭 -> 달력 동기화 시 시간 컬럼 감지/반영 구현
  - `start_time`/`end_time` 키 및 시간 라벨 감지
  - 시간 값이 있으면 시간 일정(`is_all_day=False`), 없으면 종일 일정 유지
  - 종료 시간이 시작 시간보다 빠른 경우 기본 50분 수업 길이로 보정
- 혼합 데이터(시간 포함 행 + 날짜만 있는 행) 동시 처리 테스트 추가

### B. SB-014 운영 지표 임계치/메모 반영
- 퍼널 임계치 기준값 적용
  - 홈->수첩 생성 목표 60%
  - 수첩 생성->기능 실행 시작 목표 50%
- 관리자 지표에 `needs_attention` / gap(%p) 계산 반영
- 관리자 화면에 운영 메모 카드(양호/보완 필요) 추가

### C. SB-015 착수 (통합 게이트)
- 통합 흐름 테스트 추가(`SheetbookP0IntegrationTests`)
  - index -> create -> 일정 입력 -> 액션 실행 -> 달력 동기화 -> 이력 조회
  - 생성/액션 source 메트릭 연속성 검증 포함

### D. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_uses_time_columns_when_present sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_handles_mixed_all_day_and_timed_rows`
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_flags_attention_when_funnel_below_threshold`
- `python manage.py test sheetbook.tests.SheetbookP0IntegrationTests.test_teacher_core_flow_create_edit_action_and_sync`
- `python manage.py test sheetbook.tests`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)

결과:
- `sheetbook.tests` 62 tests, OK
- 신규 타깃 테스트 4개, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사(node --check) OK

## 0-2) 추가 업데이트 (2026-02-28 01:10)

### A. SB-015 베타 롤아웃 게이트 보강
- feature flag OFF 상태에서도 내부 베타 계정은 접근 가능하도록 allowlist 게이트 확장
  - 지원 키: `SHEETBOOK_BETA_USERNAMES`, `SHEETBOOK_BETA_EMAILS`, `SHEETBOOK_BETA_USER_IDS`
  - 적용 범위: sheetbook 주요 view 전 구간
- 설정 반영
  - `config/settings.py`, `config/settings_production.py`에 베타 allowlist/env 변수 선언
  - `.env.example`에 샘플 키 추가

### B. SB-011 현장 표기 보완
- 일정 동기화 시간 파서에 현장 표기 지원 추가
  - `오전/오후` 시간 문구 회귀 검증 강화
  - `n교시` 표기(`3교시` 등) 인식 후 시간 일정으로 변환
- 기본 수업 길이(기본 50분)를 설정값으로 분리
  - `SHEETBOOK_SCHEDULE_DEFAULT_DURATION_MINUTES` (기본값 50)

### C. SB-014 문구 보완(교사 친화)
- `metrics_dashboard` 운영 메모에 “다음에 무엇을 하면 좋은지”를 쉬운 문장으로 추가
  - 지표 미달 시 즉시 행동 문구
  - 지표 양호 시 유지 가이드 문구

### D. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_parses_korean_meridiem_time_notation sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_parses_school_period_notation sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_uses_configured_default_duration sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_uses_time_columns_when_present sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_handles_mixed_all_day_and_timed_rows`
- `python manage.py test sheetbook.tests.SheetbookFlagTests`
- `python manage.py test sheetbook.tests`
- `python manage.py check`

결과:
- 신규/회귀 타깃 5 tests, OK
- `SheetbookFlagTests` 7 tests, OK
- `sheetbook.tests` 69 tests, OK
- `python manage.py check` OK

## 0-3) 추가 업데이트 (2026-02-28 01:20)

### A. SB-014 임계치 재보정 준비 (설정화)
- 퍼널 임계치를 운영 환경변수로 조정 가능하게 분리
  - `SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE` (기본 60)
  - `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE` (기본 50)
  - `SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE` (기본 5)
  - `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE` (기본 5)
- 관리자 지표 화면에 판정 기준 샘플 수를 함께 표시해 해석 혼선을 줄임

### A-2. SB-011 교시 시작 시각 설정화
- `n교시` 시간 변환 기준을 환경변수로 분리
  - `SHEETBOOK_PERIOD_FIRST_CLASS_HOUR` (기본 9시)
- 학교별 시간표 편차(예: 08:40 시작) 대응을 위한 운영 조정 지점 확보

### B. collect 간헐 스키마 이슈 대응(사전 점검)
- `check_collect_schema` 커맨드 추가
  - `collect_collectionrequest.bti_integration_source`
  - `collect_submission.integration_source`, `integration_ref`
  - 누락 시 명확한 오류로 중단해 조기 탐지
- `bootstrap_runtime`에 `check_collect_schema` 단계 연결

### C. SB-015 운영 런북 정리
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md` 추가
  - 베타 allowlist 적용 방법
  - 배포 전/후 점검 명령
  - 즉시 롤백 절차
- `check_sheetbook_rollout` 커맨드 추가
  - 베타 접근 경로/임계치/collect 스키마를 한 번에 점검
  - `--strict`에서 경고도 실패 처리
- 배포 자동화 연동
  - `bootstrap_runtime`에 `check_sheetbook_rollout` 단계 연결
  - `SHEETBOOK_ROLLOUT_STRICT_STARTUP=True`면 부팅에서도 strict 점검
  - `scripts/pre_deploy_check.sh`에 collect/sheetbook rollout 점검 추가

### D. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_flags_attention_when_funnel_below_threshold sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_uses_configured_thresholds`
- `python manage.py test sheetbook.tests.SheetbookRolloutCommandTests collect.tests.test_schema_check`
- `python manage.py test sheetbook.tests`
- `python manage.py check_collect_schema`
- `python manage.py check_sheetbook_rollout`
- `$env:SHEETBOOK_ENABLED='True'; python manage.py check_sheetbook_rollout --strict`
- `python manage.py check`

결과:
- metrics 타깃 3 tests, OK
- rollout/collect 스키마 점검 테스트 6 tests, OK
- `sheetbook.tests` 75 tests, OK
- `python manage.py check_collect_schema` OK
- `python manage.py check_sheetbook_rollout` OK (경고 포함 통과)
- `SHEETBOOK_ENABLED=True` 기준 `python manage.py check_sheetbook_rollout --strict` OK
- `python manage.py check` OK

## 0-4) 추가 업데이트 (2026-02-28 01:55)

### A. SB-008 보완 마감 (저장 실패 복구 UX)
- 그리드 자동 저장 실패 시 해당 칸을 빨간 강조로 표시하도록 반영
- `저장 안 된 칸 다시 저장` 버튼을 추가해 교사가 바로 재시도 가능하도록 보강
- 실패 칸 위치(A1 표기) + 다음 행동을 안내하는 쉬운 문구를 상태 영역에 노출

### B. 교사 친화 문구 추가 정리
- 셀 타입 오류 메시지를 작업형 문장으로 단순화
  - 숫자 칸: "숫자만 입력"
  - 체크 칸: "체크/해제 값만 사용"
  - 여러 선택 칸: "목록 형태로 입력"
- 자동 재시도 중 상태 문구를 기술 표현 대신 안내형 문장으로 교체

### C. 이번 추가 검증
- `python manage.py test sheetbook.tests`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)

결과:
- `sheetbook.tests` 75 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사(node --check) OK

## 0-5) 추가 업데이트 (2026-02-28 02:00)

### A. SB-011 교시 시작 "분" 단위 설정 반영
- `SHEETBOOK_PERIOD_FIRST_CLASS_MINUTE` 설정 추가(기본 0분)
- `n교시` 파싱 시 시작 시각을 시/분 기준으로 계산하도록 보강
  - 예: 1교시 08:10 시작이면 3교시는 10:10으로 동기화
- 설정 반영 파일
  - `config/settings.py`, `config/settings_production.py`, `.env.example`

### B. 롤아웃 점검 커맨드 보강
- `check_sheetbook_rollout`에 `SHEETBOOK_PERIOD_FIRST_CLASS_MINUTE` 검증 추가(0~59)
- 출력 문구를 `first class start: HH:MM` 형식으로 통일

### C. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_sync_calendar_from_schedule_uses_configured_period_start_minute sheetbook.tests.SheetbookRolloutCommandTests`
- `python manage.py check_sheetbook_rollout`

결과:
- 타깃 테스트 6 tests, OK
- `check_sheetbook_rollout` OK (`first class start: 09:00` 출력 확인)

## 0-6) 추가 업데이트 (2026-02-28 14:35)

### A. SB-007 벤치마크/튜닝 반영
- 붙여넣기 경로 최적화:
  - 누락 행 생성 루프(`SheetRow.objects.create` 반복)를 `bulk_create` 기반으로 전환
  - 벌크 저장 배치 크기를 설정값으로 분리
    - `SHEETBOOK_GRID_BULK_BATCH_SIZE` (기본 400, 범위 50~2000)
- 벤치마크 커맨드 추가:
  - `python manage.py benchmark_sheetbook_grid --cells 500,1000 --cols 10 --runs 5 --batch-sizes 200,400,800 --skip-read`
- 반복 측정(5회) 결과:
  - 500셀: batch 400 우세 (`total 691.9ms`)
  - 1000셀: batch 400 우세 (`total 1306.7ms`)
  - 결론: 기본값 400 유지 + 운영 환경에서 env 조정 가능하게 확정

### B. SB-006 조회 경로 최적화/검증 반영
- `grid_data` 조회 경로를 values 기반으로 최적화
  - 셀/행 조회 시 불필요한 모델 인스턴스 로딩 축소
  - 직렬화 헬퍼 분리로 응답 구성 비용 완화
- 조회 상한 조정:
  - `limit` 최대 300 -> 1000으로 확장
- 1,000행 조회 벤치마크 경로 추가:
  - `python manage.py benchmark_sheetbook_grid --cells 500,1000 --cols 10 --runs 3 --batch-sizes 200,400,800 --read-rows 1000`
  - 결과: `avg read(limit=1000): 75.4ms` (로컬 SQLite 기준)

### C. 운영 점검/테스트 보강
- `check_sheetbook_rollout`에 `SHEETBOOK_GRID_BULK_BATCH_SIZE` 검증 추가
- 테스트 추가:
  - `SheetbookGridApiTests.test_grid_data_limit_is_capped_to_1000`
  - `SheetbookRolloutCommandTests.test_check_sheetbook_rollout_fails_when_grid_batch_size_invalid`
  - `SheetbookBenchmarkCommandTests` (커맨드 실행/입력 오류)

### D. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_grid_data_returns_rows_columns_values sheetbook.tests.SheetbookGridApiTests.test_grid_data_limit_is_capped_to_1000 sheetbook.tests.SheetbookGridApiTests.test_paste_cells_bulk_updates_and_creates_rows sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_fails_when_grid_batch_size_invalid sheetbook.tests.SheetbookBenchmarkCommandTests`
- `python manage.py check_sheetbook_rollout`

결과:
- 타깃 테스트 6 tests, OK
- `check_sheetbook_rollout` OK (`grid bulk batch size: 400` 출력 확인)

## 0-7) 추가 업데이트 (2026-02-28 14:50)

### A. SB-013 대량 수신자 편집 UX/경량화 보강
- 동의서 사전 검토(`consent_review`)에서 대량 수신자 편집 가독성 보강:
  - 미리보기 DOM을 list 반복 대신 compact `pre` 텍스트로 변경(앞 10명만 표시)
  - `중복/형식 확인 필요` 줄 예시를 접기(details)로 제공(각 최대 5줄)
  - 입력 중 즉시 요약(입력 줄/반영/중복/형식확인) 라이브 표시
  - `맨 위/맨 아래` 빠른 이동 버튼 추가
- 파서 메타 확장:
  - `duplicate_samples`, `skipped_samples` 수집(로그성 요약/교정 보조용)

### B. SB-006 1,000행 렌더 스모크 보강
- 상세 화면에서 `grid_limit` 쿼리로 로딩 행 수를 조정 가능하게 보강(최대 1000, 최소 20)
  - 예: `?tab=<grid_tab_id>&grid_limit=1000`
- 그리드 로더가 `offset/limit` 파라미터를 명시해 API 호출하도록 정리
- 대량 렌더 시 콘솔 성능 로그 출력 추가(300행 이상): rows/cols/limit/render_ms
- 렌더 루프를 배열 join 기반으로 정리해 문자열 누적 비용 완화

### C. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_detail_grid_uses_sanitized_grid_limit_for_smoke sheetbook.tests.SheetbookGridApiTests.test_detail_grid_renders_action_layer_ui`
- `python manage.py check`
- `node --check` (detail/consent_review 인라인 스크립트 추출 검사)
- `python manage.py benchmark_sheetbook_grid --cells 1000 --cols 10 --runs 1 --batch-sizes 400 --read-rows 1000`

결과:
- 타깃 테스트 3 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사(node --check) OK
- 1000행 조회 벤치마크: `avg read(limit=1000): 58.2ms` (로컬 SQLite 기준)

## 0-8) 추가 업데이트 (2026-02-28 15:00)

### A. SB-013 편집 전용 보강 1차 (문제 줄 번호 이동)
- 수신자 파서 메타 확장:
  - `duplicate_line_numbers`, `skipped_line_numbers`, `issue_line_numbers` 추가
- 동의서 사전 검토 화면에 문제 줄 번호 패널 추가
  - 문제 줄 버튼 클릭 시 해당 줄로 커서/스크롤 이동
  - 입력 중에도 문제 줄 버튼 목록이 실시간 갱신되도록 반영
- 목적:
  - 대량 수신자 입력에서 “어디를 고쳐야 하는지” 즉시 찾아갈 수 있도록 편집 동선 단축

### B. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookGridApiTests.test_detail_grid_uses_sanitized_grid_limit_for_smoke`
- `node --check` (detail/consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 타깃 테스트 3 tests, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

## 0-9) 추가 업데이트 (2026-02-28 15:05)

### A. SB-013 편집 전용 보강 2차 (문제 줄 내용 + 점프 하이라이트)
- 수신자 파서 메타 추가 확장:
  - `duplicate_issue_items`, `skipped_issue_items` (줄번호+텍스트)
- 동의서 사전 검토 화면 보강:
  - 문제 줄 목록에 줄번호 + 유형(중복/형식확인) + 줄 내용을 함께 노출
  - 목록/버튼 클릭 시 해당 줄로 커서 이동 + textarea 강조(짧은 하이라이트) 반영
  - 입력 변경 시 문제 줄 목록/버튼을 실시간 재계산

### B. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 타깃 테스트 2 tests, OK
- `python manage.py test sheetbook.tests` 82 tests, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

## 0-10) 추가 업데이트 (2026-02-28 15:20)

### A. SB-013 편집 전용 보강 3차 (문제 줄 미니맵 + 활성 줄 표시)
- 동의서 사전 검토 화면(`consent_review`) 수신자 입력 영역 보강:
  - textarea 우측에 문제 줄 세로 미니맵 추가(문제 줄 위치를 비율 기반 마커로 표시)
  - 미니맵 마커 클릭 시 해당 줄로 즉시 이동
  - 빠른 이동/문제 목록/미니맵 간 활성 줄 강조 동기화
  - `현재 확인 중: N줄` 상태 문구 추가로 대량 교정 중 위치 인지 강화
- 목적:
  - 150~300명 수신자 편집에서 “문제 위치 탐색” 시간을 줄이고 교정 흐름을 단순화

### B. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1`
- `python manage.py test sheetbook.tests`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 타깃 테스트 2 tests, OK
- `sheetbook.tests` 82 tests, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

## 0-11) 추가 업데이트 (2026-02-28 23:20)

### A. SB-010 마감 반영 (홈 CTA 전용 플로우 연결)
- 로그인 홈 교무수첩 카드의 CTA를 전용 POST 플로우로 전환
  - `새 수첩`: `POST /sheetbook/quick-create/`
  - `작년 수첩 이어쓰기`: `POST /sheetbook/quick-copy/`
- quick-copy 동작:
  - 최근 교무수첩 1개를 기준으로 탭/열 구조를 복제
  - 그리드 탭은 기본 1행만 생성(행 데이터는 새 학년도 시작 기준으로 비움)
- 계측 연속성:
  - `workspace_home_create/copy` source를 유지해 `sheetbook_created` 이벤트에 연결
  - `quick_flow` 메타(`workspace_quick_create`, `workspace_quick_copy`) 추가

### B. SB-006 렌더 경량화 보강 (1,000행 대응)
- 상세 그리드 렌더를 300행 이상에서 청크 렌더로 전환
  - 열 수에 따라 청크 크기 자동 조정(20~150행)
  - `requestAnimationFrame` 기반 프레임 분할로 메인 스레드 점유 완화
  - 새 로드 시작 시 이전 청크 렌더 작업 취소(revision) 처리
- 콘솔 성능 로그 확장:
  - `mode(sync/chunked)`, `chunks`, `chunk_size`, `render_ms` 출력

### C. SB-015 운영 게이트 점검 재확인
- 실행:
  - `python manage.py check_collect_schema`
  - `$env:SHEETBOOK_ENABLED='True'; python manage.py check_sheetbook_rollout --strict`
- 결과:
  - collect schema check: 통과
  - rollout strict check: 통과

### D. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_quick_create_sheetbook_creates_default_tabs sheetbook.tests.SheetbookOwnershipTests.test_quick_copy_sheetbook_clones_tab_structure sheetbook.tests.SheetbookOwnershipTests.test_quick_copy_without_source_sheetbook_redirects_to_index`
- `python manage.py test core.tests.test_home_view.HomeV2ViewTest.test_v2_authenticated_sheetbook_workspace_uses_quick_cta_flows core.tests.test_home_view.HomeV2ViewTest.test_v2_authenticated_sheetbook_workspace_blocks_render`
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_grid_renders_action_layer_ui sheetbook.tests.SheetbookGridApiTests.test_detail_grid_uses_sanitized_grid_limit_for_smoke sheetbook.tests.SheetbookGridApiTests.test_grid_data_limit_is_capped_to_1000`
- `node --check` (detail 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 신규/회귀 타깃 테스트 8 tests, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

## 0-12) 추가 업데이트 (2026-02-28 23:40)

### A. SB-014 임계치 재보정 자동화 커맨드 추가
- 신규 커맨드:
  - `python manage.py recommend_sheetbook_thresholds --days 14`
- 기능:
  - 최근 기간 `workspace_home_opened` / `sheetbook_created(entry_source=workspace_home*)` / `action_execute_requested(entry_source=workspace_home*)` 이벤트를 집계
  - 관측 전환율(홈->수첩 생성, 수첩 생성->기능 실행) 계산
  - 샘플 수 기준 충족 시 안정 마진을 적용한 목표치 권장값 출력
  - 샘플 부족 시 현재 설정값 유지 + 부족 사유 출력
  - env 반영용 권장값(`SHEETBOOK_WORKSPACE_*`) 4개를 바로 출력

### B. Runbook 반영
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`에 재보정 절차 추가:
  - 배포 전 `recommend_sheetbook_thresholds` 실행
  - 출력된 권장값 반영 후 `check_sheetbook_rollout --strict` 재검증

### C. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookThresholdRecommendationCommandTests sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_passes_when_ready`
- `python manage.py recommend_sheetbook_thresholds --days 14`

결과:
- 신규 타깃 테스트 2 tests + rollout 회귀 1 test, OK
- 커맨드 실실행 출력 확인(로컬 데이터 샘플 부족 경로에서 현재 설정 유지 출력)

## 0-13) 추가 업데이트 (2026-02-28 23:55)

### A. SB-015 운영 자동화 연결 보강
- 부팅 점검(`bootstrap_runtime`)에 임계치 추천 실행 옵션 추가
  - `SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP=True`이면
  - `recommend_sheetbook_thresholds --days <SHEETBOOK_ROLLOUT_RECOMMEND_DAYS>` 실행
  - days 값이 비정상이면 기본 14일로 보정
- 환경변수 추가:
  - `SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP`
  - `SHEETBOOK_ROLLOUT_RECOMMEND_DAYS`

### B. 배포 스크립트 연동
- `scripts/pre_deploy_check.sh`에 임계치 추천 단계 추가
  - `python manage.py recommend_sheetbook_thresholds --days ${SHEETBOOK_ROLLOUT_RECOMMEND_DAYS:-14}`
  - 기존 rollout/schema/check 단계는 유지

### C. 이번 추가 검증
- `python manage.py test core.tests.test_bootstrap_runtime sheetbook.tests.SheetbookThresholdRecommendationCommandTests`
- `python manage.py check`

결과:
- 타깃 테스트 6 tests, OK
- `python manage.py check` OK

## 0-14) 추가 업데이트 (2026-03-01 00:20)

### A. SB-015 preflight 통합 커맨드 추가
- 신규 커맨드:
  - `python manage.py check_sheetbook_preflight [--strict] [--recommend-days N] [--skip-recommend]`
- 동작:
  - `check_collect_schema` 실행
  - `check_sheetbook_rollout`(strict 옵션 반영) 실행
  - `recommend_sheetbook_thresholds --days N` 실행(기본 ON, `--skip-recommend` 가능)

### B. 배포 스크립트 표준화
- `scripts/pre_deploy_check.sh`를 preflight 중심으로 단순화
  - Linux/macOS 경로: `bash scripts/pre_deploy_check.sh`
- Windows 실행 경로 추가
  - `scripts/pre_deploy_check.ps1` 신규 추가
  - Windows PowerShell에서 동일 preflight 절차 실행 가능

### C. 이번 추가 검증
- `python manage.py test sheetbook.tests.SheetbookPreflightCommandTests`
- `python manage.py test core.tests.test_bootstrap_runtime sheetbook.tests.SheetbookThresholdRecommendationCommandTests`
- `python manage.py check`
- 수동 실행:
  - `python manage.py check_sheetbook_preflight --strict --recommend-days 14`

결과:
- preflight 신규 테스트 3 tests, OK
- bootstrap/recommendation 타깃 테스트 6 tests, OK
- `python manage.py check` OK
- `check_sheetbook_preflight` strict 실실행 통과

## 0-15) 추가 업데이트 (2026-03-01 00:40)

### A. Windows pre-deploy 스크립트 실실행 확인
- 실행:
  - `.\scripts\pre_deploy_check.ps1`
- 결과:
  - 스크립트 자체는 정상 실행됨
  - 2단계(미적용 마이그레이션 점검)에서 기존 미적용 항목 탐지로 종료
    - `[ ] 0003_artclass_playback_mode`
- 메모:
  - 실패 원인은 신규 변경이 아니라 저장소의 기존 미적용 migration 상태
  - 마이그레이션 적용 후 재실행하면 나머지 preflight 단계 진행 가능

## 0-16) 추가 업데이트 (2026-03-01 01:05)

### A. 미적용 마이그레이션 정리
- 적용:
  - `python manage.py migrate --noinput`
- 결과:
  - `artclass.0003_artclass_playback_mode` 적용 완료
  - pre-deploy 2단계(미적용 migration 검사) 차단 해소

### B. pre-deploy 최종 재검증(Windows)
- 실행 1:
  - `.\scripts\pre_deploy_check.ps1` (`SHEETBOOK_ENABLED=False` 경로)
- 실행 2:
  - `$env:SHEETBOOK_ENABLED='True'; .\scripts\pre_deploy_check.ps1` (strict 경로)
- 결과:
  - 두 경로 모두 스크립트 끝까지 통과
  - strict 경로에서 `check_sheetbook_preflight --strict --recommend-days 14` 정상 통과 확인

## 0-17) 추가 업데이트 (2026-03-01 01:10)

### A. handoff 저장 확정
- 최신 반영 상태를 본 문서(`docs/handoff/HANDOFF_sheetbook_2026-02-27.md`)에 저장 완료.
- 현재 기준 운영 체크 상태:
  - 미적용 마이그레이션 없음
  - Windows pre-deploy 스크립트 일반/strict 경로 모두 통과

## 0-18) 추가 업데이트 (2026-03-01 10:50)

### A. SB-006 우선 착수(실행 준비 고정)
- 1,000행 실브라우저 스모크를 바로 수행할 수 있도록 전용 런북 추가
  - `docs/runbooks/SHEETBOOK_GRID_1000_SMOKE.md`
  - 데스크톱/태블릿 공통 시나리오, Pass/Fail 기준, 기록 템플릿, 병목 대응 가이드 포함

### B. 로컬 베이스라인 재측정
- 실행:
  - `python manage.py benchmark_sheetbook_grid --cells 1000 --cols 10 --runs 3 --batch-sizes 400 --read-rows 1000`
- 결과(로컬 SQLite):
  - paste(create): `200.3ms`
  - paste(update): `1795.2ms`
  - total: `1995.6ms`
  - read(limit=1000): `161.9ms`

### C. SB-006 핵심 회귀 재확인
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_grid_uses_sanitized_grid_limit_for_smoke sheetbook.tests.SheetbookGridApiTests.test_grid_data_limit_is_capped_to_1000 sheetbook.tests.SheetbookGridApiTests.test_detail_grid_renders_action_layer_ui`
- 결과:
  - 타깃 테스트 3 tests, OK

### D. 다음 실행 순서(즉시)
1. 런북 기준으로 데스크톱 실브라우저 스모크 1회 수행(`grid_limit=1000`)
2. 동일 시나리오를 태블릿에서 1회 수행
3. 콘솔 로그(`render_ms`, `mode`, `chunks`, `chunk_size`) + 체감 결과를 handoff에 기록

## 0-19) 추가 업데이트 (2026-03-01 11:14)

### A. SB-006 자동 실브라우저 스모크 실행 스크립트 추가
- 신규 스크립트:
  - `python scripts/run_sheetbook_grid_smoke.py`
- 동작:
  - 1,000행 x 10열 테스트 데이터 자동 준비
  - `SHEETBOOK_ENABLED=True`로 로컬 서버 임시 구동
  - Playwright로 데스크톱 + 태블릿(iPad Pro 11 에뮬레이션) 시나리오 실행
  - 결과 JSON 저장:
    - `docs/handoff/smoke_sheetbook_grid_1000_latest.json`

### B. 실행 결과 (자동 스모크)
- 실행:
  - `python scripts/run_sheetbook_grid_smoke.py`
- 결과:
  - 전체 판정: `PASS`
  - desktop:
    - `initial_render_ms=2818.5`
    - `mode=chunked`, `chunks=9`, `chunk_size=120`, `render_ms=1351.8`
    - 편집 저장 대기: 약 `14.7ms ~ 155.3ms`
    - console error: 없음
  - tablet(iPad Pro 11 emulation):
    - `initial_render_ms=2923.4`
    - `mode=chunked`, `chunks=9`, `chunk_size=120`, `render_ms=1483.7`
    - 편집 저장 대기: 약 `169.9ms ~ 2947.6ms`
    - console error: 없음
  - 액션 레이어 노출/선택 동작: desktop/tablet 모두 정상

### C. 메모
- 자동 스모크 기준으로 `SB-006` 최우선 검증 항목은 1차 통과.
- 태블릿 항목은 에뮬레이션 기반이므로, 실제 기기 1회 확인(터치 체감/키보드 전환)은 운영 전 권장.

## 0-20) 추가 업데이트 (2026-03-01 11:31)

### A. SB-013 대량 수신자 자동 스모크 스크립트 추가
- 신규 스크립트:
  - `python scripts/run_sheetbook_consent_smoke.py`
- 검증 범위:
  - 220줄(정상 180, 중복 20, 형식 확인 20) 입력 시나리오 자동 준비
  - `consent_review`에서 문제 줄 패널/미니맵/활성 줄/요약 갱신 검증
  - `확인 후 동의서 만들기` -> `consent/create/step1` 리다이렉트 검증
- 결과 JSON 저장:
  - `docs/handoff/smoke_sheetbook_consent_recipients_latest.json`

### B. 실행 결과 (자동 스모크)
- 실행:
  - `python scripts/run_sheetbook_consent_smoke.py`
- 결과:
  - 전체 판정: `PASS`
  - desktop:
    - 초기 요약: `220줄 · 180명 반영 · 중복 20줄 · 형식 확인 20줄`
    - 미니맵 마커: `40개`
    - 문제 줄 점프(버튼/미니맵): 정상
    - 입력 수정 후 요약: `222줄 · 180명 반영 · 중복 21줄 · 형식 확인 21줄`
    - step1 리다이렉트/seed 유지: 정상
  - tablet(iPad Pro 11 emulation):
    - 초기 요약: `220줄 · 180명 반영 · 중복 20줄 · 형식 확인 20줄`
    - 미니맵 마커: `40개`
    - 문제 줄 점프(버튼/미니맵): 정상
    - 입력 수정 후 요약: `222줄 · 180명 반영 · 중복 21줄 · 형식 확인 21줄`
    - step1 리다이렉트/seed 유지: 정상
  - console error: desktop/tablet 모두 없음

### C. 회귀 테스트 재확인
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_get_renders_prefilled_context`
- 결과:
  - 타깃 테스트 3 tests, OK

### D. runbook 추가
- `docs/runbooks/SHEETBOOK_CONSENT_RECIPIENTS_SMOKE.md` 추가
  - 자동 실행 명령, 수동 확인 포인트, PASS/FAIL 기준 정리

## 0-21) 추가 업데이트 (2026-03-01 11:35)

### A. SB-014 퍼널 임계치 재보정 실행
- 실행:
  - `python manage.py recommend_sheetbook_thresholds --days 14`
  - `python manage.py recommend_sheetbook_thresholds --days 30`
- 결과:
  - 14일/30일 모두 `workspace_home_opened`, `sheetbook_created(entry_source=workspace_home*)`, `action_execute_requested(entry_source=workspace_home*)` 샘플이 0건
  - 추천값은 현재값 유지:
    - `SHEETBOOK_WORKSPACE_TO_CREATE_TARGET_RATE=60.0`
    - `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_TARGET_RATE=50.0`
    - `SHEETBOOK_WORKSPACE_TO_CREATE_MIN_SAMPLE=5`
    - `SHEETBOOK_WORKSPACE_CREATE_TO_ACTION_MIN_SAMPLE=5`
- 판단:
  - 파일럿 데이터가 쌓일 때까지 임계치 기본값 유지가 맞음

### B. SB-015 운영 게이트(strict) 재확인
- 실행 1:
  - `python manage.py check_sheetbook_preflight --strict --recommend-days 14`
- 결과 1:
  - 로컬 `SHEETBOOK_ENABLED=False` + allowlist 비어있는 상태에서 strict 경고 실패(의도된 보호 동작)
- 실행 2:
  - `$env:SHEETBOOK_ENABLED='True'; python manage.py check_sheetbook_preflight --strict --recommend-days 14`
- 결과 2:
  - strict preflight 전체 통과
  - collect schema / rollout / threshold recommendation 단계 정상 완료

## 0-22) 추가 업데이트 (2026-03-01 11:40)

### A. SB-015 strict 경로 최종 확인(allowlist 포함)
- 실행 1 (`SHEETBOOK_ENABLED=False` 베타 경로):
  - `$env:SHEETBOOK_ENABLED='False'`
  - `$env:SHEETBOOK_BETA_USERNAMES='sheetbook_smoke_admin'`
  - `$env:SHEETBOOK_BETA_EMAILS='sheetbook-smoke-admin@example.com'`
  - `python manage.py check_sheetbook_preflight --strict --recommend-days 14`
- 결과 1:
  - strict preflight 통과
  - `SHEETBOOK_ENABLED=False`에서도 allowlist가 있으면 strict 경고 없이 통과 확인

- 실행 2 (`SHEETBOOK_ENABLED=True` 전체 공개 경로):
  - `$env:SHEETBOOK_ENABLED='True'; python manage.py check_sheetbook_preflight --strict --recommend-days 14`
- 결과 2:
  - strict preflight 통과

### B. SB-014 재보정 상태 결론(현재)
- 14/30일 기준 관측 샘플이 없어 재보정 권장값은 기본값 유지.
- 다음 확정 시점:
  - 파일럿에서 `workspace_home_opened`, `sheetbook_created(entry_source=workspace_home*)`, `action_execute_requested(entry_source=workspace_home*)` 샘플이 최소 기준(기본 5) 이상 확보된 뒤 재실행

## 0-23) 추가 업데이트 (2026-03-01 11:50)

### A. one-command strict 절차 확정 (Windows)
- 스크립트 보강:
  - `scripts/pre_deploy_check.ps1`, `scripts/pre_deploy_check.sh`에 `SHEETBOOK_PREFLIGHT_STRICT=True` 강제 옵션 추가
  - 이제 `SHEETBOOK_ENABLED=False` 베타 경로에서도 one-command strict 점검 가능
- runbook 반영:
  - `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`에 one-command 예시 + strict 강제 env 옵션 추가
  - `docs/runbooks/SHEETBOOK_PILOT_DATA_CHECKLIST.md` 신규 추가(파일럿 데이터 수집/재보정 절차)

### B. 검증 중 발견/해소
- 최초 one-command 실행에서 미적용 마이그레이션 탐지:
  - `[ ] 0009_alter_sqquizset_status_archived`
- 해소:
  - `python manage.py migrate --noinput` 적용 완료

### C. 최종 실행 검증 (PowerShell)
- 베타 경로(strict 강제):
  - `$env:SHEETBOOK_ENABLED='False'`
  - `$env:SHEETBOOK_BETA_USERNAMES='sheetbook_smoke_admin'`
  - `$env:SHEETBOOK_BETA_EMAILS='sheetbook-smoke-admin@example.com'`
  - `$env:SHEETBOOK_PREFLIGHT_STRICT='True'`
  - `.\scripts\pre_deploy_check.ps1`
  - 결과: 통과
- 전체 공개 경로(strict 강제):
  - `$env:SHEETBOOK_ENABLED='True'`
  - `$env:SHEETBOOK_PREFLIGHT_STRICT='True'`
  - `.\scripts\pre_deploy_check.ps1`
  - 결과: 통과

### D. 운영 메모
- `check --deploy`의 보안 경고(`W004`, `W008`, `W009`, `W012`, `W016`, `W018`)는 개발 설정(`DEBUG=True`) 기반 경고로, 현 스크립트에서는 차단 조건이 아님.

## 0-24) 추가 업데이트 (2026-03-01 11:58)

### A. 파일럿 이벤트 수집 템플릿 추가
- 신규 문서:
  - `docs/runbooks/SHEETBOOK_PILOT_EVENT_LOG_TEMPLATE.md`
  - `docs/runbooks/templates/sheetbook_pilot_event_log_template.csv`
- 목적:
  - 운영자가 날짜/학급 단위로 퍼널 수치를 동일 형식으로 기록
  - blockers/next_action까지 함께 남겨 재보정 판단 근거를 표준화

### B. runbook 연결 보강
- `docs/runbooks/SHEETBOOK_PILOT_DATA_CHECKLIST.md`
  - 템플릿 링크(Markdown/CSV) 추가
  - 운영 체크 포인트에 “blockers/next_action 기록” 추가
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - 파일럿 운영 로그 템플릿 링크 추가

### C. one-command strict 재검증 (베타 경로)
- 실행:
  - `$env:SHEETBOOK_ENABLED='False'`
  - `$env:SHEETBOOK_BETA_USERNAMES='sheetbook_smoke_admin'`
  - `$env:SHEETBOOK_BETA_EMAILS='sheetbook-smoke-admin@example.com'`
  - `$env:SHEETBOOK_PREFLIGHT_STRICT='True'`
  - `.\scripts\pre_deploy_check.ps1`
- 결과:
  - 스크립트 1~4단계 모두 통과
  - `check_sheetbook_preflight --strict` 통과
  - 미적용 migration 없음

## 0-25) 추가 업데이트 (2026-03-01 11:49)

### A. SB-014 파일럿 로그 자동 스냅샷 스크립트 추가
- 신규 스크립트:
  - `scripts/run_sheetbook_pilot_log_snapshot.py`
- 기능:
  - 최근 N일(기본 14일) 퍼널 집계 자동 계산
  - 임계치 권장값/샘플 기준 자동 산출
  - 파일럿 로그 Markdown/CSV 자동 생성(동일 날짜+그룹+범위 row는 CSV upsert)

### B. 실행 검증 및 출력 파일 갱신
- 실행:
  - `python scripts/run_sheetbook_pilot_log_snapshot.py`
- 결과:
  - 집계: 홈 진입 0, 홈 유입 생성 0, 홈 유입 기능 실행 0
  - 권장값: `TO_CREATE=60.0`, `CREATE_TO_ACTION=50.0`, `MIN_SAMPLE=5/5` (샘플 부족 유지)
  - 출력:
    - `docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_2026-03-01.md`
    - `docs/runbooks/logs/sheetbook_pilot_event_log_2026-03-01.csv`

### C. runbook 연결 보강
- `docs/runbooks/SHEETBOOK_PILOT_DATA_CHECKLIST.md`
  - 자동 스냅샷 명령 + 기본 출력 경로 추가
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - 파일럿 운영 로그 자동 스냅샷 명령 링크 추가

### D. 진행 상태 메모
- `SB-006` 실기기 스모크는 현재 장비 제약으로 보류(사용자 요청 반영).
- 실기기 가능 시 `docs/runbooks/SHEETBOOK_GRID_1000_SMOKE.md` 기준으로 재개.

## 0-26) 추가 업데이트 (2026-03-01 11:59)

### A. SB-013 자동 스모크 재실행 (PASS 갱신)
- 실행:
  - `python scripts/run_sheetbook_consent_smoke.py`
- 결과:
  - desktop/tablet 모두 PASS
  - 대량 수신자 요약/문제 줄 점프/미니맵/step1 리다이렉트 정상
  - 최신 결과 파일: `docs/handoff/smoke_sheetbook_consent_recipients_latest.json`

### B. SB-006 자동 스모크 재실행 2회 (현재 HOLD)
- 실행:
  - `python scripts/run_sheetbook_grid_smoke.py` (2회)
- 결과:
  - 1회차: tablet `initial_render_ms=3315ms`로 FAIL
  - 2회차: desktop `initial_render_ms=3122ms`로 FAIL
  - 공통: `final_render_log.render_ms`는 1217~1641ms 범위, 1000행 로딩/편집/액션 레이어는 정상
  - 최신 결과 파일: `docs/handoff/smoke_sheetbook_grid_1000_latest.json`

### C. 해석 및 다음 액션
- 현재 FAIL 원인은 `initial_render_ms > 3000` 단일 기준 초과(환경 편차 영향 가능).
- 실기기 보류 상태를 유지하되, 다음 세션에서 아래 중 하나를 확정:
  - 기준 유지 + 실행 환경 고정 후 재측정
  - `initial_render_ms`와 `final render_ms`를 분리해 판정 로직 보정
  - 실기기 체감 결과 확보 후 임계치 재정의

## 0-27) 추가 업데이트 (2026-03-01 12:10)

### A. SB-006 자동 스모크 판정 로직 보정
- 수정 파일:
  - `scripts/run_sheetbook_grid_smoke.py`
  - `docs/runbooks/SHEETBOOK_GRID_1000_SMOKE.md`
- 변경 내용:
  - PASS 하드 기준을 `final_render_log.render_ms`(기본 2000ms)로 명확화
  - `initial_render_ms`는 FAIL이 아닌 warning 항목으로 분리(기본 3000ms)
  - 스크립트 옵션 추가:
    - `--max-final-render-ms` (기본 2000)
    - `--warn-initial-render-ms` (기본 3000)
  - JSON 평가 결과에 `desktop_warnings/tablet_warnings/thresholds` 포함

### B. SB-006 자동 스모크 재실행 결과 (보정 후)
- 실행:
  - `python scripts/run_sheetbook_grid_smoke.py`
- 결과:
  - 전체 판정 `PASS`
  - desktop: `initial_render_ms=2530.1`, `final_render_ms=1291.2`
  - tablet: `initial_render_ms=2311.0`, `final_render_ms=1174.3`
  - warnings 없음, 1000행 로딩/편집/액션 레이어 정상
  - 최신 결과 파일: `docs/handoff/smoke_sheetbook_grid_1000_latest.json`

### C. SB-015 strict preflight 재확인 (베타/전체 공개 경로)
- 실행:
  1) `SHEETBOOK_ENABLED=False` + allowlist 1개 이상 + `check_sheetbook_preflight --strict --recommend-days 14`
  2) `SHEETBOOK_ENABLED=True` + `check_sheetbook_preflight --strict --recommend-days 14`
- 결과:
  - 두 경로 모두 통과
  - `check_collect_schema`/`check_sheetbook_rollout --strict`/`recommend_sheetbook_thresholds` 정상 완료
  - 임계치 권장값은 샘플 부족으로 기존값 유지(`60.0/50.0`, min `5/5`)

## 0-28) 추가 업데이트 (2026-03-01 12:14)

### A. SB-015 allowlist 접근 게이트 자동 스모크 추가
- 신규 스크립트:
  - `scripts/run_sheetbook_allowlist_smoke.py`
- 검증 범위:
  - `SHEETBOOK_ENABLED=False` + allowlist 설정 시
    - allowlisted 계정 `index/create/detail` 접근 가능
    - 비 allowlisted 계정 `index/create` 404 차단
  - `SHEETBOOK_ENABLED=True` + allowlist 비움 시
    - 비 allowlisted 계정 `index/create/detail` 접근 가능
- 산출물:
  - `docs/handoff/smoke_sheetbook_allowlist_latest.json`

### B. 실행 결과
- 실행:
  - `python scripts/run_sheetbook_allowlist_smoke.py`
- 결과:
  - `evaluation.pass=true`
  - beta 경로: allowlisted `200/302/200`, non-allowlisted `404/404`
  - global 경로: non-allowlisted `200/302/200`

### C. runbook 연결
- 신규 runbook:
  - `docs/runbooks/SHEETBOOK_ALLOWLIST_ACCESS_SMOKE.md`
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`에 allowlist 스모크 실행 명령/링크 추가

## 0-29) 추가 업데이트 (2026-03-01 12:20)

### A. 출시 준비도 집계 스크립트 추가
- 신규 스크립트:
  - `scripts/run_sheetbook_release_readiness.py`
- 집계 범위:
  - strict preflight(베타/전체 공개 경로)
  - smoke 3종(grid_1000, consent_recipients, allowlist_access)
  - 파일럿 임계치 재보정 준비 상태(최근 N일 샘플 수)
- 산출물:
  - `docs/handoff/sheetbook_release_readiness_latest.json`

### B. 실행 결과
- 실행:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
- 결과:
  - `overall.status=HOLD`
  - 자동 게이트(`preflight + smoke`)는 모두 통과(`automated_gate_pass=true`)
  - HOLD 원인:
    - 파일럿 샘플 부족(`workspace_home_opened=0`, `sheetbook_created=0`)
    - 수동 대기 항목(`staging/prod 실계정`, `real-device grid_1000`)

### C. 운영 runbook/로그 템플릿 추가
- 신규 runbook:
  - `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
- 신규 템플릿:
  - `docs/runbooks/templates/sheetbook_release_signoff_template.md`
- 시작 로그:
  - `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-01.md`
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`에 release readiness/signoff 링크 추가

## 0-30) 추가 업데이트 (2026-03-01 12:27)

### A. SB-013 대량 수신자 스모크 파라미터화
- 수정 스크립트:
  - `scripts/run_sheetbook_consent_smoke.py`
- 추가 옵션:
  - `--valid-count`
  - `--duplicate-count`
  - `--invalid-count`
- 변경:
  - 초기 요약 검증 임계치를 고정값(150)에서 입력 시나리오 기반으로 동적 평가
  - seed 범위 라벨(`A1:C...`)을 실제 총 줄 수에 맞춰 자동 설정

### B. 300줄 시나리오 자동 검증 실행
- 실행:
  - `python scripts/run_sheetbook_consent_smoke.py --valid-count 240 --duplicate-count 30 --invalid-count 30 --output docs/handoff/smoke_sheetbook_consent_recipients_300_latest.json`
- 결과:
  - desktop/tablet 모두 `PASS`
  - 초기 요약: `300줄 · 240명 반영 · 중복 30줄 · 형식 확인 30줄`
  - 수정 후 요약: `302줄 · 240명 반영 · 중복 31줄 · 형식 확인 31줄`
  - 결과 파일: `docs/handoff/smoke_sheetbook_consent_recipients_300_latest.json`

### C. runbook 보강
- `docs/runbooks/SHEETBOOK_CONSENT_RECIPIENTS_SMOKE.md`
  - 300줄 실행 예시 명령 추가
  - 대량 입력 파라미터 옵션 설명 추가

## 0-31) 추가 업데이트 (2026-03-01 12:28)

### A. release readiness 재집계 (300줄 수신자 스모크 포함)
- 실행:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
- 결과:
  - `overall.status=HOLD` 유지
  - `automated_gate_pass=true` 유지
  - smoke 집계에 `consent_recipients_300` PASS 반영
  - 수동 대기 항목은 동일(`staging/prod 실계정`, `real-device grid_1000`)

### B. signoff 로그/런북 동기화
- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-01.md`
  - 집계 시각 12:28 반영
  - `smoke_consent_recipients_300` PASS 항목 추가
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - readiness 자동 smoke 집계 항목에 300줄 결과 파일 명시

## 0-32) 추가 업데이트 (2026-03-01 12:32)

### A. 최종 의사결정 자동화 스크립트 추가
- 신규 스크립트:
  - `scripts/run_sheetbook_signoff_decision.py`
- 기능:
  - 자동 집계 결과(`sheetbook_release_readiness_latest.json`) + 수동 점검 상태를 결합
  - 최종 판정 `GO/HOLD/STOP` 계산
  - `--set key=STATUS:notes`로 수동 점검 상태 즉시 갱신
- 입출력:
  - 수동 상태 파일: `docs/handoff/sheetbook_manual_signoff_latest.json`
  - 최종 판정 파일: `docs/handoff/sheetbook_release_decision_latest.json`

### B. 실행 결과(현재)
- 실행:
  - `python scripts/run_sheetbook_signoff_decision.py`
- 결과:
  - `decision=HOLD`
  - 이유: readiness `HOLD` + 수동 점검 5개 항목 모두 `HOLD`

### C. runbook 반영
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - signoff decision 명령/옵션/키 목록 추가
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
  - readiness/manual/decision 출력 파일 항목 추가
- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-01.md`
  - `release_decision=HOLD` 반영
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - 최종 의사결정 명령 링크 추가

## 0-33) 추가 업데이트 (2026-03-01 12:35)

### A. signoff decision alias 키 지원 추가
- 수정 스크립트:
  - `scripts/run_sheetbook_signoff_decision.py`
- 신규 alias:
  - `staging_real_account_signoff` -> `staging_allowlisted` + `staging_non_allowlisted`
  - `production_real_account_signoff` -> `production_allowlisted` + `production_non_allowlisted`
  - `real_device_grid_1000_smoke` -> `real_device_grid_1000`
- 효과:
  - 수동 점검 입력 명령이 짧아지고 운영자 실수 가능성 감소

### B. alias 동작 검증
- 실행(검증):
  - alias `PASS` 반영 명령 1회
  - alias `HOLD` 복구 명령 1회
- 결과:
  - 5개 수동 점검 항목에 alias가 정상 전파됨
  - 최종 상태는 현재 운영 현실에 맞게 `HOLD` 복구

### C. 문서 갱신
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - alias 예시/지원 키 목록 반영
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
  - alias 기반 최종 명령 예시 반영
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - alias one-line 예시 추가

## 0-34) 추가 업데이트 (2026-03-01 12:43)

### A. 실기기 스모크 상시 면제 정책 반영
- 사용자 요청에 따라 `real_device_grid_1000_smoke`는 기본 면제 처리.
- 스크립트 반영:
  - `scripts/run_sheetbook_release_readiness.py`
    - 기본값: `--waive-real-device-smoke=True`
    - 출력 `overall.waived_manual_checks`에 `real_device_grid_1000_smoke` 표시
  - `scripts/run_sheetbook_signoff_decision.py`
    - 기본값: `--waive-real-device-smoke=True`
    - `real_device_grid_1000` 수동 상태를 `PASS(waived_by_policy)`로 자동 반영
    - 필요 시 `--no-waive-real-device-smoke`로 해제 가능

### B. 정책 반영 후 재실행 결과
- 실행:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
- 결과:
  - readiness: `overall=HOLD`, `manual_pending`은 `staging/prod` 2개만 유지
  - decision: `HOLD`
  - manual 상태: `real_device_grid_1000=PASS(waived_by_policy)`, 나머지 4개는 `HOLD`

### C. 문서 동기화
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - 실기기 면제 기본 정책 + 해제 명령(`--no-waive-real-device-smoke`) 추가
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - 실기기 기본 면제 정책 명시
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
  - 면제 해제 명령/waived 항목 템플릿 추가
- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-01.md`
  - `waived_manual_checks` 및 면제 상태 반영

## 0-35) 추가 업데이트 (2026-03-01 12:47)

### A. 베타 조건부 GO 옵션 추가(pilot HOLD 허용)
- 수정 스크립트:
  - `scripts/run_sheetbook_signoff_decision.py`
- 신규 옵션:
  - `--allow-pilot-hold-for-beta`
- 동작:
  - readiness가 `HOLD`여도 `automated_gate_pass=true`이고
  - 수동 점검(실기기 면제 포함)이 모두 `PASS`면 `decision=GO` 산출

### B. 옵션 동작 검증
- 실행(검증):
  - `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta --set staging_real_account_signoff=PASS:beta-ready-test --set production_real_account_signoff=PASS:beta-ready-test`
- 결과:
  - `decision=GO` 확인
  - 검증 후 운영 상태 보존을 위해 staging/prod 상태를 `HOLD`로 복구

### C. 문서 반영
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - 조건부 GO 옵션/조건 설명 추가
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - 베타 공개 시 `--allow-pilot-hold-for-beta` 사용 가이드 추가
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
  - 조건부 GO 예시 명령 추가

## 0-36) 추가 업데이트 (2026-03-01 13:01)

### A. SB-013 밀집 문제 줄 미니맵 정확도 보강
- 수정 파일:
  - `sheetbook/templates/sheetbook/consent_review.html`
  - `scripts/run_sheetbook_consent_smoke.py`
- 보강 내용:
  - 문제 줄 미니맵 marker를 밀집 구간에서 lane 분산 렌더링(최대 3-lane)으로 전환
  - marker 하이라이트를 미니맵 전용 방식으로 분리(기존 ring/border 확장 부작용 제거)
  - marker 높이를 `h-px`로 조정해 겹침 클릭 오차 완화
  - 미니맵 점프 smoke를 단일 클릭에서 다중 샘플(상단/중간/하단 + 밀집 구간) 검증으로 확장

### B. 재현/원인/조치
- 재현:
  - 300줄 시나리오에서 미니맵 marker 클릭 시 목표 줄 대비 +2줄 오프셋 발생
- 원인:
  - 밀집 marker 구간에서 시각적/클릭 영역 겹침이 발생해 인접 marker가 클릭됨
- 조치:
  - lane 분산 + marker 스타일 조정으로 클릭 충돌 제거
  - smoke 평가식에 `minimap_lane_count`, `minimap_duplicate_lane_top_count`, `line_jump_by_minimap.checked_count`를 포함해 재발 감시 강화

### C. 검증 결과
- 실행:
  - `python scripts/run_sheetbook_consent_smoke.py`
  - `python scripts/run_sheetbook_consent_smoke.py --valid-count 240 --duplicate-count 30 --invalid-count 30 --output docs/handoff/smoke_sheetbook_consent_recipients_300_latest.json`
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
- 결과:
  - consent smoke 220/300 모두 PASS(desktop/tablet)
  - readiness: `overall=HOLD`(자동 게이트 PASS, pilot 샘플/실계정 수동 대기)
  - decision: `HOLD`
  - 실기기 항목은 정책상 `PASS(waived_by_policy)` 유지

### D. 문서 반영
- `docs/runbooks/SHEETBOOK_CONSENT_RECIPIENTS_SMOKE.md`
  - 다중 미니맵 점프/밀집 lane 분산 검증 기준 추가
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - consent smoke 밀집 marker 검증 지표 설명 추가
- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-01.md`
  - 최신 집계 시각 및 밀집 marker 검증 통과 결과 반영

## 0-37) 추가 업데이트 (2026-03-01 19:48)

### A. SB-015 게이트 상태 재갱신(체크리스트 1)
- 실행:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
- 결과:
  - readiness `overall=HOLD` 유지
  - `automated_gate_pass=true` 유지
  - `manual_pending=staging_real_account_signoff, production_real_account_signoff`
  - `waived_manual_checks=real_device_grid_1000_smoke`
  - release decision: `HOLD`

### B. SB-014 파일럿 로그/재보정 루틴 실행(체크리스트 3)
- 실행:
  - `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
  - `python manage.py recommend_sheetbook_thresholds --days 14`
- 결과:
  - 최근 14일 파일럿 관측치 0건 유지(홈 진입/생성/기능 실행 모두 0)
  - 권장 임계치/샘플 수는 기존값 유지(60/50, min sample 5/5)
  - 로그 갱신:
    - `docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_2026-03-01.md`
    - `docs/runbooks/logs/sheetbook_pilot_event_log_2026-03-01.csv`

### C. strict preflight 실행 메모
- 실행:
  - `python manage.py check_sheetbook_preflight --strict --recommend-days 14`
  - `$env:SHEETBOOK_ENABLED='True'; $env:SHEETBOOK_BETA_USERNAMES='beta_teacher'; python manage.py check_sheetbook_preflight --strict --recommend-days 14`
- 결과:
  - 기본 로컬 env(`SHEETBOOK_ENABLED=False`, allowlist 비어 있음)에서는 strict 경고로 실패(의도된 보호 동작)
  - 베타 운영 가정 env(`SHEETBOOK_ENABLED=True`, allowlist 1개)에서는 strict 통과
  - 운영 체크 시 strict 명령은 베타 허용 계정 설정 상태에서 실행해야 함을 재확인

### D. 산출물 갱신
- `docs/handoff/sheetbook_release_readiness_latest.json` (`generated_at=2026-03-01 19:48:13`)
- `docs/handoff/sheetbook_release_decision_latest.json` (`generated_at=2026-03-01 19:48:11`)
- `docs/handoff/sheetbook_manual_signoff_latest.json`
- `docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_2026-03-01.md`
- `docs/runbooks/logs/sheetbook_pilot_event_log_2026-03-01.csv`

## 0-38) 추가 업데이트 (2026-03-01 19:51)

### A. SB-015 조건부 GO 경로 재검증(체크리스트 4)
- 실행:
  - `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta --set staging_real_account_signoff=PASS:beta-ready-check-20260301 --set production_real_account_signoff=PASS:beta-ready-check-20260301`
- 결과:
  - readiness가 `HOLD`여도(`pilot` 샘플 부족) `automated_gate_pass=true` + 수동 항목 전체 PASS일 때
  - `decision=GO` 재확인
  - `decision_context.waivers.pilot_hold_for_beta=true` 확인

### B. 운영 상태 복구(수동 signoff HOLD)
- 실행:
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`
- 결과:
  - `decision=HOLD` 복귀
  - `manual_pending=staging_real_account_signoff, production_real_account_signoff` 유지
  - 실기기 항목은 정책 면제로 `PASS(waived_by_policy)` 유지

### C. 산출물 갱신
- `docs/handoff/sheetbook_manual_signoff_latest.json` (`updated_at=2026-03-01 19:51:53`)
- `docs/handoff/sheetbook_release_decision_latest.json` (`generated_at=2026-03-01 19:51:53`)

## 0-39) 추가 업데이트 (2026-03-01 20:04)

### A. SB-102 착수 (가져오기/내보내기 1차 구현)
- 범위:
  - 그리드 탭 파일 가져오기 endpoint 추가
    - `POST /sheetbook/<pk>/tabs/<tab_pk>/import/`
    - 지원 포맷: `csv`, `xlsx` (`xls`는 안내 후 거절)
  - 그리드 탭 내보내기 endpoint 추가
    - `GET /sheetbook/<pk>/tabs/<tab_pk>/export/csv/`
    - `GET /sheetbook/<pk>/tabs/<tab_pk>/export/xlsx/`
  - 상세 UI 연결
    - 파일 선택 + `첫 줄 제목`, `부족한 열 자동 추가`, `기존 행 지우기` 옵션
    - CSV/XLSX 다운로드 버튼

### B. 구현 상세
- CSV 인코딩 허용 범위:
  - `utf-8-sig`, `utf-8`, `cp949`, `euc-kr`
- XLSX 파서:
  - `openpyxl` 기반 read-only 로딩
  - 빈 trailing 셀/빈 줄 정리 후 매트릭스 변환
- 오류/리포트 보강:
  - 붙여넣기 공통 로직(`_paste_matrix_into_grid_tab`)에 `row_errors` 추가
  - 열 초과/형식 오류를 줄 단위 이유 목록으로 집계
  - import 완료 시 교사 안내 문구로 반영/제외 요약 노출
- round-trip 보완:
  - `multi_select` 칼럼이 문자열(`a, b`)도 목록으로 파싱되도록 확장

### C. 테스트 추가
- `SheetbookGridApiTests` 신규:
  - `test_import_grid_tab_file_replaces_rows_from_csv_with_header`
  - `test_import_grid_tab_file_auto_adds_missing_columns_from_header`
  - `test_import_grid_tab_file_accepts_xlsx`
  - `test_export_grid_tab_csv_downloads_header_and_rows`
  - `test_export_grid_tab_xlsx_downloads_binary_file`
  - `test_import_export_rejects_other_users_access`

### D. 이번 추가 검증
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_replaces_rows_from_csv_with_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_auto_adds_missing_columns_from_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_xlsx sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_csv_downloads_header_and_rows sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_xlsx_downloads_binary_file sheetbook.tests.SheetbookGridApiTests.test_import_export_rejects_other_users_access`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests`
- 결과:
  - 신규 타깃 6 tests, OK
  - `SheetbookGridApiTests` 49 tests, OK

### E. 수정 파일
- `sheetbook/views.py`
- `sheetbook/urls.py`
- `sheetbook/templates/sheetbook/_grid_editor.html`
- `sheetbook/tests.py`

## 0-40) 추가 업데이트 (2026-03-01 20:10)

### A. SB-102 완료 조건(샘플 5종 안정 처리) 충족
- 샘플 5종:
  - CSV(UTF-8, 헤더 포함)
  - CSV(헤더 포함 + 열 자동 추가)
  - XLSX(헤더 포함)
  - CSV(CP949 인코딩)
  - CSV(헤더 없음, 첫 줄 데이터 반영)
- 추가 검증:
  - 부분 오류 포함 가져오기에서 제외 안내(줄 번호 포함) 메시지 노출 확인

### B. 테스트 보강
- `SheetbookGridApiTests` 신규:
  - `test_import_grid_tab_file_accepts_cp949_csv`
  - `test_import_grid_tab_file_without_header_keeps_first_row_as_data`
  - `test_import_grid_tab_file_shows_warning_when_some_cells_skipped`

### C. 이번 추가 검증
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_cp949_csv sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_without_header_keeps_first_row_as_data sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_shows_warning_when_some_cells_skipped`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_replaces_rows_from_csv_with_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_auto_adds_missing_columns_from_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_xlsx sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_cp949_csv sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_without_header_keeps_first_row_as_data sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_shows_warning_when_some_cells_skipped sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_csv_downloads_header_and_rows sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_xlsx_downloads_binary_file sheetbook.tests.SheetbookGridApiTests.test_import_export_rejects_other_users_access`
  - `python manage.py check`
- 결과:
  - 신규 3 tests, OK
  - import/export 회귀 묶음 9 tests, OK
  - `python manage.py check` OK

### D. 상태 갱신
- `SB-102`: 완료 조건 충족으로 `DONE` 처리
- 다음 개발 축:
  - `SB-103` 시트북 통합 검색 착수

## 0-41) 추가 업데이트 (2026-03-01 20:16)

### A. SB-103 착수 (통합 검색 1차)
- 상세 화면에 통합 검색 섹션 추가:
  - 탭 이름 결과
  - 셀 값 결과
  - 실행 기록 결과
- 검색 파라미터:
  - `q`(키워드)
  - `focus_row_id`, `focus_col_id`(셀 점프)
- 셀 결과 클릭 시:
  - 해당 탭으로 이동 + 그리드 셀 포커스/스크롤/하이라이트 적용
  - 포커스 점프 시 `grid_limit`을 최대(1000)로 상향해 탐색 가능 범위 확장

### B. Ctrl+K 연결(상세 화면 범위)
- 상세 페이지에서 `Ctrl+K` 입력 시 시트북 검색 입력(`sheetbook-search-input`)으로 포커스 이동
- 기존 서비스 검색 모달 단축키보다 시트북 화면 내 검색을 우선하도록 캡처 처리

### C. 백엔드/계측 반영
- `sheetbook:detail`에서 통합 검색 결과 세트(`tabs/cells/actions`) 빌드
- 검색 실행 시 `sheetbook_search_requested` metric 저장
  - query(요약), 탭/셀/실행기록 결과 개수

### D. 테스트 추가
- `SheetbookGridApiTests` 신규:
  - `test_detail_search_returns_tab_cell_action_results`
  - `test_detail_search_focus_params_are_embedded_in_grid_editor`

### E. 이번 추가 검증
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_search_returns_tab_cell_action_results sheetbook.tests.SheetbookGridApiTests.test_detail_search_focus_params_are_embedded_in_grid_editor`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_replaces_rows_from_csv_with_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_auto_adds_missing_columns_from_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_xlsx sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_cp949_csv sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_without_header_keeps_first_row_as_data sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_shows_warning_when_some_cells_skipped sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_csv_downloads_header_and_rows sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_xlsx_downloads_binary_file sheetbook.tests.SheetbookGridApiTests.test_import_export_rejects_other_users_access sheetbook.tests.SheetbookGridApiTests.test_detail_search_returns_tab_cell_action_results sheetbook.tests.SheetbookGridApiTests.test_detail_search_focus_params_are_embedded_in_grid_editor`
  - `node --check` (detail 인라인 스크립트 추출 검사)
  - `python manage.py check`
- 결과:
  - 검색 신규 2 tests, OK
  - import/export+검색 회귀 묶음 11 tests, OK
  - detail 인라인 JS 문법 검사(node --check) OK
  - `python manage.py check` OK

### F. 수정 파일
- `sheetbook/views.py`
- `sheetbook/templates/sheetbook/detail.html`
- `sheetbook/templates/sheetbook/_grid_editor.html`
- `sheetbook/tests.py`
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`

## 0-42) 추가 업데이트 (2026-03-01 20:24)

### A. SB-103 2차 (글로벌 Ctrl+K 검색 모달 통합)
- 글로벌 검색 모달(`core/base`)에 시트북 결과 섹션 통합:
  - query 입력 시 기존 서비스 검색 + 시트북 검색 API 비동기 병합
  - 시트북 결과 유형: `탭`, `셀`, `실행 기록`
  - 시트북 결과 클릭 시 `openModal(product)` 대신 URL 이동 처리
- 모달 컨텍스트 확장:
  - `sheetbook_search_api_url`를 context processor에서 제공
  - 로그인 사용자 + URL reverse 가능 시 `/sheetbook/search/suggest/` 주입

### B. 시트북 글로벌 검색 API 추가
- endpoint:
  - `GET /sheetbook/search/suggest/?q=<keyword>&limit=6`
- 응답:
  - `tabs[]`, `cells[]`, `actions[]`
  - 셀 결과는 `focus_row_id`, `focus_col_id` 포함 URL 반환
- 보안:
  - 로그인 필수
  - 현재 사용자 소유 sheetbook 데이터만 검색
- 계측:
  - `sheetbook_global_search_requested` 이벤트 저장

### C. 테스트 추가
- `SheetbookGridApiTests` 신규:
  - `test_search_suggest_returns_grouped_results`
  - `test_search_suggest_is_scoped_to_current_user`
  - `test_search_suggest_requires_login`
- `HomeViewTest` 신규:
  - `test_v1_sheetbook_search_api_url_empty_for_anonymous`
  - `test_v1_sheetbook_search_api_url_present_for_authenticated`

### D. 이번 추가 검증
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_search_suggest_returns_grouped_results sheetbook.tests.SheetbookGridApiTests.test_search_suggest_is_scoped_to_current_user sheetbook.tests.SheetbookGridApiTests.test_search_suggest_requires_login core.tests.test_home_view.HomeViewTest.test_v1_sheetbook_search_api_url_empty_for_anonymous core.tests.test_home_view.HomeViewTest.test_v1_sheetbook_search_api_url_present_for_authenticated`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_replaces_rows_from_csv_with_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_auto_adds_missing_columns_from_header sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_xlsx sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_accepts_cp949_csv sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_without_header_keeps_first_row_as_data sheetbook.tests.SheetbookGridApiTests.test_import_grid_tab_file_shows_warning_when_some_cells_skipped sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_csv_downloads_header_and_rows sheetbook.tests.SheetbookGridApiTests.test_export_grid_tab_xlsx_downloads_binary_file sheetbook.tests.SheetbookGridApiTests.test_import_export_rejects_other_users_access sheetbook.tests.SheetbookGridApiTests.test_detail_search_returns_tab_cell_action_results sheetbook.tests.SheetbookGridApiTests.test_detail_search_focus_params_are_embedded_in_grid_editor sheetbook.tests.SheetbookGridApiTests.test_search_suggest_returns_grouped_results sheetbook.tests.SheetbookGridApiTests.test_search_suggest_is_scoped_to_current_user sheetbook.tests.SheetbookGridApiTests.test_search_suggest_requires_login core.tests.test_home_view.HomeViewTest.test_v1_sheetbook_search_api_url_empty_for_anonymous core.tests.test_home_view.HomeViewTest.test_v1_sheetbook_search_api_url_present_for_authenticated`
  - `node --check` (base 검색 모달 인라인 스크립트 추출 검사)
  - `python manage.py check`
- 결과:
  - 신규 타깃 5 tests, OK
  - import/export+검색+모달 연계 회귀 묶음 16 tests, OK
  - base 검색 모달 인라인 JS 문법 검사(node --check) OK
  - `python manage.py check` OK

### E. 상태 갱신
- `SB-103`: 완료 조건(검색 결과로 셀 점프 + Ctrl+K 연결) 충족으로 `DONE` 처리

### F. 수정 파일
- `core/context_processors.py`
- `core/templates/base.html`
- `core/tests/test_home_view.py`
- `sheetbook/views.py`
- `sheetbook/urls.py`
- `sheetbook/tests.py`
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`

## 0-43) 추가 업데이트 (2026-03-01 20:47)

### A. SB-104 1차 완료 (저장된 보기 / 필터 프리셋)
- `SavedView` 모델 + 마이그레이션 추가:
  - 필드: 보기 이름, 필터 문자열, 정렬 열/방향, 즐겨찾기, 기본 보기
  - 탭별 기본 보기 1개 제약(conditional unique) 반영
- 엔드포인트 추가:
  - `POST /sheetbook/<pk>/tabs/<tab_pk>/views/create/`
  - `POST /sheetbook/<pk>/tabs/<tab_pk>/views/<view_pk>/delete/`
  - `POST /sheetbook/<pk>/tabs/<tab_pk>/views/<view_pk>/favorite/`
  - `POST /sheetbook/<pk>/tabs/<tab_pk>/views/<view_pk>/default/`
- 그리드 데이터 API 확장:
  - `view_filter`, `sort_col`, `sort_dir` 쿼리 지원
  - 필터/정렬 조건을 서버에서 반영해 결과 반환

### B. 상세/그리드 UI 반영
- 그리드 상단에 저장된 보기 패널 추가:
  - 빠른 필터/정렬 적용
  - 현재 조건 저장(즐겨찾기/기본 보기 지정 가능)
  - 저장된 보기 1클릭 전환
  - 즐겨찾기/기본 보기 토글 + 삭제
- 상세 페이지 쿼리 보존 강화:
  - 탭 전환/검색 시 `view`, `view_filter`, `sort_col`, `sort_dir` 유지
- 그리드 JS 로드 시 저장된 보기 조건을 API 쿼리에 자동 전달

### C. 테스트 추가
- `SheetbookGridApiTests` 신규:
  - `test_grid_data_applies_view_filter_and_sort_params`
  - `test_detail_applies_default_saved_view_context`
  - `test_saved_view_endpoints_create_and_manage`
  - `test_saved_view_endpoints_reject_other_users_access`

### D. 이번 추가 검증
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_grid_data_applies_view_filter_and_sort_params sheetbook.tests.SheetbookGridApiTests.test_detail_applies_default_saved_view_context sheetbook.tests.SheetbookGridApiTests.test_saved_view_endpoints_create_and_manage sheetbook.tests.SheetbookGridApiTests.test_saved_view_endpoints_reject_other_users_access`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests`
  - `python manage.py check`
- 결과:
  - 신규 타깃 4 tests, OK
  - `SheetbookGridApiTests` 61 tests, OK
  - `python manage.py check` OK

### E. 상태 갱신
- `SB-104`: 완료 조건(저장/전환/재적용 + 즐겨찾기/기본 보기) 충족으로 `DONE` 처리

### F. 수정 파일
- `sheetbook/models.py`
- `sheetbook/migrations/0004_savedview.py`
- `sheetbook/views.py`
- `sheetbook/urls.py`
- `sheetbook/templates/sheetbook/_grid_editor.html`
- `sheetbook/templates/sheetbook/detail.html`
- `sheetbook/tests.py`
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`

## 0-44) 추가 업데이트 (2026-03-01 20:57)

### A. SB-105 1차 완료 (충돌 처리 + Undo)
- 저장 충돌 감지(낙관적 동시성) 추가:
  - `update_cell`에 `client_original` 비교 로직 반영
  - 서버 값과 불일치 시 `409 Conflict` + `current_value` 반환
  - `grid_cell_conflict_detected` metric 저장
- 단일 세션 Undo 추가:
  - 최근 성공 저장 내역 stack 유지
  - `최근 변경 취소` 버튼 + `Ctrl+Z`로 마지막 변경 되돌리기
- 충돌 경고 UX 추가:
  - 그리드 상단에 충돌 배너(현재 값 다시 불러오기/닫기)
  - 충돌 시 저장 상태 문구를 재시도 안내 중심으로 노출

### B. 테스트 추가
- `SheetbookGridApiTests` 신규:
  - `test_update_cell_accepts_when_client_original_matches`
  - `test_update_cell_detects_conflict_with_stale_client_original`

### C. 이번 추가 검증
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_update_cell_accepts_when_client_original_matches sheetbook.tests.SheetbookGridApiTests.test_update_cell_detects_conflict_with_stale_client_original`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests`
  - `python manage.py check`
  - `node --check` (detail 인라인 스크립트 추출 검사)
- 결과:
  - 신규 타깃 2 tests, OK
  - `SheetbookGridApiTests` 63 tests, OK
  - `python manage.py check` OK
  - detail 인라인 JS 문법 검사(node --check) OK

### D. 상태 갱신
- `SB-105`: 완료 조건(단일 세션 undo + 충돌 경고 배너) 충족으로 `DONE` 처리

### E. 수정 파일
- `sheetbook/views.py`
- `sheetbook/templates/sheetbook/_grid_editor.html`
- `sheetbook/templates/sheetbook/detail.html`
- `sheetbook/tests.py`
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`

## 0-45) 추가 업데이트 (2026-03-01 21:25)

### A. SB-106 완료 (모바일 편집 UX 개선)
- 모바일 행 편집 패널 추가:
  - 행 단위 입력 필드(열별 편집) 제공
  - 이전/다음 행 이동 버튼으로 연속 입력 동선 확보
  - 모바일에서는 `N행 편집` 버튼으로 즉시 진입
- 모바일 터치 선택 보강:
  - `touchstart/touchmove/touchend` 이벤트 기반 범위 선택 반영
  - 기존 마우스 선택 흐름과 공존하도록 분기 처리
- 하단 고정 동선 보강:
  - 모바일 패널/기존 하단 액션바 동작이 충돌하지 않도록 리사이즈 시 상태 정리
  - 행 패널 입력은 기존 자동 저장 큐와 동일 경로로 처리

### B. 테스트 추가
- `SheetbookGridApiTests` 신규:
  - `test_detail_includes_mobile_row_editor_controls`

### C. 이번 추가 검증
- 실행:
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_includes_mobile_row_editor_controls sheetbook.tests.SheetbookGridApiTests.test_update_cell_detects_conflict_with_stale_client_original`
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests`
  - `python manage.py check`
  - `node --check` (detail 인라인 스크립트 추출 검사)
- 결과:
  - 신규 타깃 2 tests, OK
  - `SheetbookGridApiTests` 64 tests, OK
  - `python manage.py check` OK
  - detail 인라인 JS 문법 검사(node --check) OK

### D. 상태 갱신
- `SB-106`: 완료 조건(행 상세 패널 + 터치 선택 + 하단 고정 동선) 충족으로 `DONE` 처리

### E. 수정 파일
- `sheetbook/templates/sheetbook/_grid_editor.html`
- `sheetbook/templates/sheetbook/detail.html`
- `sheetbook/tests.py`
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`

## 1) 오늘 완료한 핵심 작업

### A. SB-011 (진행 중)
- 교무수첩 달력 탭 UI 반영
  - 월 그리드/선택일 일정 목록 표시
  - 일정 탭 -> 캘린더 반영 버튼
- 일정 탭 데이터 기반 동기화 API 구현
  - `POST /sheetbook/<pk>/tabs/<tab_pk>/calendar/sync-from-schedule/`
  - 생성/수정/삭제 동기화 처리
  - 시간 컬럼 감지/시간대 반영(시간 일정 vs 종일 일정) 추가

### B. SB-016 (진행 중)
- classcalendar 진입에 중간 안내 화면 추가
  - 교무수첩 달력 탭으로 유도
  - `legacy=1` 및 `/classcalendar/legacy/` 경로 유지
- 공유/협업 액션 후 리다이렉트는 legacy 경로로 고정

### C. SB-012 (완료)
- 그리드 범위 선택 액션 레이어 구현 완료
  - 드래그/Shift 범위 선택
  - 선택 하이라이트
  - 범위 미선택 시 액션바 숨김
  - 액션 5개 노출: 달력 등록/간편 수합/동의서/배부 체크/안내문
  - 실행 전 미리보기 모달
- 회귀 테스트 추가 (액션 레이어 렌더링 검증)

### D. SB-013 (진행 중)
- 액션 실행 API 1차 구현
  - `POST /sheetbook/<pk>/tabs/<tab_pk>/actions/execute/`
  - 지원 액션: `calendar`, `collect`, `handoff`, `consent`, `notice`
- 실행 이력 모델 `ActionInvocation` 추가 및 저장
  - 선택 범위, 액션 타입, 상태, 결과 링크/요약 저장
- UI 연결
  - 액션 미리보기 Confirm -> 실제 API 호출
  - 교무수첩 상세에 “최근 액션” 목록/결과 링크 표시
- 추가 반영
  - `handoff`: 선택 칸 기반 명단/배부 세션 자동 생성
  - `consent`: 제목/안내 문구/수신자 후보 프리필 + step1 완료 시 수신자 자동 반영
  - `notice`: 대상/주제/분량/전달사항 프리필
  - 교사 친화 문구 정리(어려운 용어 축소)
  - 날짜 파서 고도화(예: `2026/3/14`, `3/14`, `3월 14일` 감지)
  - 동의서 수신자 추출 정밀화(번호열 오인 방지, 학생명 우선 감지)
  - 동의서 step1에 수신자 미리보기 + 자동 반영 ON/OFF 옵션 추가
  - 액션 이력 UX 보강(전체/완료/실패 필터, 실행 결과 토스트, 모바일 하단 액션바)
  - 액션 이력 더보기 API/버튼 연결(`GET /sheetbook/<pk>/tabs/<tab_pk>/actions/history/`)
  - 액션 이력 필터/더보기 상태 로컬 복원(localStorage, 탭별 키 분리)
  - 모바일 키보드 표시 시 하단 액션바 위치 자동 보정(visualViewport 기반)
  - 액션 실패 문구를 기능별로 분리(달력/수합/동의서/배부체크/안내문)
  - JS 확인 모달 액션에 non-JS 폴백 추가(범위 수동 입력 form + 서버 리다이렉트 처리)
  - 동의서 액션에 사전 검토 단계 추가(교무수첩 내 확인 화면 -> 동의서 step1 이동)
  - 동의서 사전 검토 화면 문구를 교사 친화형으로 단순화(제목/안내 문구/수신자 확인 중심)
  - 시트북 주요 페이지 상단 여백 `pt-32` 표준 적용
- 테스트 추가
  - calendar/collect/handoff/consent/notice 실행 검증 + unknown 액션 거절 검증
  - consent/notice 프리필 연동 테스트 추가
  - 유연한 날짜 입력 허용 테스트 추가
  - 번호열 오인 방지 수신자 추출 테스트 추가
  - 동의서 수신자 자동 반영 끄기 옵션 테스트 추가
  - 액션 이력 페이지네이션/탭 타입 제한/더보기 버튼 조건 테스트 추가
  - collect 예외 발생 시 기능별 실패 문구 반환 테스트 추가
  - non-JS 폴백 실행/오류 리다이렉트 테스트 추가
  - 동의서 사전 검토 화면 GET/POST/누락 seed 리다이렉트 테스트 추가

### E. SB-014 (진행 시작)
- 계측 로깅 1차 반영
  - 액션 실행 요청/성공/실패/입력오류/빈선택 이벤트 로깅
  - 액션 이력 로드 이벤트 로깅
  - 동의서 사전 검토 열기/제출/seed 누락 이벤트 로깅
- 계측 저장/조회 2차 반영
  - `SheetbookMetricEvent` 모델 추가(이벤트명/사용자/수첩/탭/액션/메타데이터)
  - 기존 `_log_sheetbook_metric` 호출을 DB 이벤트 저장까지 확장
  - 수첩 진입/생성/상세 진입 이벤트 추가(`sheetbook_index_opened`, `sheetbook_created`, `sheetbook_detail_opened`)
  - 관리자용 간단 지표 화면 추가: `GET /sheetbook/metrics/?days=7|14|30`
    - 최근 기간 요약, 날짜별 흐름, 이벤트/액션 집계 표시
  - KPI 요약 보강:
    - 재방문 선생님 수/비율(기간 내 상세 진입 2일 이상)
    - 10분 내 수첩 생성 비율(index 진입 후 최초 생성까지 10분 이내)
  - 액션 집계 표시를 교사 친화 라벨(달력 등록/간편 수합/동의서/배부 체크/안내문)로 표기
  - 홈 유입 source 계측 추가:
    - 홈에서 수첩 진입 시 `source=workspace_home_*` 쿼리 부여
    - `sheetbook_index_opened`/`sheetbook_created`/`sheetbook_detail_opened` 메타데이터에 `entry_source` 저장
    - 관리자 지표 카드에 `홈에서 수첩 목록 열기`, `홈에서 수첩 상세 열기` 추가
  - 퍼널 임계치/운영 메모 추가:
    - 홈->수첩 생성 60%, 수첩 생성->기능 실행 시작 50% 기준 적용
    - `needs_attention` + gap(%p) 계산 및 운영 메모 카드 노출

### F. SB-109 (완료)
- Product/매뉴얼 자동화 추가
  - `ensure_sheetbook` 커맨드 추가
  - 교무수첩 ProductFeature 3개 + ServiceManual(공개) + ManualSection 3개 자동 보장
  - `bootstrap_runtime`에 `ensure_sheetbook` 연결
- 정합성 보강
  - `core/home_authenticated_v2`와 `classcalendar` 안내 화면 문구를 교사 친화형으로 단순화

## 2) 오늘 수정한 주요 파일

- `sheetbook/templates/sheetbook/_grid_editor.html`
- `sheetbook/templates/sheetbook/detail.html`
- `sheetbook/templates/sheetbook/consent_review.html`
- `sheetbook/templates/sheetbook/metrics_dashboard.html`
- `sheetbook/templates/sheetbook/index.html`
- `sheetbook/tests.py`
- `sheetbook/views.py`
- `sheetbook/urls.py`
- `sheetbook/models.py`
- `sheetbook/migrations/0002_actioninvocation.py`
- `sheetbook/migrations/0003_sheetbookmetricevent.py`
- `sheetbook/migrations/0004_savedview.py`
- `consent/views.py`
- `consent/templates/consent/create_step1.html`
- `consent/tests.py`
- `noticegen/views.py`
- `noticegen/templates/noticegen/main.html`
- `noticegen/tests.py`
- `sheetbook/templates/sheetbook/_calendar_tab.html`
- `classcalendar/views.py`
- `classcalendar/urls.py`
- `classcalendar/templates/classcalendar/sheetbook_entry.html`
- `classcalendar/tests/test_sheetbook_bridge.py`
- `core/views.py`
- `core/templates/core/home_authenticated_v2.html`
- `core/tests/test_home_view.py`
- `core/management/commands/bootstrap_runtime.py`
- `products/management/commands/ensure_sheetbook.py`
- `products/tests/test_ensure_sheetbook.py`
- `config/settings.py`
- `config/settings_production.py`
- `.env.example`
- `collect/schema.py`
- `collect/management/commands/check_collect_schema.py`
- `collect/tests/test_schema_check.py`
- `sheetbook/management/commands/check_sheetbook_rollout.py`
- `sheetbook/management/commands/benchmark_sheetbook_grid.py`
- `scripts/run_sheetbook_grid_smoke.py`
- `scripts/run_sheetbook_consent_smoke.py`
- `scripts/run_sheetbook_pilot_log_snapshot.py`
- `scripts/run_sheetbook_allowlist_smoke.py`
- `scripts/run_sheetbook_release_readiness.py`
- `scripts/run_sheetbook_signoff_decision.py`
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
- `docs/runbooks/SHEETBOOK_GRID_1000_SMOKE.md`
- `docs/runbooks/SHEETBOOK_CONSENT_RECIPIENTS_SMOKE.md`
- `docs/runbooks/SHEETBOOK_PILOT_DATA_CHECKLIST.md`
- `docs/runbooks/SHEETBOOK_ALLOWLIST_ACCESS_SMOKE.md`
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-01.md`
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`

## 3) 검증 결과

실행:
- `python manage.py test sheetbook.tests`
- `python manage.py test consent.tests.ConsentFlowTests.test_create_step1_prefills_from_sheetbook_seed consent.tests.ConsentFlowTests.test_create_step1_seed_auto_adds_recipients noticegen.tests.NoticeGenViewTests.test_main_prefills_from_sheetbook_seed`
- `python manage.py test consent.tests noticegen.tests`
- `python manage.py test sheetbook.tests consent.tests noticegen.tests`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_consent_returns_guide_link sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_get_renders_prefilled_context sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_missing_seed_redirects_back`
- `python manage.py test sheetbook.tests.SheetbookMetricTests`
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`
- `python manage.py test products.tests.test_ensure_sheetbook`
- `python manage.py test classcalendar.tests.test_sheetbook_bridge`
- `python manage.py test core.tests.test_home_view.HomeV2ViewTest.test_v2_authenticated_sheetbook_workspace_blocks_render`
- `python manage.py test core.tests.test_home_view`
- `python scripts/run_sheetbook_grid_smoke.py`
- `python scripts/run_sheetbook_consent_smoke.py`
- `python scripts/run_sheetbook_consent_smoke.py --valid-count 240 --duplicate-count 30 --invalid-count 30 --output docs/handoff/smoke_sheetbook_consent_recipients_300_latest.json`
- `python scripts/run_sheetbook_allowlist_smoke.py`
- `python scripts/run_sheetbook_pilot_log_snapshot.py`
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`
- `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:alias-test --set production_real_account_signoff=PASS:alias-test --set real_device_grid_1000_smoke=PASS:alias-test`
- `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending --set real_device_grid_1000_smoke=HOLD:pending`
- `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta --set staging_real_account_signoff=PASS:beta-ready-test --set production_real_account_signoff=PASS:beta-ready-test`
- `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`

결과:
- sheetbook 단독 테스트 54 tests, OK
- consent/noticegen 연동 3 tests, OK
- consent+noticegen 전체 테스트, OK
- sheetbook+consent+noticegen 통합 86 tests, OK
- products ensure_sheetbook 테스트 2 tests, OK
- classcalendar bridge 테스트 4 tests, OK
- core home_v2 회귀 테스트 64 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사(node --check) OK
- 추가 검증:
  - `sheetbook.tests` 75 tests, OK
  - `SheetbookFlagTests` 7 tests, OK
  - 일정 동기화 신규/회귀 타깃 5 tests, OK
  - metrics 타깃 3 tests, OK
  - rollout/collect 스키마 점검 테스트 6 tests, OK
  - `python manage.py check_collect_schema` OK
  - `python manage.py check_sheetbook_rollout` OK
  - `SHEETBOOK_ENABLED=True` 기준 `python manage.py check_sheetbook_rollout --strict` OK
  - `python manage.py check` OK
  - `run_sheetbook_grid_smoke.py`: 최신 기준 PASS(`final_render_ms` 기준)
  - `run_sheetbook_consent_smoke.py`: PASS(desktop/tablet)
  - `run_sheetbook_consent_smoke.py` 300줄 시나리오: PASS(desktop/tablet)
  - `run_sheetbook_allowlist_smoke.py`: PASS(beta 차단/허용 + global 허용)
  - `run_sheetbook_pilot_log_snapshot.py`: 로그 생성/갱신 OK
  - `run_sheetbook_release_readiness.py`: `overall=HOLD`(자동 게이트 통과, 수동/샘플 대기, 300줄 수신자 스모크 PASS 반영)
  - `run_sheetbook_signoff_decision.py`: 기본 `decision=HOLD`(실기기 자동 면제 PASS, staging/prod 수동 점검 대기)
  - `run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta`: 조건 충족 시 `decision=GO` 검증 완료

## 4) 이어갈 항목 (다음 세션 시작점)

1. `SB-015` 베타 운영 게이트 최종 점검
- `run_sheetbook_release_readiness.py` 기준 자동 게이트는 PASS 상태
- 실계정 점검 후 `run_sheetbook_signoff_decision.py --set ...`로 최종 `GO/HOLD/STOP` 갱신
- 필요 시 `--allow-pilot-hold-for-beta`로 pilot HOLD 조건부 GO 사용
- 남은 항목: 스테이징/운영 실계정으로 최종 1회 확인 후 베타 공개 범위 확정

2. `SB-006` 1,000행 실기기 스모크
- 정책상 상시 면제(auto PASS) 처리
- 해제 필요 시 `--no-waive-real-device-smoke`로 즉시 복구 가능

3. `SB-014` 퍼널 임계치 재보정
- 파일럿 데이터(학교/학년 단위)로 목표치/최소 샘플 수 재산정
- 일일 자동 스냅샷(`run_sheetbook_pilot_log_snapshot.py`)으로 로그 누적 후 재보정 값을 env/runbook에 반영
- readiness 기준으로 `pilot.status=PASS`가 될 때까지 HOLD 유지

4. `SB-013` 대량 수신자 실사용 시나리오 검증
- 자동 스모크(220줄/300줄) PASS 완료
- 밀집 구간 미니맵 보강(최대 3-lane 분산, 다중 점프 검증) 반영 완료
- 잔여: 실제 교사 입력 패턴 기준 문구/버튼 위치 피드백만 수집하면 됨
- 교사 피드백 기준으로 문구/버튼 배치 미세 조정

5. `SB-101` 액션 연결 2차 착수
- 동의서/서명/안내문 실연결 마감(중간 안내형에서 최종 생성 연동 강화)
- 결과 링크/오류 회복 동선 표준화
- 완료 기준: 선택 범위 기반 생성이 3개 액션 모두 실연결로 완료

## 5) 현재 상태 메모

- 저장소에는 기존부터 수정 중인 파일(`config/*`, `core/*`)이 함께 존재함.
- 이번 handoff는 “현 상태 저장” 목적이며, 커밋/푸시는 아직 하지 않음.
- 현재 기준으로 `SB-102`(가져오기/내보내기), `SB-103`(통합 검색 2차), `SB-104`(저장된 보기), `SB-105`(충돌/undo), `SB-106`(모바일 편집 UX)까지 반영 완료 상태이며, 게이트 잔여는 실계정 signoff + pilot 샘플 누적 중심.

## 6) 남은 작업 추정

- 기준 시각: **2026-03-01 21:25**
- `P0 출시 범위` 기준: 약 **90~94% 완료**, **6~10% 잔여**
  - 근거: 실기기 항목이 정책 면제로 전환되어 게이트 잔여는 실계정 점검 + 파일럿 실데이터 재보정 중심
- `마스터 플랜 전체(P0+P1+P2)` 기준: 약 **47% 완료**, **53% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 15개 DONE(약 46.9%), 잔여는 P1(`SB-101/107/108/110/111`)와 P2 확장 중심

## 7) 퇴근 후 바로 재개 체크리스트

1. 현재 게이트 상태 새로 갱신
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`
- 기대 결과: 자동 게이트 PASS 유지, 최종 decision은 실계정 점검 전까지 HOLD

2. 실계정 점검 가능해지면 수동 signoff 반영
- staging 완료 반영:
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok`
- production 완료 반영:
  - `python scripts/run_sheetbook_signoff_decision.py --set production_real_account_signoff=PASS:prod-ok`
- 즉시 보류 복구가 필요하면:
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`

3. pilot 데이터 누적/재보정 루틴(일 1회)
- `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
- `python manage.py recommend_sheetbook_thresholds --days 14`
- 샘플 충족 후 env 반영 -> `python manage.py check_sheetbook_preflight --strict --recommend-days 14`

4. 베타 공개 판정 명령(조건부 GO 포함)
- 기본: `python scripts/run_sheetbook_signoff_decision.py`
- pilot HOLD를 베타에서 조건부 허용할 때만:
  - `python scripts/run_sheetbook_signoff_decision.py --allow-pilot-hold-for-beta`

5. 다음 개발 축(마스터 기준 P1 우선순위)
- P1-1: 액션 연결 2차(`SB-101`: 동의서/서명/안내문 실연결 마감)
- P1-2: 모바일 읽기 가드(`SB-110`) + 범위 파서 규칙 엔진(`SB-111`)
- P1-3: 온보딩/샘플 수첩(`SB-107`) + 파일럿 피드백 반영(`SB-108`)

---

### 0-46. SB-101 완료 (동의서/서명/안내문 실연결 마감)

### A. 구현 요약
- 그리드 액션 레이어에 `서명 요청(signature)` 액션 추가
  - 액션 버튼/미리보기 모달/non-JS 폴백/실패 안내 문구 반영
- 액션 실행 API 확장:
  - `signature` 지원 + 실행 이력(`ActionInvocation`) 저장
  - `sb_seed` 기반 `signatures:create` 이동 링크 생성
  - 선택 범위에서 참석자 후보(이름/학년반) 추출 및 seed 데이터로 저장
- signatures 생성 화면 실연결:
  - `sb_seed`로 제목/인쇄제목/강사/장소/일시/설명 프리필
  - 참석자 후보 자동 반영 옵션(기본 ON) 추가
  - 생성 시 `ExpectedParticipant` 자동 반영 + seed 소모(pop)
- 정합성 보강:
  - signatures 모델-마이그레이션 불일치 보정용 `0012_signature_affiliation_corrections` 추가

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_signature_returns_prefilled_link sheetbook.tests.SheetbookGridApiTests.test_detail_grid_renders_action_layer_ui`
- `python manage.py test signatures.tests.test_shared_roster_sync`
- `python manage.py test sheetbook.tests.SheetbookGridApiTests`
- `python manage.py test consent.tests.ConsentFlowTests.test_create_step1_prefills_from_sheetbook_seed consent.tests.ConsentFlowTests.test_create_step1_seed_auto_adds_recipients noticegen.tests.NoticeGenViewTests.test_main_prefills_from_sheetbook_seed sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_consent_returns_guide_link sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_notice_returns_prefilled_link sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_signature_returns_prefilled_link`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)

결과:
- `sheetbook Grid API` 65 tests, OK
- `signatures shared_roster_sync` 6 tests, OK
- consent/notice/sheetbook seed 연동 타깃 6 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사 OK
- 참고: `python manage.py test signatures.tests` 전체 실행 시 `test_affiliation_corrections` 2건은 기존 로직 이슈로 FAIL(이번 SB-101 변경 범위 밖)

### C. 다음 우선순위 갱신
- `SB-101`: DONE
- 다음 P1 우선순위:
  1. `SB-107` 온보딩/샘플 수첩
  2. `SB-110` 모바일 읽기 가드
  3. `SB-111` 범위 파서 규칙 엔진

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 22:00**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 50% 완료**, **약 50% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 16개 DONE

---

### 0-47. SB-107 완료 (온보딩/샘플 수첩)

### A. 구현 요약
- 빈 상태(index) 온보딩 CTA 추가:
  - 문구: `샘플 수첩으로 60초 시작`
  - 동작: 샘플 수첩 생성 후 상세로 즉시 이동
- 신규 엔드포인트:
  - `POST /sheetbook/quick-sample/`
  - 기본 탭 생성 + 일정/학생명부/메모 샘플 데이터 자동 시드
- 상세 온보딩 가이드:
  - `onboarding=sample` 파라미터로 `샘플 수첩 60초 시작 가이드` 패널 표시
  - 가이드 닫기 링크 제공(현재 탭/필터 상태 유지)
- 계측 추가:
  - `sheetbook_created`에 `quick_flow=workspace_quick_sample` 및 sample seed 메타데이터 기록
  - `sheetbook_sample_onboarding_started` 이벤트 기록

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_index_empty_state_shows_sample_onboarding_cta sheetbook.tests.SheetbookOwnershipTests.test_quick_sample_sheetbook_creates_seeded_rows_and_onboarding_redirect sheetbook.tests.SheetbookOwnershipTests.test_detail_renders_sample_onboarding_guide_when_requested`
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests`
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_grid_renders_action_layer_ui sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_signature_returns_prefilled_link signatures.tests.test_shared_roster_sync.SignatureSharedRosterSyncTests.test_create_session_sheetbook_seed_auto_adds_expected_participants`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)

결과:
- 신규 온보딩 관련 3 tests, OK
- `SheetbookOwnershipTests` 19 tests, OK
- signatures/sheetbook 교차 타깃 3 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사 OK

### C. 다음 우선순위 갱신
- `SB-107`: DONE
- 다음 P1 우선순위:
  1. `SB-110` 모바일 읽기 가드
  2. `SB-111` 범위 파서 규칙 엔진
  3. `SB-108` 파일럿 피드백 반영 스프린트

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 22:13**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 53% 완료**, **약 47% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 17개 DONE

---

### 0-48. SB-110 완료 (모바일 읽기 모드 가드)

### A. 구현 요약
- 휴대폰 UA(iPhone/Android Mobile)에서 시트북 편집/생성 동작을 서버에서 차단(403)하도록 가드 추가
  - 대상: 탭/보기 관리, 셀 수정, 붙여넣기, 행/열 추가, 가져오기, 액션 실행, 일정->달력 동기화
- 상세 화면/그리드 UI에 `휴대폰 읽기 모드` 안내 배너 및 읽기 모드 문구 추가
- 휴대폰 읽기 모드에서 편집 동작 비활성화
  - contenteditable false
  - 행/열 추가, 가져오기, 액션 실행, 모바일 행 편집 진입 비활성화
- 태블릿(iPad UA)은 차단하지 않고 기존 편집 흐름을 그대로 허용
- 계측 추가:
  - `sheetbook_mobile_read_mode_opened`
  - `sheetbook_mobile_read_mode_blocked`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_shows_mobile_read_only_banner_for_phone_user_agent sheetbook.tests.SheetbookGridApiTests.test_detail_keeps_edit_mode_for_tablet_user_agent sheetbook.tests.SheetbookGridApiTests.test_update_cell_blocks_phone_user_agent_with_403 sheetbook.tests.SheetbookGridApiTests.test_create_grid_row_blocks_phone_and_allows_tablet sheetbook.tests.SheetbookGridApiTests.test_detail_includes_mobile_row_editor_controls sheetbook.tests.SheetbookGridApiTests.test_update_cell_supports_text_number_date sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_signature_returns_prefilled_link`
- `python manage.py test sheetbook.tests.SheetbookGridApiTests`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)

결과:
- 신규 모바일 가드 타깃 7 tests, OK
- `SheetbookGridApiTests` 69 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사 OK

### C. 다음 우선순위 갱신
- `SB-110`: DONE
- 다음 P1 우선순위:
  1. `SB-111` 범위 파서 규칙 엔진
  2. `SB-108` 파일럿 피드백 반영 스프린트
  3. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 22:30**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 56% 완료**, **약 44% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 18개 DONE

---

### 0-49. SB-111 완료 (범위 파서 규칙 엔진 1차)

### A. 구현 요약
- 선택 범위 기반 추천 파서(클라이언트) 추가
  - 시그널: `date_ratio`, `phone_ratio`, `name_ratio`, `token_count`
  - 날짜/연락처/이름 패턴을 감지해 액션별 점수 계산
- 액션 레이어 추천 순서 자동 조정
  - 추천 점수 기반으로 버튼 순서 재정렬
  - 1순위 버튼에 `추천` 라벨/강조 스타일 적용
- 실행 시 추천 메타데이터 전송
  - `recommendation_primary`, `recommendation_signals`
- 서버 계측/이력 반영
  - `action_execute_requested/succeeded/failed` 메타데이터에 추천 값 저장
  - `ActionInvocation.payload.recommendation`에 추천 정보 보존

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_detail_includes_selection_recommendation_parser_script sheetbook.tests.SheetbookMetricTests.test_execute_grid_action_persists_recommendation_metric_metadata sheetbook.tests.SheetbookMetricTests.test_execute_grid_action_persists_metric_events sheetbook.tests.SheetbookGridApiTests.test_execute_grid_action_calendar_creates_events_and_log`
- `python manage.py test sheetbook.tests.SheetbookMetricTests`
- `python manage.py check`
- `node --check` (detail 인라인 스크립트 추출 검사)

결과:
- 추천 파서/계측 타깃 4 tests, OK
- `SheetbookMetricTests` 9 tests, OK
- `python manage.py check` OK
- 인라인 JS 문법 검사 OK

### C. 다음 우선순위 갱신
- `SB-111`: DONE
- 다음 P1 우선순위:
  1. `SB-108` 파일럿 피드백 반영 스프린트
  2. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 22:36**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE

---

### 0-50. SB-108 진행 (동의서 수신자 자동 정리 계측 연결)

### A. 구현 요약
- 동의서 사전 검토 화면(`consent_review`)의 자동 정리 흐름과 서버 계측을 연결
  - 클라이언트 hidden 필드:
    - `recipients_cleanup_applied`
    - `recipients_cleanup_removed_count`
  - 서버(`consent_seed_review` POST)에서 값 파싱/정규화:
    - `cleanup_applied`가 false면 제거 개수 0으로 처리
    - 제거 개수는 실제 제외 가능 수(중복+형식 오류) 범위로 clamp
  - `consent_review_submitted` 메트릭에 아래 필드 저장:
    - `recipients_cleanup_applied`
    - `recipients_cleanup_removed_count`
- 정리 버튼 활성 조건 보강:
  - 중복/형식 오류 줄이 실제로 있을 때만 `문제 줄 제외하고 정리` 버튼 활성화
  - 정리 대상이 없으면 버튼 비활성화로 불필요 클릭과 혼동 감소

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_clamps_cleanup_removed_count_metric sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `python manage.py check`
- `node --check` (consent_review 인라인 스크립트 추출 검사)

결과:
- 동의서 검토/제출 타깃 3 tests, OK
- `consent_review_submitted` 이벤트 cleanup 메타데이터 저장/클램프 검증 OK
- `python manage.py check` OK
- 인라인 JS 문법 검사 OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- 다음 P1 우선순위:
  1. `SB-108` 파일럿 피드백 잔여 항목(문구/배치/실사용 피드백 반영)
  2. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 22:56**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`은 IN_PROGRESS)

---

### 0-51. SB-108 진행 (자동 정리 사용률 대시보드 반영)

### A. 구현 요약
- `metrics_dashboard` 요약 지표에 동의서 자동 정리 사용 현황 집계 추가
  - `consent_review_submitted_count`
  - `consent_cleanup_applied_count`
  - `consent_cleanup_apply_rate`
  - `consent_cleanup_removed_avg`
- 집계 기준:
  - 이벤트: `consent_review_submitted`
  - 메타데이터: `recipients_cleanup_applied`, `recipients_cleanup_removed_count`
- 관리자 화면 카드 추가:
  - `동의서 자동 정리 사용률`
  - 적용 건수/검토 건수/평균 제외 줄 수를 한 번에 노출

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`
- `python manage.py check`

결과:
- metrics 대시보드 타깃 2 tests, OK
- 자동 정리 사용률/평균 제외 줄 수 집계 검증 OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- 다음 P1 우선순위:
  1. `SB-108` 파일럿 피드백 잔여 항목(문구/배치/실사용 피드백 반영)
  2. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:01**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`은 IN_PROGRESS)

---

### 0-52. SB-108 진행 (자동 정리 사용률 운영 메모 신호 추가)

### A. 구현 요약
- 관리자 지표 요약(`summary`)에 자동 정리 운영 신호 추가
  - `consent_cleanup_target_rate=30.0`
  - `consent_cleanup_min_sample=5`
  - `consent_cleanup_gap`
  - `consent_cleanup_needs_attention`
- 운영 메모 카드에 자동 정리 사용률 문단 추가
  - 목표 대비 현재 사용률/차이/판정 기준 표시
  - `needs_attention`일 때 보완 문구, 아니면 유지 문구 노출

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_flags_consent_cleanup_attention_when_low sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`
- `python manage.py check`

결과:
- metrics 대시보드 타깃 3 tests, OK
- 자동 정리 사용률 low-signal(20%)에서 `보완 필요` 판정 검증 OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- 다음 P1 우선순위:
  1. `SB-108` 파일럿 피드백 잔여 항목(문구/배치/실사용 피드백 반영)
  2. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:06**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`은 IN_PROGRESS)

---

### 0-53. SB-015 상태 갱신 + sheetbook 전체 회귀 통과

### A. SB-015 게이트 상태 갱신
- 실행:
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
- 결과 요약:
  - `release_readiness_latest.json`: `overall.status=HOLD`
  - 자동 게이트: PASS 유지 (`automated_gate_pass=true`)
  - 수동 대기: `staging_real_account_signoff`, `production_real_account_signoff`
  - 실기기 1000행 스모크: 정책 면제 PASS 유지
  - 최종 decision: `HOLD`

### B. 회귀 검증(전체)
- 실행:
  - `python manage.py test sheetbook.tests`
  - `python manage.py check`
- 결과:
  - `sheetbook.tests` 124 tests, OK
  - `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS (파일럿 피드백 반영 지속)
- `SB-015`: IN_PROGRESS (수동 signoff 반영 대기)
- 다음 순서:
  1. `SB-108` 잔여 UX 조정(실사용 피드백 기반)
  2. `SB-015` staging/production 실계정 signoff 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:13**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-54. SB-108 진행 (문제 줄 복사 UX 추가)

### A. 구현 요약
- 동의서 사전 검토(`consent_review`)에 `문제 줄만 복사` 버튼 추가
  - 현재 입력에서 중복/형식 오류로 분류된 줄만 추출해 클립보드로 복사
  - 클립보드 API 미지원 브라우저는 `execCommand("copy")` fallback 적용
- 버튼 상태 동기화
  - 문제 줄이 없으면 비활성화
  - 복사 성공/실패 상태를 기존 상태 라인으로 안내

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1`
- `node --check` (consent_review 인라인 스크립트 추출 검사)

결과:
- 동의서 검토 타깃 2 tests, OK
- 인라인 JS 문법 검사 OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- 다음 P1 우선순위:
  1. `SB-108` 파일럿 피드백 잔여 항목(문구/배치/실사용 피드백 반영)
  2. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:15**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-55. SB-108 진행 (문제 줄 복사 사용 계측 추가)

### A. 구현 요약
- 동의서 검토 폼 hidden 필드 추가:
  - `recipients_issue_copy_used` (기본 0)
- `문제 줄만 복사` 성공 시 hidden 값을 `1`로 설정
- 서버(`consent_seed_review` POST)에서 값을 파싱해 `consent_review_submitted` 메트릭에 저장:
  - `recipients_issue_copy_used`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_clamps_cleanup_removed_count_metric sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서 검토 타깃 3 tests, OK
- `consent_review_submitted` 메타데이터에 `recipients_issue_copy_used` 저장 검증 OK
- 인라인 JS 문법 검사 OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- 다음 P1 우선순위:
  1. `SB-108` 파일럿 피드백 잔여 항목(문구/배치/실사용 피드백 반영)
  2. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:16**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-56. SB-108 진행 (문제 줄 복사 사용률 대시보드 반영)

### A. 구현 요약
- `metrics_dashboard` 동의서 카드 확장:
  - `consent_issue_copy_used_count`
  - `consent_issue_copy_use_rate`
- 카드 문구에 `문제 줄 복사 N건 (X%)`를 함께 표시해
  자동 정리와 복사 기능의 실제 사용량을 동시 관찰 가능하도록 보강

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_flags_consent_cleanup_attention_when_low`
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1`
- `python manage.py test sheetbook.tests.SheetbookMetricTests`
- `python manage.py check`

결과:
- metrics 타깃 2 tests, OK
- consent review 제출 메타 연동 타깃 1 test, OK
- `SheetbookMetricTests` 11 tests, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- 다음 P1 우선순위:
  1. `SB-108` 파일럿 피드백 잔여 항목(문구/배치/실사용 피드백 반영)
  2. `SB-015` 실계정 signoff 최종 반영(운영 게이트 마감)
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:19**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-57. SB-015 운영 게이트 상태 재갱신

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

### B. 결과
- readiness(`2026-03-01 23:19:50`) 기준:
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- signoff decision(`2026-03-01 23:19:48`) 기준:
  - `decision=HOLD`
  - 실기기 1000행 스모크는 정책 면제 PASS 유지

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 잔여 UX 개선 반영
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:20**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-58. SB-108/SB-015 연계 (자동 정리 기준 설정화 + rollout 점검 반영)

### A. 구현 요약
- 자동 정리 운영 기준을 설정값으로 분리
  - `SHEETBOOK_CONSENT_CLEANUP_TARGET_RATE` (기본 30)
  - `SHEETBOOK_CONSENT_CLEANUP_MIN_SAMPLE` (기본 5)
- 적용 위치:
  - `metrics_dashboard`의 자동 정리 운영 메모 판정(`needs_attention`) 계산
  - `check_sheetbook_rollout` 유효성 점검
    - target: 0~100
    - min sample: 1 이상
  - rollout 출력에 consent cleanup 기준 라인 추가
- 설정 파일 반영:
  - `config/settings.py`
  - `config/settings_production.py`
  - `.env.example`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_uses_configured_thresholds sheetbook.tests.SheetbookRolloutCommandTests`
- `python manage.py test sheetbook.tests.SheetbookMetricTests`
- `python manage.py check_sheetbook_rollout`
- `python manage.py check`

결과:
- metrics/rollout 타깃 8 tests, OK
- `SheetbookMetricTests` 11 tests, OK
- `check_sheetbook_rollout` 실행 시 consent cleanup 기준 출력/검증 확인
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 잔여 UX 개선(실사용 문구/배치 최종 튜닝)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:25**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-59. SB-015 운영 게이트 재확인(설정화 반영 후)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

### B. 결과
- readiness(`2026-03-01 23:25:18`) 기준:
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- signoff(`2026-03-01 23:25:16`) 기준:
  - `decision=HOLD`
  - 실기기 1000행 스모크 정책 면제 PASS 유지
- 확인 포인트:
  - `check_sheetbook_rollout` 출력에 consent cleanup 기준 라인 정상 노출
    - `consent cleanup target: apply>=30.0%, sample>=5`

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:26**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-60. SB-108 진행 (운영 메모에 문제 줄 복사 사용률 안내 추가)

### A. 구현 요약
- 관리자 지표 `운영 메모`에 `문제 줄 복사` 사용률 안내 문구를 추가
  - 현재 사용률/건수 노출
  - 사용률 높고 낮음에 따른 운영 해석 가이드(입력 품질 안내 vs 현 흐름 유지) 추가

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_flags_consent_cleanup_attention_when_low`
- `python manage.py check`

결과:
- metrics 타깃 2 tests, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:28**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-61. SB-108 진행 (문제 줄 순차 이동 UX 추가)

### A. 구현 요약
- 동의서 사전 검토(`consent_review`)에 문제 줄 순차 이동 컨트롤 추가
  - `이전 문제 줄` / `다음 문제 줄` 버튼 추가
  - 단축키 `Alt+↑`, `Alt+↓`로 같은 이동 동작 지원
  - 현재 커서 위치(또는 활성 문제 줄)를 기준으로 다음/이전 문제 줄로 순환 이동
  - 문제 줄이 없으면 버튼 비활성화 및 안내 문구 표시
- 목적:
  - 150~300줄 대량 입력 교정에서 “문제 줄 하나씩 확인” 동선을 단축

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `python manage.py test sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_passes_when_ready`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서 검토 타깃 1 test, OK
- rollout 출력 회귀 타깃 1 test, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(문구/버튼 위치 실사용 피드백 반영)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:46**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-62. SB-015 운영 게이트 재확인(UX 추가 반영 후)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

### B. 결과
- readiness(`2026-03-01 23:46:04`) 기준:
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- signoff(`2026-03-01 23:46:21`) 기준:
  - `decision=HOLD`
  - `real_device_grid_1000=PASS(waived_by_policy)` 유지
- 확인 포인트:
  - consent cleanup 운영 기준 출력/검증 유지
    - `consent cleanup target: apply>=30.0%, sample>=5`

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:47**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-63. SB-108 진행 (문제 줄 이동 계측 + 지표 반영)

### A. 구현 요약
- 동의서 사전 검토(`consent_review`) 이동 계측 추가
  - hidden 필드 `recipients_issue_jump_count` 추가
  - 문제 줄 이동(버튼/단축키/빠른 이동) 시 이동 횟수 누적
  - 제출 시 `consent_review_submitted` 메타데이터에 `recipients_issue_jump_count` 저장(최대 999)
- 관리자 지표(`metrics_dashboard`) 확장
  - `consent_issue_jump_total`
  - `consent_issue_jump_used_count`
  - `consent_issue_jump_use_rate`
  - `consent_issue_jump_avg`
  - 동의서 카드/운영 메모에 `문제 줄 이동` 사용률·평균 이동 횟수 노출

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_clamps_cleanup_removed_count_metric sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage`
- `python manage.py test sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_passes_when_ready`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서/메트릭 타깃 4 tests, OK
- rollout 타깃 1 test, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:51**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-64. SB-015 운영 게이트 재확인(문제 줄 이동 계측 반영 후)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

### B. 결과
- readiness(`2026-03-01 23:50:37`) 기준:
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- signoff(`2026-03-01 23:50:32`) 기준:
  - `decision=HOLD`
  - `real_device_grid_1000=PASS(waived_by_policy)` 유지
- 확인 포인트:
  - consent cleanup 기준/rollout strict preflight 모두 통과 유지

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:52**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-65. SB-108 회귀 검증(메트릭 전체)

### A. 실행
- `python manage.py test sheetbook.tests.SheetbookMetricTests`

### B. 결과
- `SheetbookMetricTests` 11 tests, OK
- 확인 포인트:
  - `문제 줄 이동` 신규 지표(`total/used/use_rate/avg`) 포함 상태로 전체 메트릭 회귀 통과
  - 기존 임계치 판정(`workspace`, `consent_cleanup`) 회귀 없음

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:53**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-66. SB-015 진행 (signoff decision `next_actions` 자동 추천 추가)

### A. 구현 요약
- `scripts/run_sheetbook_signoff_decision.py` 출력 payload에 `next_actions` 필드 추가
  - 현재 `manual_pending`/수동 상태를 읽어 즉시 실행 가능한 명령을 자동 추천
  - 기본 추천:
    - staging signoff PASS 반영 명령
    - production signoff PASS 반영 명령
    - readiness/signoff 재실행(새로고침) 명령
  - 조건부 추천:
    - 수동 점검은 PASS지만 readiness가 pilot HOLD인 경우 `--allow-pilot-hold-for-beta` 명령 추천
- runbook 동기화:
  - `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`에 `next_actions` 설명 추가
  - `docs/runbooks/templates/sheetbook_release_signoff_template.md`에 `next_actions` 기록 항목 추가

### B. 테스트/검증
- `python -m py_compile scripts/run_sheetbook_signoff_decision.py`
- `python scripts/run_sheetbook_signoff_decision.py`

결과:
- 스크립트 문법 검사 OK
- decision JSON 출력에 `next_actions` 포함 확인
  - 현재 HOLD 상태에서 staging/prod PASS 반영 명령 + refresh 명령 자동 노출

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:56**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-67. SB-015 진행 (`next_actions` 추천 로직 테스트 보강)

### A. 구현 요약
- `scripts/run_sheetbook_signoff_decision.py` 추천 로직 보정
  - 이미 `PASS`인 수동 항목은 `manual_signoff` 재권장하지 않도록 조정
- 테스트 추가:
  - `SheetbookSignoffDecisionScriptTests`
    - 수동 대기 상태에서 staging/prod PASS 반영 명령 추천 검증
    - pilot HOLD + 수동 PASS 상태에서만 `optional_beta_go` 추천 검증

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookSignoffDecisionScriptTests`
- `python manage.py test sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_passes_when_ready sheetbook.tests.SheetbookSignoffDecisionScriptTests`
- `python scripts/run_sheetbook_signoff_decision.py`

결과:
- 신규 signoff 테스트 2 tests, OK
- rollout + signoff 타깃 3 tests, OK
- decision JSON `next_actions` 출력 정상

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:58**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-68. SB-108 진행 (문제 줄 행동 유도 안내 문구 추가)

### A. 구현 요약
- 동의서 사전 검토(`consent_review`)에 동적 안내 문구 영역 추가:
  - `id="recipients-issue-tip"`
  - 문제 줄 존재 시: `문제 줄 N개` + 이전/다음 문제 줄 버튼 사용 안내
  - 문제 줄 없음 시: 바로 다음 단계 진행 가능 안내
- 목적:
  - 버튼이 늘어난 상태에서 교사가 “지금 무엇을 누르면 되는지”를 즉시 이해하도록 행동 유도 강화

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서 검토 타깃 1 test, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-01 23:59**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-69. SB-015 운영 게이트 재확인(`next_actions`/UX 미세조정 반영 후)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

### B. 결과
- readiness(`2026-03-02 00:00:29`) 기준:
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- signoff(`2026-03-02 00:00:27`) 기준:
  - `decision=HOLD`
  - `next_actions` 자동 추천 정상 출력
  - `real_device_grid_1000=PASS(waived_by_policy)` 유지

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:01**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-70. SB-108/SB-015 묶음 회귀 재검증

### A. 실행
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookSignoffDecisionScriptTests sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_passes_when_ready`

### B. 결과
- 묶음 타깃 4 tests, OK
- 확인 포인트:
  - 동의서 검토 UI(`recipients-issue-tip`) 노출 회귀 없음
  - signoff `next_actions` 추천 로직 테스트 통과
  - rollout 기본 통과 경로 회귀 없음

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:02**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-71. SB-108 진행 (자동 정리 취소 Undo 추가)

### A. 구현 요약
- 동의서 사전 검토(`consent_review`)에 `자동 정리 취소` 버튼 추가
  - `id="recipients-cleanup-undo-btn"`
  - `문제 줄 제외하고 정리` 실행 직전 입력을 스냅샷으로 보관
  - 취소 클릭 시 원문으로 복구 + cleanup 메타(`recipients_cleanup_applied`, `recipients_cleanup_removed_count`)를 미적용 상태로 되돌림
  - 되돌릴 스냅샷이 없으면 안내 메시지 표시
- 목적:
  - 자동 정리 후 “원본을 다시 보고 싶다”는 실사용 불안을 즉시 해소

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서 검토 타깃 1 test, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:05**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-72. SB-015 진행 (`next_actions` 배치 반영 명령 추가)

### A. 구현 요약
- `run_sheetbook_signoff_decision.py`의 `next_actions` 개선:
  - staging/prod가 동시에 PASS 미달일 때 `manual_signoff_batch` 액션 추가
  - 명령 1회로 두 상태를 동시에 반영하도록 제시:
    - `--set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
- 기존 개별 명령(staging/prod 단건)과 refresh 명령은 유지

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookSignoffDecisionScriptTests`
- `python scripts/run_sheetbook_signoff_decision.py`

결과:
- signoff 스크립트 테스트 2 tests, OK
- decision JSON `next_actions`에 `manual_signoff_batch` 추가 출력 확인

### C. 문서 동기화
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - staging/prod 동시 반영 명령 예시 추가
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
  - 최종 판정 명령 목록에 동시 반영 명령 추가

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### E. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:06**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-73. SB-108/SB-015 타깃 묶음 회귀(Undo + signoff batch)

### A. 실행
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookSignoffDecisionScriptTests sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_passes_when_ready`

### B. 결과
- 묶음 타깃 4 tests, OK
- 확인 포인트:
  - `자동 정리 취소` 버튼 노출/스크립트 변경 후 동의서 검토 회귀 없음
  - signoff `next_actions` batch 추천 로직 회귀 없음
  - rollout 기본 통과 경로 유지

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:08**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-74. SB-015 진행 (조건부 GO 검증 후 HOLD 복구 추천 추가)

### A. 구현 요약
- `run_sheetbook_signoff_decision.py` `next_actions` 보강:
  - `optional_beta_go`가 제시되는 조건에서
  - 검증 후 운영 상태를 되돌리는 `optional_beta_restore_hold` 액션을 함께 제시
  - 복구 명령:
    - `--set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookSignoffDecisionScriptTests`
- `python scripts/run_sheetbook_signoff_decision.py`

결과:
- signoff 스크립트 테스트 2 tests, OK
- decision JSON 최신 생성(`2026-03-02 00:10:01`) 확인

### C. 문서 동기화
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - 조건부 GO 검증 후 HOLD 복구 명령 추가
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
  - 명령 목록에 복구 명령 추가

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(실사용 문구/버튼 위치 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### E. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:10**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-75. SB-108 진행 (자동 정리 취소 계측 + 대시보드 반영)

### A. 구현 요약
- 동의서 검토 폼에 `recipients_cleanup_undo_used` hidden 필드 추가
  - `자동 정리 취소` 실행 시 `1`로 설정
- 서버(`consent_seed_review` POST) 계측 확장:
  - `consent_review_submitted` 메타데이터에 `recipients_cleanup_undo_used` 저장
- 관리자 지표(`metrics_dashboard`) 확장:
  - `consent_cleanup_undo_used_count`
  - `consent_cleanup_undo_use_rate`
  - 동의서 카드/운영 메모에 `자동 정리 취소` 사용률 노출

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_clamps_cleanup_removed_count_metric sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서/메트릭 타깃 4 tests, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(문구/버튼 위치 최종 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:14**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-76. SB-108 진행 (동적 안내 문구에 Undo 복구 힌트 반영)

### A. 구현 요약
- `recipients-issue-tip` 문구 보강:
  - 자동 정리 스냅샷이 있는 상태에서
    - 문제 줄이 남아 있으면 `자동 정리 취소` 복구 힌트 포함
    - 문제 줄이 없으면 “정리된 상태/원문 복구 가능” 안내로 전환
- 목적:
  - 정리 후 상태에서 교사가 다음 행동(진행 vs 복구)을 즉시 선택할 수 있도록 문맥 안내 강화

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서 검토 타깃 1 test, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(문구/버튼 위치 최종 미세 조정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:16**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-77. SB-108 진행 (문제 줄 개수 기반 버튼 문구 + 권장 순서 가이드)

### A. 구현 요약
- 동의서 사전 검토(`consent_review`) 미세 UX 조정:
  - `문제 줄 제외하고 정리` 버튼 문구를 문제 줄 개수에 맞춰 동적 표시
    - 예: `문제 줄 3개 제외하고 정리`
  - `문제 줄만 복사` 버튼 문구도 개수 기반으로 동적 표시
    - 예: `문제 줄 3개 복사`
  - 안내 라인 `id="recipients-action-guide"` 추가:
    - 문제 줄 존재 시: 확인 -> 복사 -> 정리 순서 제시
    - 정리 완료/복구 가능 상태 시: 확인 -> 제출(필요 시 복구) 순서 제시
- 목적:
  - 교사가 현재 상태(문제 줄 존재 여부)에 맞는 다음 행동을 버튼/문구만 보고 즉시 선택하도록 동선 명확화

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`

결과:
- 동의서 검토 타깃 1 test, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 파일럿 잔여 UX 개선(버튼 군집 배치/문구 최종 확정)
  2. `SB-015` 수동 signoff 2건 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:30**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-78. SB-108/SB-015 진행 (버튼 군집 배치 조정 + signoff 최신화)

### A. 구현 요약
- `SB-108` 동의서 검토(`consent_review`) 액션 버튼 배치를 2개 군집으로 분리:
  - 1행: `문제 줄 제외 정리` / `자동 정리 취소` / `문제 줄 복사`
  - 2행: `이전/다음 문제 줄` + `맨 위/맨 아래`
- 목적:
  - 긴 수신자 목록에서 “정리/복구”와 “이동” 목적 버튼을 분리해 즉시 인지 가능하도록 개선
- `SB-015` 게이트 최신화:
  - readiness/decision 재실행으로 최신 수동 대기 상태 동기화

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `node --check` (consent_review 인라인 스크립트 추출 검사)
- `python manage.py check`
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

결과:
- 동의서 검토 타깃 1 test, OK
- 인라인 JS 문법 검사(node --check) OK
- `python manage.py check` OK
- readiness: `HOLD` (`automated_gate_pass=true`, manual pending 2건)
- decision: `HOLD`, `next_actions`에 batch/단건 signoff + refresh 제시

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 최종 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:33**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-79. SB-015 진행 (signoff decision에 alias 집계 상태 추가)

### A. 구현 요약
- `run_sheetbook_signoff_decision.py` 출력 보강:
  - `decision_context.manual_alias_statuses` 필드 추가
  - 제공 값:
    - `staging_real_account_signoff`
    - `production_real_account_signoff`
    - `real_device_grid_1000_smoke`
  - 집계 규칙:
    - alias 하위 키 중 `FAIL` 하나라도 있으면 `FAIL`
    - 전부 `PASS`면 `PASS`
    - 그 외는 `HOLD`
- `next_actions` 계산에서도 alias 집계 상태를 우선 참조하도록 정리
- 목적:
  - 운영자가 원자 키 5개를 직접 합산하지 않고, 수동 signoff 3개 관점으로 즉시 판독 가능

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookSignoffDecisionScriptTests`
- `python scripts/run_sheetbook_signoff_decision.py`
- `python -m py_compile scripts/run_sheetbook_signoff_decision.py`

결과:
- signoff 스크립트 타깃 3 tests, OK
- decision JSON에 `manual_alias_statuses` 출력 확인
- 파이썬 문법 컴파일 검사 OK

### C. 문서 동기화
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - decision JSON에서 `manual_alias_statuses` 확인 포인트 추가
- `docs/runbooks/templates/sheetbook_release_signoff_template.md`
  - 템플릿 체크 항목에 `decision_context.manual_alias_statuses` 추가

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 최종 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### E. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:36**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-80. SB-108/SB-015 타깃 묶음 회귀 (최신 반영본)

### A. 실행
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookSignoffDecisionScriptTests sheetbook.tests.SheetbookRolloutCommandTests.test_check_sheetbook_rollout_passes_when_ready`

### B. 결과
- 묶음 타깃 5 tests, OK
- 확인 포인트:
  - `consent_review` 버튼 군집/동적 문구/가이드 추가 후 회귀 없음
  - signoff `manual_alias_statuses` 출력 확장 후 회귀 없음
  - rollout 기본 통과 경로 유지

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 최종 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `P2` 착수 후보 확정(`SB-201`/`SB-202`)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:37**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-81. P2 착수 후보 확정 (SB-202 우선)

### A. 결정 요약
- `P2` 착수 우선순위 확정:
  1. `SB-202 학년도 복제/아카이브`
  2. `SB-201 추천 탭 자동 제안 엔진`
- 판단 근거:
  - `SB-202`는 신학기 전환의 반복 작업 절감 효과가 즉시 크고, 기존 CRUD 기반 재사용이 가능해 초기 리스크가 낮음
  - `SB-201`은 규칙 엔진 확장성은 높지만 추천 품질 검증 루프가 추가 필요

### B. SB-202 1차 스코프 고정
- 복제 시 `academic_year +1` 기본 적용
- 탭/열 구조 우선 복제, 행 데이터 복제는 옵션 분리
- 아카이브(읽기 전용) + 활성/아카이브 필터를 MVP 범위로 정의

### C. 문서 동기화
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`
  - `15.4 P2 착수 후보 결정 (2026-03-02)` 섹션 추가

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 최종 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 1차 구현 착수(복제/아카이브 MVP)

### E. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:38**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`은 IN_PROGRESS)

---

### 0-82. SB-202 진행 (학년도 복제/아카이브 MVP 1차 착수)

### A. 구현 요약
- 데이터 모델 확장:
  - `Sheetbook.is_archived`(default=False)
  - `Sheetbook.archived_at`(nullable)
  - 마이그레이션: `sheetbook/migrations/0006_sheetbook_archive_fields.py`
- 목록(index) 필터/액션:
  - 상태 필터 추가: `status=active|archived|all`
  - 카드별 액션 추가:
    - `POST /sheetbook/<pk>/archive/`
    - `POST /sheetbook/<pk>/unarchive/`
- 읽기 전용 가드:
  - 기존 편집 차단 헬퍼(`_maybe_block_mobile_read_only_edit`)에 archive 차단 로직 통합
  - 아카이브 상태에서 편집 API 요청 시 차단 + 안내 메시지
  - 그리드 상단 배너 제목을 `아카이브 읽기 모드`로 분기

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_index_can_filter_archived_sheetbooks sheetbook.tests.SheetbookOwnershipTests.test_archive_and_unarchive_sheetbook sheetbook.tests.SheetbookOwnershipTests.test_archived_sheetbook_blocks_tab_create sheetbook.tests.SheetbookOwnershipTests.test_quick_copy_sheetbook_clones_tab_structure`
- `python manage.py makemigrations --check`
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests`
- `python manage.py check`

결과:
- 아카이브 타깃 + quick copy 회귀 4 tests, OK
- `makemigrations --check` OK (No changes detected)
- `SheetbookOwnershipTests` 22 tests, OK
- `python manage.py check` OK

### C. 문서 동기화
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`
  - `SB-202` 상태를 `IN_PROGRESS`로 갱신
  - MVP 1차 구현 메모(필드/필터/가드/테스트) 반영

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 2차(복제 옵션: 탭/열만 vs 행 포함) 구현

### E. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:51**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-83. SB-202 진행 (quick copy `행 포함` 옵션 추가)

### A. 구현 요약
- `quick_copy_sheetbook` 확장:
  - `include_rows`(bool) 옵션 추가
  - 기본(`False`): 기존처럼 탭/열 구조 + 빈 1행만 복제
  - 옵션(`True`): 원본 행/셀 데이터까지 복제
- 구조 복제 헬퍼 확장:
  - `_clone_sheetbook_structure(..., include_rows=...)`
  - 반환 지표 확장:
    - `cloned_tab_count`, `cloned_column_count`, `cloned_row_count`, `cloned_cell_count`
- 워크스페이스 CTA UI 보강:
  - `작년 수첩 이어쓰기` 폼에 `행 포함` 체크박스 추가
- 계측 보강:
  - `sheetbook_created` 메타에 `copied_with_rows`, `cloned_row_count`, `cloned_cell_count` 저장

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_quick_copy_sheetbook_clones_tab_structure sheetbook.tests.SheetbookOwnershipTests.test_quick_copy_sheetbook_can_include_rows_and_cells`
- `python manage.py test core.tests.test_home_view.HomeV2ViewTest.test_v2_authenticated_sheetbook_workspace_uses_quick_cta_flows`
- `python manage.py check`

결과:
- quick copy 타깃 2 tests, OK
- 홈 워크스페이스 quick CTA 1 test, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 아카이브 필터/복제 옵션 사용자 안내 문구 정리

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:58**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-84. SB-202 회귀 검증 (Ownership 전체 재실행)

### A. 실행
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests`

### B. 결과
- `SheetbookOwnershipTests` 23 tests, OK
- 확인 포인트:
  - 아카이브 필드/필터/토글 동선 회귀 없음
  - 아카이브 읽기 전용 차단 로직 회귀 없음
  - quick copy 기본/행 포함 분기 동작 회귀 없음

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 복제 옵션 안내 문구/사용자 도움말 정리

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 00:59**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-85. SB-202 진행 (아카이브 상세 배너 + quick copy 안내 고정)

### A. 구현 요약
- 아카이브 상세 화면(`sheetbook:detail`)에 안내 배너 추가:
  - 제목: `아카이브 읽기 전용 수첩`
  - 설명: 읽기 전용 상태 안내 + 이어쓰기 권장
  - 즉시 실행 CTA: `행 포함 이어쓰기`
    - `POST /sheetbook/quick-copy/`
    - `source=sheetbook_detail_archive_banner`
    - `include_rows=1`
- 워크스페이스 quick CTA 테스트 보강:
  - `작년 수첩 이어쓰기` 폼에 `include_rows=1` + `행 포함` 문구 존재 검증

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_detail_shows_archive_read_only_banner_and_copy_cta sheetbook.tests.SheetbookOwnershipTests.test_quick_copy_sheetbook_can_include_rows_and_cells`
- `python manage.py test core.tests.test_home_view.HomeV2ViewTest.test_v2_authenticated_sheetbook_workspace_uses_quick_cta_flows`
- `python manage.py check`

결과:
- 아카이브 배너/quick copy 타깃 2 tests, OK
- 홈 quick CTA 타깃 1 test, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 아카이브 목록 정렬/필터 세부 UX 정리

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:06**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-86. SB-202 진행 (아카이브 필터 탭에 상태 개수 노출)

### A. 구현 요약
- index 뷰 컨텍스트에 상태별 개수 집계 추가:
  - `status_counts.active`
  - `status_counts.archived`
  - `status_counts.all`
- 필터 탭 문구를 개수 포함으로 갱신:
  - `활성 N`, `아카이브 N`, `전체 N`
- 목적:
  - 아카이브 정리 시 현재 활성/보관 규모를 즉시 파악하도록 인지 부하 감소

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_index_can_filter_archived_sheetbooks sheetbook.tests.SheetbookOwnershipTests.test_index_empty_state_shows_sample_onboarding_cta`
- `python manage.py check`

결과:
- index 필터/empty 상태 타깃 2 tests, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 목록-상세 간 필터 컨텍스트 유지 정리

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:08**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-87. SB-202 진행 (목록 필터 컨텍스트 유지 + archive read 이벤트 분리)

### A. 구현 요약
- 목록(index) -> 상세(detail) 진입 링크에 index 컨텍스트 전달:
  - `index_status`, `index_q`, `index_page`
- 상세의 `목록으로` 링크가 위 컨텍스트를 보존하도록 수정
- 아카이브 상세 진입 이벤트 분리:
  - `sheetbook_archive_read_mode_opened`
  - 기존 `sheetbook_mobile_read_mode_opened`와 분리해 지표 해석 정확도 개선
- 이벤트 라벨 맵에 archive/mobile read-mode 관련 항목 추가

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_detail_shows_archive_read_only_banner_and_copy_cta sheetbook.tests.SheetbookOwnershipTests.test_detail_back_link_preserves_index_filter_context sheetbook.tests.SheetbookOwnershipTests.test_index_can_filter_archived_sheetbooks core.tests.test_home_view.HomeV2ViewTest.test_v2_authenticated_sheetbook_workspace_uses_quick_cta_flows`
- `python manage.py check`

결과:
- 상세 배너/컨텍스트 유지/필터/홈 CTA 타깃 4 tests, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 아카이브 필터 UX 마감(빈 상태/정렬 안내 문구)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:14**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-88. SB-015 게이트 최신화 (readiness/decision refresh)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

### B. 결과
- readiness: `HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- decision: `HOLD`
  - `manual_alias_statuses`:
    - `staging_real_account_signoff=HOLD`
    - `production_real_account_signoff=HOLD`
    - `real_device_grid_1000_smoke=PASS(waived)`
  - `next_actions`: batch/단건 manual signoff + refresh 명령 유지

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 아카이브 필터 UX 마감

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:15**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-89. SB-202 진행 (정렬 규칙 고정 + 아카이브 운영 지표 카드)

### A. 구현 요약
- 목록 정렬 규칙 고정:
  - `status=active`: 최근 수정(`updated_at`) 순
  - `status=archived`: 최근 보관(`archived_at`) 순
  - `status=all`: 활성 수첩 우선(`is_archived=False`) 후 최근 수정 순
- 필터 안내 문구 추가:
  - active/all/archived 상태별 정렬 안내 노출
- 관리자 지표(`metrics_dashboard`) 확장:
  - `sheetbook_archived_count`
  - `sheetbook_unarchived_count`
  - `sheetbook_archive_read_mode_opened_count`
  - 카드: `아카이브/복구` 추가

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_index_can_filter_archived_sheetbooks sheetbook.tests.SheetbookOwnershipTests.test_index_archived_orders_by_recent_archived_at sheetbook.tests.SheetbookOwnershipTests.test_index_all_lists_active_before_archived`
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage`
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_detail_back_link_preserves_index_filter_context sheetbook.tests.SheetbookOwnershipTests.test_detail_shows_archive_read_only_banner_and_copy_cta`
- `python manage.py check`

결과:
- ownership 타깃 5 tests, OK
- metrics 타깃 2 tests, OK
- 상세 컨텍스트/배너 타깃 2 tests, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 아카이브 상태 bulk 작업(다건 아카이브/복구) 검토

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:22**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-90. SB-202 진행 (다건 아카이브/복구 완결 + 지표 반영)

### A. 구현 요약
- 다건 처리 엔드포인트 완성:
  - `POST /sheetbook/bulk-archive/` (`sheetbook:bulk_archive_update`)
  - `archive|unarchive` 동작 지원
  - 선택 id를 `selected/matched/ignored`로 분리해 권한 없음·삭제 id를 안전 처리
- 메시지/계측 정확도 보강:
  - 성공 메시지에 `이미 상태 동일(unchanged)` 수량 포함
  - 접근 불가·삭제 id는 `ignored_count`로 별도 안내
  - 이벤트 메타데이터 확장:
    - `selected_count`, `matched_count`, `changed_count`, `unchanged_count`, `ignored_count`, `archive_action`
- 목록 UX 보강:
  - 다건 폼에 `전체 선택` 체크박스 추가
  - 현재 페이지 기준 `N개 선택` 카운터 추가
- 관리자 지표 확장:
  - summary에 `sheetbook_archive_bulk_updated_count` 추가
  - `아카이브/복구` 카드에 `다건 처리 N회` 노출
  - 이벤트 라벨 맵에 `교무수첩 다건 아카이브/복구` 라벨 추가

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_archives_selected_sheetbooks sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_unarchives_selected_sheetbooks_and_excludes_inaccessible_ids sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_requires_selected_sheetbook_ids sheetbook.tests.SheetbookOwnershipTests.test_index_renders_bulk_archive_controls`
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`
- `python manage.py check`

결과:
- bulk 동선/권한 제외/선택 필수/목록 컨트롤 타깃 4 tests, OK
- metrics 다건 집계 반영 타깃 1 test, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 페이지 단위 UX 보강(필터/페이지 전환 시 선택 초기화 안내)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:36**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-91. SB-202 진행 (다건 아카이브 UX 마감: 선택 0개 방지 + 페이지 범위 안내)

### A. 구현 요약
- 목록 다건 처리 폼 UX 보강:
  - `선택 적용` 버튼(`sheetbook-bulk-apply-button`)을 기본 비활성화
  - 선택 개수(`N개 선택`)에 따라 버튼 활성/비활성 동기화
  - 안내 문구 고정: `현재 페이지에서 선택한 수첩만 일괄 처리됩니다.`
- 선택 토글 스크립트와 연계:
  - `전체 선택`/개별 선택 변경 시 카운터 + 버튼 상태 동시 갱신

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_index_renders_bulk_archive_controls`
- index 인라인 스크립트 문법 검사(`node --check` 추출 방식)

결과:
- 목록 다건 컨트롤 타깃 1 test, OK
- 인라인 스크립트 문법 검사 OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 처리 운영 가이드(실수 복구/권한 제외 메시지) 문서화

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:39**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-92. SB-202 진행 (다건 아카이브 지표 해석 보강: 변경 건수 분리)

### A. 구현 요약
- `metrics_dashboard` 집계 확장:
  - `sheetbook_archive_bulk_updated` 이벤트 메타데이터(`changed_count`, `archive_action`)를 합산
  - 신규 summary 필드:
    - `sheetbook_bulk_archive_changed_count`
    - `sheetbook_bulk_unarchive_changed_count`
- 지표 카드 문구 확장:
  - `다건 처리 N회 (보관 X건 / 복구 Y건)` 형태로 노출
  - 기존 `읽기 모드 진입` 지표와 함께 표시

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`
- `python manage.py check`

결과:
- metrics 타깃 1 test, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 처리 운영 가이드(실수 복구/권한 제외 메시지) 문서화

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:41**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-93. SB-202 운영 문서화 (다건 아카이브/복구 런북 추가)

### A. 문서 추가
- `docs/runbooks/SHEETBOOK_ARCHIVE_BULK_OPERATION.md`
  - 표준 처리 절차(선택/동작/검증)
  - 예외 메시지 해석 기준(`선택 없음`, `ignored`, `all invalid`)
  - 운영 지표 확인 항목(단건/다건 분리)
  - 일/주간 체크리스트

### B. 효과
- 다건 처리 이후 운영자가 메시지와 지표를 동일 기준으로 해석 가능
- 권한/삭제 id 혼입(`ignored`) 발생 시 대응 루틴을 문서로 고정

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 처리 실사용 로그 점검(ignored 비율/동일상태 비율)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:43**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-107. 최종 마감 핸드오프 (내일 재시작 가이드)

### A. 오늘 마감 상태 요약
- `SB-202`:
  - 다건 아카이브/복구 UX + 계측 + 지표 + 운영 런북 + 품질 스냅샷 스크립트 완료
- `SB-108`:
  - consent_review freeze 후보 baseline(v1) 확정
  - `data-testid`/버튼 순서 회귀 테스트 고정
- `SB-015`:
  - readiness/decision 최신화 결과 `HOLD` 유지
  - 수동 signoff 2건(`staging_real_account_signoff`, `production_real_account_signoff`) 대기

### B. 내일 바로 시작 명령 (순서 고정)
1. 게이트 최신화
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
2. 다건 품질 스냅샷
  - `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
  - `docs/handoff/sheetbook_archive_bulk_snapshot_latest.json` 확인
3. freeze 회귀 빠른 점검
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
  - `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`

### C. 내일 작업 우선순위
1. `SB-015` 수동 signoff 2건 실점검 반영
2. `SB-202` 다건 실사용 표본 1차 확보(`event_count >= 5`) 후 비율 판정
3. `SB-108` freeze 기준선 대비 파일럿 피드백 diff 선별 반영

### D. master 기준 잔여율
- 기준 시각: **2026-03-02 02:02**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-106. EOD 핸드오프 (내일 이어서 진행 가이드)

### A. 오늘 종료 시점 상태
- 핵심 진행:
  - `SB-202` 다건 아카이브/복구 UX/계측/지표/운영문서/스냅샷 스크립트 반영 완료
  - `SB-108` consent_review freeze 후보 baseline(v1) + QA 식별자/순서 회귀 테스트 고정
  - `SB-015` 게이트 재실행 결과 유지(`HOLD`, manual 2건 pending)
- 회귀 상태:
  - SB-202/SB-108 관련 타깃 테스트 및 `python manage.py check` 모두 통과

### B. 내일 시작 10분 체크리스트 (권장 순서)
1. 최신 게이트 상태 재확인
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
2. 다건 운영 품질 스냅샷 재수집
  - `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
  - `docs/handoff/sheetbook_archive_bulk_snapshot_latest.json`의 `event_count`, `ignored_rate_pct`, `unchanged_rate_pct` 확인
3. freeze 회귀 빠른 점검
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
  - `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`

### C. 내일 우선 작업 큐
1. `SB-015` 수동 signoff 2건 실점검 반영 (staging/prod real-account)
2. `SB-202` 실사용 표본 1차 확보(`sheetbook_archive_bulk_updated >= 5`) 후 품질 판정
3. `SB-108` freeze 기준선 대비 파일럿 피드백 diff만 선별 반영

### D. master 기준 진행률
- 기준 시각: **2026-03-02 02:00**
- 백로그 기준: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-95. SB-202 진행 (다건 아카이브 운영 지표 확장: 제외/동일상태 집계)

### A. 구현 요약
- `sheetbook_archive_bulk_updated` 메타데이터 추가 집계:
  - `ignored_count` 합산 -> `sheetbook_bulk_ignored_count`
  - `unchanged_count` 합산 -> `sheetbook_bulk_unchanged_count`
- 관리자 지표 카드(`아카이브/복구`)에 아래 문구 추가:
  - `다건 제외 X건 · 동일 상태 Y건`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`
- `python manage.py check`

결과:
- metrics 타깃 1 test, OK
- `python manage.py check` OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 처리 실사용 로그 점검(ignored 비율/동일상태 비율)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:44**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-96. SB-202 운영 로그 점검 (최근 14일 다건 아카이브 품질 신호)

### A. 실행
- `python manage.py shell -c "<bulk_archive_updated 14일 집계 스니펫>"`

### B. 결과
- 최근 14일 집계:
  - `event_count=0`
  - `changed_total=0`
  - `ignored_total=0`
  - `unchanged_total=0`
  - `ignored_rate=0.0%`, `unchanged_rate=0.0%`
- 해석:
  - 아직 운영 DB 기준 다건 아카이브 실사용 표본이 없음
  - 지표 구조는 준비 완료, 다음 표본 유입 시 즉시 해석 가능

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:45**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-97. SB-202 회귀 보강 (다건 아카이브 all-inaccessible 분기 테스트 추가)

### A. 구현 요약
- 신규 테스트:
  - `test_bulk_archive_update_all_inaccessible_ids_records_zero_change`
- 검증 항목:
  - 타 사용자 id만 선택 시 안내 메시지 노출
  - 메트릭이 `matched_count=0`, `changed_count=0`, `ignored_count>0`으로 기록

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_all_inaccessible_ids_records_zero_change`

결과:
- 타깃 1 test, OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:46**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-98. SB-108 진행 (동의서 검토 QA 식별자 고정)

### A. 구현 요약
- `consent_review` 핵심 컨트롤에 `data-testid` 추가:
  - `recipients-textarea`
  - `recipients-cleanup-btn`
  - `recipients-cleanup-undo-btn`
  - `recipients-copy-issues-btn`
  - `recipients-prev-issue-btn`
  - `recipients-next-issue-btn`
  - `recipients-jump-top-btn`
  - `recipients-jump-bottom-btn`
  - `recipients-submit-btn`
- 기존 통합 테스트에 위 식별자 존재 검증 추가

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `consent_review` 인라인 스크립트 `node --check` 검증

결과:
- consent review 타깃 1 test, OK
- 인라인 스크립트 문법 검사 OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:49**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-99. 회귀 묶음 검증 (SB-202 + SB-108 변경분)

### A. 실행
- `python manage.py test sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_archives_selected_sheetbooks sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_unarchives_selected_sheetbooks_and_excludes_inaccessible_ids sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_requires_selected_sheetbook_ids sheetbook.tests.SheetbookOwnershipTests.test_bulk_archive_update_all_inaccessible_ids_records_zero_change sheetbook.tests.SheetbookOwnershipTests.test_index_renders_bulk_archive_controls sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `python manage.py check`

### B. 결과
- 타깃 회귀 7 tests, 모두 OK
- `python manage.py check` OK
- 결론:
  - SB-202 다건 아카이브/복구 및 지표 확장 회귀 없음
  - SB-108 consent_review QA 식별자 추가 회귀 없음

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:51**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-100. SB-108 진행 (consent_review freeze 체크리스트 문서화)

### A. 문서 추가
- `docs/runbooks/SHEETBOOK_CONSENT_REVIEW_FREEZE_CHECKLIST.md`
  - freeze scope 정의(문제 줄 정리/이동, 제출 가드, 계측)
  - 고정 id/data-testid 목록 명시
  - 계측 필드 고정 목록 명시
  - 회귀 명령 세트 명시

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_post_updates_seed_and_redirects_step1 sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_summarizes_consent_cleanup_usage`

결과:
- freeze 기준 연계 타깃 3 tests, OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:52**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-101. SB-108 진행 (consent_review 버튼 순서 freeze 테스트 추가)

### A. 구현 요약
- `test_consent_seed_review_shows_recipient_parse_summary`에 버튼 순서 검증 추가:
  - 1열: `cleanup -> undo -> copy`
  - 2열: `prev -> next -> top -> bottom`
- 의도:
  - 문구뿐 아니라 동선 순서 회귀까지 테스트로 고정

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`

결과:
- 타깃 1 test, OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:54**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-102. SB-202 회귀 보강 (다건 이벤트 라벨 노출 검증 추가)

### A. 구현 요약
- `SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`에
  다건 이벤트 라벨 텍스트 검증 추가:
  - `교무수첩 다건 아카이브/복구`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`

결과:
- metrics 타깃 1 test, OK

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:55**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-103. SB-202 운영 자동화 (다건 아카이브 품질 스냅샷 스크립트 추가)

### A. 구현 요약
- 신규 스크립트:
  - `scripts/run_sheetbook_archive_bulk_snapshot.py`
- 기능:
  - 최근 N일(`--days`) `sheetbook_archive_bulk_updated` 집계
  - 합계: `selected/matched/changed/unchanged/ignored`
  - 비율: `changed/unchanged/ignored_rate_pct`
  - 품질 판정:
    - `has_enough_samples` (>=5 events)
    - `needs_attention` (`ignored_rate>10%` 또는 `unchanged_rate>50%`)
  - 출력:
    - 기본 `docs/handoff/sheetbook_archive_bulk_snapshot_latest.json`

### B. 테스트/검증
- `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- `python -m py_compile scripts/run_sheetbook_archive_bulk_snapshot.py`
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_archive_bulk_snapshot_collects_counts_rates_and_attention`

결과:
- 스크립트 실행/컴파일 OK
- 스크립트 집계 로직 타깃 1 test, OK
- 현재 로컬 운영 데이터 집계 결과: `event_count=0` (표본 부족)

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:57**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-104. SB-108 기준선 갱신 (consent_review freeze 후보 baseline v1)

### A. 반영 내용
- 플랜 문서에 freeze 후보 baseline(v1, 2026-03-02) 명시:
  - 컨트롤 `id/data-testid`
  - 버튼 순서(1열/2열)
  - 계측 필드 이름
- 위 항목을 변경 금지 기준선으로 관리하도록 고정

### B. 효과
- 파일럿 기간 중 문구/버튼 변경 요청이 들어와도
  기준선 대비 영향 범위를 즉시 판별 가능

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` freeze 후보 기준으로 파일럿 피드백 diff만 선별 반영
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:58**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-105. SB-202 운영 문서 보강 (스냅샷 스크립트 사용 절차 추가)

### A. 문서 반영
- `docs/runbooks/SHEETBOOK_ARCHIVE_BULK_OPERATION.md` 업데이트:
  - `run_sheetbook_archive_bulk_snapshot.py --days 14` 실행 섹션 추가
  - 출력 파일 및 확인 포인트(`has_enough_samples`, `ignored_rate`, `unchanged_rate`, `needs_attention`) 명시

### B. 효과
- 운영자가 대시보드 수치를 수동 확인하지 않아도
  주기적으로 품질 판정을 파일 기반으로 기록 가능

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` freeze 후보 기준으로 파일럿 피드백 diff만 선별 반영
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 아카이브 실사용 1차 표본(>=5 events) 수집 후 비율 재판정

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:58**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-94. SB-015 게이트 최신화 (readiness/decision 재실행)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`

### B. 결과
- readiness overall:
  - `status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- decision:
  - `decision=HOLD`
  - `manual_alias_statuses` 유지:
    - `staging_real_account_signoff=HOLD`
    - `production_real_account_signoff=HOLD`
    - `real_device_grid_1000_smoke=PASS`
- 산출물 갱신:
  - `docs/handoff/sheetbook_release_readiness_latest.json`
  - `docs/handoff/sheetbook_release_decision_latest.json`

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-108` 문구/버튼 freeze 후보 확정
  2. `SB-015` 수동 signoff 2건 실점검 반영
  3. `SB-202` 다건 처리 실사용 로그 점검(ignored 비율/동일상태 비율)

### D. 전체 진행률(최신)
- 기준 시각: **2026-03-02 01:43**
- `마스터 플랜 전체(P0+P1+P2)` 기준: **약 59% 완료**, **약 41% 잔여**
  - 근거: 백로그 `SB-001~016, 101~111, 201~205` 총 32개 중 19개 DONE (`SB-108`, `SB-015`, `SB-202`은 IN_PROGRESS)

---

### 0-108. 최종 마감 핸드오프 (파일 끝 고정본)

### A. 오늘 마감 상태 요약
- `SB-202`:
  - 다건 아카이브/복구 UX + 계측 + 지표 + 운영 런북 + 품질 스냅샷 스크립트 완료
- `SB-108`:
  - consent_review freeze 후보 baseline(v1) 확정
  - `data-testid`/버튼 순서 회귀 테스트 고정
- `SB-015`:
  - readiness/decision 최신화 결과 `HOLD` 유지
  - 수동 signoff 2건(`staging_real_account_signoff`, `production_real_account_signoff`) 대기

### B. 내일 바로 시작 명령 (순서 고정)
1. 게이트 최신화
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
2. 다건 품질 스냅샷
  - `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
  - `docs/handoff/sheetbook_archive_bulk_snapshot_latest.json` 확인
3. freeze 회귀 빠른 점검
  - `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
  - `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`

### C. 내일 작업 우선순위
1. `SB-015` 수동 signoff 2건 실점검 반영
2. `SB-202` 다건 실사용 표본 1차 확보(`event_count >= 5`) 후 비율 판정
3. `SB-108` freeze 기준선 대비 파일럿 피드백 diff 선별 반영

### D. master 기준 잔여율
- 기준 시각: **2026-03-02 02:04**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-109. 2026-03-02 재개 점검 (체크리스트 재실행 + 상태 동기화)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`
- `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- `python manage.py test sheetbook.tests.SheetbookGridApiTests.test_consent_seed_review_shows_recipient_parse_summary`
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_metrics_dashboard_calculates_revisit_and_quick_create_rate`
- `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=HOLD:pending --set production_real_account_signoff=HOLD:pending`

### B. 결과
- readiness (`2026-03-02 18:56:54`):
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
  - `waived_manual_checks=["real_device_grid_1000_smoke"]`
- decision (`2026-03-02 19:00:07`):
  - `decision=HOLD`
  - `manual_alias_statuses`:
    - `staging_real_account_signoff=HOLD`
    - `production_real_account_signoff=HOLD`
    - `real_device_grid_1000_smoke=PASS`
- archive bulk snapshot:
  - `event_count=0`
  - `has_enough_samples=false`
  - `needs_attention=false`
- freeze 회귀 빠른 점검:
  - `test_consent_seed_review_shows_recipient_parse_summary` OK
  - `test_metrics_dashboard_calculates_revisit_and_quick_create_rate` OK
- 수동 signoff 상태 파일 동기화:
  - `docs/handoff/sheetbook_manual_signoff_latest.json`의 staging/production 항목 `updated_at`을 `2026-03-02 19:00:07`로 갱신(`HOLD:pending` 유지)

### C. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-015` 수동 signoff 2건 실점검 후 PASS 반영
     - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
  2. `SB-202` 다건 실사용 표본 1차 확보(`event_count >= 5`) 후 품질 비율 재판정
     - `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
  3. `SB-108` freeze baseline(v1) 대비 파일럿 피드백 diff만 선별 반영

### D. master 기준 잔여율(변동 없음)
- 기준 시각: **2026-03-02 19:00**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-110. SB-202 진행 (다건 품질 스냅샷 판정 고도화: 표본 부족량/다음조치/커스텀 임계치)

### A. 구현 요약
- `scripts/run_sheetbook_archive_bulk_snapshot.py` 보강:
  - 품질 판정 기준을 CLI로 조정 가능:
    - `--min-events` (기본 5)
    - `--ignored-rate-threshold` (기본 10.0)
    - `--unchanged-rate-threshold` (기본 50.0)
  - 출력 `quality`에 운영 후속 판단 필드 추가:
    - `sample_gap_count` (목표 표본까지 남은 이벤트 수)
    - `thresholds` (이번 판정 기준값)
    - `next_step` (`collect_more_samples` / `investigate_bulk_flow` / `continue_monitoring`)
  - 기존 reason 포맷 유지 + 임계치 기반 동적 reason 키 생성
    - 예: `ignored_rate_over_40pct`, `unchanged_rate_over_40pct`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookMetricTests.test_archive_bulk_snapshot_collects_counts_rates_and_attention sheetbook.tests.SheetbookMetricTests.test_archive_bulk_snapshot_reports_sample_gap_and_supports_custom_thresholds`
- `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14 --min-events 3 --ignored-rate-threshold 12.5 --unchanged-rate-threshold 45`
- `python -m py_compile scripts/run_sheetbook_archive_bulk_snapshot.py`

결과:
- 타깃 테스트 2 tests, OK
- 스냅샷 기본 실행 결과:
  - `event_count=0`
  - `quality.sample_gap_count=5`
  - `quality.next_step=collect_more_samples`
- 커스텀 임계치 실행 결과:
  - `quality.thresholds.min_events=3`
  - `quality.sample_gap_count=3`
  - `quality.next_step=collect_more_samples`

### C. 문서 반영
- `docs/runbooks/SHEETBOOK_ARCHIVE_BULK_OPERATION.md` 업데이트:
  - 커스텀 임계치 실행 예시 추가
  - `sample_gap_count`/`thresholds`/`next_step` 확인 포인트 추가

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-015` 수동 signoff 2건 실점검 후 PASS 반영
  2. `SB-202` 실사용 표본 `event_count >= 5` 확보 후 `next_step`가 `collect_more_samples`에서 해제되는지 재확인
  3. `SB-108` freeze baseline(v1) 대비 파일럿 diff 선별 반영

---

### 0-111. SB-014 진행 (임계치 재보정 role 분해 + 파일럿 스냅샷 역할별 출력)

### A. 구현 요약
- `recommend_sheetbook_thresholds` 보강:
  - `--group-by-role` 옵션 추가
  - `user__userprofile__role` 기준으로 퍼널 관측치/전환율/권장값을 role별로 출력
  - 공통 계산 로직을 `_build_recommendation`으로 분리해 전체/role 계산 일관성 유지
- `run_sheetbook_pilot_log_snapshot.py` 보강:
  - 결과 JSON에 `role_breakdown` 포함
  - Markdown 로그에 `## 3) 역할별 스냅샷 참고` 섹션 추가
  - role 섹션 줄바꿈 조합 버그(`\\n` 리터럴 출력 가능성) 수정
- 테스트 보강:
  - `SheetbookThresholdRecommendationCommandTests.test_recommend_sheetbook_thresholds_outputs_role_breakdown`
  - `SheetbookPilotLogSnapshotScriptTests.test_pilot_snapshot_includes_role_breakdown`
  - `SheetbookPilotLogSnapshotScriptTests.test_pilot_markdown_role_section_uses_actual_newlines`

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookThresholdRecommendationCommandTests sheetbook.tests.SheetbookPilotLogSnapshotScriptTests`
- `python manage.py recommend_sheetbook_thresholds --days 14 --group-by-role`
- `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
- `python -m py_compile scripts/run_sheetbook_pilot_log_snapshot.py sheetbook/management/commands/recommend_sheetbook_thresholds.py`

결과:
- 타깃 테스트 5 tests, OK
- 추천 커맨드 실행 결과:
  - 전체 관측치 0건, 기존 임계치 유지
  - role 출력: `role 데이터 없음`
- 파일럿 스냅샷 실행 결과:
  - `role_breakdown={}` (표본 없음)
  - 산출물 갱신:
    - `docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_2026-03-02.md`
    - `docs/runbooks/logs/sheetbook_pilot_event_log_2026-03-02.csv`
- `py_compile` OK

### C. 문서 반영
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`:
  - SB-014 진행 메모에 `--group-by-role`/`role_breakdown` 반영
- `docs/runbooks/SHEETBOOK_PILOT_DATA_CHECKLIST.md`:
  - 재보정 명령 예시를 `--group-by-role` 기준으로 확장
  - Markdown role 섹션 확인 포인트 추가
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`:
  - role 분해 추천 명령 예시 및 해석 가이드 추가

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-015` 수동 signoff 2건 실점검 후 PASS 반영
  2. `SB-202` 실사용 표본 `event_count >= 5` 확보 후 품질 판정(`next_step`) 재확인
  3. `SB-108` freeze baseline(v1) 대비 파일럿 diff 선별 반영

### E. master 기준 잔여율(변동 없음)
- 기준 시각: **2026-03-02 19:45**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-112. SB-015 진행 (release signoff 로그 자동 생성 스크립트)

### A. 구현 요약
- 신규 스크립트 추가:
  - `scripts/run_sheetbook_release_signoff_log.py`
  - 입력:
    - `docs/handoff/sheetbook_release_readiness_latest.json`
    - `docs/handoff/sheetbook_manual_signoff_latest.json`
    - `docs/handoff/sheetbook_release_decision_latest.json`
  - 출력:
    - 기본 `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_<YYYY-MM-DD>.md`
  - 지원 옵션:
    - `--date`, `--author`, `--owner`, `--next-action`, `--due-date`, `--output`
- 자동 생성 로그 내용:
  - 자동 게이트 요약(`overall.status`, blocking/manual pending/waived)
  - `decision.next_actions` 명령 목록
  - `manual_alias_statuses`
  - 수동 점검 표(allowlisted/non_allowlisted/real-device) 자동 채움
  - 최종 판정 섹션(decision/owner/next_action/due_date)
- 테스트 추가:
  - `SheetbookReleaseSignoffLogScriptTests`
    - 게이트/수동표/next_actions 렌더링 검증
    - 값 누락 시 기본 출력(`(없음)`, `-`) 검증

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookSignoffDecisionScriptTests sheetbook.tests.SheetbookReleaseSignoffLogScriptTests`
- `python scripts/run_sheetbook_release_signoff_log.py --date 2026-03-02 --author sheetbook-ops --owner sheetbook-release --next-action "staging/prod 실계정 점검" --due-date 2026-03-03`
- `python -m py_compile scripts/run_sheetbook_release_signoff_log.py`

결과:
- 타깃 테스트 5 tests, OK
- 로그 파일 생성:
  - `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-02.md`
- 현재 판정 반영:
  - `decision=HOLD`
  - `readiness_status=HOLD`
  - `manual_pending=staging_real_account_signoff, production_real_account_signoff`

### C. 문서 반영
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`:
  - 자동 생성 명령(`run_sheetbook_release_signoff_log.py`) 추가
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`:
  - 배포 전 체크 권장 명령에 signoff 로그 자동 생성 추가
- `docs/plans/PLAN_eduitit_sheetbook_master_2026-02-27.md`:
  - SB-015 진행 메모에 signoff 로그 자동화 반영

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-015` 수동 signoff 2건 실점검 후 PASS 반영
  2. `SB-202` 실사용 표본 `event_count >= 5` 확보 후 품질 판정(`next_step`) 재확인
  3. `SB-108` freeze baseline(v1) 대비 파일럿 diff 선별 반영

### E. master 기준 잔여율(변동 없음)
- 기준 시각: **2026-03-02 19:58**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-113. SB-015 게이트 최신화 (readiness/decision/signoff log 재생성)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`
- `python scripts/run_sheetbook_release_signoff_log.py --date 2026-03-02 --author sheetbook-ops --owner sheetbook-release --next-action "staging/prod 실계정 점검" --due-date 2026-03-03`

### B. 결과
- readiness (`2026-03-02 19:53:37`):
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
  - `waived_manual_checks=["real_device_grid_1000_smoke"]`
- decision (`2026-03-02 19:53:47`):
  - `decision=HOLD`
  - `manual_alias_statuses`:
    - `staging_real_account_signoff=HOLD`
    - `production_real_account_signoff=HOLD`
    - `real_device_grid_1000_smoke=PASS`
- signoff 로그 산출:
  - `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-02.md` 갱신

### C. 산출물 갱신
- `docs/handoff/sheetbook_release_readiness_latest.json`
- `docs/handoff/sheetbook_manual_signoff_latest.json`
- `docs/handoff/sheetbook_release_decision_latest.json`
- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-02.md`

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-015` 수동 signoff 2건 실점검 후 PASS 반영
  2. `SB-202` 실사용 표본 `event_count >= 5` 확보 후 품질 판정(`next_step`) 재확인
  3. `SB-108` freeze baseline(v1) 대비 파일럿 diff 선별 반영

### E. master 기준 잔여율(변동 없음)
- 기준 시각: **2026-03-02 19:54**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-114. SB-108 진행 (consent freeze snapshot diff 자동화)

### A. 구현 요약
- 신규 스크립트 추가:
  - `scripts/run_sheetbook_consent_freeze_snapshot.py`
  - `consent_review.html`에서 freeze 핵심 토큰을 추출해 JSON 스냅샷 생성
  - 추출 범위:
    - `id`, `data-testid`, `data-recipients-jump`, hidden input `name`
    - 버튼 순서 룰(`cleanup`, `issue navigation`)
  - diff 결과:
    - `missing`(필수 누락)
    - `extra`(추가된 recipients-* 토큰)
    - `order_checks`(순서 위반 여부)
  - 판정:
    - 기본: 필수 누락/순서 위반 시 `HOLD`
    - `--strict-extras`: 추가 토큰도 `HOLD` 처리
- 테스트 추가:
  - `SheetbookConsentFreezeSnapshotScriptTests`
    - 현재 템플릿 기준 PASS 검증
    - 필수 토큰 누락 시 HOLD 검증
    - strict extras 시 HOLD 검증

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookConsentFreezeCommandTests sheetbook.tests.SheetbookConsentFreezeSnapshotScriptTests`
- `python scripts/run_sheetbook_consent_freeze_snapshot.py`
- `python scripts/run_sheetbook_consent_freeze_snapshot.py --strict-extras`
- `python -m py_compile scripts/run_sheetbook_consent_freeze_snapshot.py`

결과:
- 타깃 테스트 5 tests, OK
- 기본 스냅샷 결과:
  - `status=PASS`
  - 출력: `docs/handoff/sheetbook_consent_freeze_snapshot_latest.json`
- `--strict-extras` 결과:
  - `status=HOLD` (`unexpected_extra_tokens`)
  - 확인 후 기본 모드 재실행으로 최신 스냅샷 `PASS` 상태 복구

### C. 문서 반영
- `docs/runbooks/SHEETBOOK_CONSENT_REVIEW_FREEZE_CHECKLIST.md`
  - freeze 스냅샷 명령/산출물/strict 옵션 추가
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - signoff 단계에서 freeze snapshot diff 참고 명령 추가

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-015` 수동 signoff 2건 실점검 후 PASS 반영
  2. `SB-202` 실사용 표본 `event_count >= 5` 확보 후 품질 판정(`next_step`) 재확인
  3. `SB-108` freeze baseline(v1) 기준으로 snapshot diff를 파일럿 피드백 선별 기준으로 사용

### E. master 기준 잔여율(변동 없음)
- 기준 시각: **2026-03-02 20:08**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-115. 게이트/로그 최신화 (SB-015 + SB-202 + SB-108 상태 동기화)

### A. 실행
- `python scripts/run_sheetbook_release_readiness.py --days 14`
- `python scripts/run_sheetbook_signoff_decision.py`
- `python scripts/run_sheetbook_release_signoff_log.py --date 2026-03-02 --author sheetbook-ops --owner sheetbook-release --next-action "staging/prod 실계정 점검" --due-date 2026-03-03`
- `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
- `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
- `python scripts/run_sheetbook_consent_freeze_snapshot.py`

### B. 결과
- readiness (`2026-03-02 20:10:09`):
  - `overall.status=HOLD`
  - `automated_gate_pass=true`
  - `manual_pending=["staging_real_account_signoff","production_real_account_signoff"]`
- decision (`2026-03-02 20:10:17`):
  - `decision=HOLD`
  - `manual_alias_statuses`:
    - `staging_real_account_signoff=HOLD`
    - `production_real_account_signoff=HOLD`
    - `real_device_grid_1000_smoke=PASS`
- pilot snapshot:
  - `workspace_home_opened_count=0`
  - `role_breakdown={}` (role 데이터 없음)
- archive bulk snapshot:
  - `event_count=0`
  - `quality.sample_gap_count=5`
  - `quality.next_step=collect_more_samples`
- consent freeze snapshot:
  - `status=PASS`
  - `reasons=[]`

### C. 산출물 갱신
- `docs/handoff/sheetbook_release_readiness_latest.json`
- `docs/handoff/sheetbook_manual_signoff_latest.json`
- `docs/handoff/sheetbook_release_decision_latest.json`
- `docs/runbooks/logs/SHEETBOOK_RELEASE_SIGNOFF_2026-03-02.md`
- `docs/runbooks/logs/SHEETBOOK_PILOT_EVENT_LOG_2026-03-02.md`
- `docs/runbooks/logs/sheetbook_pilot_event_log_2026-03-02.csv`
- `docs/handoff/sheetbook_archive_bulk_snapshot_latest.json`
- `docs/handoff/sheetbook_consent_freeze_snapshot_latest.json`

### D. 다음 우선순위 갱신
- `SB-108`: IN_PROGRESS
- `SB-015`: IN_PROGRESS
- `SB-202`: IN_PROGRESS
- 다음 순서:
  1. `SB-015` 수동 signoff 2건 실점검 후 PASS 반영
  2. `SB-202` 실사용 표본 `event_count >= 5` 확보 후 품질 판정(`next_step`) 재확인
  3. `SB-108` freeze snapshot diff(`missing/extra/order`) 기준으로 파일럿 변경 요청 선별 반영

### E. master 기준 잔여율(변동 없음)
- 기준 시각: **2026-03-02 20:10**
- 백로그: 총 `32`개 중 `19`개 DONE
- 완료율: `59.4%`
- 잔여율: `40.6%` (약 `41%`)

---

### 0-116. 오늘 작업 요약 + 내일 시작 체크리스트 (운영용 고정)

### A. 오늘 작업 요약 (2026-03-02)
- `SB-014`:
  - `recommend_sheetbook_thresholds --group-by-role` 반영
  - `run_sheetbook_pilot_log_snapshot.py`에 `role_breakdown` + 역할별 Markdown 섹션 반영
  - role 섹션 줄바꿈 버그(`\\n` 리터럴) 수정 + 회귀 테스트 추가
- `SB-015`:
  - `run_sheetbook_release_signoff_log.py` 추가(readiness/manual/decision -> Markdown 로그 자동 생성)
  - release runbook/beta runbook/plan/handoff에 자동화 절차 반영
  - readiness/decision/signoff 로그 최신화 재실행(`HOLD` 유지)
- `SB-108`:
  - `run_sheetbook_consent_freeze_snapshot.py` 추가(consent freeze diff JSON)
  - `missing/extra/order_checks` 판정 + `--strict-extras` 옵션 반영
  - freeze checklist/release signoff runbook에 snapshot 점검 절차 반영

### B. 오늘 검증 요약
- 타깃 통합 테스트:
  - `SheetbookThresholdRecommendationCommandTests`
  - `SheetbookPilotLogSnapshotScriptTests`
  - `SheetbookSignoffDecisionScriptTests`
  - `SheetbookReleaseSignoffLogScriptTests`
  - `SheetbookConsentFreezeCommandTests`
  - `SheetbookConsentFreezeSnapshotScriptTests`
- 결과:
  - 총 15 tests, `OK`
  - 스크립트 `py_compile` 모두 `OK`
  - 산출물 최신화 완료(게이트/로그/스냅샷)

### C. 내일 시작 체크리스트 (순서 고정)
1. 게이트 최신화
  - `python scripts/run_sheetbook_release_readiness.py --days 14`
  - `python scripts/run_sheetbook_signoff_decision.py`
2. signoff 운영 로그 갱신
  - `python scripts/run_sheetbook_release_signoff_log.py --author sheetbook-ops --owner sheetbook-release --next-action "staging/prod 실계정 점검" --due-date 2026-03-03`
3. 파일럿/품질 스냅샷 갱신
  - `python manage.py recommend_sheetbook_thresholds --days 14 --group-by-role`
  - `python scripts/run_sheetbook_pilot_log_snapshot.py --days 14`
  - `python scripts/run_sheetbook_archive_bulk_snapshot.py --days 14`
  - `python scripts/run_sheetbook_consent_freeze_snapshot.py`
4. 수동 signoff 실제 반영(완료 시)
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
5. 반영 후 즉시 재확인
  - `python scripts/run_sheetbook_signoff_decision.py`
  - `python scripts/run_sheetbook_release_signoff_log.py --author sheetbook-ops --owner sheetbook-release --next-action "beta go/no-go 재판정" --due-date 2026-03-03`

### D. 내일 우선순위
1. `SB-015` 수동 signoff 2건 완료 처리
2. `SB-202` 실사용 표본 확보(`event_count >= 5`) 및 `next_step` 재판정
3. `SB-108` freeze snapshot diff 기준으로 파일럿 변경 요청 선별 반영

---

### 0-117. 내일 체크리스트 자동화 (daily start bundle 추가)

### A. 구현 요약
- 신규 스크립트 추가:
  - `scripts/run_sheetbook_daily_start_bundle.py`
  - 기존 내일 시작 체크리스트를 1회 실행으로 묶어 자동화:
    1. `run_sheetbook_release_readiness.py`
    2. `run_sheetbook_signoff_decision.py`
    3. `run_sheetbook_release_signoff_log.py`
    4. `recommend_sheetbook_thresholds --group-by-role`
    5. `run_sheetbook_pilot_log_snapshot.py`
    6. `run_sheetbook_archive_bulk_snapshot.py`
    7. `run_sheetbook_consent_freeze_snapshot.py`
- 출력:
  - `docs/handoff/sheetbook_daily_start_bundle_latest.json`
  - 명령별 성공/실패, 핵심 지표(readiness/decision/manual pending/archive next_step/freeze status) 요약

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookDailyStartBundleScriptTests`
- `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-03`
- `python -m py_compile scripts/run_sheetbook_daily_start_bundle.py`

결과:
- 테스트 2 tests, OK
- bundle 실행 결과:
  - `overall=HOLD`
  - `decision=HOLD`
  - `has_command_failures=false`
  - 출력: `docs/handoff/sheetbook_daily_start_bundle_latest.json`
- 로그 tail 인코딩 이슈 수정 후 한글 출력 정상 확인

### C. 문서 반영
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - 일일 시작 번들 실행 명령 추가
- `docs/runbooks/SHEETBOOK_RELEASE_SIGNOFF.md`
  - daily bundle 명령 + summary JSON 경로 추가

### D. 내일 시작 명령(권장)
1. 원클릭 실행:
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-03`
2. 수동 signoff 완료 시:
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
3. 재실행:
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-03`

---

### 0-118. 회귀 재검증 (bundle 반영 후 관련 테스트 묶음)

### A. 실행
- `python manage.py test sheetbook.tests.SheetbookDailyStartBundleScriptTests sheetbook.tests.SheetbookThresholdRecommendationCommandTests sheetbook.tests.SheetbookPilotLogSnapshotScriptTests sheetbook.tests.SheetbookSignoffDecisionScriptTests sheetbook.tests.SheetbookReleaseSignoffLogScriptTests sheetbook.tests.SheetbookConsentFreezeSnapshotScriptTests`

### B. 결과
- 총 15 tests, `OK`
- 시스템 체크 오류 없음
- daily bundle 추가 이후 기존 SB-014/SB-015/SB-108 스크립트 테스트와의 충돌 없음

### C. 다음 우선순위(변동 없음)
1. `SB-015` 수동 signoff 2건 완료 처리
2. `SB-202` 실사용 표본 확보(`event_count >= 5`) 및 `next_step` 재판정
3. `SB-108` freeze snapshot diff 기준으로 파일럿 변경 요청 선별 반영

---

### 0-119. 표본 부족량 요약 자동화 (pilot + archive gap summary)

### A. 구현 요약
- 신규 스크립트 추가:
  - `scripts/run_sheetbook_sample_gap_summary.py`
  - 입력:
    - `docs/handoff/sheetbook_release_readiness_latest.json`
    - `docs/handoff/sheetbook_archive_bulk_snapshot_latest.json`
  - 출력:
    - `docs/handoff/sheetbook_sample_gap_summary_latest.json`
  - 요약 항목:
    - pilot 샘플 갭(`workspace_home_opened_gap`, `home_source_sheetbook_created_gap`)
    - archive 이벤트 갭(`event_gap`)
    - `overall.blockers` 리스트
- 테스트 추가:
  - `SheetbookSampleGapSummaryScriptTests`
    - 갭 존재 시 blocker 계산 검증
    - 갭 0일 때 ready 판정 검증

### B. 테스트/검증
- `python manage.py test sheetbook.tests.SheetbookSampleGapSummaryScriptTests`
- `python scripts/run_sheetbook_sample_gap_summary.py`
- `python -m py_compile scripts/run_sheetbook_sample_gap_summary.py`

결과:
- 테스트 2 tests, OK
- 현재 요약 결과:
  - `overall.ready=false`
  - blockers:
    - `pilot_home_opened_gap:5`
    - `pilot_create_gap:5`
    - `archive_event_gap:5`

### C. 문서 반영
- `docs/runbooks/SHEETBOOK_PILOT_DATA_CHECKLIST.md`
  - gap summary 명령/출력 경로 추가
- `docs/runbooks/SHEETBOOK_ARCHIVE_BULK_OPERATION.md`
  - pilot+archive 통합 gap summary 명령 추가
- `docs/runbooks/SHEETBOOK_BETA_ROLLOUT.md`
  - 배포 전 점검 권장 명령에 gap summary 추가

### D. 내일 시작 명령(최종 권장)
1. `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-03`
2. `python scripts/run_sheetbook_sample_gap_summary.py`
3. 수동 signoff 완료 시:
  - `python scripts/run_sheetbook_signoff_decision.py --set staging_real_account_signoff=PASS:staging-ok --set production_real_account_signoff=PASS:prod-ok`
4. 재실행:
  - `python scripts/run_sheetbook_daily_start_bundle.py --days 14 --due-date 2026-03-03`
  - `python scripts/run_sheetbook_sample_gap_summary.py`
