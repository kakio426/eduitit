# 행복의 씨앗 (Seeds of Happiness) - Implementation Plan

## Context

PRD v1.0에 기반한 초등학교 교실용 긍정행동 강화 시스템. 교사가 학생의 긍정적 행동에 씨앗/블룸 티켓을 부여하고, 랜덤 추첨(꽃피움)을 통해 보상을 제공. "빈 정원 -> 1년 후 꽃밭" 공개 대시보드로 학급 공동체 성장을 시각화.

핵심 원칙: 긍정행동 강화만 사용(벌점 금지), 모든 보상은 랜덤 1회 구조, 교사 자율성 존중, 확률은 학생 비공개.

비범위 고정: 학부모 리포트/포털 없음, 벌점/확률 하락/자동 처벌 없음, 문제행동 즉시 보상 없음.

기준 문서: `CLAUDE.md`, `SERVICE_INTEGRATION_STANDARD.md`, `codex/SKILL.md`, `docs/plans/PLAN_happy_seed_service.md`

---

## App SSOT

- 앱 디렉토리명: `happy_seed`
- Product title(고정): `행복의 씨앗`
- URL namespace: `happy_seed`
- 진입 URL: `/happy-seed/`
- 모델 prefix: `HS` (`HSClassroom`, `HSStudent` 등)
- 서비스 성격: 교실 운영형(교사 주도), 학생 공개 대시보드 포함

---

## 1. Data Models (`happy_seed/models.py`)

### MVP1 Models (8개)

### HSClassroom - 교실(학급)
- id UUIDField PK
- teacher FK(User) - 소유 교사
- name CharField(100) - "6학년 1반"
- school_name CharField(100, blank) - 학교명
- slug SlugField(unique) - 공개 정원 URL용 (auto 8-char hex)
- is_active BoolField(default=True)
- created_at, updated_at

### HSClassroomConfig - 교실 설정 (Classroom과 분리)
- OneToOne(HSClassroom)
- seeds_per_bloom IntField(default=10) - 블룸 전환 기준 N
- base_win_rate IntField(default=5) - 기본 당첨 확률(%)
- group_draw_count IntField(default=1) - 모둠 성공 시 랜덤 인원수
- balance_mode_enabled BoolField(default=False) - 따뜻한 균형 모드
- balance_epsilon FloatField(default=0.05) - 보정 계수
- balance_lookback_days IntField(default=30) - 보정 기간
- updated_at

### HSStudent - 학생
- id UUIDField PK
- classroom FK(HSClassroom)
- name CharField(50)
- number IntField(default=0) - 번호
- seed_count IntField(default=0) - 현재 씨앗 (비정규화)
- ticket_count IntField(default=0) - 현재 보유 티켓 수 (비정규화)
- total_wins IntField(default=0) - 총 당첨 횟수
- pending_forced_win BoolField(default=False) - 다음 회 강제 당첨 예약
- is_active BoolField(default=True)
- created_at, updated_at
- unique_together: (classroom, number)

### HSGuardianConsent - 보호자 동의 상태
- OneToOne(HSStudent)
- status CharField: pending/approved/rejected/expired/withdrawn
- external_url URLField(blank) - 외부 전자서명 링크
- note TextField(blank)
- requested_at DateTimeField(null, blank) - 동의 요청 시각
- completed_at DateTimeField(null, blank) - 동의 완료 시각
- updated_at
- 규칙: 미동의 학생은 기록 저장/보상 지급 불가, 동의 철회 시 즉시 비활성

### HSPrize - 당첨 보상
- id UUIDField PK
- classroom FK(HSClassroom)
- name CharField(200)
- description TextField(blank)
- total_quantity IntField(null, blank) - null=무제한
- remaining_quantity IntField(null, blank)
- is_active BoolField(default=True)
- display_order IntField(default=0)
- property is_available: total_quantity is None or remaining > 0
- 동시 추첨 음수 방지: 재고 차감 시 `HSPrize.objects.filter(id=prize.id, remaining_quantity__gt=0).update(remaining_quantity=F('remaining_quantity')-1)` 조건부 업데이트 사용. 반환값 0이면 재고 소진으로 간주하고 다른 Prize 재선택

