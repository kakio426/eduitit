# SNS 통합 프로젝트 Handoff

**날짜:** 2026-02-04
**작성자:** Claude Sonnet 4.5
**프로젝트:** EDUITIT SNS 기능 확장 및 서비스 통합

---

## 📋 프로젝트 개요

EDUITIT 플랫폼의 기존 SNS 기능을 분석하고, 쌤BTI 서비스에 통합하는 작업을 진행했습니다. 이 문서는 현재까지 구현된 내용과 향후 개발이 필요한 기능들을 정리합니다.

---

## ✅ 완료된 작업 (2026-02-04)

### 1. SNS 기능 분석
- 기존 `core` 앱에 구현된 SNS 기능 전체 분석 완료
- 모델, 뷰, 템플릿, URL 구조 파악
- 구현된 기능과 미구현 기능 식별

### 2. 쌤BTI에 SNS Sidebar 통합
**구현된 페이지:**
- ✅ `ssambti/templates/ssambti/main.html` - 퀴즈 메인 페이지
- ✅ `ssambti/templates/ssambti/detail.html` - 결과 상세 페이지

**구현 방식:**
```html
<!-- 레이아웃 구조 -->
<div class="max-w-7xl mx-auto flex flex-col lg:flex-row gap-6">
    <!-- 메인 콘텐츠 (좌측) -->
    <div class="flex-1 max-w-3xl">
        {{ 쌤BTI 콘텐츠 }}
    </div>

    <!-- SNS 사이드바 (우측, 데스크톱만) -->
    <div class="hidden lg:block">
        {% include 'core/partials/sns_widget.html' %}
    </div>
</div>
```

**특징:**
- 반응형 디자인: 모바일에서는 숨김, 데스크톱(lg 이상)에서만 표시
- Sticky 포지셔닝: 스크롤 시 상단에 고정
- 기존 SNS 위젯 재사용 (컨텍스트 통합)

---

## 📊 현재 SNS 구현 현황

### 구현된 핵심 기능 ✅

| 기능 | 상태 | 위치 | 설명 |
|------|------|------|------|
| **게시글 작성** | ✅ | `core/views.py:post_create` | 텍스트(500자) + 이미지 업로드 |
| **게시글 수정** | ✅ | `core/views.py:post_edit` | 작성자만 수정 가능 (텍스트만) |
| **게시글 삭제** | ✅ | `core/views.py:post_delete` | 작성자/관리자 삭제 가능 |
| **댓글 작성** | ✅ | `core/views.py:comment_create` | 게시글에 댓글 추가(300자) |
| **댓글 수정/삭제** | ✅ | `core/views.py` | 작성자만 수정/삭제 |
| **좋아요** | ✅ | `core/views.py:post_like` | 토글 방식 좋아요 |
| **피드/타임라인** | ✅ | `core/views.py:home` | 최신순 정렬 |
| **이미지 업로드** | ✅ | Cloudinary 통합 | 10MB 제한, 드래그앤드롭/붙여넣기 지원 |
| **HTMX 통합** | ✅ | 전체 | 페이지 새로고침 없는 실시간 업데이트 |

### 데이터베이스 모델

#### Post 모델 (`core/models.py`)
```python
class Post(models.Model):
    author = ForeignKey(User, related_name='posts')
    content = TextField(max_length=500)
    image = ImageField(upload_to='posts/%Y/%m/', blank=True, null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    likes = ManyToManyField(User, related_name='liked_posts', blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def like_count(self):
        return self.likes.count()
```

#### Comment 모델
```python
class Comment(models.Model):
    post = ForeignKey(Post, related_name='comments')
    author = ForeignKey(User)
    content = TextField(max_length=300)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
```

---

## ⚠️ 미구현 기능 (우선순위별)

### 🔴 High Priority - 핵심 소셜 기능

#### 1. 팔로우/팔로잉 시스템
**현재 상태:** 미구현
**필요성:** 사용자 간 관계 형성, 개인화된 피드
**구현 방안:**

