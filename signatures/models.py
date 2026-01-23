import uuid
from django.db import models
from django.contrib.auth.models import User


class TrainingSession(models.Model):
    """연수 정보 모델"""
    title = models.CharField('연수 제목', max_length=200)
    instructor = models.CharField('강사명', max_length=100)
    datetime = models.DateTimeField('연수 일시')
    location = models.CharField('장소', max_length=200)
    description = models.TextField('설명', blank=True)

    # UUID for public access (prevents ID guessing)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Creator
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='training_sessions',
        verbose_name='생성자'
    )
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    # Session status
    is_active = models.BooleanField('서명 받기 활성화', default=True)

    class Meta:
        verbose_name = '연수'
        verbose_name_plural = '연수 목록'
        ordering = ['-datetime']

    def __str__(self):
        return f"{self.title} ({self.datetime.strftime('%Y-%m-%d')})"

    @property
    def signature_count(self):
        return self.signatures.count()


class Signature(models.Model):
    """서명 정보 모델"""
    training_session = models.ForeignKey(
        TrainingSession,
        on_delete=models.CASCADE,
        related_name='signatures',
        verbose_name='연수'
    )
    participant_affiliation = models.CharField('직위/학년반', max_length=100, blank=True)
    participant_name = models.CharField('참여자 이름', max_length=50)

    # Store signature as Base64 - efficient for small images
    signature_data = models.TextField('서명 데이터 (Base64)')

    created_at = models.DateTimeField('서명 일시', auto_now_add=True)

    class Meta:
        verbose_name = '서명'
        verbose_name_plural = '서명 목록'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.participant_name} - {self.training_session.title}"
