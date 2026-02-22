## [Canonical Top Summary] 2026-02-17
- Declare UI scope before edits: global/app/page
- Declare `target_app` and `do_not_touch_apps` before edits
- Preserve stable service UI language by default
- Validate behavior parity first (routing, modal close, ESC, focus)
- If Korean text is corrupted: recover encoding/text first, then re-apply feature/style changes
- Run python manage.py check (and node --check for changed JS)
- For changed JS, do a runtime smoke test (load page + click core tabs/buttons once) and confirm browser console has zero `ReferenceError`
- For user-triggered `fetch` actions, never use empty `catch`; enforce `response.ok` check and show failure feedback (toast/alert)
- For form pages: never hide required model fields without making them optional/defaulted, and always render form errors
- For JS confirmation UX (modal/step): keep a non-JS submit fallback so critical actions never become "no response"
- In dirty workspace, commit only request-scoped files after `git diff --cached` review
- Do not change global settings/flags unless explicitly requested

---

## [운영 기준] 2026-02-17 (최신 규칙 — 충돌 시 이 섹션 우선)

### 1) UI 변경 원칙
- 변경 시작 전에 범위를 명시한다: `global` / `app-level` / `single-page`.
- 범위 외 변경(특히 공용 레이아웃/공용 스크립트)은 금지한다.
- 기존 서비스가 정상 동작하면 시각 통일보다 동작 안정성을 우선한다.

### 2) 한국어 인코딩 사고 방지
- 한글 이상 징후 발견 시: 기능 수정 중단 → 텍스트 복구 → 기능 재적용 순서 고정
- 대량 치환보다 `apply_patch` 기반의 국소 수정 우선
- 정책 변경 시 `CLAUDE.md`, `SERVICE_INTEGRATION_STANDARD.md`, `codex/SKILL.md` 동시 반영

### 2-1) Cloudinary 런타임 점검 규칙 (2026-02-19)
- `USE_CLOUDINARY`는 환경변수로 직접 넣지 않는다. 런타임에서 자동 계산된다.
  - 계산 기준: `CLOUDINARY_CLOUD_NAME` + `CLOUDINARY_API_KEY` 존재 여부
- 운영 장애 진단 시 서버 시작 로그에서 확인:
  - `CLOUDINARY_URL: SET/[X]`
  - `CLOUDINARY_API_KEY: xxxx.../[X]`
  - `USE_CLOUDINARY = True/False`
- 서비스별 파일 저장 규칙:
  - 이미지 외 문서(PDF/HWP/XLSX/ZIP)는 `RawMediaCloudinaryStorage` 사용
  - 문서 공개 링크는 가능하면 URL 기반 응답을 우선 사용
- 동의서(Consent) 운영 점검: `python manage.py check_consent_files --only-missing`

### 2-2) Cloudinary 파일 프록시 규칙 (2026-02-21)
- **CDN URL (`res.cloudinary.com`) 직접 접근은 신뢰하지 않는다.**
  - Strict Transformations 등 보안 설정에 따라 공개 파일도 401을 반환할 수 있다.
- **파일 프록시는 `private_download_url` (Admin API) 방식을 1순위로 사용한다.**
  - `cloudinary.utils.private_download_url(public_id, "", resource_type=rt, type=dt)`
  - api_key + api_secret으로 직접 인증 → CDN 보안 설정과 무관하게 항상 작동
- **resource_type은 `file_field.url`에서 파싱한다.**
  - URL 형식: `https://res.cloudinary.com/{cloud}/{resource_type}/{delivery_type}/...`
  - 확장자 없는 파일은 `image`로 저장될 수 있음 (PDF 포함)
  - `private_download_url` 호출 시 `image`, `raw` 순으로 시도
- **브라우저 리다이렉트(302) 방식은 CORS 문제로 PDF.js에서 실패한다.**
  - Django 서버가 파일을 가져와 `StreamingHttpResponse`로 same-origin 응답해야 한다.
- 구현 위치: `consent/views.py` → `_iter_remote_file_urls()`

### 3) 서비스 진화 시 점검 체크리스트
- 대시보드 진입 / 모달 열기·닫기(배경 클릭, ESC) / 서비스 라우팅 회귀 점검
- 신규 기능은 "기능 정확성 → 사용성 → 시각 개선" 순서로 적용한다.
- 삭제가 필요한 변경은 사용자 승인 후에만 수행한다.

### 4) 폼/모달 안정성 가드레일
- ModelForm에 포함된 필드를 템플릿에서 숨길 경우: `required=False` + 서버 기본값 or 명시적 노출
- POST 폼은 유효성 실패 시 오류를 반드시 노출한다 (`form.errors`, `non_field_errors`)
- 확인 모달/2단계 UX라도 최종 실행은 서버 제출 기반으로 유지한다
- JS 확인 UX에는 `noscript` 또는 직접 제출 폴백을 반드시 제공한다

### 5) 신규 서비스 추가 가드레일
- 라우팅 SSOT를 먼저 정한다. 가능하면 `title` 문자열 분기 대신 명시적 route 필드를 사용한다.
- `title` 분기를 유지해야 한다면 최소 2곳을 동시 반영:
  - `core/views.py` (`_resolve_product_launch_url`)
  - `products/templates/products/partials/preview_modal.html`
- 대화면 전용 서비스는 phone 차단 + 롤백 플래그(`ALLOW_TABLET_ACCESS`) + 우회 경로(`force_desktop=1`) 제공
- 기능 플래그는 목적별로 분리한다 (공통 기능을 화면 플래그에 묶지 않기)
- 모바일/태블릿에서 핵심 액션은 hover 의존 금지
- 신규 서비스는 등록과 동시에 `search_products_json`에 노출 가능해야 한다
- 테스트 게이트: 서비스 진입 라우팅 / 모달 열기·닫기 / phone·iPad·desktop 정책 / 플래그 ON·OFF 동작
- 문서 동기화: `CLAUDE.md` + `codex/SKILL.md` 같은 커밋에서 처리

### 6) Target Service Lock
- 작업 시작 전 선언: `target_app` + `do_not_touch_apps`
- 선언 범위 밖 파일 수정이 감지되면 즉시 중단하고 범위 재확인
- 공용 파일(`settings`, `base`, 공통 템플릿) 수정은 "요청 명시"가 있는 경우에만 허용

### 7) 서비스 제거 표준 절차
1. 라우팅 제거 (`urls`)
2. 앱 등록 제거 (`INSTALLED_APPS`)
3. 제품/매뉴얼 데이터 제거 (마이그레이션 `RunPython`)
4. 설정/가이드/설명 흔적 제거
5. 상태 검증 (`/service-path → 404`, 관련 헬스체크 통과)
- 데이터 제거는 셸 수작업 대신 마이그레이션으로 남긴다.

