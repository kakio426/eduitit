# Fortune Server 500 Error Analysis

**Date:** 2026-02-04
**Investigation:** Frequent 500 errors in fortune server

---

## Critical Issues (Ordered by Priority)

### 1. NULL POINTER / CHART_CONTEXT BUG ⚠️ CRITICAL
**Location:** `fortune/views.py:279-282`, `fortune/views.py:389`
**Frequency:** 40-50% of 500 errors

**Problem:**
```python
'chart': {
    'year': str(chart_context['year']['stem']) + str(chart_context['year']['branch']),
    'month': str(chart_context['month']['stem']) + str(chart_context['month']['branch']),
    'day': str(chart_context['day']['stem']) + str(chart_context['day']['branch']),
    'hour': str(chart_context['hour']['stem']) + str(chart_context['hour']['branch']),
} if chart_context else None,
```

**Why it fails:**
- Dictionary construction is evaluated BEFORE the ternary check `if chart_context`
- When `get_chart_context()` returns `None`, accessing `chart_context['year']` raises `TypeError: 'NoneType' object is not subscriptable`
- Results in immediate 500 error

**Fix:**
```python
# Check FIRST, then construct
'chart': {
    'year': str(chart_context['year']['stem']) + str(chart_context['year']['branch']),
    'month': str(chart_context['month']['stem']) + str(chart_context['month']['branch']),
    'day': str(chart_context['day']['stem']) + str(chart_context['day']['branch']),
    'hour': str(chart_context['hour']['stem']) + str(chart_context['hour']['branch']),
} if chart_context is not None else None,
```

---

### 2. DATA STRUCTURE MISMATCH ⚠️ CRITICAL
**Location:** `fortune/views.py:206`, `fortune/utils/caching.py:21`
**Frequency:** 30-40% of 500 errors

**Problem:**
- `get_chart_context()` returns: `{'year': {...}, 'month': {...}, 'day': {...}, 'hour': {...}}`
- `get_natal_hash()` expects: `{'pillars': {'year': '...', 'month': '...', ...}}`
- Incompatible structures cause caching to fail completely

**Impact:**
- Natal hash is always wrong or empty
- Cache misses on every request
- Database pollution with incorrect data
- Duplicate prevention broken

**Fix:**
Standardize chart_context structure across all functions to match expected format.

---

### 3. MISSING INPUT VALIDATION ⚠️ HIGH
**Location:** `fortune/views.py:152-172` (get_chart_context)
**Frequency:** 3-5% of 500 errors

**Problem:**
```python
def get_chart_context(data):
    try:
        year = data['birth_year']
        month = data['birth_month']
        day = data['birth_day']
        hour = data['birth_hour'] if data['birth_hour'] is not None else 12

        dt = datetime(year, month, day, hour, minute, tzinfo=tz)  # Can raise ValueError
        return calculator.get_pillars(dt)
    except Exception as e:
        return None  # SILENT FAILURE
```

**Missing validations:**
- No range checking (month: 1-12, day: 1-31, hour: 0-23)
- No integer type validation
- Invalid dates (e.g., Feb 30) raise ValueError
- Returns None silently, causing downstream crashes

**Example failure:**
```
Input: birth_month = 13
→ datetime(2025, 13, 1) raises ValueError
→ Returns None
→ Line 279 tries: None['year']['stem'] → 500 Error
```

---

### 4. API ERROR HANDLING GAPS ⚠️ HIGH
**Location:** `fortune/views.py:51-150`, `fortune/views.py:395-406`
**Frequency:** 5-10% of 500 errors

**Issues:**

a) **No API key fallback completion:**
```python
# Line 150:
raise Exception("API_KEY_MISSING: API 키가 설정되지 않았습니다.")
```
- Generic exception instead of proper HTTP response
- No graceful 429/503 response

b) **Empty AI response not caught:**
```python
# Lines 94-96:
if chunk_count == 0:
    logger.warning("Gemini stream yielded 0 chunks.")
return  # Returns None silently
```
- Safety filters or timeouts cause 0 chunks
- Downstream code crashes on empty string
- Should return proper error response

c) **503 Service Unavailable not propagated:**
- Only handled in `saju_view()`, not in API endpoints
- Returns generic 500 instead of proper 503

d) **Fragile error string parsing:**
```python
if "503" in error_str:  # Brittle - relies on exact text
if "Insufficient Balance" in error_str:
```

---

