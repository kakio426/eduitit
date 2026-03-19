import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone


def _get_raw_storage():
    """Cloudinary가 설정된 경우 Cloudinary Raw 저장소, 아니면 기본 저장소."""
    if getattr(settings, 'USE_CLOUDINARY', False):
        try:
            from cloudinary_storage.storage import RawMediaCloudinaryStorage
            return RawMediaCloudinaryStorage()
        except (ImportError, Exception):
            return default_storage
    return default_storage


# ── Tag ──────────────────────────────────────────────────

class Tag(models.Model):
    """사용자별 태그 (보드·카드에 공통 사용)."""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='infoboard_tags')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default='#6366f1')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ('owner', 'name')
        verbose_name = '태그'
        verbose_name_plural = '태그 목록'

    def __str__(self):
        return self.name


# ── Board ────────────────────────────────────────────────

class Board(models.Model):
    """정보 모음 보드."""
    LAYOUT_CHOICES = [
        ('grid', '격자형'),
        ('list', '목록형'),
        ('timeline', '타임라인'),
    ]
    COLOR_CHOICES = [
        ('blue', '파란색'),
        ('green', '초록색'),
        ('purple', '보라색'),
        ('orange', '주황색'),
        ('red', '빨간색'),
        ('dark', '어두운색'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='infoboard_boards')
    title = models.CharField(max_length=200, help_text='보드 이름')
    description = models.TextField(blank=True, help_text='보드 설명')
    icon = models.CharField(max_length=10, default='📌', help_text='이모지 아이콘')
    color_theme = models.CharField(max_length=20, choices=COLOR_CHOICES, default='purple')
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='grid')
    is_public = models.BooleanField(default=False, help_text='비로그인 열람 허용')
    allow_student_submit = models.BooleanField(default=False, help_text='학생 카드 제출 허용')
    shared_roster_group = models.ForeignKey(
        "handoff.HandoffRosterGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="infoboard_boards",
        help_text="학생 제출 이름을 공용 명부와 연결",
    )
    access_code = models.CharField(max_length=6, unique=True, null=True, blank=True, help_text='6자리 입장코드')
    tags = models.ManyToManyField(Tag, blank=True, related_name='boards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = '보드'
        verbose_name_plural = '보드 목록'

    def __str__(self):
        return f'{self.icon} {self.title}'

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = self._generate_unique_code()
        super().save(*args, **kwargs)

    @property
    def card_count(self):
        return self.cards.count()

    @staticmethod
    def _generate_unique_code():
        import random
        import string
        for _ in range(100):
            code = ''.join(random.choices(string.digits, k=6))
            if not Board.objects.filter(access_code=code).exists():
                return code
        return None


# ── Card ─────────────────────────────────────────────────

class Card(models.Model):
    """보드 안의 정보 카드."""
    TYPE_CHOICES = [
        ('link', '링크'),
        ('file', '파일'),
        ('image', '이미지'),
        ('text', '메모'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='cards')
    author_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='infoboard_cards')
    author_name = models.CharField(max_length=100, blank=True, help_text='비로그인 제출자 이름')
    card_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='text')
    title = models.CharField(max_length=300, help_text='카드 제목')
    content = models.TextField(blank=True, help_text='텍스트/메모 내용')
    url = models.URLField(max_length=1000, blank=True, help_text='링크 URL')
    file = models.FileField(upload_to='infoboard/files/', null=True, blank=True, storage=_get_raw_storage)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(default=0, help_text='파일 크기(bytes)')
    image = models.ImageField(upload_to='infoboard/images/', null=True, blank=True)
    color = models.CharField(max_length=20, blank=True, help_text='카드 배경색 hex')
    # OG 메타데이터 (링크 카드 자동 추출)
    og_title = models.CharField(max_length=500, blank=True, help_text='OG 제목')
    og_description = models.TextField(blank=True, help_text='OG 설명')
    og_image = models.URLField(max_length=1000, blank=True, help_text='OG 이미지 URL')
    og_site_name = models.CharField(max_length=200, blank=True, help_text='OG 사이트명')
    is_pinned = models.BooleanField(default=False, help_text='상단 고정')
    display_order = models.IntegerField(default=0)
    tags = models.ManyToManyField(Tag, blank=True, related_name='cards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', 'display_order', '-created_at']
        verbose_name = '카드'
        verbose_name_plural = '카드 목록'

    def __str__(self):
        return f'[{self.get_card_type_display()}] {self.title}'

    @property
    def display_author(self):
        if self.author_user:
            profile = getattr(self.author_user, 'userprofile', None)
            if profile and profile.nickname:
                return profile.nickname
            return self.author_user.username
        return self.author_name or '익명'


# ── Collection ───────────────────────────────────────────

class Collection(models.Model):
    """보드의 묶음 (컬렉션)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='infoboard_collections')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    boards = models.ManyToManyField(Board, blank=True, related_name='collections')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = '컬렉션'
        verbose_name_plural = '컬렉션 목록'

    def __str__(self):
        return self.title


# ── SharedLink ───────────────────────────────────────────

class SharedLink(models.Model):
    """보드 공유 링크."""
    ACCESS_CHOICES = [
        ('view', '보기만'),
        ('submit', '카드 제출'),
        ('edit', '편집'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='shared_links')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='infoboard_shared_links')
    access_level = models.CharField(max_length=10, choices=ACCESS_CHOICES, default='view')
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    access_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '공유 링크'
        verbose_name_plural = '공유 링크 목록'

    def __str__(self):
        return f'{self.board.title} → {self.get_access_level_display()}'

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
