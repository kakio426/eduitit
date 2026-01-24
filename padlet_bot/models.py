from django.db import models
from django.contrib.auth.models import User


class PadletDocument(models.Model):
    """패들릿 내보내기 문서"""

    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
    ]

    title = models.CharField('문서 제목', max_length=200)
    file = models.FileField('파일', upload_to='padlet_bot/docs/')
    file_type = models.CharField(
        '파일 유형',
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        default='pdf'
    )
    description = models.TextField('설명', blank=True)

    # 처리 상태
    is_processed = models.BooleanField('벡터DB 처리 완료', default=False)
    chunk_count = models.IntegerField('청크 수', default=0)

    # 메타 정보
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_padlet_docs',
        verbose_name='업로드한 사용자'
    )
    created_at = models.DateTimeField('업로드일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '패들릿 문서'
        verbose_name_plural = '패들릿 문서 목록'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_file_type_display()}] {self.title}"

    @property
    def file_extension(self):
        """파일 확장자 반환"""
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return ''

    def save(self, *args, **kwargs):
        # 파일 확장자에 따라 file_type 자동 설정
        if self.file and not self.file_type:
            ext = self.file_extension
            if ext == 'csv':
                self.file_type = 'csv'
            else:
                self.file_type = 'pdf'
        super().save(*args, **kwargs)


class LinkedPadletBoard(models.Model):
    """API로 연동된 패들릿 보드"""

    board_id = models.CharField('보드 ID', max_length=100, unique=True)
    board_url = models.URLField('패들릿 URL', blank=True)
    title = models.CharField('보드 제목', max_length=200)
    description = models.TextField('보드 설명', blank=True)
    post_count = models.IntegerField('게시물 수', default=0)

    # 처리 상태
    is_processed = models.BooleanField('벡터DB 처리 완료', default=False)
    chunk_count = models.IntegerField('청크 수', default=0)
    last_synced = models.DateTimeField('마지막 동기화', null=True, blank=True)

    # 메타 정보
    linked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='linked_padlet_boards',
        verbose_name='연동한 사용자'
    )
    created_at = models.DateTimeField('연동일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '연동된 패들릿'
        verbose_name_plural = '연동된 패들릿 목록'
        ordering = ['-created_at']

    def __str__(self):
        return f"[API] {self.title}"


class PadletBotSettings(models.Model):
    """패들릿 봇 설정 (시스템 프롬프트 관리)"""

    name = models.CharField('설정 이름', max_length=100, unique=True)
    system_prompt = models.TextField('시스템 프롬프트')
    welcome_message = models.TextField('환영 메시지', blank=True)
    is_active = models.BooleanField('활성화', default=True)

    class Meta:
        verbose_name = '패들릿 봇 설정'
        verbose_name_plural = '패들릿 봇 설정 목록'

    def __str__(self):
        return self.name
