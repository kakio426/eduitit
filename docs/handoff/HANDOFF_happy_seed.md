# 행복의 씨앗 (Happy Seed) - Handoff Document

**작성일**: 2026-02-17
**기준 문서**: `docs/plans/PLAN_happy_seed_service.md`

---

## 1. 현재 진행 상태

### 완료된 작업 (Step A: Foundation)

| # | 파일 | 상태 | 비고 |
|---|------|------|------|
| 1 | `happy_seed/__init__.py` | ✅ 완료 | |
| 2 | `happy_seed/apps.py` | ✅ 완료 | `HappySeedConfig`, verbose_name='행복의 씨앗' |
| 3 | `happy_seed/models.py` | ✅ 완료 | MVP1 8개 + MVP2 6개 = 총 14개 모델 |
| 4 | `happy_seed/admin.py` | ✅ 완료 | select_related, annotate, raw_id_fields 적용 |
| 5 | `happy_seed/forms.py` | ✅ 완료 | HSClassroomForm, HSClassroomConfigForm, HSStudentForm, HSPrizeForm, StudentBulkAddForm |
| 6 | `happy_seed/urls.py` | ✅ 완료 | app_name='happy_seed', 전체 URL 패턴 등록 |
| 7 | `happy_seed/views.py` | ✅ 완료 | 21개 MVP1 FBV 모두 작성 |
| 8 | `happy_seed/services/__init__.py` | ✅ 완료 | |
| 9 | `happy_seed/services/engine.py` | ✅ 완료 | execute_bloom_draw, add_seeds, grant_tickets, get_garden_data, 균형모드 보정 |
| 10 | `happy_seed/services/analytics.py` | ✅ 완료 | MVP2 placeholder |
| 11 | `happy_seed/tests/__init__.py` | ✅ 완료 | |

### 미완료 작업

#### Step B: Templates (진행 중 - 2개만 생성됨)

생성된 템플릿:
- `happy_seed/templates/happy_seed/landing.html` - ⚠️ 내용 미확인 (빈 파일일 수 있음)
- `happy_seed/templates/happy_seed/dashboard.html` - ⚠️ 내용 미확인

**아직 생성되지 않은 템플릿 (17개)**:

메인 템플릿 (9개):
- `classroom_detail.html` - 메인 관리 화면 (학생 그리드 + 블룸 + 씨앗)
- `classroom_form.html` - 교실 생성/수정 폼
- `classroom_settings.html` - 교실 설정
- `student_bulk_add.html` - 학생 일괄 추가
- `consent_manage.html` - 동의 상태 관리
- `prize_manage.html` - 보상 관리
- `bloom_run.html` - 추첨 실행 화면
- `garden_public.html` - 공개 꽃밭 (로그인 불필요)
- `celebration.html` - 축하 화면 (fullscreen, 교사만 닫기)

Partial 템플릿 (8개):
- `partials/student_grid.html`
- `partials/student_row.html`
- `partials/student_tooltip.html`
- `partials/garden_flowers.html`
- `partials/bloom_result.html`
- `partials/consent_row.html`
- `partials/prize_row.html`
- `partials/seed_badge.html`

#### Step C: Integration (미시작)

| 파일 | 작업 | 상태 |
|------|------|------|
| `config/settings.py` | INSTALLED_APPS에 `'happy_seed.apps.HappySeedConfig'` 추가 | ❌ |
| `config/settings_production.py` | INSTALLED_APPS + `run_startup_tasks()`에 `call_command('ensure_happy_seed')` 추가 | ❌ |
| `config/urls.py` | `path('happy-seed/', include('happy_seed.urls', namespace='happy_seed'))` | ❌ |
| `products/management/commands/ensure_happy_seed.py` | Product + Feature 3개 + ServiceManual + ManualSection 3개 | ❌ |
| `products/templates/products/partials/preview_modal.html` | `행복의 씨앗` URL 분기 추가 | ❌ |
| `Procfile` | `ensure_happy_seed` 추가 | ❌ |
| `nixpacks.toml` | Procfile과 동기화 | ❌ |

#### Step D: Migration & Verification (미시작)

- `python manage.py makemigrations happy_seed`
- `python manage.py migrate`
- `python manage.py check`

---

## 2. 모델 구조 요약 (models.py에 작성 완료)