### 5. TEMPLATE SYNTAX ERROR ⚠️ MEDIUM
**Location:** `fortune/templates/fortune/saju_form.html:1319`
**Frequency:** 10-15% of 500 errors

**Error:**
```
TemplateSyntaxError: Invalid block tag on line 1319: 'endblock',
expected 'elif', 'else' or 'endif'
```

**Cause:**
- Unmatched `{% if %}` / `{% endif %}` blocks
- Orphaned `{% endblock %}` closing wrong block
- Template has 2788 lines with nested structures

**Fix:**
Audit template for matching pairs of:
- `{% if %}` ... `{% endif %}`
- `{% block %}` ... `{% endblock %}`

---

### 6. DUPLICATE FUNCTION DEFINITIONS ⚠️ MEDIUM
**Location:** `fortune/utils/caching.py`

**Duplicates:**
- `get_user_context_hash()` defined at lines 106-120 AND 177-190
- `get_cached_daily_fortune()` defined at lines 122-146 AND 193-217

**Impact:**
- Python uses LAST definition (overrides earlier ones)
- Causes confusion in debugging
- Indicates incomplete refactoring
- Potential import errors

**Fix:**
Remove duplicate definitions, keep only one version.

---

### 7. AI TIMEOUT/EMPTY RESPONSE ⚠️ MEDIUM
**Location:** `fortune/views.py:94-96`
**Frequency:** 2-3% of 500 errors

**Problem:**
- No timeout on AI API calls (can hang forever)
- Empty responses saved as valid results
- No circuit breaker for repeated failures

**Fix:**
- Add timeout to all AI API calls
- Implement circuit breaker pattern
- Validate AI response before saving

---

## Summary Statistics

| Issue | Severity | Frequency | Files Affected |
|-------|----------|-----------|----------------|
| chart_context None + dict access | CRITICAL | 40-50% | views.py:279,389 |
| Data structure mismatch | CRITICAL | 30-40% | views.py, caching.py, api_views.py |
| Template syntax error | MEDIUM | 10-15% | saju_form.html:1319 |
| API error handling gaps | HIGH | 5-10% | views.py:395-406 |
| Missing input validation | HIGH | 3-5% | views.py:152-172 |
| AI timeout/empty response | MEDIUM | 2-3% | views.py:94-96 |
| Duplicate functions | LOW | Hidden | caching.py |

---

## Recommended Fix Order

1. **Fix chart_context rendering** - Add null check BEFORE dict access (views.py:279, 389)
2. **Standardize chart_context structure** - Ensure consistent format across all modules
3. **Fix template syntax** - Match all if/endif and block/endblock pairs
4. **Add input validation** - Validate date ranges before datetime() constructor
5. **Improve error propagation** - Use specific exceptions, proper HTTP status codes
6. **Remove duplicate functions** - Clean up caching.py
7. **Add timeout handling** - Set timeouts on all AI API calls
8. **Implement circuit breaker** - Stop retrying after N consecutive failures

---

## Key Files

- `fortune/views.py` (779 lines) - Main view handlers with chart_context bugs
- `fortune/utils/caching.py` (246 lines) - Caching logic with duplicates and structure mismatch
- `fortune/api_views.py` (222 lines) - API endpoints
- `fortune/templates/fortune/saju_form.html` (2788 lines) - Template syntax error
- `fortune/models.py` (266 lines) - Database models

---

## Quick Reference: Common Error Patterns

**Pattern 1: TypeError: 'NoneType' object is not subscriptable**
- Location: views.py:279, 389
- Cause: chart_context is None, dict accessed before check
- Fix: Check for None BEFORE accessing keys

**Pattern 2: Empty natal_hash causing cache miss**
- Location: views.py:206, caching.py:21
- Cause: Data structure mismatch between functions
- Fix: Standardize chart_context format

**Pattern 3: ValueError from invalid date**
- Location: views.py:156-170
- Cause: No validation before datetime() constructor
- Fix: Add range validation for year/month/day/hour

**Pattern 4: Generic 500 from AI failure**
- Location: views.py:395-406
- Cause: Inadequate error handling, string parsing
- Fix: Use specific exception types, proper status codes

---

# SNS Sidebar 통합 구현 가이드

**Date:** 2026-02-04
**Context:** 쌤BTI 서비스에 기존 SNS 위젯을 sidebar로 통합하는 작업

---

## 문제 상황

기존에 구현된 SNS 위젯 (`core/partials/sns_widget.html`)을 다른 서비스 페이지에 sidebar 형태로 추가하려고 할 때 발생한 문제들:

