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

### 관련 파일
- `fortune/prompts.py` - AI 프롬프트 (원본: `prompts_backup.py`)
- `fortune/templates/fortune/detail.html` - 보관함 상세 (마크다운 렌더링)
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

**마지막 업데이트:** 2026-02-08