### HSTicketLedger - 꽃피움 티켓 원장
- id UUIDField PK
- student FK(HSStudent)
- source CharField: participation/achievement/seed_accumulation/group_draw/teacher_grant
- amount IntField - 양수=부여, 음수=사용
- detail CharField(200, blank)
- balance_after IntField - 변동 후 잔액
- request_id UUIDField(default=uuid4) - 멱등성 보장 키
- created_at
- unique_together: (student, request_id) - DB 레벨 멱등성 강제

### HSSeedLedger - 씨앗 원장
- id UUIDField PK
- student FK(HSStudent)
- amount IntField - 양수=추가, 음수=차감
- reason CharField: no_win/behavior/recovery/bloom_convert/teacher_grant
- detail CharField(200, blank)
- balance_after IntField
- request_id UUIDField(default=uuid4) - 멱등성 보장 키
- created_at
- unique_together: (student, request_id) - DB 레벨 멱등성 강제

### HSBloomDraw - 추첨 결과 로그
- id UUIDField PK
- student FK(HSStudent)
- is_win BoolField
- prize FK(HSPrize, null, blank)
- input_probability DecimalField(max_digits=5, decimal_places=2) - 투입 확률(%)
- balance_adjustment DecimalField(max_digits=5, decimal_places=4, default=0) - 균형모드 보정값(ε)
- effective_probability DecimalField(max_digits=5, decimal_places=2) - 최종 적용 확률(%)
- is_forced BoolField(default=False) - 교사 개입 여부
- force_reason CharField(200, blank)
- request_id UUIDField(default=uuid4, unique=True) - 멱등성 DB 레벨 강제
- celebration_token UUIDField(default=uuid4, unique=True) - 축하 화면 접근 토큰
- celebration_closed BoolField(default=False) - 교사 닫기 여부
- drawn_at DateTimeField(auto_now_add=True)
- created_by FK(User, null) - 실행 교사

### MVP2 Models (6개)

### HSBehaviorCategory - 행동 카테고리
- classroom FK(HSClassroom)
- code CharField(20)
- name CharField(50) - 기본 5종: 질문/협력/도전/배려/회복
- icon CharField(10, default='🌱')
- seeds_reward IntField(default=1)
- is_active, display_order
- unique_together: (classroom, code)

### HSBehaviorLog - 행동 기록
- student FK(HSStudent), category FK(HSBehaviorCategory, null)
- note, seeds_awarded, created_at, created_by FK(User, null)

### HSActivity - 활동 (시험/과제)
- classroom FK(HSClassroom)
- title, description, threshold_score(default=80), extra_bloom_count(default=1)

### HSActivityScore - 활동 점수
- activity FK(HSActivity), student FK(HSStudent)
- score, bloom_granted BoolField
- unique_together: (activity, student)

### HSStudentGroup - 모둠
- classroom FK(HSClassroom), name, members M2M(HSStudent)

### HSInterventionLog - 교사 개입 로그 (학생 비공개)
- id UUIDField PK
- classroom FK(HSClassroom), student FK(HSStudent)
- action: forced_win_immediate/forced_win_next/seed_grant/seed_deduct
- detail TextField(blank) - 사유 (선택 입력)
- created_by FK(User), created_at

---

## 2. Business Logic (`happy_seed/services/engine.py`)

### execute_bloom_draw(student, classroom, created_by, request_id=None)

1. 멱등성 체크: request_id로 기존 결과 조회, 있으면 재반환
2. 트랜잭션: select_for_update로 student row lock
3. 티켓 차감: student.ticket_count -= 1 (선차감)
4. 강제 당첨 체크: student.pending_forced_win == True -> 무조건 당첨, 플래그 해제
5. 확률 계산: base_win_rate + 균형모드 보정 (epsilon 적용)
6. RNG: 서버측 random.randint(1, 100) <= effective_rate
7. 당첨 시: 활성+잔여 있는 Prize 중 랜덤 선택, 재고 차감
8. 미당첨 시: add_seeds(student, 1, 'no_win') (규칙 C)
9. 로그 기록: HSBloomDraw (input_probability, balance_adjustment, effective_probability, is_forced)
10. 원장 기록: HSTicketLedger (amount=-1)
11. 단일 DB 트랜잭션으로 모든 변경 원자적 처리

### add_seeds(student, amount, reason, detail, request_id=None)

