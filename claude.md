# Eduitit 프로젝트 - Claude Code 설정

## 개인 정보
- 이름: 유병주 (Byungju Yu)
- GitHub: yb941213
- 회사: SCHOOL

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
- `ensure_*` management command에서 Admin 관리 필드(service_type, display_order 등) 강제 덮어쓰기 금지 → Procfile이 매 배포마다 실행하므로 Admin 수정이 초기화됨

## 작업 완료 후 체크리스트
- [ ] Django Check 통과 (`python manage.py check`)
- [ ] console.log 및 debug print 제거
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
| DB 백업 | `python manage.py backup_db` | dumpdata JSON, Cron 가능 |

**context_processors 등록 순서** (두 settings 파일 모두 동일해야 함):
```python
'core.context_processors.visitor_counts',
'core.context_processors.toast_messages',
'core.context_processors.site_config',
'core.context_processors.seo_meta',
```

**VisitorLog 모델**: `user_agent`, `is_bot` 필드 보유. `get_visitor_stats(days, exclude_bots=True)`로 필터링.

## UI 레이아웃 표준

NavBar가 `fixed` 포지션이므로 모든 페이지에서 상단 여백 확보 필수.

```html
<!-- 표준 페이지 구조 -->
{% block content %}
<section class="pt-32 pb-20 px-4 min-h-screen">
    <div class="max-w-7xl mx-auto">
        <!-- 콘텐츠 -->
    </div>
</section>
{% endblock %}
```

- **표준**: `pt-32` (128px) - 모든 페이지
- **최소**: `pt-24` (Banner 없을 때)
- 전체 화면 모드 시 `z-index: 50+` 필요

---

# 반복 실수 방지 규칙

## 1. Django 설정 파일 동기화 (CRITICAL)

로컬(`settings.py`)과 프로덕션(`settings_production.py`)은 반드시 동기화.

**특히 주의할 설정**: `MIDDLEWARE`, `INSTALLED_APPS`, `TEMPLATES > context_processors`, `LOGGING`

```bash
diff config/settings.py config/settings_production.py
```

> **사례 (2026-02-02)**: 방문자 카운터가 계속 0명. 코드는 정상이었으나 `settings_production.py`에 미들웨어/context processor 누락이 원인.

## 2. Django views.py 필수 체크

500 에러의 3대 원인:

1. **`from django.conf import settings` import 누락** → `NameError`
2. **상수를 함수보다 아래에 정의** → `NameError` (상수는 파일 상단에)
3. **view 함수에서 `return` 문 누락** → `None` 반환 → 500 에러

> **사례 (ssambti 앱)**: 위 3가지가 동시 발생. import 추가 + 함수 순서 재배치 + return 문 추가로 해결.

> **사례 (2026-02-09, fortune 앱)**: `has_personal_api_key`를 `fortune/views.py`에서 import 없이 `@ratelimit` 콜백(`fortune_rate_h`, `fortune_rate_d`)에서 사용 → 일반 유저 요청 시 `NameError` → 500 에러. **superuser는 `or` 단축 평가로 해당 함수가 호출되지 않아 재현 불가**했음. 교훈: 데코레이터 콜백 안의 import 누락은 특정 조건에서만 터지므로, 코드 작성 시 **모든 함수 참조의 import 여부를 반드시 확인**할 것.

## 3. Railway 배포 환경 제약

- **`pg_dump` 없음** → `dumpdata` JSON 백업 사용 (`core/management/commands/backup_db.py`)
- **Neon PostgreSQL = PgBouncer** → `DISABLE_SERVER_SIDE_CURSORS = True` 설정 필요
- **Cron Job = 별도 컨테이너** → `raise` 대신 `sys.exit(0/1)` 사용
- **패키지 추가 시**: `requirements.txt` 즉시 반영, 시스템 바이너리 의존성 확인 → `nixpacks.toml`에 추가

## 4. select_related와 선택적 관계

```python
# ❌ UserProfile이 없는 User가 있으면 에러
.select_related('author__userprofile')

# ✅ 필수 관계만 select_related
.select_related('author')
# 선택적 관계는 템플릿에서: {% if post.author.userprofile %}
```

> **사례 (2026-02-04)**: 프로덕션에서 UserProfile 없는 User 존재 → 500 에러. 로컬에서는 재현 안 됨.

## 5. Alpine.js `<template x-if>` 안에 HTMX 넣지 않기

`<template x-if>`는 조건에 따라 DOM을 완전히 제거/추가하므로, 그 안의 HTMX 속성(`hx-trigger`, `hx-get` 등)이 제대로 초기화되지 않을 수 있다.

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

> **사례 (2026-02-08)**: studentmbti 세션 상세 페이지에서 전체화면 모드의 실시간 학생 목록이 항상 0명으로 표시. `<template x-if>` 안의 HTMX 폴링이 작동하지 않았음.

## 6. JSON 파싱 시 HTML 에러 페이지 감지

Django가 에러를 반환할 때 JSON 대신 HTML 에러 페이지를 보낼 수 있다. `JSON.parse()`에 HTML을 넘기면 `Unexpected token '<'` 에러 발생.

```javascript
// ❌ 위험: HTML 에러 페이지 파싱 시 크래시
const data = JSON.parse(element.textContent);

// ✅ 안전: HTML 감지 및 fallback
function safeJSONParse(text, fallback = null) {
    if (!text) return fallback;
    const trimmed = text.trim();
    
    // HTML 에러 페이지 감지
    if (trimmed.startsWith('<')) {
        console.error("HTML detected instead of JSON");
        return fallback;
    }
    
    try {
        return JSON.parse(trimmed);
    } catch (e) {
        console.error("JSON parse error:", e);
        return fallback;
    }
}

// 사용
const data = safeJSONParse(element.textContent, {});
```

**Django 템플릿에서 JSON 전달 시 주의사항**:
```django
{# ✅ json_script 필터 사용 #}
{{ chart|json_script:"chart-data" }}

{# ✅ View에서 chart가 None일 수 있으므로 항상 생성 #}
chart_data = {...} if chart_context else None
```

> **사례 (2026-02-08)**: Fortune 앱에서 캐싱된 사주 결과 불러온 후 일진 확인 시 `Unexpected token '<'` 에러. 원인: 캐싱 시 `chart` 데이터가 재생성되지 않아 템플릿에서 `None` → `json_script`가 빈 값 생성 → JavaScript에서 파싱 실패. 해결: (1) View에서 캐싱 여부와 관계없이 `chart_data` 항상 생성, (2) 모든 `JSON.parse()` → `safeJSONParse()`로 교체.

## 7. 초등학생 대상 콘텐츠 어휘 수준

학생에게 보여지는 텍스트에서 다음과 같은 어려운 단어 사용 금지:
- **한자어/전문용어**: 사색가, 통찰력, 유일무이, 조망, 적재적소, 카리스마, 비전, 본능적, 전략적, 효율성, 역산
- **현실과 맞지 않는 표현**: 기말고사(시험을 보지 않는 학교가 많음)
- **대체 방식**: 쉬운 우리말로 풀어쓰기 (조망→한눈에 보기, 적재적소→딱 맞는 순간, 역산→거꾸로 계산)

> **사례 (2026-02-08)**: studentmbti 결과지에서 초등학생이 이해하기 어려운 단어 다수 발견. 12개 이상의 어휘 순화 작업 진행.

## 8. SNS Sidebar 통합 패턴

다른 서비스에 SNS sidebar 추가 시:

**템플릿**: `max-w-7xl` 외부 컨테이너 → `flex flex-col lg:flex-row gap-6 items-start` → 메인(`flex-1 lg:max-w-3xl`) + 사이드바(`hidden lg:block w-[380px] flex-shrink-0`)

**뷰**: `from core.models import Post` import → `select_related('author')` + `prefetch_related('comments__author', 'likes')` + `annotate(like_count, comment_count)` → context에 `'posts': posts` 전달

---

# 앱별 이슈 분석 기록

## Fortune 앱 - 500 에러 분석 (2026-02-04)

### CRITICAL

**1. chart_context None 접근 (빈도: 40-50%)**
- 위치: `fortune/views.py:279-282, 389`
- 원인: 딕셔너리 생성이 삼항 연산자(`if chart_context`) 체크보다 먼저 평가됨
- 수정: `if chart_context is not None else None` 으로 명시적 체크
```python
# ❌ dict 생성이 먼저 평가 → TypeError
'chart': { chart_context['year']... } if chart_context else None

# ✅ None 체크를 먼저
if chart_context is not None:
    chart = { ... }
else:
    chart = None
```

**2. 데이터 구조 불일치 (빈도: 30-40%)**
- 위치: `fortune/views.py:206`, `fortune/utils/caching.py:21`
- `get_chart_context()` 반환값과 `get_natal_hash()` 기대값이 다른 구조
- 캐시 미스, DB 오염, 중복 방지 실패 유발

### HIGH

**3. 입력 검증 누락 (빈도: 3-5%)**
- 위치: `fortune/views.py:152-172`
- 날짜 범위 체크 없음 (month 13 등) → `ValueError` → `None` 반환 → 연쇄 에러

**4. API 에러 핸들링 부실 (빈도: 5-10%)**
- API 키 누락 시 generic exception, 빈 AI 응답 미처리, 503 미전파, 문자열 파싱 의존

