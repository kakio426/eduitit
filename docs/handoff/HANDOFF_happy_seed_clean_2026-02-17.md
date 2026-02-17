# HANDOFF: 행복의 씨앗 (Happy Seed)
Status: Official handoff document (approved)

작성일: 2026-02-17  
기준 계획서:
- `docs/plans/PLAN_happy_seed_service.md`
- `docs/plans/PLAN_happy_seed_service_detailed_v1.md`
- `docs/plans/PLAN_happy_seed_service_master_v1.md`

## 1) 현재 완료 상태

### Step A Foundation: 완료
- `happy_seed/__init__.py`
- `happy_seed/apps.py`
- `happy_seed/models.py` (MVP1 8개 + MVP2 6개 + `HSClassEventLog`)
- `happy_seed/admin.py`
- `happy_seed/forms.py`
- `happy_seed/urls.py`
- `happy_seed/views.py` (MVP1 + 확장 FBV)
- `happy_seed/services/__init__.py`
- `happy_seed/services/engine.py`
- `happy_seed/services/analytics.py`

### Step B Templates: 완료
- 메인 템플릿 14개 + partial 8개 작성 완료
- 핵심 레이아웃 가드레일 반영: `pt-32 pb-20 px-4 min-h-screen`
- 신규 화면:
  - `happy_seed/templates/happy_seed/activity_manage.html`
  - `happy_seed/templates/happy_seed/analysis_dashboard.html`
  - `happy_seed/templates/happy_seed/group_manage.html`
  - `happy_seed/templates/happy_seed/teacher_manual.html`

### Step C Integration: 완료
- `config/settings.py`: `happy_seed.apps.HappySeedConfig` 추가
- `config/settings_production.py`: 앱 등록 + startup 경량화(`sync_site_domain()`만 실행)
- `config/urls.py`: `path('happy-seed/', include('happy_seed.urls', namespace='happy_seed'))` 추가
- `products/management/commands/ensure_happy_seed.py` 추가
- `core/management/commands/bootstrap_runtime.py` 추가
- `products/templates/products/partials/preview_modal.html`: `행복의 씨앗` 분기 추가
- `Procfile`: startup을 `python3 manage.py bootstrap_runtime && uvicorn ...`로 통합
- `nixpacks.toml`: startup 명령 동기화

### Step D Migration/Verification: 완료
- `python manage.py makemigrations happy_seed`
- `python manage.py migrate`
- `python manage.py check`
- `python manage.py ensure_happy_seed`
- `python manage.py makemigrations --check`
- 추가 마이그레이션 반영:
  - `happy_seed/migrations/0002_hsprize_win_rate_percent.py`
  - `happy_seed/migrations/0003_hsclasseventlog.py`
  - `happy_seed/migrations/0004_alter_hsclasseventlog_type.py`

## 2) 추가 반영 사항

- 보상별 상대 확률(가중치) 지원
  - `HSPrize.win_rate_percent` 추가
  - 당첨 시 보상 선택은 상대비율 기반 추첨(합계 100 강제 없음)

- 라이브 운영 가드레일 강화
  - 보상 미등록/재고 없음 시 추첨 차단
  - 미동의 학생 추첨 비활성 안내
  - 최근 실행 결과 패널 + 디스플레이 분리

- 동의 연동 강화
  - 서명톡 링크 생성/재발송/동기화
  - 명단 미일치 건은 교사 수동 확인 승인 플로우 추가

- 모둠 UX 확장
  - 모둠 편성 UI(생성/삭제/멤버 저장)
  - 라이브에서 모둠 미션 성공 시 랜덤 1~2명 티켓 지급

- 활동/분석 확장
  - 활동 화면: 성실참여 기본 지급 + 점수 기준 추가 지급 + 점수 없이 수동 추가 지급 체크
  - 분석 화면: 장기 미당첨/편중/정체 알림 + 개입 예약

- 이벤트 로그 표준화
  - `HSClassEventLog` 기반으로 핵심 이벤트 기록
  - 지급/추첨/미당첨씨앗/자동전환/개입/동의 이벤트 추적

