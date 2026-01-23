import uuid
from django.db import models
from django.contrib.auth.models import User


class GuidelineDocument(models.Model):
    """학교폭력 관련 가이드북/매뉴얼 문서"""

    CATEGORY_CHOICES = [
        ('guidebook', '사안처리 가이드북'),
        ('manual', '업무 매뉴얼'),
        ('law', '법령/지침'),
        ('case', '사례집'),
        ('other', '기타'),
    ]

    title = models.CharField('문서 제목', max_length=200)
    category = models.CharField('분류', max_length=20, choices=CATEGORY_CHOICES, default='guidebook')
    file = models.FileField('파일', upload_to='school_violence/docs/')
    description = models.TextField('설명', blank=True)

    # 처리 상태
    is_processed = models.BooleanField('벡터DB 처리 완료', default=False)
    chunk_count = models.IntegerField('청크 수', default=0)

    # 메타 정보
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_guidelines',
        verbose_name='업로드한 사용자'
    )
    created_at = models.DateTimeField('업로드일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '가이드라인 문서'
        verbose_name_plural = '가이드라인 문서 목록'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"

    @property
    def file_extension(self):
        """파일 확장자 반환"""
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return ''


class ConsultationMode(models.Model):
    """상담 모드 설정 (시스템 프롬프트 관리)"""

    MODE_CHOICES = [
        ('homeroom', '담임교사 모드'),
        ('officer', '학폭책임교사 모드'),
        ('admin', '교육청/행정 모드'),
    ]

    mode_key = models.CharField('모드 키', max_length=20, choices=MODE_CHOICES, unique=True)
    display_name = models.CharField('표시 이름', max_length=50)
    description = models.TextField('모드 설명')
    system_prompt = models.TextField('시스템 프롬프트')
    icon = models.CharField('아이콘 클래스', max_length=50, default='fa-solid fa-user')
    color = models.CharField('색상 클래스', max_length=50, default='purple')
    is_active = models.BooleanField('활성화', default=True)

    class Meta:
        verbose_name = '상담 모드'
        verbose_name_plural = '상담 모드 목록'

    def __str__(self):
        return self.display_name