1. 멱등성 체크
2. student.seed_count += amount
3. HSSeedLedger 생성
4. while seed_count >= seeds_per_bloom: 자동 전환 -> HSTicketLedger + HSSeedLedger(bloom_convert) + ticket_count +1 + seed_count 차감
5. student.save()

### grant_tickets(student, source, amount, detail, request_id=None)

1. 멱등성 체크
2. 동의 확인: 미동의 학생 -> 에러
3. student.ticket_count += amount
4. HSTicketLedger 생성
5. student.save()

### get_garden_data(classroom)

1. 활성+동의완료 학생 목록 조회
2. 학생별 seed_count / seeds_per_bloom stage 계산 (seed/sprout/bud/bloom)
3. student.id 해시 기반 고정 micro-offset (10px) 계산
4. 꽃 데이터 리스트 반환

### 균형모드 보정 (get_effective_win_rate)

- 기본 확률 고정(Base)
- ON 시: lookback_days 내 학생별 누적 당첨 횟수 기반
- 당첨 적은 학생: rate + base * epsilon (소폭 증가)
- 당첨 많은 학생: rate - base * epsilon (소폭 감소)
- 최종 확률은 base ± (base * epsilon) 범위 제한

---

## 3. URL Structure (`happy_seed/urls.py`)

- happy-seed/ -> landing (공개)
- happy-seed/dashboard/ -> dashboard (교사 교실 목록)
- happy-seed/classroom/create/ -> classroom_create
- happy-seed/<uuid>/ -> classroom_detail (메인 관리)
- happy-seed/<uuid>/settings/ -> classroom_settings
- happy-seed/<uuid>/students/add/ -> student_add (HTMX POST)
- happy-seed/<uuid>/students/bulk-add/ -> student_bulk_add
- happy-seed/<uuid>/consent/ -> consent_manage
- happy-seed/<uuid>/bloom/grant/ -> bloom_grant (POST)
- happy-seed/<uuid>/bloom/run/ -> bloom_run (추첨 실행 화면)
- happy-seed/<uuid>/prizes/ -> prize_manage
- happy-seed/student/<uuid>/edit/ -> student_edit (HTMX POST)
- happy-seed/student/<uuid>/seed/grant/ -> seed_grant (POST)
- happy-seed/student/<uuid>/consent/update/ -> consent_update (HTMX POST)
- happy-seed/draw/<uuid>/execute/ -> bloom_draw (POST - 실제 추첨)
- happy-seed/draw/<uuid>/celebrate/ -> celebration (축하 화면)
- happy-seed/draw/<uuid>/close/ -> close_celebration (POST - 교사 닫기)
- happy-seed/garden/<slug>/ -> garden_public (공개 꽃밭, 로그인 불필요)
- happy-seed/<uuid>/partials/student-grid/ -> HTMX partial
- happy-seed/<uuid>/partials/garden/ -> HTMX partial
- happy-seed/student/<uuid>/partials/tooltip/ -> HTMX partial

---

## 4. Views (`happy_seed/views.py`)

모든 view는 FBV + 데코레이터 패턴. 교사 소유권 검증 헬퍼:

```python
def get_teacher_classroom(request, classroom_id):
    return get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user, is_active=True)
```

MVP1 Views (21개):

- landing (GET, 공개)
- dashboard (GET, login)
- classroom_create (GET/POST, login)
- classroom_detail (GET, login)
- classroom_settings (GET/POST, login)
- student_add (POST, login)
- student_bulk_add (GET/POST, login)
- student_edit (POST, login)
- consent_manage (GET, login)
- consent_update (POST, login)
- bloom_grant (POST, login)
- bloom_run (GET, login)
- bloom_draw (POST, login)
- prize_manage (GET/POST, login)
- seed_grant (POST, login)
- garden_public (GET, 공개)
- celebration (GET, token 검증)
- close_celebration (POST, login)
- student_grid_partial (GET, login)
- garden_partial (GET, 공개)
- student_tooltip_partial (GET, 공개)

---

## 5. Templates (`happy_seed/templates/happy_seed/`)

- landing.html
- dashboard.html
- classroom_detail.html
- classroom_form.html
- classroom_settings.html
- student_bulk_add.html
- consent_manage.html
- prize_manage.html
- bloom_run.html
- garden_public.html
- celebration.html