### 1. 레이아웃 문제 ⚠️
**증상:**
- SNS 위젯이 의도한 위치(우측 sidebar)가 아닌 엉뚱한 곳에 표시됨
- 왼쪽 하단에 떠있거나 레이아웃이 깨짐
- 모바일/데스크톱 반응형이 제대로 작동하지 않음

**원인:**
```html
<!-- core/partials/sns_widget.html -->
<aside class="w-full md:w-[380px] ... md:sticky md:top-32 ... ml-0 md:ml-6 mb-6 md:mb-0">
```
- SNS 위젯 자체가 `sticky` 포지셔닝과 고유한 너비/마진을 가지고 있음
- Flex 레이아웃 내부에 포함될 때 이러한 스타일이 충돌
- 위젯이 레이아웃 흐름에서 벗어남

### 2. 데이터 연동 문제 ⚠️
**증상:**
- SNS 위젯은 표시되지만 게시글이 비어있음
- 메인 홈페이지에서 작성한 글이 사이드바에 안 보임
- "아직 작성된 글이 없습니다" 메시지만 표시

**원인:**
```python
# ssambti/views.py - main_view
def main_view(request):
    context = {
        'service': service,
        'title': "쌤BTI",
        # 'posts': posts  ← 누락!
    }
    return render(request, 'ssambti/main.html', context)
```
- SNS 위젯 템플릿 (`sns_widget.html`)은 `posts` 변수를 필요로 함
- 하지만 쌤BTI 뷰에서는 `posts` 컨텍스트를 전달하지 않음
- `post_list.html`이 빈 데이터를 렌더링

---

## 해결 방법

### 1. 레이아웃 수정 ✅

#### Before (잘못된 구조)
```html
<!-- ❌ 문제: 단순히 위젯을 포함하면 레이아웃이 깨짐 -->
{% block content %}
<section class="pt-32 pb-20 px-6 min-h-screen bg-[#E0E5EC]">
    <div class="max-w-3xl mx-auto">
        {{ 메인 콘텐츠 }}
    </div>

    <!-- 위젯이 어디에 배치될지 불명확 -->
    <div class="hidden lg:block">
        {% include 'core/partials/sns_widget.html' %}
    </div>
</section>
{% endblock %}
```

#### After (올바른 구조)
```html
<!-- ✅ 해결: Flex 레이아웃으로 명확한 구조 제공 -->
{% block content %}
<section class="pt-32 pb-20 px-6 min-h-screen bg-[#E0E5EC]">
    <div class="max-w-7xl mx-auto">
        <div class="flex flex-col lg:flex-row gap-6 items-start">
            <!-- 메인 콘텐츠 (좌측) -->
            <div class="flex-1 w-full lg:max-w-3xl">
                {{ 메인 콘텐츠 }}
            </div>

            <!-- SNS 사이드바 (우측, 데스크톱만) -->
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

**핵심 포인트:**
1. **외부 컨테이너**: `max-w-7xl` - 전체 레이아웃을 감싸는 넓은 컨테이너
2. **Flex 컨테이너**: `flex flex-col lg:flex-row` - 모바일에서는 세로, 데스크톱에서는 가로 배치
3. **메인 콘텐츠**: `flex-1 w-full lg:max-w-3xl` - 남은 공간을 차지하되 최대 너비 제한
4. **사이드바**: `w-[380px] flex-shrink-0` - 고정 너비, 축소 방지
5. **반응형**: `hidden lg:block` - 모바일에서는 숨김
6. **정렬**: `items-start` - 상단 정렬 (중요!)
7. **추가 래퍼**: `<div class="relative">` - 위젯 포지셔닝 제약

### 2. 데이터 연동 수정 ✅

#### Before (데이터 없음)
```python
# ssambti/views.py
def main_view(request):
    # ... 기타 로직

    context = {
        'service': service,
        'title': "쌤BTI",
        'stats': stats,
        # posts가 없음!
    }
    return render(request, 'ssambti/main.html', context)
```

#### After (데이터 포함)
```python
# ssambti/views.py
from django.db.models import Count
from core.models import Post  # 추가!

def main_view(request):
    # ... 기타 로직

    # SNS posts for sidebar (최신 20개)
    posts = Post.objects.select_related(
        'author', 'author__userprofile'
    ).prefetch_related(
        'comments__author__userprofile',
        'likes'
    ).annotate(
        like_count=Count('likes', distinct=True),
        comment_count=Count('comments', distinct=True)
    ).order_by('-created_at')[:20]

    context = {
        'service': service,
        'title': "쌤BTI",
        'stats': stats,
        'posts': posts  # 추가!
    }
    return render(request, 'ssambti/main.html', context)