```python
# models.py 추가
class Follow(models.Model):
    follower = ForeignKey(User, related_name='following')
    following = ForeignKey(User, related_name='followers')
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        constraints = [
            CheckConstraint(
                check=~Q(follower=F('following')),
                name='prevent_self_follow'
            )
        ]
```

**필요한 뷰:**
- `follow_user(user_id)` - 팔로우/언팔로우 토글
- `followers_list(user_id)` - 팔로워 목록
- `following_list(user_id)` - 팔로잉 목록

**피드 변경:**
- 현재: 모든 게시글 표시 (전체 피드)
- 변경 후: 팔로우한 사용자 게시글만 표시 (개인화 피드)
- 추가: "전체 보기" 탭과 "팔로잉" 탭 분리

---

#### 2. 알림 시스템
**현재 상태:** 미구현
**필요성:** 사용자 참여 유도, 실시간 소통
**알림 유형:**
- 게시글에 좋아요
- 게시글에 댓글
- 댓글에 답글
- 새로운 팔로워
- 멘션(@username)

**구현 방안:**

```python
# models.py 추가
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('like', '좋아요'),
        ('comment', '댓글'),
        ('reply', '답글'),
        ('follow', '팔로우'),
        ('mention', '멘션'),
    ]

    recipient = ForeignKey(User, related_name='notifications')
    sender = ForeignKey(User, related_name='sent_notifications')
    notification_type = CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = ForeignKey(Post, null=True, blank=True)
    comment = ForeignKey(Comment, null=True, blank=True)
    is_read = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

**필요한 뷰:**
- `notifications_list()` - 알림 목록
- `mark_as_read(notification_id)` - 읽음 처리
- `mark_all_read()` - 전체 읽음 처리
- `unread_count()` - 미읽음 개수 (헤더 뱃지용)

**실시간 업데이트:**
- Django Channels + WebSocket (권장)
- 또는 HTMX polling (간단한 방법)

---

#### 3. 사용자 프로필 페이지
**현재 상태:** UserProfile 모델만 존재, 공개 페이지 없음
**필요성:** 사용자 정보 확인, 게시글 히스토리
**구현 필요:**

- `/profile/<user_id>/` - 사용자 프로필 페이지
- 표시할 정보:
  - 프로필 사진, 닉네임, 역할(교사/강사/기업)
  - 게시글 개수, 팔로워/팔로잉 수
  - 작성한 게시글 목록
  - 좋아요한 게시글 목록 (선택사항)
- 본인 프로필: 편집 버튼 추가

**템플릿 구조:**
```html
<!-- profile.html -->
<div class="profile-header">
    <img src="{{ user.profile_picture }}" />
    <h1>{{ user.nickname }}</h1>
    <p>{{ user.role }}</p>

    <!-- 통계 -->
    <div class="stats">
        <div>게시글 {{ post_count }}</div>
        <div>팔로워 {{ followers_count }}</div>
        <div>팔로잉 {{ following_count }}</div>
    </div>

    <!-- 팔로우 버튼 (타인 프로필) -->
    <button hx-post="/follow/{{ user.id }}/">팔로우</button>
</div>

<!-- 게시글 탭 -->
<div class="tabs">
    <div class="tab active">게시글</div>
    <div class="tab">좋아요</div>
</div>
<div id="user-posts">
    <!-- 사용자 게시글 목록 -->
</div>
```

---

#### 4. 검색 기능
**현재 상태:** 미구현
**필요성:** 콘텐츠 발견, 사용자 찾기
**구현 범위:**

**Phase 1: 기본 검색**
- 게시글 내용 검색 (제목 + 본문)
- 사용자 검색 (닉네임, 이름)

**Phase 2: 고급 검색**
- 해시태그 검색
- 날짜 범위 필터
- 작성자 필터
- 정렬 옵션 (최신순/인기순/관련도순)

**구현 방안:**

```python
# views.py
def search_view(request):
    query = request.GET.get('q', '')
    search_type = request.GET.get('type', 'all')  # all, posts, users

    results = {}

    if search_type in ['all', 'posts']:
        results['posts'] = Post.objects.filter(
            Q(content__icontains=query)
        ).select_related('author', 'author__userprofile')

    if search_type in ['all', 'users']:
        results['users'] = User.objects.filter(
            Q(username__icontains=query) |
            Q(userprofile__nickname__icontains=query)
        ).select_related('userprofile')

    return render(request, 'core/search_results.html', {
        'query': query,
        'results': results
    })
