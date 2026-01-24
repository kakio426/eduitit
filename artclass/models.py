from django.db import models
from django.contrib.auth.models import User


class ArtClass(models.Model):
    """미술 수업 정보를 저장하는 모델"""
    title = models.CharField(max_length=200, blank=True, verbose_name="수업 제목")
    youtube_url = models.URLField(verbose_name="유튜브 URL")
    default_interval = models.PositiveIntegerField(default=10, verbose_name="기본 간격(초)")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='art_classes',
        verbose_name="생성자"
    )

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