### 8) AI Provider Switch Protocol
- Gemini/DeepSeek 전환 시 동시 점검:
  - 서버 키 소스(`MASTER_*`, fallback 포함)
  - 사용자 메시지(한도/설정 안내 문구)
  - 설정 화면의 키 입력/가이드 문구
  - 관련 테스트(기본 진입/오류 코드/미설정 처리)
- 제공자 전환 중에는 다른 서비스의 AI 경로를 변경하지 않는다.

### 9) Dirty Workspace Commit Guard
- 작업트리가 더러우면 선택 커밋만 허용:
  - `git add <요청 범위 파일들>` → `git diff --cached --name-only` → `git diff --cached`
- 위 검토 없이 전체 커밋/푸시 금지. 커밋 보고 시 포함/제외 파일을 명시한다.

---

# Eduitit 프로젝트 — Claude Code 설정

## 개인 정보
- 이름: 유병주 (Byungju Yu) / GitHub: yb941213 / 회사: SCHOOL

## 기술 스택
| 영역 | 기술 |
|------|------|
| Backend | Django (Python 3.10+), Django Template Language |
| Frontend | Vanilla JS, Alpine.js, HTMX, Tailwind CSS |
| Infra | Railway, Neon PostgreSQL, Cloudinary |
| Monitoring | Sentry (production only) |

## 코딩 규칙
- 한국어로 주석과 커밋 메시지 작성
- Django 표준 준수: 명확한 URL 네이밍, Service Layer/Utils 활용
- Frontend: Alpine.js + HTMX 우선, 가볍고 빠른 반응형
- CSS: Tailwind CSS 클래스 우선 (커스텀 CSS 최소화)
- 커밋 형식: `[타입] 제목` (feat, fix, docs, style, refactor, test, chore)

## 금지 사항
- Production settings 직접 수정 금지 (settings_production.py는 신중히)
- `.env` 파일이나 민감한 정보 커밋 금지
- 하드코딩된 API 키 사용 금지
- UI 오버랩(NavBar 가림) 방치 금지 → 모든 페이지 `pt-32` 준수
- `ensure_*` management command에서 데이터 중복 생성 및 Admin 관리 데이터 덮어쓰기 금지
  → Procfile이 매 배포마다 실행하므로 Admin 수정이 초기화되거나 데이터가 중복됨
- **[Manual]** 신규 서비스 추가 시 `ServiceManual` 작성 누락 금지 (3개 이상 섹션 필수)

## 작업 완료 후 체크리스트
- [ ] Django Check 통과 (`python manage.py check`)
- [ ] 변경 페이지 핵심 인터랙션 스모크 테스트 (탭 전환/주요 버튼/저장·해제 액션 최소 1회)
- [ ] 브라우저 Console 에러 0건 + 의도치 않은 Network 4xx/5xx 0건 확인
- [ ] console.log 및 debug print 제거
- [ ] **[Manual]** 서비스 매뉴얼(`ServiceManual`) 데이터 및 레이아웃 포함 여부 확인
- [ ] 보안 검토 (API 키, 시크릿 노출 여부)
- [ ] settings.py 변경 시 settings_production.py도 동기화

---

# 핵심 아키텍처

## 서비스 인프라 구조

| 기능 | 파일 | 비고 |
|------|------|------|
| Toast 알림 | `core/context_processors.py` → `toast_messages()` | Django messages + Alpine.js |
| 글로벌 배너 | `core/models.py` → `SiteConfig` (싱글톤) | Admin에서 관리 |
| SEO 메타태그 | `core/context_processors.py` → `seo_meta()` | view context로 override 가능 |
| 피드백 위젯 | `core/models.py` → `Feedback`, `/feedback/` | HTMX + 플로팅 버튼 |
| 관리자 대시보드 | `/admin-dashboard/` | superuser 전용, 봇/사람 구분 |
| DB 백업 | `python manage.py backup_db` | dumpdata JSON |

**context_processors 등록 순서** (두 settings 파일 모두 동일해야 함):
```python
'core.context_processors.visitor_counts',
'core.context_processors.toast_messages',
'core.context_processors.site_config',
'core.context_processors.seo_meta',
```

**VisitorLog 모델**: `user_agent`, `is_bot` 필드. `get_visitor_stats(days, exclude_bots=True)`로 필터링.

## UI 레이아웃 표준

NavBar가 `fixed` 포지션이므로 모든 페이지에서 상단 여백 확보 필수.

```html
{% block content %}
<section class="pt-32 pb-20 px-4 min-h-screen">
    <div class="max-w-7xl mx-auto">...</div>
</section>
{% endblock %}
```

- **표준**: `pt-32` (128px) — 모든 페이지
- **최소**: `pt-24` (Banner 없을 때)

### 반응형 브레이크포인트
| 접두사 | 최소 너비 | 용도 |
|--------|----------|------|
| (없음) | 0px | 모바일 기본 |
| `sm:` | 640px | 큰 모바일/소형 태블릿 |
| `md:` | 768px | 태블릿 |
| `lg:` | 1024px | 데스크톱 |
| `xl:` | 1280px | SNS 사이드바 분기 기준 |

## 문서 관리 UI 패턴 (Mobile-First)

**목록 화면**: `hidden md:block` (데스크톱 table) / `md:hidden` (모바일 Card Grid)
**상세 화면**: 모바일 Alpine.js 탭 / 데스크톱 2단 컬럼 (`lg:grid-cols-3`)
**입력 폼**: 모바일 `py-3.5`, `text-base` 이상 / 버튼·입력창 `w-full`

## SNS Sidebar 통합 패턴 (V2 기준)

**레이아웃 구조:**
```html
<div class="flex flex-col xl:flex-row max-w-[1920px] mx-auto">
    <div class="hidden xl:block flex-shrink-0">
        {% include 'core/partials/sns_widget.html' %}
    </div>
    <main class="flex-1">
        {{ 메인 콘텐츠 }}
        <div x-data="{ snsOpen: false }" class="block xl:hidden">
            {% include 'core/partials/sns_widget_mobile.html' with hide_header=True expand_all_mobile=True %}
        </div>
    </main>
</div>
```

**뷰 쿼리 규칙:**
- `select_related('author', 'author__userprofile')`
- `prefetch_related('likes', 'comments', 'comments__author', 'comments__author__userprofile')`
- `annotate(likes_count_annotated=Count('likes', distinct=True), comments_count_annotated=Count('comments', distinct=True))`