partials/
- student_grid.html
- student_row.html
- student_tooltip.html
- garden_flowers.html
- bloom_result.html
- consent_row.html
- prize_row.html
- seed_badge.html

축하 화면 핵심 스펙:
- 접근 정책: `celebration_token` 쿼리 검증 (`/happy-seed/draw/<draw_id>/celebrate/?token=<uuid>`)
- 토큰 없거나 불일치 시 403
- close 시 토큰 무효화
- 3~5초 애니메이션
- 교사만 닫기 버튼 (POST)
- 자동 종료 금지
- 미당첨 문구: "이번엔 씨앗이 자랐어요. 다음 꽃피움을 준비했어요."

꽃밭 시각화:
- Grid + 고정 micro-offset
- 0-2: 🌰, 3-6: 🌱, 7-9: 🌿, 10: 🌸
- 이름 소형 표시 + HTMX 툴팁
- 서열/랭킹/배지 미제공

접근성:
- 본문 >= 20px, 핵심 수치 >= 28px
- 터치 타깃 >= 44x44
- WCAG AA 권장
- `prefers-reduced-motion` 대응

---

## 6. Integration Checklist

수정 파일:
- config/settings.py
- config/settings_production.py
- config/urls.py
- products/templates/products/partials/preview_modal.html
- Procfile
- nixpacks.toml

신규:
- products/management/commands/ensure_happy_seed.py

ensure_happy_seed 스펙:
- Product: title='행복의 씨앗', icon='🌱', color_theme='green', service_type='classroom'
- ProductFeature 3개
- ServiceManual + ManualSection 3개 이상

---

## 7. 상태 전이/원자성 규칙

- 성실참여: ticket_count +1
- 우수성취: ticket_count +N
- 추첨: 선차감 -> 당첨/미당첨 처리
- 미당첨: seed_count +1, N 도달 시 ticket_count +1
- 다음 회 개입: pending_forced_win=True
- 멱등키(request_id), 단일 트랜잭션, row lock
- 서버측 RNG만 사용

---

## 8. 동의/데이터 수명주기

- 미동의: 지급/기록 불가
- 철회: 즉시 비활성
- 재동의: 교사 승인 후 재활성
- 요청/완료 시각 감사 기록
- 학년 종료 일괄 삭제 옵션
- 계정 삭제 시 연계 데이터 파기 옵션

---

## 9. 권한 경계 매트릭스

- 교사: 본인 반 운영/조회
- 학생: 공개 꽃밭/본인 진행도
- 보호자(서명 링크): 동의 제출
- 비로그인: 공개 페이지 열람만

---

## 10. MVP1 구현 순서

A. Foundation (1-8)  
B. Integration (9-10)  
C. Classroom + Student CRUD (11-16)  
D. Bloom/Seed Core Mechanics (17-22)  
E. Public Garden + Celebration (23-27)  
F. Landing + Verification (28-29)

---

## 11. Verification Plan

1. `python manage.py check`
2. `python manage.py makemigrations --check`
3. JS 변경 시 `node --check`
4. CRUD/교사 플로우/미당첨+1/씨앗전환/공개꽃밭/축하화면/라우팅 검증
5. 타 교사 404, 미동의 차단, request_id 멱등 검증

DoD:
- MVP-1 범위 기능 동작
- 학생 화면에 확률/개입 비공개
- 씨앗은 기회(티켓) 전환만
- 축하 화면 수동 종료
- 서비스 카드 정상 진입

---

## 12. 신규/수정 파일 전체 목록

신규:
- happy_seed/__init__.py
- happy_seed/apps.py
- happy_seed/models.py
- happy_seed/views.py
- happy_seed/urls.py
- happy_seed/admin.py
- happy_seed/forms.py
- happy_seed/services/__init__.py
- happy_seed/services/engine.py
- happy_seed/services/analytics.py
- happy_seed/templates/happy_seed/*.html
- happy_seed/static/happy_seed/
- happy_seed/tests/test_engine.py
- happy_seed/tests/test_views.py
- happy_seed/tests/test_permissions.py
- products/management/commands/ensure_happy_seed.py

수정:
- config/settings.py
- config/settings_production.py
- config/urls.py
- products/templates/products/partials/preview_modal.html
- Procfile
- nixpacks.toml
