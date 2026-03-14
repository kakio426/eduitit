from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('school', '학교 (관리자 및 정교사)'),
        ('instructor', '강사 (기간제, 돌봄, 늘봄 등)'),
        ('company', '교육행사업체'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True, verbose_name="역할")
    nickname = models.CharField(max_length=50, blank=True, null=True, verbose_name="별명")
    gemini_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Gemini API Key")
    padlet_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Padlet API Key")
    default_classroom = models.ForeignKey(
        "happy_seed.HSClassroom",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="default_users",
        verbose_name="기본 학급",
    )

    def __str__(self):
        return self.user.username


class UserPolicyConsent(models.Model):
    AGREEMENT_SOURCE_CHOICES = [
        ('social_first_login', '소셜 첫 로그인'),
        ('social_reconsent', '소셜 재동의'),
        ('required_gate', '필수 동의 게이트'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='policy_consents')
    provider = models.CharField(max_length=32, default='direct', verbose_name='로그인 제공사')
    terms_version = models.CharField(max_length=32, verbose_name='이용약관 버전')
    privacy_version = models.CharField(max_length=32, verbose_name='개인정보처리방침 버전')
    agreed_at = models.DateTimeField(verbose_name='동의 일시')
    agreement_source = models.CharField(
        max_length=32,
        choices=AGREEMENT_SOURCE_CHOICES,
        default='required_gate',
        verbose_name='동의 경로',
    )
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name='IP 주소')
    user_agent = models.TextField(blank=True, default='', verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-agreed_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'terms_version', 'privacy_version'],
                name='core_policyconsent_user_terms_privacy_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['user', '-agreed_at']),
            models.Index(fields=['provider', '-agreed_at']),
            models.Index(fields=['terms_version', 'privacy_version']),
        ]
        verbose_name = '정책 동의 기록'
        verbose_name_plural = '정책 동의 기록'

    def __str__(self):
        return f'{self.user.username} ({self.terms_version}/{self.privacy_version})'


class NewsSource(models.Model):
    SOURCE_TYPE_CHOICES = [
        ('gov', '기관/정부'),
        ('institute', '교육기관'),
        ('media', '언론'),
        ('aggregator', '집계'),
    ]

    name = models.CharField(max_length=120, verbose_name="소스 이름")
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default='media', verbose_name="소스 유형")
    url = models.URLField(max_length=1000, unique=True, verbose_name="RSS/API URL")
    is_active = models.BooleanField(default=True, verbose_name="활성화")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "뉴스 수집 소스"
        verbose_name_plural = "뉴스 수집 소스"

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class Post(models.Model):
    POST_TYPE_CHOICES = [
        ('general', '일반'),
        ('notice', '공지'),
        ('news_link', '뉴스 링크'),
    ]
    APPROVAL_STATUS_CHOICES = [
        ('approved', '게시중'),
        ('pending', '검토 대기'),
        ('rejected', '반려'),
    ]
    SOURCE_TYPE_CHOICES = [
        ('user', '사용자'),
        ('gov', '기관/정부'),
        ('institute', '교육기관'),
        ('media', '언론'),
        ('aggregator', '집계'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField(max_length=500, verbose_name="내용")
    image = models.ImageField(upload_to='posts/%Y/%m/', null=True, blank=True, verbose_name="이미지")
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='general', verbose_name="게시글 유형")
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default='user', verbose_name="콘텐츠 출처 유형")
    source_url = models.URLField(max_length=1000, blank=True, default='', verbose_name="원문 링크")
    canonical_url = models.URLField(max_length=1000, blank=True, default='', verbose_name="정규화 링크")
    og_title = models.CharField(max_length=300, blank=True, default='', verbose_name="OG 제목")
    og_description = models.TextField(blank=True, default='', verbose_name="OG 설명")
    og_image_url = models.URLField(max_length=1000, blank=True, default='', verbose_name="OG 이미지 링크")
    publisher = models.CharField(max_length=120, blank=True, default='', verbose_name="매체/출처")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="기사 발행일")
    primary_tag = models.CharField(max_length=40, blank=True, default='', verbose_name="기본 태그")
    secondary_tag = models.CharField(max_length=40, blank=True, default='', verbose_name="보조 태그")
    ranking_score = models.FloatField(default=0.0, verbose_name="랭킹 점수")
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='approved', verbose_name="게시 승인 상태")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="검토 일시")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_posts')
    featured_from = models.DateTimeField(null=True, blank=True, verbose_name="상단 노출 시작")
    featured_until = models.DateTimeField(null=True, blank=True, verbose_name="상단 노출 종료")
    news_source = models.ForeignKey('NewsSource', on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post_type', '-created_at']),
            models.Index(fields=['post_type', '-ranking_score']),
            models.Index(fields=['approval_status', '-created_at']),
            models.Index(fields=['featured_from', 'featured_until']),
            models.Index(fields=['publisher', '-created_at']),
        ]

    def __str__(self):
        return f"{self.author.username} - {self.created_at}"

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def is_news_link(self):
        return self.post_type == 'news_link'

    @property
    def is_visible(self):
        return self.approval_status == 'approved'

    @property
    def is_featured_now(self):
        if not self.featured_from:
            return False

        now = timezone.now()
        if self.featured_from > now:
            return False
        if self.featured_until and self.featured_until < now:
            return False
        return True

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Ensure profile exists whenever user is saved
    UserProfile.objects.get_or_create(user=instance)

