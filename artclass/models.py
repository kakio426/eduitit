from django.db import models
from django.contrib.auth.models import User


class ArtClass(models.Model):
    """미술 수업 정보를 저장하는 모델"""
    PLAYBACK_MODE_EMBED = "embed"
    PLAYBACK_MODE_EXTERNAL_WINDOW = "external_window"
    PLAYBACK_MODE_CHOICES = [
        (PLAYBACK_MODE_EMBED, "내장 플레이어 (기본)"),
        (PLAYBACK_MODE_EXTERNAL_WINDOW, "새 창 재생 (임베드 차단 대응)"),
    ]

    title = models.CharField(max_length=200, blank=True, verbose_name="수업 제목")
    youtube_url = models.URLField(verbose_name="유튜브 URL")
    default_interval = models.PositiveIntegerField(default=10, verbose_name="기본 간격(초)")
    playback_mode = models.CharField(
        max_length=24,
        choices=PLAYBACK_MODE_CHOICES,
        default=PLAYBACK_MODE_EMBED,
        verbose_name="영상 재생 모드",
        help_text="임베드 불가 영상일 경우 새 창 재생 모드를 사용할 수 있습니다.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='art_classes',
        verbose_name="생성자"
    )
    is_shared = models.BooleanField(default=True, verbose_name="공유 여부")
    view_count = models.PositiveIntegerField(default=0, verbose_name="조회수")

    class Meta:
        verbose_name = "미술 수업"
        verbose_name_plural = "미술 수업들"
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"수업 #{self.pk}"


class ArtStep(models.Model):
    """수업의 각 단계를 저장하는 모델"""
    art_class = models.ForeignKey(
        ArtClass, on_delete=models.CASCADE, 
        related_name='steps',
        verbose_name="수업"
    )
    step_number = models.PositiveIntegerField(verbose_name="단계 번호")
    description = models.TextField(blank=True, verbose_name="설명")
    image = models.ImageField(
        upload_to='artclass/steps/', 
        blank=True, null=True,
        verbose_name="참고 이미지"
    )

    class Meta:
        verbose_name = "수업 단계"
        verbose_name_plural = "수업 단계들"
        ordering = ['step_number']

    def __str__(self):
        return f"Step {self.step_number}: {self.description[:30]}..." if self.description else f"Step {self.step_number}"