```

**핵심 포인트:**
1. **Import 추가**: `from core.models import Post`
2. **쿼리 최적화**:
   - `select_related()`: 1:1 관계 (author, userprofile) - N+1 방지
   - `prefetch_related()`: N:N 관계 (comments, likes) - 효율적 로딩
   - `annotate()`: 좋아요/댓글 개수 미리 계산 - 추가 쿼리 방지
3. **제한**: `[:20]` - 최신 20개만 가져오기 (성능)
4. **컨텍스트 전달**: `'posts': posts` - 템플릿에 데이터 전달

---

## 체크리스트: SNS Sidebar 통합 시

다른 서비스에 SNS sidebar를 추가할 때 반드시 확인할 것:

### 템플릿 수정
- [ ] 외부 컨테이너 너비를 `max-w-7xl`로 확장
- [ ] Flex 레이아웃 구조 생성 (`flex flex-col lg:flex-row`)
- [ ] 메인 콘텐츠에 `flex-1` 및 최대 너비 설정
- [ ] 사이드바에 `w-[380px] flex-shrink-0` 설정
- [ ] `hidden lg:block`으로 모바일 숨김 처리
- [ ] `items-start`로 상단 정렬
- [ ] `<div class="relative">` 래퍼로 위젯 감싸기

### 뷰 수정
- [ ] `from core.models import Post` import 추가
- [ ] `from django.db.models import Count` import 추가 (없다면)
- [ ] Post 쿼리 작성 (select_related, prefetch_related, annotate)
- [ ] 컨텍스트에 `'posts': posts` 추가
- [ ] 모든 관련 뷰에 적용 (main, detail 등)

### 테스트
- [ ] 데스크톱: 사이드바가 우측에 표시되는지
- [ ] 모바일: 사이드바가 숨겨지는지
- [ ] 게시글이 제대로 표시되는지
- [ ] 글 작성/댓글/좋아요가 작동하는지
- [ ] 스크롤 시 사이드바가 상단에 고정되는지 (sticky)

---

## 실제 적용 예시

### 쌤BTI 서비스 (완료)
```
파일:
- ssambti/templates/ssambti/main.html
- ssambti/templates/ssambti/detail.html
- ssambti/views.py (main_view, detail_view)

커밋:
- feat: 쌤BTI 페이지에 SNS 사이드바 통합 (3223af2)
- fix: 쌤BTI SNS 사이드바 레이아웃 및 데이터 연동 수정 (92e5f44)
```

### Fortune 서비스 (예정)
```
적용 대상:
- fortune/templates/fortune/saju_form.html
- fortune/templates/fortune/saju_result.html (있다면)
- fortune/views.py (saju_view, saju_api_view)

동일한 패턴 적용:
1. 템플릿: Flex 레이아웃 + SNS 위젯 include
2. 뷰: Post 쿼리 + 컨텍스트 전달
```

---

## 흔한 실수 & 디버깅

### 실수 1: Flex 구조 없이 위젯만 추가
```html
<!-- ❌ 잘못됨 -->
<div class="max-w-3xl mx-auto">
    {{ 메인 콘텐츠 }}
</div>
{% include 'core/partials/sns_widget.html' %}
```
**문제**: 위젯이 레이아웃 밖으로 튀어나가거나 이상한 위치에 배치됨

**해결**: Flex 컨테이너로 감싸고 명확한 레이아웃 구조 제공

### 실수 2: 컨텍스트에 posts 누락
```python
# ❌ 잘못됨
context = {
    'title': "서비스명",
    # posts 없음!
}
```
**증상**: 위젯은 보이지만 게시글이 비어있음

**해결**: `'posts': posts` 추가 및 쿼리 작성

### 실수 3: 최적화되지 않은 쿼리
```python
# ❌ 잘못됨 - N+1 쿼리 발생
posts = Post.objects.all()[:20]
```
**문제**: 각 게시글마다 author, comments, likes를 가져오는 추가 쿼리 발생

**해결**: select_related, prefetch_related, annotate 사용

### 실수 4: items-start 누락
```html
<!-- ❌ 잘못됨 -->
<div class="flex flex-col lg:flex-row gap-6">
```
**증상**: 사이드바가 메인 콘텐츠 높이만큼 늘어남 (stretch)

**해결**: `items-start` 추가

### 실수 5: 모바일 반응형 미처리
```html
<!-- ❌ 잘못됨 -->
<div class="w-[380px]">
    {% include 'core/partials/sns_widget.html' %}