- 테스트 보강
  - `happy_seed/tests/test_engine.py`
  - `happy_seed/tests/test_views.py`
  - `happy_seed/tests/test_permissions.py`
  - `happy_seed/tests/test_flow.py`

## 3) 최신 검증 결과

- `python manage.py test happy_seed`
  - 결과: 16 tests, OK
- `python manage.py check`
  - 결과: OK
- `python manage.py makemigrations --check`
  - 결과: No changes detected

## 4) 필수/권장 후속 작업

필수 작업:
- 없음 (MVP1 + 핵심 확장 구현 + 통합 + 검증 완료)

권장 작업:
1. 실운영 시나리오 수동 점검 1회
   - 교사: 생성 -> 학생등록 -> 동의 -> 지급 -> 추첨 -> 축하 닫기
   - 모둠: 편성 -> 모둠 성공 -> 랜덤 1~2명 지급 검증
   - 동의: 서명 동기화 -> 미일치 수동 승인 검증
   - 공개 꽃밭: 비로그인 접근 + 프로젝터 가독성 확인
2. PR 직전 재검증
   - `python manage.py test happy_seed`
   - `python manage.py check`
   - `python manage.py makemigrations --check`

## 5) 주의사항

- 한글 파일은 UTF-8(무 BOM) 유지
- 파이프 기반 재저장(`Get-Content | Set-Content`) 금지
- 한글-heavy 파일은 `apply_patch` 기반 국소 수정만 수행

## 6) 문제 발생 시 롤백 절차 (Runbook)

### A. 코드 롤백(가장 빠른 복구)
1. 배포 중인 브랜치에서 롤백 대상 커밋 확인:
   - `git log --oneline -n 15`
2. 안정 커밋으로 즉시 되돌리기:
   - 예시) `git revert --no-edit 8fc5692` (deploy 최적화 롤백)
3. 푸시 후 재배포:
   - `git push origin main`
4. 스모크 체크:
   - `python manage.py check`
   - `python manage.py bootstrap_runtime`
   - `/happy-seed/`, `/happy-seed/dashboard/`, `/happy-seed/garden/<slug>/` 접속 확인

### B. DB/마이그레이션 이슈 롤백
1. 현재 마이그레이션 상태 확인:
   - `python manage.py showmigrations happy_seed`
2. 문제 마이그레이션 직전으로 다운:
   - `python manage.py migrate happy_seed <이전_마이그레이션>`
3. 코드도 동일 시점으로 맞춘 뒤 재배포(코드/스키마 불일치 방지)

### C. 운영 안전 수칙
- `git reset --hard` 사용 금지
- 롤백은 `revert` 우선(이력 보존)
- 롤백 커밋 생성 후 반드시 최소 스모크 체크 수행

## 7) 추가 개발 재개 절차 (Forward Path)

1. 기준점 확보:
   - `git pull origin main`
   - `python manage.py check`
   - `python manage.py test happy_seed`
2. 작업 브랜치 생성:
   - `git checkout -b feat/happy-seed-<작업명>`
3. 구현 우선순위(권장):
   - 1) MVP2 기능(카테고리/분석/개입로그/균형모드 고도화)
   - 2) 운영 안정화(에러 핸들링/관측성/관리자 알림)
   - 3) UX 다듬기(교실 프로젝터 가독성/저자극 모드)
4. 완료 체크리스트:
   - `python manage.py makemigrations --check`
   - `python manage.py test happy_seed`
   - `python manage.py check`
5. 병합 전 handoff/plan 동기화:
   - 변경된 엔드포인트, 모델, 운영명령(`bootstrap_runtime`) 반영

## 8) 현재 기준 커밋(참조)

- 기능 통합 기준: `e53e9a6`
- 배포 최적화 기준: `8fc5692`
- 기능 확장(설명서/보상가중치/서명연동): `e7a4198`
- 기능 확장(라이브가드/모둠/동의수동승인/활동수동보너스): `83fcf73`