### MEDIUM

**5. 템플릿 구문 에러** - `saju_form.html:1319` if/endif 짝 불일치
**6. 중복 함수 정의** - `caching.py`에 `get_user_context_hash()`, `get_cached_daily_fortune()` 2번씩 정의
**7. AI 타임아웃/빈 응답** - 타임아웃 없음, 빈 응답을 유효 결과로 저장

### 에러 패턴 빠른 참조

| 에러 | 위치 | 원인 | 수정 |
|------|------|------|------|
| `TypeError: 'NoneType' not subscriptable` | views.py:279,389 | chart_context None인데 dict 접근 | None 체크 선행 |
| 빈 natal_hash → 캐시 미스 | views.py:206, caching.py:21 | 데이터 구조 불일치 | 구조 표준화 |
| `ValueError` from invalid date | views.py:156-170 | 날짜 검증 없음 | 범위 검증 추가 |
| Generic 500 from AI failure | views.py:395-406 | 에러 핸들링 부실 | 타입별 예외 처리 |

### 수정 우선순위
1. chart_context null 체크 → 2. 데이터 구조 표준화 → 3. 템플릿 구문 → 4. 입력 검증 → 5. 에러 전파 → 6. 중복 함수 제거 → 7. 타임아웃

### 관련 파일
- `fortune/views.py` (779줄) - chart_context 버그
- `fortune/utils/caching.py` (246줄) - 중복/구조 불일치
- `fortune/api_views.py` (222줄) - API 엔드포인트
- `fortune/templates/fortune/saju_form.html` (2788줄) - 템플릿 구문 에러
- `fortune/models.py` (266줄)

---

## Fortune 앱 - 프롬프트/캐시/UI 이슈 (2026-02-08)

### 9. AI 프롬프트 SSOT 지시에는 반드시 볼드 유지

프롬프트 톤을 부드럽게 바꾸더라도, **SSOT 정체성 규칙에는 `**볼드**`를 유지**해야 AI가 강하게 따른다.

```
# ❌ 볼드 제거 → AI가 일간 오행을 무시하고 엉뚱한 비유 사용
선생님의 정체성은 반드시 상단 [SSOT Data]의 'Day' 첫 글자입니다.

# ✅ 볼드 유지 → AI가 정확히 일간 기준으로 해석
**정체성 고정**: 선생님의 정체성은 반드시 **[SSOT Data]의 일주(Day) 첫 글자(천간)**입니다.
```

또한 출력 템플릿에서 "자연물 비유"라고만 쓰면 AI가 아무 자연물이나 매칭한다. **"일간 오행에 맞는 자연물"**이라고 제약을 걸어야 함.

> **사례**: 신금(辛金)인데 "맑은 샘물"로 묘사 → 출력 템플릿에 "일간 오행에 맞는" 제약이 빠졌기 때문. 오행-자연물 매핑(`금=보석/쇠, 수=물/비`)을 명시하여 해결.

### 10. detail.html `const` 재할당 크래시 (마크다운 미렌더링)

```javascript
// ❌ const 변수에 재할당 → TypeError → 마크다운 렌더링 전체 실패
const rawText = outputArea.innerText;
rawText = rawText.replace(...);  // try/catch 밖이라 크래시

// ✅ escapejs로 순수 문자열 전달 (saju_form.html과 동일 방식)
const rawMarkdown = "{{ item.result_text|escapejs }}";
marked.parse(rawMarkdown);
```

> **사례**: 보관함 상세 페이지에서 마크다운이 raw 텍스트로 보임. `const` 재할당 에러가 `try/catch` 밖에서 발생하여 스크립트 전체 중단.

### 11. 보관함 삭제 시 localStorage 캐시 동기화 필수

DB에서 `FortuneResult`를 삭제해도 브라우저 `localStorage`의 사주 캐시는 남아있어서, 같은 조건으로 분석하면 옛 결과가 반환된다.

**삭제 시 함께 제거해야 할 캐시 키 패턴**:
- `saju_result_cache_*`, `saju_result_v2_*`
- `daily_saju_cache_*`, `daily_saju_v2_*`
- `pendingSajuResult`, `lastSajuInput`

> **사례**: 프롬프트를 개선했는데 캐시된 옛 결과만 계속 표시됨. 보관함 삭제 시 localStorage 캐시도 함께 삭제하도록 수정.

### 12. AI 프롬프트에서 "제목 쓰지 마세요" 지시는 `## ` 헤더까지 생략시킴

프롬프트에 "별도 제목은 쓰지 마세요"라고 쓰면 AI가 출력 템플릿의 `## ` 섹션 헤더까지 모두 생략한다. 서론만 금지하고 싶으면 명확히 분리해야 함.

```
# ❌ AI가 ## 헤더를 모두 생략 → 결과 글에 중간 제목 없음
서론이나 별도 제목은 쓰지 마세요.

# ✅ 서론만 금지, 섹션 헤더는 필수로 지시
서론을 쓰지 마세요. 각 섹션은 반드시 아래 출력 템플릿의 `## ` 제목을 그대로 포함하세요.
```

> **사례 (2026-02-08)**: 일반사주 결과에 핵심 요약, 원국 분석, 기질/성격 등 중간 제목이 전혀 표시되지 않음. "별도 제목은 쓰지 마세요" 지시가 원인.

### 13. JS `element.className = ...` 전체 교체 시 레이아웃 클래스 유실

`className`을 통째로 교체하면 원래 HTML에 있던 `inline-flex`, `items-center`, `gap-1` 등 레이아웃 클래스가 사라진다. `classList.add/remove`를 쓰거나, 전체 교체 시 레이아웃 클래스를 반드시 포함해야 함.

```javascript
// ❌ 레이아웃 클래스 유실 → 텍스트 중앙 정렬 깨짐
badge.className = `text-sm py-1 px-3 rounded-full ${colorClass}`;

// ✅ 레이아웃 클래스 포함
badge.className = `inline-flex items-center justify-center gap-1 text-sm py-1 px-3 rounded-full ${colorClass}`;
```

> **사례 (2026-02-08)**: 신금(辛金) 배지 텍스트가 중앙 정렬되지 않음. JS에서 `badge.className`을 교체하면서 `items-center`, `gap-1` 등이 빠진 것이 원인.

### 14. Django Admin N+1 쿼리 — 새 모델 추가 시 반드시 체크

`ModelAdmin`에서 `list_display`에 FK 필드나 `.count()` 메서드를 넣으면 행마다 쿼리가 발생한다.

```python
# ❌ list_display에 FK 필드 → 행마다 SELECT
list_display = ['user', 'product', 'created_at']
# 결과: N+1 쿼리 (100행이면 200+ 쿼리)

# ✅ get_queryset에 select_related 추가
def get_queryset(self, request):
    return super().get_queryset(request).select_related('user', 'product')
```

```python
# ❌ .count() 메서드 → 행마다 COUNT 쿼리
def like_count(self, obj):
    return obj.likes.count()

# ✅ annotate로 단일 쿼리 집계 + admin_order_field로 정렬 지원
def get_queryset(self, request):
    return super().get_queryset(request).annotate(
        _like_count=Count('likes', distinct=True)
    )

def like_count_display(self, obj):
    return obj._like_count
like_count_display.admin_order_field = '_like_count'
```

**새 앱/모델 추가 시 체크리스트**:
- [ ] `list_display`에 FK 필드가 있으면 → `get_queryset`에 `select_related` 추가
- [ ] `list_display`에 `.count()` 메서드가 있으면 → `annotate` + `_display` 메서드로 교체
- [ ] User FK에는 `raw_id_fields` 사용 (드롭다운 대신 ID 입력)
- [ ] 규칙 4번 주의: `author__userprofile` 같은 선택적 관계는 `select_related` 금지

> **사례 (2026-02-08)**: 10개 앱의 admin에 select_related/annotate 일괄 적용. Fortune 앱 11개 모델 신규 등록 시에도 동일 패턴 적용.

### 관련 파일
- `fortune/prompts.py` - AI 프롬프트 (원본: `prompts_backup.py`)
- `fortune/templates/fortune/detail.html` - 보관함 상세 (마크다운 렌더링, 이미지 저장)
- `fortune/templates/fortune/history.html` - 보관함 목록 (삭제 + 캐시)
- `fortune/templates/fortune/saju_form.html` - 사주 입력/결과 화면

---

## SNS Sidebar 통합 상세 가이드 (2026-02-04)

### 올바른 레이아웃 구조

```html
{% block content %}
<section class="pt-32 pb-20 px-6 min-h-screen bg-[#E0E5EC]">
    <div class="max-w-7xl mx-auto">
        <div class="flex flex-col lg:flex-row gap-6 items-start">
            <!-- 메인 콘텐츠 -->
            <div class="flex-1 w-full lg:max-w-3xl">
                {{ 메인 콘텐츠 }}
            </div>
            <!-- SNS 사이드바 (데스크톱만) -->
            <div class="hidden lg:block w-[380px] flex-shrink-0">
                <div class="relative">
                    {% include 'core/partials/sns_widget.html' %}
                </div>
            </div>
        </div>
    </div>
</section>
{% endblock %}
```

### 올바른 뷰 쿼리

```python
from core.models import Post
from django.db.models import Count

