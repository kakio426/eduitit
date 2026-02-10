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

## Fortune 앱 - 일반 모드(general) 숨김 (2026-02-09)

**상태:** 비활성화 (교사 모드만 노출)

**재활성화 방법 (3곳 수정):**
1. `fortune/templates/fortune/saju_form.html` — `MODE_TOGGLE_START` ~ `MODE_TOGGLE_END` 주석 해제
2. `fortune/views.py` — `saju_view` 함수 내 `mode = 'teacher'` → `mode = data['mode']`로 복원
3. `fortune/views.py` — `saju_streaming_api` 함수 내 `get_prompt('teacher', ...)` → `get_prompt(data['mode'], ...)`로 복원
4. `fortune/views.py` — `saju_api_view` 함수 내 `mode = 'teacher'` → `mode = data['mode']`로 복원

**검색 키워드:** `일반 모드 임시 비활성화` 로 grep하면 모든 수정 지점 확인 가능

**참고:** `fortune/forms.py`의 MODE_CHOICES, `fortune/prompts.py`의 `get_general_prompt()`, 템플릿의 `generalTabs` 배열 등 백엔드/프롬프트 코드는 그대로 유지. UI와 뷰 진입점만 잠금.

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

---

**마지막 업데이트:** 2026-02-10