### MVP1 (8개)
1. **HSClassroom** - UUID PK, teacher FK, name, school_name, slug(auto 8-char hex), is_active
2. **HSClassroomConfig** - OneToOne(HSClassroom), seeds_per_bloom=10, base_win_rate=5, balance_mode, epsilon, lookback
3. **HSStudent** - UUID PK, classroom FK, name, number, seed_count, ticket_count, total_wins, pending_forced_win
4. **HSGuardianConsent** - OneToOne(HSStudent), status(pending/approved/rejected/expired/withdrawn)
5. **HSPrize** - UUID PK, classroom FK, name, total_quantity(null=무제한), remaining_quantity, is_available property
6. **HSTicketLedger** - UUID PK, student FK, source, amount, balance_after, request_id (멱등성)
7. **HSSeedLedger** - UUID PK, student FK, amount, reason, balance_after, request_id (멱등성)
8. **HSBloomDraw** - UUID PK, student FK, is_win, prize FK, probabilities, celebration_token, request_id

### MVP2 (6개) - 모델만 정의, 뷰/템플릿 미구현
9. HSBehaviorCategory
10. HSBehaviorLog
11. HSActivity
12. HSActivityScore
13. HSStudentGroup
14. HSInterventionLog

---

## 3. 비즈니스 로직 (engine.py에 작성 완료)

| 함수 | 역할 | 핵심 |
|------|------|------|
| `execute_bloom_draw()` | 추첨 실행 | 멱등키, select_for_update, 강제 당첨, 균형모드, Prize 재고 차감 |
| `add_seeds()` | 씨앗 부여 | 멱등키, 자동 블룸 전환 (seed_count >= seeds_per_bloom) |
| `grant_tickets()` | 티켓 부여 | 동의 확인, 멱등키 |
| `get_garden_data()` | 꽃밭 데이터 | 4단계(seed/sprout/bud/bloom), 해시 기반 micro-offset |
| `get_effective_win_rate()` | 확률 계산 | 균형모드 보정 포함 |

---

## 4. 작성 완료된 View 함수 (views.py)

총 21개 FBV 모두 작성 완료:
- `landing`, `dashboard`
- `classroom_create`, `classroom_detail`, `classroom_settings`
- `student_add`, `student_bulk_add`, `student_edit`
- `consent_manage`, `consent_update`
- `prize_manage`
- `bloom_grant`, `bloom_run`, `bloom_draw`
- `seed_grant`
- `celebration`, `close_celebration`
- `garden_public`
- `student_grid_partial`, `garden_partial`, `student_tooltip_partial`

---

## 5. 다음 세션에서 이어할 작업 순서

### 즉시 실행 (순서대로)

1. **템플릿 17개 생성** (위 미완료 목록 참조)
   - 핵심 스펙: `extends 'base.html'`, `pt-32 pb-20 px-6 min-h-screen`, `.clay-card`, HTMX partial 패턴
   - 축하 화면: CSS @keyframes confetti/sparkle, 교사만 닫기 POST 버튼, 철학 문구
   - 꽃밭: CSS Grid + micro-offset, 4단계 아이콘(🌰🌱🌿🌸), `prefers-reduced-motion` 대응
   - 접근성: 프로젝터 본문 >= 20px, 터치 44x44px, WCAG AA 색 대비

2. **Integration 파일 수정** (위 Step C 표 참조)
   - `ensure_happy_seed.py` 패턴: `ensure_version_manager.py` 참조 (get_or_create + ServiceManual + ManualSection)
   - `preview_modal.html` 라인 86: `{% elif product.title == '행복의 씨앗' %}{% url 'happy_seed:landing' %}` 추가
   - settings INSTALLED_APPS: `'happy_seed.apps.HappySeedConfig'` (reservations 다음)
   - settings_production run_startup_tasks: `call_command('ensure_happy_seed')` 추가

3. **Migration 실행**
   ```bash
   cd /c/Users/kakio/eduitit
   python manage.py makemigrations happy_seed
   python manage.py migrate
   python manage.py check
   ```

4. **검증** (Plan §11 Verification Plan 참조)

---

## 6. 참조해야 할 기존 파일