# 선택적 관계(UserProfile)는 select_related 제외
try:
    posts = Post.objects.select_related(
        'author'
    ).prefetch_related(
        'comments__author',
        'likes'
    ).annotate(
        like_count=Count('likes', distinct=True),
        comment_count=Count('comments', distinct=True)
    ).order_by('-created_at')[:20]
except Exception as e:
    posts = []

context['posts'] = posts
```

### 흔한 실수 5가지

1. **Flex 구조 없이 위젯만 추가** → 레이아웃 깨짐 → Flex 컨테이너로 감싸기
2. **context에 `posts` 누락** → 위젯 빈 화면 → `'posts': posts` 추가
3. **N+1 쿼리** → `Post.objects.all()[:20]` → select_related/prefetch_related 사용
4. **`items-start` 누락** → 사이드바 stretch → 추가
5. **모바일 반응형 미처리** → `hidden lg:block` 추가

### 관련 파일
- SNS 위젯: `core/templates/core/partials/sns_widget.html`
- 게시글: `core/templates/core/partials/post_list.html`, `post_item.html`
- 모델/뷰: `core/models.py` (Post, Comment), `core/views.py`
- HTMX: 작성(`hx-post="/post/create/"`), 좋아요(`hx-post="/post/<id>/like/"`), 댓글(`hx-post="/post/<id>/comment/"`)

### 적용 현황
- 쌤BTI: 완료 (커밋 3223af2, 92e5f44, hotfix 6b90179)
- Fortune: 미적용

### 향후 개선
- Post 모델에 `service` 필드 추가 → 서비스별 게시글 필터링
- HTMX 무한 스크롤 페이지네이션

---

# 스킬 & 워크플로우

## 설치된 스킬

### Frontend
| 스킬 | 용도 |
|------|------|
| `alpinejs-best-practices` | Alpine.js 상태 관리 및 DOM 조작 |
| `htmx-power-usage` | HTMX 비동기 통신 및 부분 렌더링 |
| `vanilla-js-dom-master` | 순수 JS 기술 |
| `tailwind-design-system` | Tailwind 컴포넌트 설계 |
| `ui-ux-pro-max` | UX 디자인 원칙 및 애니메이션 |
| `web-design-guidelines` | UI 가이드라인 및 웹 접근성 |

### Backend
| 스킬 | 용도 |
|------|------|
| `django-architecture-pro` | Service Layer 및 Fat Model 분리 |
| `api-design-principles` | REST/HTMX 대응 API 설계 |
| `async-python-django` | 비동기 View 및 Celery 패턴 |
| `python-testing-django` | PyTest-Django 테스트 패턴 |

## 에이전트
| 에이전트 | 용도 |
|----------|------|
| `planner` | 복잡한 기능 계획 (DB 마이그레이션 등) |
| `django-specialist` | Django View, Model, Template 전문 |
| `frontend-developer` | Alpine.js, HTMX, Tailwind UI |
| `code-reviewer` | 코드 품질 및 Django 보안 리뷰 |

## 워크플로우
```
# 프론트엔드
/frontend [요청사항] → frontend-developer → /verify

# 백엔드
/plan [요청사항] → Django 구현 → /verify
```

## 커맨드
| 커맨드 | 용도 |
|--------|------|
| `/plan` | 작업 계획 수립 |
| `/commit-push-pr` | 커밋→푸시→PR |
| `/verify` | `python manage.py check` 및 검증 |
| `/review` | 보안 및 Performance 리뷰 |
| `/simplify` | 복잡한 로직 단순화 |
| `/handoff` | 세션 종료 시 갈무리 |

---

# 임시 비활성화 기능

## Fortune 앱 - 일반 모드(general) (2026-02-09 비활성화 → 2026-02-13 복구)

**상태:** 활성화 (교사 모드 + 일반 모드 모두 노출)

**이력:**
- 2026-02-09: 일반 모드 임시 비활성화 (커밋 15b5737)
- 2026-02-13: 일반 모드 복구 완료 (UI 주석 해제 + views.py 3곳 원복)

---

## Chess 앱 - JS 게임 로직 주의사항 (2026-02-09)

### 15. JS `var` 호이스팅 — 같은 함수 내 변수 재선언 금지

`var`로 같은 이름을 재선언하면 호이스팅에 의해 하나의 변수로 합쳐져, 이후 분기에서 예상과 다른 값을 참조한다.

```javascript
// ❌ var piece가 2번 선언 → 호이스팅으로 하나로 합쳐짐
function onSquareClick(square) {
    var piece = game.get(square);         // 클릭한 칸
    if (selectedSquare) {
        var piece = game.get(selectedSquare); // 이전 선택 칸으로 덮어씀
        // move 실패 시 fall-through...
    }
    // 여기서 piece는 selectedSquare 기준 → 잘못된 값
    if (!piece || piece.color !== game.turn()) { ... }
}

// ✅ 다른 이름 사용
var selectedPiece = game.get(selectedSquare);
```

> **사례 (2026-02-09)**: 체스 앱에서 기물 선택 후 잘못된 칸 클릭 → 새 기물 선택이 안 되는 버그. `var piece` 재선언이 원인.

### 16. Undo/Reset 시 모든 파생 상태 동기화 필수

게임에서 `undo()` 또는 `reset()` 호출 시, 핵심 상태뿐 아니라 **파생 UI 상태**도 반드시 동기화해야 한다.

**체크리스트** (체스 기준):
- [ ] `capturedPieces` 배열에서 되돌린 기물 제거 + `renderCapturedPieces()` 호출
- [ ] `lastMove` 갱신 (남은 기록의 마지막 수 또는 null) + `highlightLastMove()` 호출
- [ ] `moveHistory` 배열 pop + `updateMoveHistory()` 호출
- [ ] Reset 시 `renderCapturedPieces()` 호출 (initGame이 배열만 비우고 DOM은 안 건드림)

> **사례 (2026-02-09)**: 되돌리기 후 잡은 기물 패널에 이미 돌아간 기물이 표시되고, 하이라이트가 잘못된 칸에 남아있었음.

### 17. Web Audio API — AudioContext 공유 필수

`playSound()` 호출마다 `new AudioContext()`를 생성하면 브라우저 제한(보통 6개)에 도달하여 사운드가 멈춘다. 전역에 하나를 생성하고 `suspended` 상태일 때 `resume()` 호출.

```javascript
// ❌ 매번 생성
function playSound() {
    var ctx = new AudioContext();
}