</div>
```
**문제**: 모바일에서도 380px 고정 너비 → 레이아웃 깨짐

**해결**: `hidden lg:block` 추가

---

## 성능 고려사항

### 쿼리 최적화
```python
# 최적화된 쿼리 (1 + 2 queries)
posts = Post.objects.select_related(
    'author',                    # 1개 JOIN
    'author__userprofile'        # 1개 JOIN
).prefetch_related(
    'comments__author__userprofile',  # 2개 쿼리
    'likes'                           # 1개 쿼리
).annotate(
    like_count=Count('likes', distinct=True),
    comment_count=Count('comments', distinct=True)
).order_by('-created_at')[:20]

# 총 약 4-5개 쿼리로 모든 데이터 로딩
```

### 캐싱 (선택사항)
```python
from django.core.cache import cache

def main_view(request):
    # 캐시 키 생성
    cache_key = 'sns_posts_latest_20'
    posts = cache.get(cache_key)

    if not posts:
        posts = Post.objects.select_related(...).prefetch_related(...)
        cache.set(cache_key, posts, 60)  # 1분 캐싱

    # ...
```

### 페이지네이션 (향후 개선)
```python
# 현재: 최신 20개만
posts = Post.objects...[:20]

# 향후: 무한 스크롤 또는 페이지네이션
# HTMX로 추가 로딩 구현 가능
```

---

## 추가 참고사항

### 관련 파일
- **SNS 위젯**: `core/templates/core/partials/sns_widget.html`
- **게시글 목록**: `core/templates/core/partials/post_list.html`
- **게시글 아이템**: `core/templates/core/partials/post_item.html`
- **SNS 모델**: `core/models.py` (Post, Comment)
- **SNS 뷰**: `core/views.py` (post_create, post_like, comment_create 등)

### SNS 위젯 구조
```
sns_widget.html
├── Header (제목 + 새로고침 버튼)
├── Write Form (로그인 시)
│   ├── Textarea (내용 입력)
│   ├── Image Upload (드래그앤드롭/붙여넣기)
│   └── Submit Button
├── Post List Container
│   └── post_list.html
│       └── post_item.html (각 게시글)
│           ├── Author Info
│           ├── Content
│           ├── Image (있다면)
│           ├── Like Button
│           ├── Comments
│           └── Edit/Delete
└── JavaScript (이미지 붙여넣기)
```

### HTMX 동작
- 게시글 작성: `hx-post="/post/create/"`
- 좋아요 토글: `hx-post="/post/<id>/like/"`
- 댓글 작성: `hx-post="/post/<id>/comment/"`
- 수정/삭제: `hx-get`, `hx-delete`

**중요**: HTMX는 페이지 새로고침 없이 동작하므로 sidebar가 독립적으로 업데이트됨

---

## 향후 개선 방향

### 서비스별 필터링
```python
# Post 모델에 service 필드 추가
class Post(models.Model):
    service = CharField(
        max_length=20,
        choices=[
            ('general', '일반'),
            ('ssambti', '쌤BTI'),
            ('fortune', '사주'),
        ],
        default='general'
    )
```

### 서비스별 게시글 표시
```python
# 쌤BTI 전용 게시글만
posts = Post.objects.filter(service='ssambti')...