```

**검색 UI:**
- 헤더에 검색바 추가
- 자동완성 (HTMX로 구현 가능)
- 검색 결과 페이지 (`search_results.html`)

---

#### 5. 해시태그 시스템
**현재 상태:** 미구현
**필요성:** 콘텐츠 분류, 트렌드 파악
**구현 방안:**

```python
# models.py 추가
class Hashtag(models.Model):
    name = CharField(max_length=50, unique=True)
    created_at = DateTimeField(auto_now_add=True)

    @property
    def post_count(self):
        return self.posts.count()

# Post 모델에 추가
class Post(models.Model):
    # ... 기존 필드들
    hashtags = ManyToManyField(Hashtag, related_name='posts', blank=True)
```

**자동 해시태그 추출:**
```python
import re

def extract_hashtags(text):
    """텍스트에서 #태그 추출"""
    return re.findall(r'#(\w+)', text)

# post_create 뷰에서
hashtag_names = extract_hashtags(content)
for name in hashtag_names:
    hashtag, _ = Hashtag.objects.get_or_create(name=name)
    post.hashtags.add(hashtag)
```

**해시태그 페이지:**
- `/hashtag/<tag_name>/` - 해당 해시태그 게시글 목록
- 트렌딩 해시태그 위젯 (사이드바에 추가)

---

#### 6. 멘션(@) 시스템
**현재 상태:** 미구현
**필요성:** 사용자 태그, 대화 유도
**구현 방안:**

```python
# models.py - Post 모델에 추가
class Post(models.Model):
    # ... 기존 필드들
    mentions = ManyToManyField(User, related_name='mentioned_in_posts', blank=True)
```

**자동 멘션 추출 및 알림:**
```python
def extract_mentions(text):
    """텍스트에서 @username 추출"""
    return re.findall(r'@(\w+)', text)

# post_create 뷰에서
mentioned_usernames = extract_mentions(content)
for username in mentioned_usernames:
    try:
        user = User.objects.get(username=username)
        post.mentions.add(user)
        # 알림 생성
        Notification.objects.create(
            recipient=user,
            sender=request.user,
            notification_type='mention',
            post=post
        )
    except User.DoesNotExist:
        pass
```

**프론트엔드:**
- 작성 중 자동완성 (HTMX + JavaScript)
- 멘션된 사용자 하이라이트 표시

---

### 🟡 Medium Priority - UX 개선

#### 7. 프라이버시 설정
**현재 상태:** 모든 게시글 공개
**추가할 옵션:**
- 전체 공개 (현재 기본값)
- 팔로워만
- 비공개 (본인만)
- 특정 사용자 숨김 (차단)

```python
# Post 모델에 추가
class Post(models.Model):
    # ... 기존 필드들
    visibility = CharField(
        max_length=20,
        choices=[
            ('public', '전체 공개'),
            ('followers', '팔로워만'),
            ('private', '나만 보기'),
        ],
        default='public'
    )