// ✅ 전역 공유
var sharedAudioContext = null;
function getAudioContext() {
    if (!sharedAudioContext) {
        sharedAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (sharedAudioContext.state === 'suspended') sharedAudioContext.resume();
    return sharedAudioContext;
}
```

### 관련 파일
- `chess/static/chess/js/chess_logic.js` - 게임 로직 전체
- `chess/templates/chess/play.html` - 게임 UI (모달, 하이라이트 CSS)
- `chess/templates/chess/index.html` - 로비 페이지

### 18. CSS `transform` 충돌 — 전역 hover가 모달 centering을 파괴

`base.html`의 `.clay-card:hover { transform: translateY(-4px) scale(1.005) }`처럼 전역 hover 스타일이 있으면, `fixed` + `transform: translate(-50%, -50%)`로 중앙 정렬된 모달의 위치를 **완전히 덮어쓴다**. CSS `transform`은 개별 값이 아닌 **전체가 교체**되기 때문이다.

**증상**: 모달 위에 마우스를 올리면 오른쪽 아래로 튀어나가고, 마우스가 벗어나면 돌아오면서 반짝거림(flicker) 발생.

```css
/* ❌ base.html 전역 스타일이 모달 centering을 파괴 */
.clay-card:hover {
    transform: translateY(-4px) scale(1.005);  /* translate(-50%,-50%) 사라짐 */
}

/* ✅ 모달에 고유 클래스 부여 후 hover transform 고정 */
.tool-modal.clay-card:hover {
    transform: translate(-50%, -50%) !important;
}
```

**체크리스트** (fixed + transform 중앙 정렬 모달 만들 때):
- [ ] 모달에 `clay-card`, `clay-btn` 등 전역 hover transform이 있는 클래스를 사용하고 있는가?
- [ ] 사용한다면, 모달 전용 클래스로 hover transform을 `translate(-50%, -50%)`로 고정했는가?

> **사례 (2026-02-09)**: tools 페이지 모달이 `.clay-card:hover`의 `translateY(-4px)`에 의해 centering이 깨지면서 반짝거림 발생. `.tool-modal.clay-card:hover`로 transform 고정하여 해결.

---

## 소셜 로그인 / Gunicorn / allauth 이슈 (2026-02-10)

### 19. allauth ACCOUNT_SIGNUP_FORM_CLASS vs SOCIALACCOUNT_FORMS 구분 (CRITICAL)

allauth 65.x에서 커스텀 가입 폼을 만들 때, **`SOCIALACCOUNT_FORMS`를 사용하면 안 된다.**

```python
# ❌ SOCIALACCOUNT_FORMS로 폼을 교체하면 try_save()/save() 없어서 500 에러
SOCIALACCOUNT_FORMS = {
    'signup': 'core.signup_forms.CustomSignupForm',
}

# ❌ allauth.socialaccount.forms.SignupForm을 직접 상속하면 순환 import → 크래시
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
class CustomSignupForm(SocialSignupForm): ...

# ✅ ACCOUNT_SIGNUP_FORM_CLASS만 사용 (allauth가 자동 상속 체인 구성)
ACCOUNT_SIGNUP_FORM_CLASS = 'core.signup_forms.CustomSignupForm'
# → allauth 내부: SignupForm(BaseSignupForm(CustomSignupForm))
# → try_save() → save() → custom_signup() → signup() 정상 작동
```

**CustomSignupForm은 `forms.Form`을 상속하고, 추가 필드 + `signup(request, user)` 메서드만 정의:**
```python
class CustomSignupForm(forms.Form):
    nickname = forms.CharField(...)
    def signup(self, request, user):
        # 추가 프로필 저장 로직
```

> **사례**: `SOCIALACCOUNT_FORMS`로 `forms.Form` 기반 폼을 지정 → allauth가 `form.try_save()` 호출 → `AttributeError` → 500. 직접 상속으로 우회 시도 → 순환 import → 서버 크래시. `ACCOUNT_SIGNUP_FORM_CLASS`만 사용하여 해결.

### 20. Gunicorn sync worker 고갈 — AI API 호출 시 필수 설정

기본 Gunicorn 설정(`gunicorn config.wsgi`)은 **worker 1개 + sync 모드**. AI API처럼 30~60초 걸리는 동기 호출이 있으면 그 동안 **서버 전체가 먹통**.

```bash
# ❌ 기본 설정 (worker 1개) — AI 1건 처리 중 모든 요청 499
gunicorn config.wsgi --timeout 120

# ✅ gthread 모드 (동시 12개 요청 처리)
gunicorn config.wsgi --workers 3 --threads 4 --worker-class gthread --timeout 120
```

**증상**: `/fortune` POST 처리 중 `/accounts/login/`, `/accounts/kakao/login/callback/` 등 모든 경로에서 499 에러 발생.

> **사례**: 사주 분석 API가 54초간 worker를 점유 → 같은 시간대 모든 요청(로그인, 가입, 다른 서비스)이 499로 실패.

### 21. OnboardingMiddleware — OAuth 콜백 경로 허용 필수

`OnboardingMiddleware`의 `allowed_paths`에 `/accounts/` 전체를 포함해야 소셜 로그인 콜백이 차단되지 않음.

```python
# ❌ /accounts/logout/ 만 허용 → OAuth 콜백 차단
allowed_paths = ['/accounts/logout/', ...]

# ✅ /accounts/ 전체 허용
allowed_paths = ['/accounts/', ...]
```

> **사례**: 카카오/네이버 로그인 콜백(`/accounts/kakao/login/callback/`)이 `allowed_paths`에 없어서, 인증 완료 후 `/update-email/`로 강제 리다이렉트 → 가입 실패.

### 22. 커스텀 가입 폼 widget readonly — 소셜 제공자 이메일 미제공 시 입력 불가

```python
# ❌ 기본 widget에 readonly → 이메일 없으면 빈 칸 + 입력 불가 → 가입 불가
email = forms.EmailField(widget=forms.EmailInput(attrs={'readonly': 'readonly'}))

# ✅ 기본은 편집 가능, 소셜 이메일 있을 때만 __init__에서 readonly 설정
email = forms.EmailField(widget=forms.EmailInput(attrs={...}))
# __init__에서:
if self.sociallogin and self.sociallogin.user.email:
    self.fields['email'].widget.attrs['readonly'] = True
```

> **사례**: 카카오 로그인 시 이메일 미제공 → 가입 폼 이메일 칸이 readonly + 빈 값 → 필수 필드라 제출 불가 → 모든 신규 가입 차단.

### 23. settings_production.py 서버 시작 시 DB 조작 주의

`sync_site_domain()` 같은 시작 시 실행 함수에서 `SocialApp.objects.all().delete()` 등 **전체 삭제 쿼리**를 넣지 않기. 매 배포마다 불필요한 DB 조작이 발생하고, 레이스 컨디션 위험.

### 24. SESSION_SAVE_EVERY_REQUEST 성능 영향

`SESSION_SAVE_EVERY_REQUEST = True`는 **모든 HTTP 요청마다 DB write**를 발생시킴. 트래픽이 많은 서비스에서는 `False`로 설정하고, `SESSION_COOKIE_AGE`를 충분히 길게(24시간+) 설정.

### 관련 파일
- `core/signup_forms.py` — 소셜 가입 커스텀 폼 (nickname + signup)
- `core/middleware.py` — OnboardingMiddleware (allowed_paths)
- `config/settings_production.py` — allauth, 세션, Gunicorn 관련 설정
- `Procfile`, `nixpacks.toml` — Gunicorn worker 설정

---

## 홈 화면 레이아웃 & 카테고리 시스템 (2026-02-10)

### 25. Django 템플릿 태그 `{% %}` 안에 줄바꿈 금지

`{% if ... %}` 태그의 조건이 길어도 **절대 줄바꿈하면 안 된다**. Django 템플릿 파서는 `{%`와 `%}` 사이의 줄바꿈을 인식하지 못해 `TemplateSyntaxError: Invalid block tag 'endif'`를 발생시킨다.

```html
<!-- ❌ 줄바꿈 → TemplateSyntaxError -->
{% if user.is_authenticated and
    user.userprofile.nickname %}

<!-- ✅ 한 줄로 -->
{% if user.is_authenticated and user.userprofile.nickname %}
```

> **사례 (2026-02-10)**: `base.html` 피드백 위젯의 `{% if %}` 태그가 두 줄에 걸쳐 있어 홈 페이지 전체가 500 에러. git rebase 충돌 해결 과정에서 기존에 우연히 동작하던 줄바꿈이 깨짐.

### 26. 홈 화면 레이아웃 구조 (모바일/PC 분리)

**모바일**: 서비스 카드 above the fold → SNS 미리보기(최신 2개) → "소통창 열기" 아코디언
**PC**: SNS 사이드바(왼쪽, sticky) + 메인 콘텐츠(오른쪽)

```
모바일 스크롤 간섭 해결 핵심:
- SNS를 별도 스크롤 컨테이너(overflow-auto)에 넣지 않기
- 페이지 본문 흐름에 통합 (overflow-visible)
- 아코디언으로 펼치기/접기 → x-show + x-transition 사용
```

**관련 파일:**
- `core/templates/core/home.html` — 비로그인 홈
- `core/templates/core/home_authenticated.html` — 로그인 홈
- `core/templates/core/partials/sns_widget.html` — PC 전용 사이드바
- `core/templates/core/partials/sns_widget_mobile.html` — 모바일 전용 (아코디언 내부)

### 27. 서비스 카테고리 시스템

`products/models.py`의 `SERVICE_CHOICES`로 관리. Django Admin `list_editable`로 바로 수정 가능.

| 코드 | 이름 | 탭 색상 | 아이콘 색상 |
|------|------|---------|------------|
| `classroom` | 운영과 수업 | 파란색 | `text-blue-500` |
| `work` | 업무경감 | 초록색 | `text-emerald-500` |
| `game` | 게임모음 | 빨간색 | `text-red-500` |
| `counsel` | 상담·운세 | 보라색 | `text-violet-500` |
| `edutech` | 에듀테크 | 시안색 | `text-cyan-500` |
| `etc` | 기타 | 회색 | `text-slate-500` |

**카테고리 추가/변경 시 수정 필요한 파일 (4곳):**
1. `products/models.py` — `SERVICE_CHOICES` + 마이그레이션
2. `core/templates/core/home.html` — CSS `.cat-{code}` + 탭 버튼
3. `core/templates/core/home_authenticated.html` — 위와 동일
4. `core/templates/core/includes/card_product.html` — 아이콘/라벨 색상 분기

**카드 컴포넌트 `card_product.html`:**
- `is_filtered=True` 전달 시: 외부 `x-show` 래퍼와 함께 사용 (Alpine.js 필터링 모드)
- 미전달 시: 원래 구조 유지 (다른 페이지 호환)
- `{{ product.get_service_type_display }}` — 한글 카테고리명 표시

### 28. DB 데이터 변경 시 반드시 데이터 마이그레이션 작성

Django shell로 로컬 DB만 수동 수정하면 **프로덕션에는 반영되지 않는다**. DB 데이터를 변경할 때는 반드시 `RunPython` 데이터 마이그레이션을 함께 작성해야 한다.

```python
# ❌ Django shell로만 변경 → 프로덕션 미반영
Product.objects.filter(id=121).update(service_type='classroom')

# ✅ 데이터 마이그레이션 작성
# python manage.py makemigrations products --empty --name update_xxx_data
def update_data(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(id=121).update(service_type='classroom')

migrations.RunPython(update_data, migrations.RunPython.noop)
```

**적용 대상:** 카테고리 변경, 기본값 일괄 변경, 필드명 변경에 따른 기존 데이터 매핑 등 모든 DB 레코드 수정

### 29. git rebase 충돌 해결 시 주의사항

충돌 해결 후 반드시:
1. `{% if %}` / `{% endif %}` 밸런스 확인
2. 줄바꿈으로 분리된 템플릿 태그가 없는지 확인
3. `python manage.py check` + 실제 페이지 렌더링 테스트

### 30. Procfile ensure_* 명령어 — Admin 관리 필드 덮어쓰기 금지 (CRITICAL)

Procfile의 `ensure_*` 명령어는 **매 배포(git push)마다 실행**된다. 이 명령어 안에서 `service_type`, `display_order`, `color_theme` 등 **Admin에서 수동 관리하는 필드를 강제 변경하면, 배포할 때마다 Admin 수정 내용이 초기화**된다.

**단, 초기 개발 중 서비스 카테고리(`service_type`)가 변경되거나 치명적인 오류가 있는 경우에는 조건부 보정 로직을 포함해야 한다.**

```python
# ❌ 매 배포마다 service_type 덮어씀 → Admin 수정 무효화
if ssambti.service_type != 'game':
    ssambti.service_type = 'game'

# ❌ 조건 없이 무조건 save → Admin 변경 전부 리셋
product.service_type = 'tool'
product.save()

# ✅ ensure 명령어는 "존재 보장"만 담당, Admin 관리 필드는 건드리지 않기
if not product.is_active:
    product.is_active = True
    needs_update = True
if needs_update:
    product.save()

# ✅ 단, 초기 개발 중 서비스 카테고리(service_type)가 변경되거나 치명적인 오류가 있는 경우에는 조건부 보정 로직을 포함해야 한다.
if product.service_type != 'counsel':  # 잘못된 값일 때만 수정
    product.service_type = 'counsel'
    product.save()
```

**ensure_* 명령어 작성 규칙:**
- 상품이 없을 때 **생성**하는 것만 담당
- 이미 존재하는 상품의 `service_type`, `display_order`, `color_theme` 등은 **절대 덮어쓰지 않기**
- `is_active`, `external_url` 등 기능적 필수값만 조건부로 보정

**현재 Procfile 실행 순서:**
```
migrate --noinput → ensure_ssambti → ensure_studentmbti → ensure_notebooklm → check_visitors → gunicorn
```

> **사례 (2026-02-10)**: `ensure_ssambti`가 매 배포마다 `service_type='game'`으로, `ensure_studentmbti`가 `service_type='tool'`로 강제 변경 → Admin에서 카테고리를 수정해도 다음 push에서 원복됨. service_type 강제 변경 로직 제거로 해결.

---

## 새 서비스(앱) 추가 시 체크리스트 (2026-02-10)

### 31. 서비스 시작 버튼 URL 라우팅 — preview_modal.html 수정 필수

`products/templates/products/partials/preview_modal.html`의 "시작하기" 버튼은 **product.title 기반 조건문**으로 URL을 결정한다. 새 서비스를 추가할 때 여기에 `{% elif %}` 분기를 추가하지 않으면, 시작 버튼을 눌러도 홈으로 돌아간다.

```html
<!-- preview_modal.html 라인 86 — 한 줄로 작성해야 함 (규칙 25) -->
{% if product.external_url %}{{ product.external_url }}{% elif product.title == '쌤BTI' %}{% url 'ssambti:main' %}{% elif product.title == '간편 수합' %}{% url 'collect:landing' %}{% elif product.title == '교사 백과사전' %}{% url 'encyclopedia:landing' %}{% else %}{% url 'home' %}{% endif %}
```

**새 서비스 추가 시:**
- [ ] `{% elif product.title == '서비스명' %}{% url 'app:landing' %}` 분기 추가
- [ ] `external_url` 사용하는 외부 서비스는 분기 불필요 (첫 번째 조건에서 처리됨)

> **사례 (2026-02-12)**: '간편 수합', '교사 백과사전', '학교 예약 시스템' 등 새 서비스를 추가할 때 `preview_modal.html`에 등록을 누락하여 시작 버튼이 작동하지 않는 현상이 반복됨. 신규 앱 생성 시 체크리스트 5번 항목(`preview_modal.html` 분기 추가)을 반드시 준수할 것. (현재: '학교 예약 시스템' -> `reservations:reservation_index`)

### 32. ensure_* 명령어 — defaults의 service_type은 반드시 SERVICE_CHOICES 값 사용

`get_or_create(defaults={...})`에서 `service_type`을 지정할 때, 반드시 `products/models.py`의 `SERVICE_CHOICES`에 있는 값을 사용해야 한다.

**현재 유효한 값:** `classroom`, `work`, `game`, `counsel`, `edutech`, `etc`

```python
# ❌ SERVICE_CHOICES에 없는 값 → Admin에서 표시 이상
'service_type': 'guide',    # ← 없는 값!
'service_type': 'tool',     # ← 없는 값!

# ✅ 유효한 값만 사용
'service_type': 'edutech',  # ← SERVICE_CHOICES에 존재
```

> **사례 (2026-02-10)**: `ensure_notebooklm`이 `service_type='guide'`로 생성 → Admin에서 카테고리가 빈 값으로 표시. 데이터 마이그레이션으로 `'edutech'`로 수정.

### 33. 새 Django 앱 추가 시 전체 체크리스트

| 단계 | 파일 | 작업 |
|------|------|------|
| 1 | 앱 디렉토리 | `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, `apps.py` 생성 |
| 2 | `config/settings.py` | `INSTALLED_APPS`에 추가 |
| 3 | `config/settings_production.py` | `INSTALLED_APPS`에 동일하게 추가 (규칙 1) |
| 4 | `config/urls.py` | `path('앱/', include('앱.urls', namespace='앱'))` 추가 |
| 5 | `preview_modal.html` | 시작 버튼 URL 분기 추가 (규칙 31) |
| 6 | `ensure_*` 명령어 | Product 생성 보장, Admin 필드 덮어쓰기 금지 (규칙 30) |
| 7 | `settings_production.py` | `run_startup_tasks()`에 `call_command('ensure_*')` 추가 |
| 8 | `Procfile` | `ensure_*` 명령어 체인에 추가 |
| 9 | `nixpacks.toml` | Procfile과 동기화 |
| 10 | `admin.py` | `select_related` + `annotate` + `raw_id_fields` (규칙 14) |
| 11 | 마이그레이션 | `makemigrations` + `migrate` |
| 12 | 검증 | `python manage.py check` |

**현재 Procfile 실행 순서:**
```
migrate → ensure_ssambti → ensure_studentmbti → ensure_notebooklm → ensure_collect → ensure_reservations → check_visitors → gunicorn
```

### 34. 새로운 서비스 개발 시 로컬 데이터베이스 데이터 확인

로컬 환경에서는 데이터베이스(`db.sqlite3`)가 비어 있거나 개발 환경마다 데이터가 다를 수 있다. 새로운 서비스를 개발할 때 소스 코드만 작성하고 DB 레코드(`Product` 모델 등)를 생성하지 않으면, UI에서 해당 서비스가 아예 보이지 않거나 오류가 발생할 수 있다.

- **증상**: 앱 코드는 존재하지만 홈 화면이나 상세 페이지에서 서비스 정보가 표시되지 않음.
- **원인**: `get_collect_service()`와 같은 함수가 DB에서 데이터를 찾지 못해 `None`을 반환함.
- **해결**: 개발 초기 단계에서 `create_xxx_data.py` 같은 임시 스크립트를 작성하여 로컬 DB에 필수 데이터를 넣거나, `python manage.py ensure_xxx` 명령어를 실행하여 데이터를 생성할 것.

### 35. Django 템플릿의 변수 명명 규칙 제한 (CRITICAL)

Django 템플릿 엔진은 **언더바(`_`)로 시작하는 속성이나 변수에 대한 직접 접근을 허용하지 않는다.** 파이썬의 관례상 `_`로 시작하는 멤버는 Private으로 간주되기 때문이다.

- **증상**: `TemplateSyntaxError: Variables and attributes may not begin with underscores` 발생.
- **원인**: View에서 `.annotate(_count=Count(...))`와 같이 언더바로 시작하는 이름으로 데이터를 넘기고, 템플릿에서 `{{ obj._count }}`로 접근하려 할 때 발생.
- **해결**: 템플릿에서 사용할 변수나 속성 이름에는 절대 언더바를 접두어로 사용하지 말 것. (예: `_submission_count` 대신 `num_submissions` 또는 `submission_count` 사용)

### 36. Alpine.js 상태 초기화와 Django 폼 에러 연동

Alpine.js로 UI 상태(모달, 아코디언 등)를 관리할 때, 폼 제출 후 에러가 발생하면 **UI가 열린 상태로 유지**되어야 사용자가 에러를 인지할 수 있다.

```html
<!-- ❌ 에러가 있어도 닫힘 → 사용자는 "왜 안 되지?" 혼란 -->
<div x-data="{ open: false }">

<!-- ✅ 에러가 있으면 열린 상태로 초기화 -->
<div x-data="{ open: {% if form.errors %}true{% else %}false{% endif %} }">
```

> **사례 (2026-02-11)**: 수합 요청 생성 폼이 에러 발생 시 닫힌 채로 리로드되어, 사용자가 요청이 생성되지 않은 이유를 알 수 없었음.

### 37. ModelForm 필수 필드 누락 주의

`forms.py`의 `ModelForm`에서 `fields` 리스트에 포함된 필드가 **템플릿(HTML)에서 렌더링되지 않으면**, 사용자는 입력할 방법이 없는데 서버는 `required` 에러를 낸다.

**해결책**:
1. 사용자에게 입력을 받을 필요가 없는 필드(예: `max_file_size_mb`)는 `fields` 리스트에서 **제거**하거나 `exclude` 처리.
2. 반드시 필요하지만 사용자 입력이 불필요하면 `HiddenInput` 위젯 사용 또는 모델 `default` 값 활용.

```python
# ❌ 폼 필드엔 있는데 HTML엔 없음 → 유효성 검사 실패
fields = ['title', 'max_file_size_mb'] 

# ✅ 사용자 입력 불필요하면 필드 제거 (모델 default 사용)
fields = ['title']
```

> **사례 (2026-02-11)**: `max_file_size_mb`가 폼 필드에는 있었으나 템플릿에 없어, "필수 항목입니다" 에러와 함께 생성 실패. 사용자에게 굳이 입력받을 필요 없는 기술적 설정이라 폼 필드에서 제거하여 해결.

### 38. 사용자에게 기술적 설정 강요 금지 (Sensible Defaults)

사용자(특히 비개발자)에게 "파일 최대 크기(MB)", "청크 사이즈" 같은 기술적 설정을 묻지 말 것. 시스템이 합리적인 기본값(Sensible Default)을 제공하고, 꼭 필요한 경우에만 고급 설정으로 숨겨서 제공한다.

> **사례 (2026-02-11)**: 교사들에게 "파일당 최대 크기"를 입력하게 하는 것은 불필요한 인지 부하. 기본값 30MB로 고정하고 입력란 제거.

### 39. 모바일 카드 오버플로우 — `box-sizing` + 그림자 + `.clay-card` 제약 (CRITICAL)

모바일 브라우저에서 Tailwind CDN의 preflight(`box-sizing: border-box`)가 미적용되어 `padding`과 `border`가 요소 크기에 추가되거나, 깊은 `box-shadow`가 뷰포트 너비를 초과하여 오버플로우를 유발할 수 있다.

**해결 (`base.html`에 적용):**

1. **전역 `box-sizing: border-box` 명시** — 상단에 별도 `<style>`로 선언
2. **모바일 그림자 최적화** — 모바일에서는 좌우 그림자 오프셋을 0으로 설정(`box-shadow: 0 4px 12px ...`)
3. **`.clay-card`에 `max-width: 100%; overflow: hidden;`** — 부모 너비를 넘지 못하게 강제

```css
/* base.html */
*, *::before, *::after { box-sizing: border-box; }

.clay-card {
    max-width: 100%;
    overflow: hidden;
    /* 모바일: 좌우 오프셋 0으로 뷰포트 확장 방지 */
    box-shadow: 0 4px 12px rgba(163, 177, 198, 0.4), 0 -2px 8px rgba(255, 255, 255, 0.6);
}

@media (min-width: 768px) {
    .clay-card { box-shadow: 8px 8px 16px rgba(163, 177, 198, 0.5), -8px -8px 16px rgba(255, 255, 255, 0.6); }
}
```

> **사례 (2026-02-11)**: studentmbti, collect 모바일 랜딩에서 카드가 오른쪽으로 튀어남. 근본 원인은 `content-box` 동작과 넓은 수평 그림자였음.

---

## 40. AI 로깅 표준 가이드 (Monitoring)

사후 추적 및 AI 에이전트의 자가 수복을 용이하게 하기 위해 모든 주요 액션은 표준화된 포맷으로 로깅한다.

**표준 포맷:** `[AppName] Action: ACTION_NAME, Status: SUCCESS/FAIL, Key: Value, ...`

```python
# ✅ 예시: 세션 생성 로깅
logger.info(f"[StudentMBTI] Action: SESSION_CREATE, Status: SUCCESS, SessionID: {session.id}, User: {request.user.username}, Type: {test_type}")
```

## 41. 메인 컴포넌트 디자인 (Claymorphism)

Eduitit의 메인 서비스 페이지(퀴즈, 대시보드 메인 카드 등)는 **Claymorphism** 디자인을 기본으로 한다.

- **클래스**: `.clay-card` 필수 적용
- **여백**: SIS Rule 8.271에 따라 모바일과 데스크톱 패딩 구분 (`p-6 md:p-14`)
- **그림자**: 전역 태그의 hover 효과 활용 (`.clay-card:hover`)

## 42. Django Template filter와 whitespace 주의

JavaScript 안에서 Django 템플릿 변수를 사용할 때, 필터(`|`) 주위에 공백을 넣으면(예: `{{ var | length }}`) 일부 JS 린터나 에디터에서 구문 오류로 오인할 수 있다.

- **권장**: `{{ questions|length }}` (공백 없이 밀착)
- **이유**: 문자열 주입 시 linter의 불필요한 노이즈 제거 및 코드 간결성 확보

---

## 43. 스크립트 중복 방지 및 JS 데이터 전달 표준

### 43.1 라이브러리 중복 로드 금지 (Duplication)
`base.html`에서 로드된 라이브러리(HTMX, Alpine.js 등)를 자식 템플릿이나 Partial에서 다시 로드하지 않는다.
- **증상**: 모달 내용 중복, 이벤트 리스너 중복 바인딩, UI 오동작 (예: 모달이 두 번 열림).
- **해결**: 모든 공통 라이브러리는 `base.html` 상단에서만 관리한다.

### 43.2 JS 데이터 전달: `json_script` 활용
템플릿 태그(`{% for %}` 등)를 `<script>` 블록 안에 직접 써서 데이터를 구성하지 않는다. 이는 IDE 린트 에러를 유발하고 보안상 취약할 수 있다.
- **해석**: `{{ data|json_script:"id" }}`를 사용하여 HTML에 JSON을 심고, JS에서 `JSON.parse(document.getElementById('id').textContent)`로 가져온다.

### 43.3 인라인 스타일의 템플릿 태그 지양
HTML `style` 속성 안에 `{{ var }}`를 직접 넣으면 에디터 파서가 문법 오류로 인식한다.
- **해결**: Alpine.js의 `:style` 바인딩을 사용하거나, CSS 변수를 활용한다.

```html
<!-- ✅ 권장 패턴 -->
<div x-data="{ color: '{{ theme_color|escapejs }}' }" :style="{ backgroundColor: color }">...</div>
```

## 44. Django Template Tag Fragmentation 및 줄바꿈 금지 (Critical)

에이전트가 가독성을 위해 Django 템플릿 태그(`{% %}`, `{{ }}`)의 앞뒤나 내부를 임의로 줄바꿈하여 로직을 깨뜨리는 행위를 엄격히 금지한다.

- **증상**: `{% if %}`와 `{{ var }}` 사이를 줄바꿈하여 텍스트가 깨지거나, HTML 속성/JavaScript 내부에서 구문 오류(500 에러) 유발.
- **해결**: 복잡한 로직이 포함된 템플릿 태그는 가급적 **한 줄(One-liner)**로 유지하며, 에디터의 자동 줄바꿈 기능에 의존하지 않고 원본의 연속성을 보존한다.
- **예시**:
    *   ❌ (나쁜 예):
        ```html
        <span>
          {% if user.nickname %}{{ user.nickname }} {% else %}{{ user.username
           }}{% endif %}
        </span>
        ```
    *   ✅ (좋은 예):
        ```html
        <span>{% if user.nickname %}{{ user.nickname }}{% else %}{{ user.username }}{% endif %}</span>
        ```

---

---

**마지막 업데이트:** 2026-02-12 12:30

## 45. 비회원 관리 접근 권한 — 세션 대신 UUID(Management ID) 사용 (CRITICAL)

비회원이 제출한 데이터(예: 간편 수합)를 나중에 다시 수정/삭제해야 할 때, **세션(Session) 기반 권한은 브라우저를 닫으면 증발**한다.

**해결 패턴**:
1. 모델에 고유한 `management_id` (UUID) 필드를 추가한다.
2. 관리 페이지 URL에 이 UUID를 포함한다: `/manage/<uuid:management_id>/`
3. 뷰에서는 세션 체크 대신 이 UUID의 존재 여부만으로 권한을 위임한다 (URL 자체가 토큰 역할).
4. 사용자에게 **"이 주소를 복사해두면 나중에 다시 와서 관리할 수 있다"**고 안내하고 '주소 복사' 버튼을 제공한다.

> **사례 (2026-02-12)**: 간편 수합(Collect) 앱에서 브라우저를 닫으면 수정이 불가능하던 문제를 세션에서 UUID(management_id) 기반으로 전환하여 해결.

## 46. Alpine.js를 이용한 간편한 UI 피드백 (주소 복사 등)

텍스트 복사 후 "복사됨!" 메시지를 잠시 보여주는 등의 작은 피드백은 Alpine.js의 `x-data`와 `setTimeout`을 활용하면 간결하게 구현 가능하다.

```html
<div x-data="{ copied: false }">
    <button @click="navigator.clipboard.writeText(window.location.href); copied = true; setTimeout(() => copied = false, 2000)">
        <span x-show="!copied">주소 복사</span>
        <span x-show="copied">복사됨!</span>
    </button>
</div>
```

> **사례 (2026-02-12)**: 제출물 관리 페이지에서 관리용 URL 복사 기능을 제공하여 사용자 편의성을 높임.

## 47. Cloudinary 비이미지 파일 처리 (resource_type='raw') (CRITICAL)

Cloudinary 기본 설정은 `resource_type='image'`입니다. HWP, XLSX, PDF, ZIP 등 이미지가 아닌 일반 파일을 업로드하려면 **`RawMediaCloudinaryStorage`**를 사용해야 합니다.

```python
# ❌ Invalid image file 에러 발생 (이미지로 처리를 시도함)
from cloudinary_storage.storage import VideoMediaCloudinaryStorage # 또는 기본 Storage
file = models.FileField(storage=VideoMediaCloudinaryStorage())

# ✅ 일반 파일용 스토리지 사용
from cloudinary_storage.storage import RawMediaCloudinaryStorage
file = models.FileField(storage=RawMediaCloudinaryStorage())
```

> **사례 (2026-02-11)**: 간편 수합 서비스에서 한글(hwp)이나 엑셀 파일을 올릴 때 "Invalid image file" 에러와 함께 500 에러 발생. `RawMediaCloudinaryStorage`로 교체하여 해결.

## 48. JS 내 Django 템플릿 태그 사용 시 공백/필터 주의

JavaScript 코드 안에서 `{{ value }}`를 사용할 때, 필터나 공백 처리가 잘못되면 JS 문법 에러(`SyntaxError`)가 발생하여 해당 블록 전체가 작동하지 않을 수 있습니다.

```javascript
/* ❌ 줄바꿈이나 공백이 JS 문법을 파괴할 수 있음 */
var maxSize = {{ req.max_file_size_mb |default: 30 }}; 

/* ✅ 괄호나 따옴표로 감싸거나, 간단한 필터만 사용 */
const maxMB = parseInt('{{ req.max_file_size_mb|default:30 }}');
```

> **사례 (2026-02-11)**: 제출 페이지에서 JS 문법 에러로 Alpine.js 초기화가 중단되어 버튼이 비활성화되는 버그 발생. 템플릿 태그를 한 줄로 정리하여 해결.

---

# 앱별 이슈 분석 기록 (계속)

## Reservations 앱 - 커스텀 교시 및 보안 URL (2026-02-12)

### 49. 공공용 URL의 무작위성 확보 (Security/Random Slugs)

사용자(교사)가 직접 주소를 정하게 하면 `hyunam`, `seoul` 등 추측하기 쉬운 단어를 사용하여 타인이 무단으로 접속하거나 장난을 칠 우려가 있다.

- **증상**: 학교 이름을 슬러그로 쓸 때 타 학교 학생이 주소를 맞혀서 예약을 엉망으로 만듦.
- **해결**: `models.py`의 `save()` 메서드에서 `uuid.uuid4().hex[:8]`를 사용해 추측 불가능한 슬러그를 자동 생성하고, UI에서 사용자의 직접 수정을 제한한다.
- **Short URL**: 보안 URL이 길어 불편하므로 `/go/<id>/` 형태의 짧은 전용 리다이렉트 링크를 제공한다.

### 50. 커스텀 교시(Period Labels) 관리 전략

학교마다 "1교시", "5교시A", "특강팀" 등 사용하는 이름과 교시 수가 다르다.

- **패턴**: `SchoolConfig` 모델에 `period_labels` (TextField, CSV) 필드를 추가.
- **작동**: 콤마(`,`)로 구분된 문자열을 `get_period_list()` 메서드로 리스트화하여, 예약 그리드(Row)를 동적으로 생성.
- **주의**: 그리드 렌더링 시 "몇 번째 교시"라는 숫자 대신 "Label과 ID"를 매칭하여 렌더링해야 함. (`{% if s.period == p.id %}`)

### 51. allauth v65.x+ 설정 마이그레이션 (Monitoring)

서버 구동 시 또는 마이그레이션 시 Deprecation 경고 및 Critical Error 발생 대응.

-   `ACCOUNT_LOGIN_METHODS = {'email', 'username'}`
-   `ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*']` (**필수 필드는 `*`를 붙여야 함**)
-   프로덕션 `settings_production.py`와 로컬 `settings.py` 모두 동기화 필수.

---

## 52. JS/Alpine 속성 내 Django 템플릿 태그 따옴표 중복 처리 (CRITICAL)

JavaScript 또는 Alpine.js 속성(예: `@click`, `:class`) 내부에 Django 템플릿 태그를 사용할 때, 내부 필터 인자의 따옴표가 외부 JavaScript 문자열의 따옴표와 충돌하면 구문 오류(SyntaxError)가 발생하여 500 에러나 JS 실행 중단을 유발한다.

```javascript
/* ❌ 500 에러 유발: 문자열 리터럴('...') 내부에서 date 필터의 작은따옴표('...')가 충돌 */
@click="openBooking(..., '{{ target_date|date:'Y-m-d' }}', ...)"

/* ✅ 해결: 내부 인자에는 쌍따옴표(") 사용 */
@click="openBooking(..., '{{ target_date|date:"Y-m-d" }}', ...)"
```

**증상**: 브라우저 콘솔에는 `SyntaxError: Unexpected token`이 나타나며, 서버 로그에는 `TemplateSyntaxError`가 찍힐 수 있다. 특히 PC에서는 잘 되고 모바일 전용 블록(`lg:hidden`) 내부에서만 이 실수가 있을 경우 원인을 찾기 매우 어렵다.

**사례 (2026-02-12)**: 예약 시스템 모바일 레이아웃 작업 중 `@click` 핸들러 내 `date:'Y-m-d'`의 작은따옴표 중복 사용으로 인해 모바일에서만 500 에러 발생.

## 53. HTMX 단독 버튼의 데이터 전송 (hx-vals 사용)

HTMX 버튼이 `<form>` 태그 밖에 단독으로 있을 때는 내부의 `<input type="hidden">` 값을 자동으로 인식하지 못한다. 이 경우 반드시 `hx-vals` 속성을 사용하여 데이터를 명시적으로 전송해야 한다.

-   **옳은 예**: `<button hx-post="..." hx-vals='{"room_id": "{{ room.id }}"}'>`
-   **나쁜 예**: `<button hx-post="..."><input type="hidden" name="name" value="..."></button>`

## 54. 부분 템플릿(Partial) 렌더링 시 컨텍스트 관리

HTMX 요청으로 그리드나 목록만 별도로 업데이트(렌더링)할 때, 해당 템플릿 안에서 사용되는 모든 변수(예: `school`, `config` 등)를 뷰(View)의 `render()` 호출 시점에 반드시 포함해야 한다. 변수가 누락되면 URL 생성 오류가 나거나 화면이 제대로 그려지지 않는다.

## 55. 모바일 레이아웃 검증 (360px 기준)

UI를 구현할 때는 항상 모바일 표준 너비인 360px에서 화면이 깨지거나 요소가 겹치지 않는지 먼저 확인한다. `flex-1`, `min-w-0`, `truncate`와 같은 CSS 클래스를 적절히 사용하여 좁은 화면에서도 레이아웃이 유연하게 대응하도록 설계한다.

## 56. HTMX 보안 토큰(CSRF) 전역 처리 및 이중 검증 (CRITICAL)

장고의 보안 정책상 모든 `POST` 요청에는 CSRF 토큰이 필수다. HTMX 단독 버튼 등에서 토큰 누락으로 인한 403 Forbidden 에러를 방지하기 위해 다음 원칙을 엄격히 준수한다.

1.  **전역 처리 (base.html)**: `document.addEventListener('htmx:configRequest', ...)`를 사용하여 모든 HTMX 요청 헤더에 `X-CSRFToken`을 자동 주입한다.
    *   **주의**: `document.body`에 리스너를 걸면 body가 로드되기 전 시점에 에러가 발생하므로 반드시 **`document` 레벨**에 걸어야 한다.
2.  **이중 검증 (결정적 조치)**: 블랙아웃 삭제, 예약 취소와 같이 **데이터가 삭제되는 중요 버튼**은 전역 설정을 100% 신뢰하지 말고 `hx-vals`에 `csrfmiddlewaretoken`을 명시적으로 포함하여 "실패 없는 삭제"를 보장한다.
    ```html
    /* ✅ 중요 버튼 예시: 전역 설정 외에 hx-vals로 한 번 더 확실하게 처리 */
    <button hx-post="..." hx-vals='{"item_id": "1", "csrfmiddlewaretoken": "{{ csrf_token }}"}'>
    ```
3.  **컨테이너 전략**: 대시보드와 같이 HTMX 작업이 많은 곳은 부모 컨테이너(`div`)에 `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'`를 미리 선언하여 자식 요소들이 자동으로 토큰을 상속받게 설계한다.

- **사례 (2026-02-12)**: `document.body` 리스너의 타이밍 문제와 전역 설정 누락으로 인해 삭제 버튼이 무반응이었던 문제를 이 삼중 방어(전역 + 컨테이너 + 개별) 전략으로 최종 해결.

## 57. 전체 데이터 생애주기(CRUD) 완결성 준수 (CRITICAL)

기능을 구현할 때는 '생성'뿐만 아니라 '수정'과 '삭제'가 포함된 전체 생애주기를 반드시 고려한다. "삭제 후 다시 등록하세요"와 같은 방식은 지양하고, 해당 페이지 내에서 즉시 수정/삭제가 가능하도록 설계한다.

- **원칙**: 모든 데이터 관리 기능에는 **[등록 - 조회 - 수정 - 삭제]**가 하나의 세트로 구현되어야 한다.
- **수정(Update)**: 파일 업로드 서비스의 경우, 삭제 후 재등록이 아닌 **새 파일 선택 시 즉시 교체**되는 로직을 지원한다.
- **삭제(Delete)**: 사용자가 실수로 등록했을 때를 대비해, 수정 화면이나 상세 화면에는 반드시 명확한 **삭제 버튼(확인 모달 포함)**을 배치한다.
- **사례 (2026-02-12)**: `collect` 앱의 제출물 수정 페이지에서 파일 교체 로직과 삭제 버튼이 누락되어 사용자가 불편을 겪었던 사례를 바탕으로 이 규칙을 강화함.

## 58. 초기 데이터 생성 및 화면 렌더링 시 중복 방지 (CRITICAL)

`ensure_` 커맨드나 초기화 로직을 통해 데이터를 생성할 때, 중복 실행으로 인한 데이터 누적을 원천 봉쇄해야 한다. 또한, 뷰(View) 레벨에서도 예기치 않은 중복 데이터가 섞여 들어오지 않도록 방어 로직을 갖춘다.

- **멱등성(Idempotency) 보장**: 초기 데이터 생성 스크립트(`management/commands`)는 여러 번 실행해도 결과가 동일해야 한다. `feature.objects.create(...)` 대신 반드시 `get_or_create` 또는 `update_or_create`를 사용한다. 필요하다면 기존 데이터를 `clear()` 하고 다시 생성한다.
- **뷰 레벨 방어**: DB에 이미 중복 데이터가 쌓였을 가능성을 대비하여, `landing` 페이지나 목록 조회 뷰에서는 **중복 제거(deduplication) 로직**을 통해 화면에 동일한 내용이 반복 출력되는 참사를 막는다.
- **사례 (2026-02-12)**: `Collect` 앱 랜딩 페이지의 [주요 기능] 섹션이 이유 없이 2번씩 반복 출력되는 현상 발생. 뷰에서 `title` 기반 중복 제거 로직을 추가하여 해결함.

---

## 59. 데이터 수합 시 보안 및 책임 안내 의무화 (CRITICAL)

파일, 링크, 텍스트 등 외부로부터 데이터를 수합하는 기능을 구현할 때는 개인정보 보호뿐만 아니라 공문서, 내부 자료 등 보안이 필요한 데이터의 유출을 방지하기 위해 명시적인 경고와 **서비스 면책(Disclaimer)** 문구를 반드시 포함해야 한다.

- **안내 배치**: 데이터 제출 화면(`submit`) 및 서비스 소개 페이지(`landing`)에 눈에 띄는 색상(Red 계열)과 경고 아이콘을 사용하여 배치한다.
- **문구 포함**: 
    1. **개인정보**: 주민번호, 연락처 등 민감 정보 포함 지양 안내.
    2. **보안자료**: 외부 유출이 금지된 **공문서, 내부 대외비 자료** 수합 지양 및 주의 촉구.
    3. **면책문구**: 데이터 관리 및 유출에 대한 책임은 당사자(요청자/제출자)에게 있으며 서비스는 책임을 지지 않는다는 점을 명시.
- **사례 (2026-02-12)**: `Collect` 앱에 개인정보 및 공문서 유출 주의, 서비스 면책 안내를 추가하여 법적/운영적 리스크를 최소화함.

---

## 60. JS Base64 해시 캐시 키 — 해시 길이와 키 순서에 의한 충돌 (CRITICAL)

`btoa(encodeURIComponent(rawKey)).substring(0, N)` 으로 캐시 키를 생성할 때, **구분자(mode 등)가 키 뒤쪽에 배치되고 해시 길이(N)가 짧으면** 서로 다른 모드가 동일한 해시를 생성한다.

Base64는 3바이트 → 4문자 변환이므로, `substring(0, 24)`는 입력의 **처음 18바이트만** 반영. 한글 이름(글자당 3바이트)과 생년월일이 이미 18바이트를 소진하면, 뒤쪽의 mode 차이(`teacher` vs `general`)가 해시에 반영되지 않는다.

```javascript
// ❌ mode가 마지막 + 해시 짧음 → 모드별 동일 해시 → 캐시 충돌
const keyParts = [name, gender, year, month, day, hour, calendar, mode]; // mode가 뒤쪽
const hash = btoa(unescape(encodeURIComponent(keyParts.join('|')))).substring(0, 24); // 18바이트만

// ✅ mode를 첫 번째로 + 해시 길이 충분히
const keyParts = [mode, name, gender, year, month, day, hour, calendar]; // mode가 앞쪽
const hash = btoa(unescape(encodeURIComponent(keyParts.join('|')))).substring(0, 32); // 24바이트
```

**캐시 키 변경 시 체크리스트:**
- [ ] 구분해야 할 필드(mode, type 등)를 키 배열의 **앞쪽**에 배치
- [ ] 해시 길이를 전체 키의 고유성을 보장할 만큼 충분히 설정 (최소 32자 권장)
- [ ] 캐시 키 접두사(prefix)를 버전업하여 기존 잘못된 캐시 무효화 (`v2_` → `v3_`)
- [ ] 페이지 로드 시 구버전 캐시 자동 삭제 로직 추가

> **사례 (2026-02-13)**: Fortune 앱에서 교사 사주(teacher)와 일반 사주(general) 결과가 동일한 localStorage 캐시 키로 저장되어, 일반 모드를 선택해도 교사 모드 결과가 반환됨. mode를 키 첫 번째로 이동 + 해시 32자로 확장 + `v2_` → `v3_` 접두사 변경으로 해결.

## 61. Alpine.js CDN — unpkg 대신 jsdelivr 사용

`unpkg.com`의 `@3.x.x` 같은 semver 와일드카드는 간헐적으로 해석 실패할 수 있다. Alpine.js가 로드되지 않으면 `x-data`, `@click`, `x-show` 등이 모두 작동하지 않아 UI 전체가 먹통이 된다.

```html
<!-- ❌ unpkg + 와일드카드 → 간헐적 로딩 실패 가능 -->
<script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>

<!-- ✅ jsdelivr + 안정적인 범위 지정 -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
```

**Alpine.js 의존 UI에 대한 방어 전략:**
- 핵심 네비게이션(로그인 드롭다운 등)은 `onclick` 속성으로 vanilla JS fallback 추가
- `if(!window.Alpine){ fallbackFunction() }` 패턴 사용

> **사례 (2026-02-13)**: PC 데스크톱 사용자 드롭다운 메뉴가 Alpine.js 미로드 시 클릭 무반응. jsdelivr CDN 변경 + vanilla JS fallback 추가로 해결.

## 62. Django 템플릿에 dict vs object 속성 접근 주의

Django 템플릿은 `{{ obj.attr }}` 구문으로 dict의 키와 object의 속성 모두 접근 가능하지만, **`{% if obj.role == 'user' %}` 같은 비교는 dict와 object 모두 작동하는 반면, `render_to_string`에 plain dict를 넘기면 `.created_at` 같은 추가 속성이 없어 다른 부분에서 에러**가 발생할 수 있다.

```python
# ❌ dict는 template에서 .role은 접근 가능하지만 .created_at이 없으면 에러
return render(request, 'chat_message.html', {'message': {'role': 'system', 'content': '...'}})

# ✅ SimpleNamespace로 속성 접근 보장
from types import SimpleNamespace
msg = SimpleNamespace(role='assistant', content='...', created_at=timezone.now())
return render(request, 'chat_message.html', {'message': msg})
```

> **사례 (2026-02-13)**: 챗봇 턴 초과 시 dict를 넘겨 template에서 `message.created_at` 접근 시 빈 값 렌더링. SimpleNamespace로 교체하여 해결.

## 63. HTMX 중복 로드 금지 (base.html과 자식 템플릿)

`base.html`에서 이미 HTMX를 로드했는데, `{% block extra_js %}`에서 다시 `<script src="htmx.org">` 를 로드하면 HTMX가 두 번 초기화되어 이벤트 핸들러 중복, 예기치 않은 동작이 발생할 수 있다.

> **사례 (2026-02-13)**: `home.html`에서 HTMX를 중복 로드하여 제거.

---

# Fortune 챗봇 아키텍처 (2026-02-13)

## 챗봇 컨텍스트 참조 방식
- 교사/일반 모드와 **별개** — 프로필의 사주 원국(natal_chart)만 기반
- `build_system_prompt()` 참조 데이터: person_name, day_gan(일간), birth_year
- DeepSeek-V3 모델 사용, StreamingHttpResponse로 실시간 응답
- 세션당 최대 10회 질문, 7일 만료

## 관련 파일
- 모델: `fortune/models.py` (ChatSession, ChatMessage)
- 뷰: `fortune/views_chat.py`
- AI 통합: `fortune/utils/chat_ai.py` (DeepSeek streaming)
- 시스템 프롬프트: `fortune/utils/chat_logic.py`
- 템플릿: `fortune/templates/fortune/chat_main.html`, `partials/chat_room.html`, `partials/chat_message.html`

---

**마지막 업데이트:** 2026-02-13