**흔한 실수:**
1. `lg:` 기준 분기 사용 → 현재 기준은 `xl:` 분기
2. 모바일 더보기를 앵커/HTMX로 처리 → `@click="snsOpen = true"` 토글 사용
3. 모바일 위젯 헤더 중복 → `hide_header=True` 전달
4. 전체 피드가 1개만 보임 → `expand_all_mobile=True` 전달
5. `like_count` 필드명 참조 → 현재는 `likes_count_annotated`, `comments_count_annotated`

**관련 파일:**
- 홈: `core/templates/core/home_v2.html`, `home_authenticated_v2.html`
- SNS 위젯: `core/templates/core/partials/sns_widget.html`, `sns_widget_mobile.html`
- 뷰: `core/views.py` (`home`, `_home_v2`)
- 테스트: `core/tests/test_home_view.py`

---

# 반복 실수 방지 규칙

## Django / Python

### 1. Django 설정 파일 동기화 (CRITICAL)
로컬(`settings.py`)과 프로덕션(`settings_production.py`)은 반드시 동기화.
특히 주의: `MIDDLEWARE`, `INSTALLED_APPS`, `TEMPLATES > context_processors`, `LOGGING`

```bash
diff config/settings.py config/settings_production.py
```

### 2. Django views.py 필수 체크
500 에러의 3대 원인:
1. **`from django.conf import settings` import 누락** → `NameError`
2. **상수를 함수보다 아래에 정의** → `NameError`
3. **view 함수에서 `return` 문 누락** → `None` 반환 → 500 에러

> **이유**: 데코레이터 콜백 안의 import 누락은 특정 조건에서만 터진다. superuser는 `or` 단축 평가로 해당 함수가 호출되지 않아 로컬/superuser 환경에서 재현 불가능한 경우가 있음. 모든 함수 참조의 import 여부를 반드시 확인할 것.

### 3. Railway 배포 환경 제약
- **`pg_dump` 없음** → `dumpdata` JSON 백업 사용 (`core/management/commands/backup_db.py`)
- **Neon PostgreSQL = PgBouncer** → `DISABLE_SERVER_SIDE_CURSORS = True` 설정 필요
- **Cron Job = 별도 컨테이너** → `raise` 대신 `sys.exit(0/1)` 사용
- **패키지 추가 시**: `requirements.txt` 즉시 반영, 시스템 바이너리 의존성은 `nixpacks.toml`에 추가

### 4. select_related와 선택적 관계
```python
# ❌ UserProfile이 없는 User가 있으면 에러
.select_related('author__userprofile')

# ✅ 필수 관계만 select_related, 선택적 관계는 템플릿에서 체크
.select_related('author')
# 템플릿: {% if post.author.userprofile %}
```

> **이유**: 프로덕션에는 UserProfile 없는 User가 존재할 수 있다. 로컬에서는 재현 안 됨.

### 5. OneToOneField 접근 시 존재 보장
```python
# ❌ config가 없으면 DoesNotExist → 500 에러
config = school.config

# ✅ get_or_create로 존재 보장
config, created = SchoolConfig.objects.get_or_create(school=school)
```

### 6. DB 데이터 변경 시 반드시 데이터 마이그레이션 작성
```python
# ❌ Django shell 수정 → 프로덕션 미반영
Product.objects.filter(id=121).update(service_type='classroom')

# ✅ 데이터 마이그레이션
def update_data(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(id=121).update(service_type='classroom')
migrations.RunPython(update_data, migrations.RunPython.noop)
```

### 7. Django 템플릿 태그 `{% %}` 안에 줄바꿈 금지 (CRITICAL)
```html
<!-- ❌ 줄바꿈 → TemplateSyntaxError: Invalid block tag 'endif' -->
{% if user.is_authenticated and
    user.userprofile.nickname %}

<!-- ✅ 한 줄로 -->
{% if user.is_authenticated and user.userprofile.nickname %}
```

> **이유**: Django 템플릿 파서는 `{%`와 `%}` 사이의 줄바꿈을 인식하지 못한다. git rebase 충돌 해결 후 특히 주의.

### 8. Django 템플릿 변수 명명 — 언더바 접두어 금지
```python
# ❌ 언더바 시작 → TemplateSyntaxError: Variables may not begin with underscores
.annotate(_count=Count(...))
# 템플릿: {{ obj._count }} → 오류

# ✅ 언더바 없이
.annotate(submission_count=Count(...))
```

> **이유**: Django 템플릿 엔진은 `_` 시작 속성 접근을 Python private 관례에 따라 차단한다.

### 9. Django Admin N+1 쿼리
```python
# ❌ list_display에 FK 필드 → 행마다 SELECT
list_display = ['user', 'product', 'created_at']

# ✅ get_queryset에 select_related 추가
def get_queryset(self, request):
    return super().get_queryset(request).select_related('user', 'product')

# ❌ .count() → 행마다 COUNT 쿼리
def like_count(self, obj): return obj.likes.count()

# ✅ annotate로 단일 쿼리
def get_queryset(self, request):
    return super().get_queryset(request).annotate(_like_count=Count('likes', distinct=True))
def like_count_display(self, obj): return obj._like_count
like_count_display.admin_order_field = '_like_count'
```

**새 앱/모델 추가 시 체크리스트:**
- [ ] FK 필드 있으면 → `get_queryset`에 `select_related`
- [ ] `.count()` 메서드 있으면 → `annotate` + `_display` 메서드로 교체
- [ ] User FK에는 `raw_id_fields` 사용
- [ ] `author__userprofile` 같은 선택적 관계는 `select_related` 금지 (규칙 4)

### 10. allauth 65.x — ACCOUNT_SIGNUP_FORM_CLASS (CRITICAL)
```python
# ❌ SOCIALACCOUNT_FORMS → try_save() 없어서 AttributeError → 500
SOCIALACCOUNT_FORMS = {'signup': 'core.signup_forms.CustomSignupForm'}

# ❌ allauth.socialaccount.forms.SignupForm 직접 상속 → 순환 import → 크래시
from allauth.socialaccount.forms import SignupForm as SocialSignupForm

# ✅ ACCOUNT_SIGNUP_FORM_CLASS만 사용
ACCOUNT_SIGNUP_FORM_CLASS = 'core.signup_forms.CustomSignupForm'
# → allauth 내부: SignupForm(BaseSignupForm(CustomSignupForm))
# → try_save() → save() → custom_signup() → signup() 정상 작동
```

**CustomSignupForm은 `forms.Form` 상속, `signup(request, user)` 메서드만 정의:**
```python
class CustomSignupForm(forms.Form):
    nickname = forms.CharField(...)
    def signup(self, request, user): ...
```