```

---

#### 8. 게시글 공유 기능
**현재 상태:** 미구현
**추가할 기능:**
- 리포스트 (트위터 스타일)
- 인용 리포스트 (코멘트 추가)
- 외부 공유 (카카오톡, 링크 복사)

---

#### 9. 리액션 확장
**현재 상태:** 좋아요만 가능
**추가할 리액션:**
- 👍 좋아요
- ❤️ 사랑해요
- 😂 웃겨요
- 😮 놀라워요
- 😢 슬퍼요
- 🤔 생각해봐요

---

#### 10. 미디어 갤러리
**현재 상태:** 이미지 업로드만 가능, 라이트박스 없음
**개선 사항:**
- 이미지 클릭 시 라이트박스 (전체 화면)
- 이미지 캐러셀 (여러 이미지 업로드 지원)
- 동영상 업로드 지원
- GIF 애니메이션 지원

---

#### 11. 무한 스크롤
**현재 상태:** "Show older posts" 버튼
**개선 방안:**
- HTMX infinite scroll 구현
- 자동 로딩 (스크롤 하단 도달 시)
- 로딩 인디케이터

---

#### 12. 게시글 임시 저장
**현재 상태:** 미구현
**추가 기능:**
- 작성 중 자동 저장 (LocalStorage)
- 초안 저장 (서버)
- 예약 발행

---

### 🟢 Lower Priority - 고급 기능

#### 13. 신고/차단 시스템
- 부적절한 콘텐츠 신고
- 사용자 차단 (게시글 숨김)
- 관리자 모더레이션 도구

#### 14. 게시글 분석
- 조회수 트래킹
- 인기 게시글 (트렌딩)
- 참여도 통계

#### 15. 활동 피드
- 팔로우한 사용자의 좋아요/댓글 활동
- "OOO님이 좋아요를 눌렀습니다" 피드

#### 16. 북마크
- 게시글 저장 기능
- 저장한 게시글 모음

#### 17. 채팅/DM
- 사용자 간 1:1 메시지
- 실시간 채팅 (WebSocket)

---

## 🔧 서비스별 SNS 통합 전략

### 현재 통합 상태
- ✅ **쌤BTI**: Sidebar 형태로 통합 완료

### 향후 통합 대상

#### 1. Fortune (사주 서비스)
**통합 방식:** 쌤BTI와 동일 (Sidebar)
**위치:**
- `fortune/templates/fortune/saju_form.html` - 사주 입력 페이지
- `fortune/templates/fortune/saju_result.html` - 결과 페이지 (있는 경우)

**추가 기능 (선택사항):**
- 사주 결과를 SNS에 자동 공유 버튼
- 게시글 작성 시 "사주 결과와 함께 공유" 옵션

---

#### 2. 서비스별 필터링 (Phase 2)

**방법 A: Post 모델에 service 필드 추가 (추천)**

```python
# models.py
class Post(models.Model):
    # ... 기존 필드들
    service = CharField(
        max_length=20,
        choices=[
            ('general', '일반'),
            ('ssambti', '쌤BTI'),
            ('fortune', '사주'),
            ('teacherkit', '티처킷'),
        ],
        default='general'
    )
    service_object_id = IntegerField(null=True, blank=True)  # 서비스별 객체 ID (선택)
```

**사용 예시:**
```python
# 쌤BTI 결과 공유 시
post = Post.objects.create(
    author=request.user,
    content=f"저는 {animal_name}이래요!",
    image=result_image,
    service='ssambti'
)

# 쌤BTI 페이지 피드: 쌤BTI 관련 게시글만 표시
ssambti_posts = Post.objects.filter(service='ssambti')

# 전체 피드: 모든 게시글 표시
all_posts = Post.objects.all()
```

**방법 B: 별도 앱으로 분리 (대규모 프로젝트)**
- `ssambti_sns`, `fortune_sns` 등으로 앱 분리
- 각 앱마다 독립적인 Post/Comment 모델
- 코드 중복 증가, 유지보수 어려움 → 비추천

---

## 📁 주요 파일 위치

### SNS 관련 파일
```
core/
├── models.py                    # Post, Comment, UserProfile 모델
├── views.py                     # SNS 뷰 함수들
├── urls.py                      # SNS URL 라우팅
├── admin.py                     # 관리자 페이지 등록
├── templates/core/
│   └── partials/
│       ├── sns_widget.html      # SNS 위젯 (재사용 가능)
│       ├── post_item.html       # 개별 게시글 템플릿
│       ├── post_list.html       # 게시글 목록
│       ├── comment_item.html    # 댓글 아이템
│       ├── post_edit_form.html  # 게시글 수정 폼
│       └── comment_edit_form.html # 댓글 수정 폼
└── static/core/js/
    └── post_image_paste.js      # 이미지 붙여넣기/드래그앤드롭
