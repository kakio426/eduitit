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
    
    # Attendance tracking
    expected_count = models.IntegerField(
        '예상 참석 인원',
        null=True,
        blank=True,
        help_text='입력 시 진행률을 실시간으로 확인할 수 있습니다'
    )

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


class SignatureStyle(models.Model):
    """사용자가 즐겨찾는 서명 스타일"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='signature_styles')
    name = models.CharField('스타일 이름', max_length=100, default='내 서명 스타일')
    
    # 스타일 옵션들
    font_family = models.CharField('폰트', max_length=100, default='Nanum Brush Script')
    color = models.CharField('글자 색상', max_length=20, default='#000000')
    background_color = models.CharField('배경 색상', max_length=20, default='transparent')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}의 스타일: {self.name}"


class SavedSignature(models.Model):
    """사용자가 저장한 서명 이미지"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_signatures')
    image_data = models.TextField('이미지 데이터 (Base64)') # 간단하게 텍스트로 저장 (실제 서비스에선 ImageField + S3 권장)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}의 서명 ({self.created_at.strftime('%Y-%m-%d')})"


class ExpectedParticipant(models.Model):
    """예상 참석자 명단"""
    training_session = models.ForeignKey(
        TrainingSession,
        on_delete=models.CASCADE,
        related_name='expected_participants',
        verbose_name='연수'
    )
    name = models.CharField('이름', max_length=100)
    affiliation = models.CharField(
        '소속/학년반',
        max_length=100,
        blank=True,
        help_text='예: 1-1, 2-3, 교사'
    )
    
    # Matching metadata
    matched_signature = models.ForeignKey(
        Signature,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_expected',
        verbose_name='매칭된 서명'
    )
    is_confirmed = models.BooleanField('매칭 확인', default=False)
    match_note = models.CharField(
        '매칭 메모',
        max_length=200,
        blank=True,
        help_text='예: 오타 수정 (박영이 → 박영희)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name', 'affiliation']
        unique_together = ('training_session', 'name', 'affiliation')
        verbose_name = '예상 참석자'
        verbose_name_plural = '예상 참석자 목록'
    
    def __str__(self):
        if self.affiliation:
            return f"{self.name} ({self.affiliation})"
        return self.name
    
    @property
    def has_signed(self):
        """서명 완료 여부"""
        return self.matched_signature is not None