### 11. allauth v65.x+ 설정
```python
ACCOUNT_LOGIN_METHODS = {'email', 'username'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*']  # 필수 필드는 * 붙임
```
`settings.py`와 `settings_production.py` 모두 동기화 필수.

### 12. OnboardingMiddleware — OAuth 콜백 경로 허용
```python
# ❌ /accounts/logout/ 만 허용 → 카카오/네이버 콜백 차단 → 가입 실패
allowed_paths = ['/accounts/logout/', ...]

# ✅ /accounts/ 전체 허용
allowed_paths = ['/accounts/', ...]
```

### 13. 소셜 가입 폼 — readonly widget 처리
```python
# ❌ 기본 readonly → 소셜 이메일 미제공 시 입력 불가 → 가입 불가
email = forms.EmailField(widget=forms.EmailInput(attrs={'readonly': 'readonly'}))

# ✅ 기본은 편집 가능, 소셜 이메일 있을 때만 __init__에서 readonly 설정
if self.sociallogin and self.sociallogin.user.email:
    self.fields['email'].widget.attrs['readonly'] = True
```

### 14. Gunicorn sync worker 고갈 — AI API 호출 시 필수 설정
```bash
# ❌ 기본 설정 (worker 1개) — AI 1건 처리 중 모든 요청 499
gunicorn config.wsgi --timeout 120

# ✅ gthread 모드 (동시 12개 요청 처리)
gunicorn config.wsgi --workers 3 --threads 4 --worker-class gthread --timeout 120
```

> **이유**: 기본 Gunicorn은 sync 단일 worker. AI API가 30~60초 점유하면 그 시간 동안 로그인·가입 등 모든 요청이 499로 실패한다.

### 15. SESSION_SAVE_EVERY_REQUEST 성능 영향
`SESSION_SAVE_EVERY_REQUEST = True`는 모든 HTTP 요청마다 DB write 발생.
트래픽이 많으면 `False`로 설정하고 `SESSION_COOKIE_AGE`를 24시간+ 설정.

### 16. settings_production.py 서버 시작 시 DB 조작 주의
시작 시 실행 함수에서 `SocialApp.objects.all().delete()` 등 전체 삭제 쿼리 금지.
매 배포마다 불필요한 DB 조작 + 레이스 컨디션 위험.

---

## Frontend (JS / Alpine.js / HTMX / Template)

### 17. Alpine.js CDN — unpkg 대신 jsdelivr 사용
```html
<!-- ❌ unpkg 와일드카드 → 간헐적 로딩 실패 -->
<script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>

<!-- ✅ jsdelivr -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
```

Alpine.js 의존 핵심 네비게이션은 vanilla JS fallback 추가:
```javascript
if (!window.Alpine) { fallbackFunction(); }
```

### 18. 라이브러리 중복 로드 금지
`base.html`에서 로드된 라이브러리(HTMX, Alpine.js 등)를 자식 템플릿이나 Partial에서 다시 로드하지 않는다.

> **이유**: 두 번 초기화되면 이벤트 핸들러가 중복 바인딩되어 모달 두 번 열림 등 예기치 않은 동작이 발생한다.

### 19. Alpine.js `<template x-if>` 안에 HTMX 넣지 않기
```html
<!-- ❌ HTMX 폴링이 작동하지 않음 -->
<template x-if="showFullscreen">
    <div hx-get="/api/data/" hx-trigger="every 5s">...</div>
</template>

<!-- ✅ HTMX를 template 밖에 두기 -->
<div x-show="showFullscreen">
    <div hx-get="/api/data/" hx-trigger="every 5s">...</div>
</div>
```

> **이유**: `template x-if`는 조건 변경 시 DOM을 완전히 제거/추가하므로 HTMX가 재초기화되지 않는다. `x-show`는 `display`만 토글하므로 HTMX가 유지된다.

### 20. JSON 파싱 시 HTML 에러 페이지 감지
```javascript
// ❌ Django 에러 시 HTML 반환 → JSON.parse 크래시
const data = JSON.parse(element.textContent);

// ✅ HTML 감지 후 fallback
function safeJSONParse(text, fallback = null) {
    if (!text) return fallback;
    if (text.trim().startsWith('<')) {
        console.error("HTML detected instead of JSON");
        return fallback;
    }
    try { return JSON.parse(text.trim()); }
    catch (e) { console.error("JSON parse error:", e); return fallback; }
}
```

Django 템플릿에서 JSON 전달 시:
```django
{# ✅ json_script 필터 사용 #}
{{ chart|json_script:"chart-data" }}
```

> **이유**: 캐싱 여부와 관계없이 View에서 `chart_data`를 항상 생성해야 한다. 없으면 `json_script`가 빈 값을 생성하고 JS 파싱 실패.

### 20-1. 다중 IIFE 스코프 누락으로 이벤트 미바인딩 방지 (2026-02-22)
```javascript
// ❌ 첫 번째 IIFE에만 있는 함수를 두 번째 IIFE bootstrap에서 호출
(function () {
    function decodeDefaultNames(raw) { ... }
})();

(function () {
    function bootstrap() {
        decodeDefaultNames(window.someData); // ReferenceError
        bindEvents(); // 실행되지 않음
    }
})();
```

- 위 패턴에서 `bootstrap` 단계 예외가 나면 이벤트 리스너가 등록되지 않아 탭/버튼이 "무반응"처럼 보인다.
- `node --check`는 문법만 검사하므로 이런 런타임 스코프 오류를 잡지 못한다.
- 재발 방지 규칙:
  - 다중 IIFE를 유지한다면, 헬퍼 함수는 **각 IIFE 내부에 명시적으로 두거나** 파일 공용 스코프로 올린다.
  - `bindEvents()` 전에 호출되는 초기화 코드(`bootstrap`)에서 외부 스코프 심볼 참조를 금지한다.
  - JS 수정 후에는 반드시 브라우저에서 핵심 탭/버튼 클릭 스모크 테스트 + 콘솔 에러 0건을 확인한다.

### 20-2. 사용자 액션 "무반응" 방지 게이트 (2026-02-22)
```javascript
// ✅ 사용자 클릭으로 호출되는 fetch 기본 패턴
async function postJSON(url, body) {
    const token = getCsrfToken(); // hidden input 우선, cookie fallback
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": token },
        body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}
```

- 금지:
  - 사용자 클릭 액션에 `.catch(function(){})` 같은 침묵 실패 처리
  - `fetch(...).then(r => r.json())`에서 `r.ok` 확인 누락
- 필수:
  - 실패 시 사용자에게 즉시 보이는 피드백(토스트/alert/인라인 메시지)
  - 실패 원인을 콘솔에 남겨 QA 중 추적 가능하게 유지
  - CSRF는 쿠키 직접 파싱 단독 의존 금지 (`CSRF_COOKIE_HTTPONLY` 환경 고려)