```

### 쌤BTI 통합 파일 (수정됨)
```
ssambti/
└── templates/ssambti/
    ├── main.html                # ✅ SNS sidebar 추가됨
    └── detail.html              # ✅ SNS sidebar 추가됨
```

---

## 🚀 구현 로드맵

### Phase 1: 핵심 소셜 기능 (2-3주)
1. **Week 1**
   - [ ] Follow 모델 및 팔로우/언팔로우 기능
   - [ ] 팔로우 기반 피드 필터링
   - [ ] 사용자 프로필 페이지 기본 구조

2. **Week 2**
   - [ ] Notification 모델 및 알림 생성 로직
   - [ ] 알림 목록 페이지
   - [ ] 헤더 알림 뱃지 (미읽음 개수)

3. **Week 3**
   - [ ] 검색 기능 (게시글/사용자)
   - [ ] 해시태그 자동 추출 및 페이지
   - [ ] 멘션 기능

### Phase 2: UX 개선 (2주)
4. **Week 4**
   - [ ] 프라이버시 설정 (공개/팔로워/비공개)
   - [ ] 게시글 공유 기능 (리포스트)
   - [ ] 무한 스크롤

5. **Week 5**
   - [ ] 리액션 확장 (다양한 이모지)
   - [ ] 미디어 갤러리 (라이트박스, 다중 이미지)
   - [ ] 게시글 임시 저장

### Phase 3: 서비스 통합 (1주)
6. **Week 6**
   - [ ] Post 모델에 `service` 필드 추가
   - [ ] Fortune 서비스에 SNS sidebar 통합
   - [ ] 서비스별 필터링 구현
   - [ ] 쌤BTI/사주 결과 자동 공유 기능

### Phase 4: 고급 기능 (선택사항, 2-3주)
7. **Week 7-9**
   - [ ] 신고/차단 시스템
   - [ ] 게시글 분석 및 트렌딩
   - [ ] 활동 피드
   - [ ] DM/채팅 (WebSocket)

---

## 🛠️ 기술 스택 & 도구

### 현재 사용 중
- **Backend:** Django 4.x
- **Database:** PostgreSQL (또는 SQLite for dev)
- **Frontend:** HTMX + Tailwind CSS
- **Icons:** Phosphor Icons
- **Image Storage:** Cloudinary
- **Authentication:** Django Allauth

### 추가 고려사항
- **WebSocket:** Django Channels (실시간 알림/채팅)
- **Caching:** Redis (피드 캐싱, 세션)
- **Task Queue:** Celery (알림 전송, 이미지 처리)
- **Search:** Elasticsearch 또는 PostgreSQL Full-Text Search

---

## ⚡ 성능 최적화 권장사항

### 1. 데이터베이스 쿼리 최적화
```python
# 현재 코드 (좋은 예시)
posts = Post.objects.select_related(
    'author', 'author__userprofile'
).prefetch_related(
    'comments__author__userprofile',
    'likes'
).annotate(
    like_count=Count('likes', distinct=True),
    comment_count=Count('comments', distinct=True)
).order_by('-created_at')
```

**추가 권장:**
- 인덱스 추가: `created_at`, `author`, `service` 필드
- 페이지네이션 또는 Cursor-based pagination
- 캐싱: 인기 게시글, 트렌딩 해시태그

### 2. 이미지 최적화
- Cloudinary 자동 리사이징 활용
- WebP 포맷 사용
- Lazy loading 적용

### 3. 프론트엔드 최적화
- HTMX로 불필요한 JavaScript 최소화
- Tailwind CSS Purge 활성화 (프로덕션)
- 이미지 스프라이트 또는 SVG 아이콘 사용

---

## 🔒 보안 고려사항

### 현재 구현된 보안
- ✅ CSRF 토큰 (모든 POST 요청)
- ✅ 작성자 권한 검증 (수정/삭제)
- ✅ 이미지 업로드 검증 (MIME type, 파일 크기)
- ✅ 로그인 필수 (글쓰기/댓글/좋아요)

### 추가 필요 보안
- [ ] Rate Limiting (스팸 방지)
- [ ] XSS 방지 (사용자 입력 필터링)
- [ ] SQL Injection 방지 (Django ORM 사용으로 대부분 방지됨)
- [ ] Content Security Policy (CSP) 헤더
- [ ] 이미지 업로드 바이러스 스캔

---

## 🐛 알려진 이슈 & 제한사항

### 1. 게시글 수정 시 이미지 변경 불가
**문제:** `post_edit_form.html`에서 이미지 수정 UI 없음
**해결 방안:** 이미지 수정 필드 추가 및 뷰 업데이트

### 2. 댓글 답글 기능 없음
**문제:** 댓글에 대한 답글(nested comments) 미구현
**해결 방안:** Comment 모델에 `parent` ForeignKey 추가

```python
class Comment(models.Model):
    # ... 기존 필드들
    parent = ForeignKey('self', null=True, blank=True, related_name='replies')