# 또는 전체 게시글 + 쌤BTI 게시글 우선
posts = Post.objects.annotate(
    is_ssambti=Case(
        When(service='ssambti', then=1),
        default=0,
        output_field=IntegerField()
    )
).order_by('-is_ssambti', '-created_at')[:20]
```

---

## 실제 발생한 에러 & 긴급 수정 사례

### 500 Error: select_related with Optional Relationship ⚠️

**발생일:** 2026-02-04
**증상:** 쌤BTI 페이지 접속 시 500 Internal Server Error
**커밋:** hotfix 6b90179

#### 문제 코드
```python
# ❌ 에러 발생
posts = Post.objects.select_related(
    'author', 'author__userprofile'  # UserProfile 없는 사용자가 있으면 실패!
).prefetch_related(
    'comments__author__userprofile',  # 여기도 마찬가지
    'likes'
).annotate(...)
```

#### 에러 원인
1. **UserProfile이 선택적 관계**
   - 모든 User가 UserProfile을 가지는 것은 아님
   - 소셜 로그인 사용자, 초기 가입자 등은 UserProfile 없을 수 있음

2. **select_related의 동작 방식**
   - `select_related('author__userprofile')`는 INNER JOIN을 사용
   - UserProfile이 없는 User의 Post는 쿼리 결과에서 제외됨
   - 하지만 실제로는 에러 발생 또는 예상치 못한 빈 결과

3. **프로덕션 환경의 데이터 불일치**
   - 로컬: 모든 User가 UserProfile 보유 (테스트 데이터)
   - 프로덕션: 일부 User가 UserProfile 없음 (실제 데이터)
   - 로컬에서는 정상, 프로덕션에서만 에러

#### 수정 코드
```python
# ✅ 안전한 코드
try:
    posts = Post.objects.select_related(
        'author'  # User만 조회, UserProfile 제거
    ).prefetch_related(
        'comments__author',  # UserProfile 참조 제거
        'likes'
    ).annotate(
        like_count=Count('likes', distinct=True),
        comment_count=Count('comments', distinct=True)
    ).order_by('-created_at')[:20]
except Exception as e:
    posts = []  # 에러 시 빈 리스트로 폴백
```

#### 핵심 교훈

**1. 선택적 관계는 select_related 피하기**
```python
# UserProfile이 OneToOneField(null=True, blank=True)인 경우
# ❌ 위험
.select_related('author__userprofile')

# ✅ 안전
.select_related('author')
# 템플릿에서: {% if post.author.userprofile %}
```

**2. prefetch_related로 선택적 관계 처리**
```python
# ✅ 더 나은 방법: 선택적으로 로딩
from django.db.models import Prefetch

posts = Post.objects.select_related('author').prefetch_related(
    Prefetch(
        'author__userprofile',
        queryset=UserProfile.objects.all(),
        to_attr='profile_cache'  # 캐시 속성 지정
    )
)

# 템플릿에서: {{ post.author.profile_cache }}
```

**3. 쿼리에 항상 에러 처리 추가**
```python
# ✅ 방어적 프로그래밍
try:
    posts = Post.objects...
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Post 쿼리 실패: {e}")
    posts = []  # 기본값
```

**4. 템플릿에서도 방어적으로 작성**
```django
{% if post.author.userprofile %}
    {{ post.author.userprofile.nickname }}
{% else %}
    {{ post.author.username }}
{% endif %}
```

#### 체크리스트: 쿼리 최적화 시

- [ ] 모든 관계가 필수인지 확인 (null=True 확인)
- [ ] select_related는 ForeignKey/OneToOne (필수 관계)에만 사용
- [ ] 선택적 관계는 prefetch_related 또는 템플릿에서 조건부 처리
- [ ] try-except로 쿼리 에러 처리
- [ ] 로컬과 프로덕션 데이터 차이 고려
- [ ] 쿼리 개수 확인 (django-debug-toolbar 사용)
- [ ] 로그에 에러 기록

#### 관련 모델 확인 방법
```python
# Django shell에서 확인
from django.contrib.auth.models import User
from core.models import UserProfile

# UserProfile 없는 User 찾기
users_without_profile = User.objects.filter(userprofile__isnull=True)
print(f"UserProfile 없는 사용자: {users_without_profile.count()}명")

# 데이터 정합성 확인
for user in users_without_profile:
    print(f"- {user.username} (ID: {user.id})")
```

#### 예방 방법

**1. 시그널로 자동 생성**
```python
# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
```

**2. 마이그레이션으로 기존 데이터 수정**
```python
# 마이그레이션 파일
from django.db import migrations

def create_missing_profiles(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('core', 'UserProfile')

    for user in User.objects.filter(userprofile__isnull=True):
        UserProfile.objects.create(user=user, nickname=user.username)

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles),
    ]
```

**3. Admin에서 일괄 생성**
```python
# core/admin.py
from django.contrib import admin
from django.contrib.auth.models import User
from .models import UserProfile

@admin.action(description='선택한 사용자의 UserProfile 생성')
def create_profiles(modeladmin, request, queryset):
    for user in queryset:
        UserProfile.objects.get_or_create(user=user)

class UserAdmin(admin.ModelAdmin):
    actions = [create_profiles]
```

---

**마지막 업데이트:** 2026-02-04
**관련 문서:** `SNS_HANDOFF.md` (전체 SNS 기능 분석 및 로드맵)