- 커밋 전 검증:
  - 변경 화면에서 핵심 클릭 플로우를 실제로 눌러 보고, 콘솔/네트워크 에러가 있으면 커밋 금지
  - "동작 안 함" 이슈는 재현 절차(클릭 순서/기대 결과/실제 결과)를 PR/커밋 메모에 1줄로 기록

### 21. JS 데이터 전달 — json_script 활용
```html
<!-- ✅ json_script로 HTML에 JSON을 심고 JS에서 가져오기 -->
{{ data|json_script:"my-data" }}
<script>const data = JSON.parse(document.getElementById('my-data').textContent);</script>
```

인라인 스타일의 템플릿 태그는 Alpine.js `:style` 바인딩 사용:
```html
<div x-data="{ color: '{{ theme_color|escapejs }}' }" :style="{ backgroundColor: color }">
```

### 22. Django 템플릿 태그 Fragmentation 금지 (CRITICAL)
복잡한 로직이 포함된 템플릿 태그는 한 줄(One-liner)로 유지한다.
```html
<!-- ❌ 줄바꿈 → 텍스트 깨짐 또는 500 에러 -->
<span>
  {% if user.nickname %}{{ user.nickname }} {% else %}{{ user.username
   }}{% endif %}
</span>

<!-- ✅ 한 줄로 -->
<span>{% if user.nickname %}{{ user.nickname }}{% else %}{{ user.username }}{% endif %}</span>
```

### 23. Django 템플릿 filter 공백 주의
```python
# ❌ 공백 → 일부 환경에서 오인
{{ questions | length }}

# ✅ 밀착
{{ questions|length }}
```

### 24. JS/Alpine 속성 내 Django 따옴표 중복 (CRITICAL)
```html
<!-- ❌ 작은따옴표 충돌 → SyntaxError -->
@click="openBooking('{{ target_date|date:'Y-m-d' }}')"

<!-- ✅ 내부 인자에 쌍따옴표 사용 -->
@click="openBooking('{{ target_date|date:"Y-m-d" }}')"
```

> **이유**: PC에서는 정상이고 `xl:hidden` 같은 모바일 전용 블록 내부에서만 발생하면 원인 찾기가 매우 어렵다.

### 25. JS `var` 호이스팅 — 같은 함수 내 변수 재선언 금지
```javascript
// ❌ var piece가 2번 선언 → 호이스팅으로 하나로 합쳐져 잘못된 값 참조
function onSquareClick(square) {
    var piece = game.get(square);
    if (selectedSquare) {
        var piece = game.get(selectedSquare); // 덮어씀
    }
}

// ✅ 다른 이름 사용
var selectedPiece = game.get(selectedSquare);
```

### 26. JS `const` 재할당 금지
```javascript
// ❌ try/catch 밖에서 const 재할당 → TypeError → 스크립트 전체 중단
const rawText = outputArea.innerText;
rawText = rawText.replace(...);

// ✅ escapejs로 순수 문자열 전달
const rawMarkdown = "{{ item.result_text|escapejs }}";
marked.parse(rawMarkdown);
```

### 27. JavaScript 내 Django 템플릿 태그 공백 처리
```javascript
/* ❌ 공백이나 줄바꿈이 JS 문법 파괴 */
var maxSize = {{ req.max_file_size_mb |default: 30 }};

/* ✅ 따옴표로 감싸거나 필터 붙여쓰기 */
const maxMB = parseInt('{{ req.max_file_size_mb|default:30 }}');
```

### 28. JS className 전체 교체 시 레이아웃 클래스 유실
```javascript
// ❌ 레이아웃 클래스 사라짐
badge.className = `text-sm py-1 px-3 rounded-full ${colorClass}`;

// ✅ 레이아웃 클래스 포함 or classList.add/remove 사용
badge.className = `inline-flex items-center justify-center gap-1 text-sm py-1 px-3 rounded-full ${colorClass}`;
```

### 29. CSS `transform` 충돌 — 전역 hover가 모달 centering 파괴
```css
/* ❌ base.html 전역 스타일이 fixed 모달 centering을 파괴 */
.clay-card:hover { transform: translateY(-4px) scale(1.005); }

/* ✅ 모달 전용 클래스로 hover transform 고정 */
.tool-modal.clay-card:hover { transform: translate(-50%, -50%) !important; }
```

> **이유**: CSS `transform`은 개별 값이 아닌 전체가 교체된다. `fixed + translate(-50%, -50%)` 중앙 정렬 모달에 전역 hover transform이 있는 클래스를 쓰면 hover 시 centering이 사라진다.

**fixed + transform 중앙 정렬 모달 체크리스트:**
- [ ] `clay-card`, `clay-btn` 등 전역 hover transform이 있는 클래스 사용 여부 확인
- [ ] 있다면 모달 전용 클래스로 hover transform을 `translate(-50%, -50%)`로 고정

### 30. Web Audio API — AudioContext 공유 필수
```javascript
// ❌ 매번 생성 → 브라우저 제한(~6개) 도달 → 사운드 중단
function playSound() { var ctx = new AudioContext(); }

// ✅ 전역 공유
var sharedAudioContext = null;
function getAudioContext() {
    if (!sharedAudioContext)
        sharedAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    if (sharedAudioContext.state === 'suspended') sharedAudioContext.resume();
    return sharedAudioContext;
}
```

### 31. Undo/Reset 시 모든 파생 UI 상태 동기화 필수
체스 기준 체크리스트:
- [ ] `capturedPieces` 배열에서 되돌린 기물 제거 + `renderCapturedPieces()` 호출
- [ ] `lastMove` 갱신 (남은 기록의 마지막 수 또는 null) + `highlightLastMove()` 호출
- [ ] `moveHistory` 배열 pop + `updateMoveHistory()` 호출
- [ ] Reset 시 `renderCapturedPieces()` 호출 (initGame이 배열만 비우고 DOM은 안 건드림)

### 32. 비동기 스크립트 로더 — 레이아웃 의존 라이브러리에 금지 (CRITICAL)
```html
<!-- ❌ 비동기 로더 → chessboard.js width 감지 실패 (에러 메시지 없는 조용한 실패) -->
<!-- loadScript('jquery.js').then(() => loadScript('chessboard.js'))... -->

<!-- ✅ 동기 로딩 — 순서대로 완전히 로드 후 실행 -->
<script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
<script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
<script>var STOCKFISH_PATH = "..."; var IS_AI_MODE = ...; var AI_DIFFICULTY = ...;</script>
<script src="{% static 'chess/js/chess_logic.js' %}"></script>
```