| 용도 | 파일 경로 |
|------|-----------|
| 템플릿 extends 패턴 | `reservations/templates/reservations/landing.html` (extends 'base.html', pt-32) |
| ensure 명령 패턴 | `products/management/commands/ensure_version_manager.py` (ServiceManual+ManualSection) |
| preview_modal 분기 | `products/templates/products/partials/preview_modal.html` 라인 86 |
| settings INSTALLED_APPS | `config/settings.py` 라인 54-92 |
| settings_production startup | `config/settings_production.py` 라인 489-504 |
| Procfile | 프로젝트 루트 `Procfile` |
| nixpacks | 프로젝트 루트 `nixpacks.toml` |
| 원본 계획 | `docs/plans/PLAN_happy_seed_service.md` |

---

## 7. 주의사항

- **한글 인코딩**: 넓은 범위 치환 금지, 국소 수정 우선 (CLAUDE.md §2)
- **ensure 명령**: `get_or_create` 필수, `delete()+create()` 금지 (CLAUDE.md §31)
- **Admin 필드 보존**: ensure에서 service_type/display_order 강제 덮어쓰기 금지 (CLAUDE.md §30)
- **HTMX 중복 로드 금지**: base.html에서만 로드 (CLAUDE.md §43.1)
- **Alpine.js CDN**: `cdn.jsdelivr.net/npm/alpinejs@3` 사용 (MEMORY.md)
- **Django 템플릿 태그 줄바꿈 금지**: `{% if %}` 등은 한 줄로 (CLAUDE.md §25, §44)
## [Canonical Completion Update] 2026-02-17

이 블록은 현재 실제 완료 상태를 우선 기준으로 사용한다.
아래 레거시 본문(깨진 텍스트 포함)과 충돌 시 이 블록을 따른다.

### 완료 상태 요약

- Step A Foundation: 완료
  - `happy_seed/models.py` (MVP1 8개 + MVP2 6개)
  - `happy_seed/views.py` (MVP1 21개 FBV)
  - `happy_seed/urls.py`
  - `happy_seed/forms.py`
  - `happy_seed/admin.py`
  - `happy_seed/services/engine.py`
  - `happy_seed/services/analytics.py`
- Step B Templates: 완료
  - 메인 템플릿 11개 + partial 8개 구성 완료
  - 핵심 레이아웃 가드레일 `pt-32 pb-20 px-4 min-h-screen` 적용
- Step C Integration: 완료
  - `config/settings.py` 앱 등록 완료
  - `config/settings_production.py` 앱 등록 + `run_startup_tasks()`에 `call_command('ensure_happy_seed')` 반영
  - `config/urls.py`에 `path('happy-seed/', include(...))` 반영
  - `products/management/commands/ensure_happy_seed.py` 추가
  - `products/templates/products/partials/preview_modal.html` 라우팅 분기 반영
  - `Procfile`/`nixpacks.toml`에 `ensure_happy_seed` 동기화
- Step D Migration/Verification: 완료
  - `python manage.py makemigrations happy_seed`
  - `python manage.py migrate`
  - `python manage.py check`
  - `python manage.py ensure_happy_seed`
  - `python manage.py makemigrations --check` (No changes)

### 추가 반영된 안정화 사항

- 축하 화면 토큰 보안 흐름 반영:
  - 추첨 후 축하 URL에 `?token=` 포함 이동
  - 닫기 시 토큰 무효화
  - 관련 파일: `happy_seed/views.py`
- 테스트 보강:
  - `happy_seed/tests/test_engine.py`
  - `happy_seed/tests/test_views.py`
  - `happy_seed/tests/test_permissions.py`
  - `happy_seed/tests/test_flow.py`
  - 현재 `happy_seed` 테스트 통과 (9 tests)

### 추가로 필요한지 점검한 결과

- 필수 추가 작업: 없음 (MVP1 구현/통합/검증 완료)
- 권장 후속 작업:
  1. 레거시 문서/템플릿의 한글 깨짐 텍스트 정리
  2. 실제 교실 디스플레이(프로젝터)에서 폰트/가독성 수동 점검 1회
  3. PR 전 최종 명령 재실행:
     - `python manage.py test happy_seed`
     - `python manage.py check`
     - `python manage.py makemigrations --check`
> LEGACY NOTE: This file is retained for history.
> Use the official handoff: `docs/handoff/HANDOFF_happy_seed_clean_2026-02-17.md`