class Comment(models.Model):
    HIDDEN_REASON_CHOICES = [
        ('', '해당 없음'),
        ('reports', '신고 누적'),
        ('admin', '관리자 처리'),
        ('policy', '운영 정책'),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(max_length=300, verbose_name="댓글 내용")
    is_hidden = models.BooleanField(default=False, verbose_name="숨김 여부")
    hidden_reason = models.CharField(max_length=20, choices=HIDDEN_REASON_CHOICES, blank=True, default='', verbose_name="숨김 사유")
    report_count = models.PositiveIntegerField(default=0, verbose_name="신고 수")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['is_hidden', '-created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post}"


class CommentReport(models.Model):
    REASON_CHOICES = [
        ('privacy', '개인정보/실명 노출'),
        ('abuse', '욕설/비하'),
        ('hate', '혐오/차별'),
        ('spam', '광고/도배'),
        ('off_topic', '주제 이탈'),
        ('other', '기타'),
    ]

    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='report_entries')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_reports')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='other')
    detail = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['comment', 'reporter'], name='core_commentreport_comment_reporter_unique'),
        ]
        indexes = [
            models.Index(fields=['reason', '-created_at']),
            models.Index(fields=['comment', '-created_at']),
        ]
        verbose_name = "댓글 신고"
        verbose_name_plural = "댓글 신고"

    def __str__(self):
        return f"Report({self.reason}) by {self.reporter.username} on comment #{self.comment_id}"


class UserModeration(models.Model):
    SCOPE_CHOICES = [
        ('comment', '댓글만 제한'),
        ('all', '전체 제한'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='moderations')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='comment')
    until = models.DateTimeField(null=True, blank=True, verbose_name="제한 만료일시")
    reason = models.CharField(max_length=300, blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_moderations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'scope']),
            models.Index(fields=['until']),
        ]
        verbose_name = "사용자 제재"
        verbose_name_plural = "사용자 제재"

    def __str__(self):
        return f"{self.user.username} ({self.scope})"

    @property
    def is_active(self):
        if self.until is None:
            return True
        return self.until > timezone.now()