> **이유**: `chessboard.js`는 초기화 시 `$(el).width()`를 읽는데, 비동기 주입 시 타이밍이 어긋나 0을 반환한다. `.board-b72b1` div가 생성은 되므로 에러 메시지도 안 뜨는 조용한 실패다. 증상은 체스판 영역에 얇은 가로선만 표시되는 것.

### 33. chess_logic.js 초기화 — readyState 체크 패턴
```javascript
// ✅ 동기/비동기 로딩 모두 호환
function initHelper() { initGame(); initBoard(); updateStatus(); }

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHelper);
} else {
    initHelper(); // 동기 로딩 시 이미 interactive 또는 complete 상태
}
```

> **이유**: `DOMContentLoaded` 단독은 비동기 주입 스크립트에서 이미 발화한 상태라 콜백이 영원히 실행되지 않는다.

### 34. 체스 CDN — production CSP 허용 목록
| 라이브러리 | CSP 허용 CDN | 비고 |
|---|---|---|
| jQuery | `cdn.jsdelivr.net` | `code.jquery.com` 차단됨 |
| chessboard.js | `unpkg.com` | OK |
| chess.js | `cdnjs.cloudflare.com` | OK |

### 35. Stockfish 경로 충돌 없음 확인
| 앱 | Static URL |
|---|---|
| Chess | `/static/chess/js/stockfish.js` |
| 장기 | `/static/janggi/js/engine/stockfish.js` |

### 36. Alpine.js 상태 초기화와 Django 폼 에러 연동
```html
<!-- ❌ 에러가 있어도 UI가 닫혀 사용자 혼란 -->
<div x-data="{ open: false }">

<!-- ✅ 에러 시 열린 상태로 초기화 -->
<div x-data="{ open: {% if form.errors %}true{% else %}false{% endif %} }">
```

### 37. HTMX 단독 버튼의 데이터 전송 (hx-vals)
HTMX 버튼이 `<form>` 밖에 있을 때는 내부 `<input type="hidden">`을 인식하지 못한다.
```html
<!-- ✅ hx-vals로 명시적 전송 -->
<button hx-post="..." hx-vals='{"room_id": "{{ room.id }}"}'>
```

### 38. HTMX 보안 토큰(CSRF) 삼중 방어 (CRITICAL)
1. **전역 처리 (base.html)**: `document` 레벨에 `htmx:configRequest` 리스너로 `X-CSRFToken` 자동 주입
   - **주의**: `document.body`에 걸면 body 로드 전 에러 → 반드시 `document` 레벨
2. **컨테이너 전략**: HTMX 작업이 많은 부모 `div`에 `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` 선언
3. **이중 검증 (삭제 등 중요 버튼)**: `hx-vals`에 `csrfmiddlewaretoken` 명시적 포함
   ```html
   <button hx-post="..." hx-vals='{"item_id": "1", "csrfmiddlewaretoken": "{{ csrf_token }}"}'>
   ```

### 39. 부분 템플릿(Partial) 렌더링 시 컨텍스트 관리
HTMX로 그리드/목록만 업데이트할 때, 해당 템플릿에서 사용하는 모든 변수(`school`, `config` 등)를 뷰의 `render()` 호출 시 반드시 포함해야 한다.

### 40. 모바일 카드 오버플로우 — `box-sizing` + 그림자 (CRITICAL)
```css
/* base.html */
*, *::before, *::after { box-sizing: border-box; }

.clay-card {
    max-width: 100%;
    overflow: hidden;
    /* 모바일: 좌우 그림자 오프셋 0으로 뷰포트 확장 방지 */
    box-shadow: 0 4px 12px rgba(163, 177, 198, 0.4), 0 -2px 8px rgba(255, 255, 255, 0.6);
}

@media (min-width: 768px) {
    .clay-card { box-shadow: 8px 8px 16px rgba(163, 177, 198, 0.5), -8px -8px 16px rgba(255, 255, 255, 0.6); }
}
```

> **이유**: Tailwind CDN의 preflight가 미적용될 수 있어 `box-sizing`을 명시해야 함. 넓은 수평 그림자가 뷰포트 너비를 초과하면 가로 스크롤 발생.

---

## 데이터 / Admin

### 41. ensure_* 명령어 표준 (CRITICAL)
`ensure_*` 명령어는 **매 배포(git push)마다 실행**된다.

**핵심 규칙:**
- Admin 관리 필드(`service_type`, `display_order`, `color_theme`)는 **절대 덮어쓰지 않기**
- `create()` 대신 **`get_or_create` 또는 `update_or_create`** 사용
- `clear()`/`delete()` 후 재생성 방식 금지 → Admin 수정 소멸 + 멱등성 보장 불가

```python
# ❌ 매 배포마다 덮어씀 → Admin 수정 무효화
product.service_type = 'game'
product.save()

# ❌ 삭제 후 재생성 → Admin 수정 소멸
product.features.all().delete()
for feat in features:
    ProductFeature.objects.create(product=product, **feat)

# ✅ 존재 보장만 담당
obj, created = ProductFeature.objects.get_or_create(
    product=product, title=feat['title'], defaults=feat
)
# 기능적 필수값(is_active 등)만 조건부 보정
if not product.is_active:
    product.is_active = True
    product.save()
```

**유효한 service_type 값:** `classroom`, `work`, `game`, `counsel`, `edutech`, `etc`

**현재 Procfile 실행 순서:**
```
migrate → ensure_ssambti → ensure_studentmbti → ensure_notebooklm → ensure_collect → ensure_reservations → check_visitors → gunicorn
```

### 42. 새 Django 앱 추가 체크리스트