```

### 3. 피드 로딩 속도
**문제:** 게시글 많아질수록 초기 로딩 느려짐
**해결 방안:**
- 페이지네이션 (현재 미구현)
- 피드 캐싱 (Redis)
- 쿼리 최적화 (이미 대부분 적용됨)

### 4. 실시간 업데이트 부족
**문제:** 새 게시글/댓글 자동 반영 안 됨
**해결 방안:**
- WebSocket (Django Channels)
- 또는 HTMX polling (간단한 방법)

---

## 📖 참고 자료

### Django 공식 문서
- [Models](https://docs.djangoproject.com/en/4.2/topics/db/models/)
- [QuerySets](https://docs.djangoproject.com/en/4.2/topics/db/queries/)
- [Authentication](https://docs.djangoproject.com/en/4.2/topics/auth/)

### HTMX
- [HTMX Docs](https://htmx.org/docs/)
- [Django + HTMX Best Practices](https://testdriven.io/blog/django-htmx/)

### Django Channels (WebSocket)
- [Channels Documentation](https://channels.readthedocs.io/)

### Cloudinary
- [Django Integration](https://cloudinary.com/documentation/django_integration)

---

## 💡 다음 작업자를 위한 팁

### 1. 개발 환경 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# 마이그레이션 적용
python manage.py migrate

# 개발 서버 실행
python manage.py runserver
```

### 2. 새 기능 추가 시 체크리스트
- [ ] 모델 변경 → 마이그레이션 생성 및 적용
- [ ] 뷰 함수 작성 → `core/views.py`
- [ ] URL 패턴 추가 → `core/urls.py`
- [ ] 템플릿 작성 → `core/templates/core/`
- [ ] 관리자 등록 → `core/admin.py` (필요시)
- [ ] 테스트 작성 → `core/tests.py`
- [ ] settings.py와 settings_production.py 동기화 확인

### 3. 디버깅 팁
- Django Debug Toolbar 설치 권장
- 쿼리 개수 확인: `connection.queries`
- HTMX 요청 확인: 브라우저 개발자 도구 Network 탭

### 4. 코드 스타일
- Django 네이밍 컨벤션 준수
- 뷰는 함수 기반 (현재 스타일)
- HTMX partial 템플릿은 `partials/` 폴더에
- 긴 쿼리는 변수로 분리

---

## 📞 문의

문서에 대한 질문이나 추가 정보가 필요하면:
- 이 Handoff 문서를 다음 작업자에게 전달
- 코드베이스: `/eduitit/core/` (SNS 기능)
- 분석 문서: `/eduitit/cluade.md` (Fortune 500 에러 분석)

---

**작성 완료: 2026-02-04**
**다음 업데이트 예정: Phase 1 구현 완료 시**