class SiteConfig(models.Model):
    """싱글톤 사이트 설정 모델 - Admin에서 배너 등 글로벌 설정 관리"""
    maintenance_mode = models.BooleanField(
        default=False,
        verbose_name="점검 모드",
        help_text="켜면 관리자(superuser) 외 사용자에게 점검 페이지(503)를 표시합니다.",
    )
    banner_text = models.CharField(max_length=200, blank=True, default='', verbose_name="배너 텍스트")
    banner_active = models.BooleanField(default=False, verbose_name="배너 활성화")
    banner_color = models.CharField(max_length=7, default='#7c3aed', verbose_name="배너 색상 (HEX)")
    banner_link = models.URLField(blank=True, default='', verbose_name="배너 링크 URL")

    featured_manuals = models.ManyToManyField(
        'products.ServiceManual', 
        blank=True, 
        verbose_name="추천 이용방법",
        help_text="홈 화면이나 리스트 상단에 노출할 매뉴얼을 선택하세요."
    )


    class Meta:
        verbose_name = "사이트 설정"
        verbose_name_plural = "사이트 설정"

    def __str__(self):
        return "사이트 설정"

    def save(self, *args, **kwargs):
        # 싱글톤 패턴: pk를 항상 1로 강제
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Feedback(models.Model):
    CATEGORY_CHOICES = [
        ('bug', '버그 신고'),
        ('suggestion', '제안/건의'),
        ('other', '기타'),
    ]
    name = models.CharField(max_length=50, verbose_name="이름")
    email = models.EmailField(blank=True, default='', verbose_name="이메일 (선택)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other', verbose_name="카테고리")
    message = models.TextField(max_length=1000, verbose_name="내용")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="작성일시")
    is_resolved = models.BooleanField(default=False, verbose_name="처리 완료")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "피드백"
        verbose_name_plural = "피드백"

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name} - {self.created_at:%Y-%m-%d}"


class ProductUsageLog(models.Model):
    """서비스 사용 기록 — 개인화 퀵 액션 및 검색 추천에 활용"""
    ACTION_CHOICES = [
        ('launch', '서비스 실행'),
        ('search', '검색 클릭'),
        ('quick_action', '퀵 액션'),
        ('modal_open', '모달 열기'),
    ]
    SOURCE_CHOICES = [
        ('home_quick', '홈 퀵 액션'),
        ('home_section', '홈 목적별 섹션'),
        ('home_game', '홈 게임 배너'),
        ('home_grid', '홈 전체 서비스'),
        ('search', '검색 모달'),
        ('other', '기타'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_usage_logs')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='usage_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='launch')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='other')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'product']),
        ]
        verbose_name = "서비스 사용 기록"
        verbose_name_plural = "서비스 사용 기록"

    def __str__(self):
        return f"{self.user.username} → {self.product.title} ({self.action})"


class ProductFavorite(models.Model):
    """사용자별 서비스 즐겨찾기"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_favorites')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='favorited_by_users')
    pin_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['pin_order', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='core_productfavorite_user_product_unique'),
        ]
        indexes = [
            models.Index(fields=['user', 'pin_order']),
            models.Index(fields=['user', '-created_at']),
        ]
        verbose_name = "서비스 즐겨찾기"
        verbose_name_plural = "서비스 즐겨찾기"

    def __str__(self):
        return f"{self.user.username} ★ {self.product.title}"


class ProductWorkbenchBundle(models.Model):
    """교사가 자주 쓰는 서비스 조합을 작업대 묶음으로 저장한다."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_workbench_bundles')
    name = models.CharField(max_length=80)
    product_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_used_at', '-updated_at', 'name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='core_workbenchbundle_user_name_unique'),
        ]
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['user', '-last_used_at']),
        ]
        verbose_name = "작업대 조합"
        verbose_name_plural = "작업대 조합"

    def __str__(self):
        return f"{self.user.username} 작업대 조합 - {self.name}"


class VisitorLog(models.Model):
    ip_address = models.GenericIPAddressField(verbose_name="IP 주소")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    is_bot = models.BooleanField(default=False, verbose_name="봇 여부")
    visit_date = models.DateField(auto_now_add=True, verbose_name="방문 날짜")

    class Meta:
        # Prevent multiple entries for same IP on same day
        unique_together = ('ip_address', 'visit_date')
        verbose_name = "방문자 기록"
        verbose_name_plural = "방문자 기록"

    def __str__(self):
        return f"{self.visit_date} - {self.ip_address}"