| 단계 | 파일 | 작업 |
|------|------|------|
| 1 | 앱 디렉토리 | `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, `apps.py` 생성 |
| 2 | `config/settings.py` | `INSTALLED_APPS`에 추가 |
| 3 | `config/settings_production.py` | `INSTALLED_APPS`에 동일하게 추가 |
| 4 | `config/urls.py` | `path('앱/', include('앱.urls', namespace='앱'))` 추가 |
| 5 | `preview_modal.html` | 시작 버튼 URL 분기 추가 |
| 6 | `ensure_*` 명령어 | Product 생성 보장, Admin 필드 덮어쓰기 금지 |
| 7 | `settings_production.py` | `run_startup_tasks()`에 `call_command('ensure_*')` 추가 |
| 8 | `Procfile` | `ensure_*` 명령어 체인에 추가 |
| 9 | `nixpacks.toml` | Procfile과 동기화 |
| 10 | `admin.py` | `select_related` + `annotate` + `raw_id_fields` |
| 11 | 마이그레이션 | `makemigrations` + `migrate` |
| 12 | 검증 | `python manage.py check` |

### 43. 서비스 시작 버튼 URL 라우팅 — preview_modal.html 수정 필수
```html
<!-- 한 줄로 작성 (줄바꿈 금지) -->
{% if product.external_url %}{{ product.external_url }}{% elif product.title == '쌤BTI' %}{% url 'ssambti:main' %}{% elif product.title == '간편 수합' %}{% url 'collect:landing' %}{% elif product.title == '교사 백과사전' %}{% url 'encyclopedia:landing' %}{% elif product.title == '학교 예약 시스템' %}{% url 'reservations:reservation_index' %}{% else %}{% url 'home' %}{% endif %}
```

새 서비스 추가 시 `{% elif product.title == '서비스명' %}{% url 'app:landing' %}` 분기 추가 필수.

### 44. 서비스 카테고리 시스템
| 코드 | 이름 | 탭 색상 |
|------|------|---------|
| `classroom` | 운영과 수업 | 파란색 |
| `work` | 업무경감 | 초록색 |
| `game` | 게임모음 | 빨간색 |
| `counsel` | 상담·운세 | 보라색 |
| `edutech` | 에듀테크 | 시안색 |
| `etc` | 기타 | 회색 |

**카테고리 추가/변경 시 수정 필요한 파일:**
1. `products/models.py` — `SERVICE_CHOICES` + 마이그레이션
2. `core/templates/core/home_v2.html` — CSS `.cat-{code}` + 탭 버튼
3. `core/templates/core/home_authenticated_v2.html` — 위와 동일
4. `core/templates/core/includes/card_product.html` — 아이콘/라벨 색상 분기

### 45. 로컬 DB 데이터 확인
새 서비스 개발 시 `db.sqlite3`가 비어있으면 UI에 서비스가 표시되지 않는다.
→ `python manage.py ensure_xxx` 실행 또는 임시 스크립트로 로컬 DB에 필수 데이터 생성.

### 46. git rebase 충돌 해결 후 체크리스트
1. `{% if %}` / `{% endif %}` 밸런스 확인
2. 줄바꿈으로 분리된 템플릿 태그 없는지 확인
3. `python manage.py check` + 실제 페이지 렌더링 테스트

---

## 보안 / UX

### 47. 비회원 관리 접근 권한 — UUID(Management ID) 사용
```python
# 모델에 management_id 추가
management_id = models.UUIDField(default=uuid.uuid4, unique=True)
# URL: /manage/<uuid:management_id>/
# URL 자체가 토큰 역할 — 세션 체크 불필요
```

사용자에게 "이 주소를 복사해두면 나중에 관리 가능" 안내 + '주소 복사' 버튼 제공.

> **이유**: 세션 기반 권한은 브라우저를 닫으면 사라진다.

### 48. 데이터 수합 시 보안 및 면책 안내 의무화
파일/링크/텍스트 수합 기능에 필수 포함:
1. **개인정보**: 주민번호, 연락처 등 민감 정보 포함 지양 안내
2. **보안자료**: 공문서, 내부 대외비 자료 수합 주의 촉구
3. **면책문구**: 데이터 관리 책임은 요청자/제출자에게 있음 명시

배치: 제출 화면(`submit`) + 소개 페이지(`landing`)에 Red 계열 + 경고 아이콘.

### 49. 공공용 URL 무작위성 확보
```python
# models.py save()에서 자동 생성
def save(self, *args, **kwargs):
    if not self.slug:
        self.slug = uuid.uuid4().hex[:8]  # 추측 불가능한 슬러그
    super().save(*args, **kwargs)
```

보안 URL이 길면 `/go/<id>/` 짧은 리다이렉트 링크 제공.

### 50. 전체 데이터 생애주기(CRUD) 완결성
모든 데이터 관리 기능에 **[등록 - 조회 - 수정 - 삭제]**가 하나의 세트로 구현되어야 한다.
삭제 버튼에는 확인 모달 포함. 파일 교체는 삭제 후 재등록이 아닌 새 파일 선택 시 즉시 교체.

### 51. ModelForm 필수 필드 처리
```python
# ❌ 폼 필드엔 있는데 HTML엔 없음 → 유효성 검사 실패
fields = ['title', 'max_file_size_mb']

# ✅ 사용자 입력 불필요하면 필드 제거 (모델 default 사용)
fields = ['title']
```

사용자(비개발자)에게 "파일 최대 크기", "청크 사이즈" 같은 기술적 설정 묻지 않기. 시스템이 합리적인 기본값 제공.

### 52. 커스텀 교시(Period Labels) 관리
`SchoolConfig` 모델의 `period_labels` (TextField, CSV 콤마 구분) 필드.
`get_period_list()` 메서드로 리스트화하여 예약 그리드 동적 생성.
그리드 렌더링 시 "몇 번째" 숫자 대신 "Label과 ID" 매칭: `{% if s.period == p.id %}`

---

## AI / 프롬프트

### 53. AI 프롬프트 SSOT 지시에는 반드시 볼드 유지
```
# ❌ 볼드 제거 → AI가 SSOT 규칙을 약하게 따름
선생님의 정체성은 반드시 상단 [SSOT Data]의 'Day' 첫 글자입니다.

# ✅ 볼드 유지 → AI가 강하게 따름
**정체성 고정**: 선생님의 정체성은 반드시 **[SSOT Data]의 일주(Day) 첫 글자(천간)**입니다.
```

출력 템플릿의 제약도 구체적으로 명시: "자연물 비유" → "일간 오행에 맞는 자연물"

### 54. AI 프롬프트 — "제목 쓰지 마세요"는 섹션 헤더까지 생략시킴
```
# ❌ AI가 ## 헤더를 모두 생략
서론이나 별도 제목은 쓰지 마세요.

# ✅ 서론만 금지, 섹션 헤더는 필수 지시
서론을 쓰지 마세요. 각 섹션은 반드시 아래 출력 템플릿의 `## ` 제목을 그대로 포함하세요.
```

### 55. localStorage 캐시 동기화
DB에서 `FortuneResult` 삭제 시 브라우저 localStorage 캐시도 함께 제거.

삭제 시 제거해야 할 캐시 키 패턴:
- `saju_result_cache_*`, `saju_result_v2_*`
- `daily_saju_cache_*`, `daily_saju_v2_*`
- `pendingSajuResult`, `lastSajuInput`

### 56. JS Base64 해시 캐시 키 — 키 순서와 해시 길이 (CRITICAL)
```javascript
// ❌ mode가 마지막 + 해시 짧음 → 캐시 충돌
const keyParts = [name, gender, year, month, day, hour, calendar, mode];
const hash = btoa(unescape(encodeURIComponent(keyParts.join('|')))).substring(0, 24);

// ✅ mode를 첫 번째로 + 해시 길이 32자 이상
const keyParts = [mode, name, gender, year, month, day, hour, calendar];
const hash = btoa(unescape(encodeURIComponent(keyParts.join('|')))).substring(0, 32);
```

> **이유**: Base64는 3바이트→4문자 변환이므로 `substring(24)`는 입력의 처음 18바이트만 반영한다. 한글 이름(글자당 3바이트)과 생년월일이 이미 18바이트를 소진하면 뒤쪽의 mode 차이(`teacher` vs `general`)가 해시에 반영되지 않는다.

**캐시 키 변경 시 체크리스트:**
- [ ] 구분 필드(mode, type)를 키 배열의 **앞쪽**에 배치
- [ ] 해시 길이 최소 32자
- [ ] 캐시 키 접두사 버전업으로 기존 캐시 무효화 (`v2_` → `v3_`)
- [ ] 페이지 로드 시 구버전 캐시 자동 삭제 로직 추가

### 57. Django 템플릿에 dict vs object 속성 접근 주의
```python
# ❌ dict는 .created_at 같은 추가 속성이 없어 에러
return render(request, 'chat_message.html', {'message': {'role': 'assistant', 'content': '...'}})

# ✅ SimpleNamespace로 속성 접근 보장
from types import SimpleNamespace
msg = SimpleNamespace(role='assistant', content='...', created_at=timezone.now())
return render(request, 'chat_message.html', {'message': msg})
```

### 58. AI 로깅 표준
```python
# 표준 포맷: [AppName] Action: ACTION_NAME, Status: SUCCESS/FAIL, Key: Value, ...
logger.info(f"[StudentMBTI] Action: SESSION_CREATE, Status: SUCCESS, SessionID: {session.id}, User: {request.user.username}")
```

---

## 초등학생 대상 콘텐츠 어휘 수준
학생에게 보여지는 텍스트에서 아래 어휘 사용 금지:
- **한자어/전문용어**: 사색가, 통찰력, 유일무이, 조망, 적재적소, 카리스마, 비전, 본능적, 전략적, 효율성, 역산
- **현실 부적합**: 기말고사(시험 없는 학교가 많음)
- **대체 방식**: 조망→한눈에 보기 / 적재적소→딱 맞는 순간 / 역산→거꾸로 계산

---

# Fortune 챗봇 아키텍처

## 챗봇 컨텍스트 참조 방식
- 교사/일반 모드와 별개 — 프로필의 사주 원국(natal_chart)만 기반
- `build_system_prompt()` 참조: `person_name`, `day_gan`(일간), `birth_year`
- DeepSeek-V3 모델, `StreamingHttpResponse`로 실시간 응답
- 세션당 최대 10회 질문, 7일 만료

## 관련 파일
- 모델: `fortune/models.py` (ChatSession, ChatMessage)
- 뷰: `fortune/views_chat.py`
- AI 통합: `fortune/utils/chat_ai.py`
- 시스템 프롬프트: `fortune/utils/chat_logic.py`
- 템플릿: `fortune/templates/fortune/chat_main.html`, `partials/chat_room.html`, `partials/chat_message.html`

---

# Enterprise Baseline (2026-02-15)

### A. Platform and Runtime
- Keep ASGI-first production runtime (`uvicorn`); verify command parity across `Procfile` and `nixpacks.toml`.
- Keep `DISABLE_SERVER_SIDE_CURSORS = True` in production (Neon = PgBouncer).
- Startup commands must be idempotent.

### B. Queue and Async Policy (DB Queue Standard)
- Default queue backend is DB queue. Do not assume Redis exists.
- Queue design must include retry budget, dead-letter policy, and operator-visible failure reason.
- Long-running/expensive jobs must be offloaded to DB queue workers, not synchronous paths.

### C. Reliability Pattern for AI Services
- Use timeout + bounded retry for all external AI calls.
- Circuit breaker must wrap the final consumer boundary for generator/stream patterns.
- Fallback message must be user-safe and non-technical.

### D. Security and Error Exposure
- Never return raw exception strings to users.
- Health endpoints must not expose internal DB/infra error details.
- Keep detailed error context in server logs only.

### E. Test and Verification Gate
- `python manage.py check` is required before merge/deploy.
- Maintain service health tests aligned with real URL/auth policy.
- Add pre-deploy and post-deploy smoke checks.

### F. Observability Baseline
- Log fields: `request_id`, `service`, `endpoint`, `status_code`, `latency_ms`
- Track AI failure rate and rate-limit hit rate as first-class operational metrics.

---

# 접근성 (A11y)

### 모달/드롭다운 키보드 접근성
- [ ] 모달 열릴 때 첫 번째 포커스 가능 요소에 자동 포커스
- [ ] ESC 키로 닫기 (`@keydown.escape`)
- [ ] 모달 외부 클릭으로 닫기 (`@click.outside`)
- [ ] 모달 닫힐 때 트리거 요소로 포커스 복귀

### 포커스 스타일
```css
/* base.html 전역 */
:focus-visible { outline: 2px solid #8b5cf6; outline-offset: 2px; }
```
`outline-none` 사용 시 반드시 대체 포커스 표시 함께 적용.

### 색 대비 최소 기준
- 본문: `text-gray-700` 이상 / 보조: `text-gray-500` 이상
- `text-gray-400`은 placeholder 등 장식 요소에만 허용

### 이미지
모든 `<img>`에 `alt` 필수. 장식용은 `alt=""`.

### 작업 완료 후 A11y 체크리스트
- [ ] 모달: ESC 닫기 + 포커스 트랩 동작
- [ ] Tab 키로 모든 인터랙티브 요소 순회 가능
- [ ] `text-gray-400` 이하 본문 텍스트 없음
- [ ] 이미지 alt 속성 누락 없음

---

# 이미지 최적화

### lazy-load 필수
```html
<!-- ✅ 뷰포트 밖 이미지에 loading="lazy" -->
<img src="..." alt="..." loading="lazy">
```
Above-the-fold(첫 화면) 이미지는 제외.

### Cloudinary 자동 최적화
```python
# ✅ f_auto,q_auto 변환으로 브라우저 최적 포맷 자동 선택
image_url = "https://res.cloudinary.com/.../upload/f_auto,q_auto/v123/image.jpg"
```
템플릿에서는 `{{ image_url|optimize }}` 사용 (`core/templatetags/cloudinary_extras.py`).

---

**마지막 업데이트:** 2026-02-21
