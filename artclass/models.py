import os

from django.db import models
from django.contrib.auth.models import User


def artclass_material_upload_to(instance, filename):
    safe_name = os.path.basename(str(filename or "").strip()) or "material"
    art_class_id = instance.art_class_id or "unassigned"
    return f"artclass/materials/{art_class_id}/{safe_name}"


class ArtClass(models.Model):
    """미술 수업 정보를 저장하는 모델"""
    PLAYBACK_MODE_EMBED = "embed"
    PLAYBACK_MODE_EXTERNAL_WINDOW = "external_window"
    PLAYBACK_MODE_CHOICES = [
        (PLAYBACK_MODE_EMBED, "브라우저 임베드 (레거시)"),
        (PLAYBACK_MODE_EXTERNAL_WINDOW, "런처 시작 (기본)"),
    ]

    title = models.CharField(max_length=200, blank=True, verbose_name="수업 제목")
    youtube_url = models.URLField(verbose_name="유튜브 URL")
    default_interval = models.PositiveIntegerField(default=10, verbose_name="기본 간격(초)")
    playback_mode = models.CharField(
        max_length=24,
        choices=PLAYBACK_MODE_CHOICES,
        default=PLAYBACK_MODE_EXTERNAL_WINDOW,
        verbose_name="영상 재생 모드",
        help_text="기본 시작은 런처입니다. 브라우저 임베드는 레거시 호환용으로만 유지됩니다.",
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
    auto_category = models.CharField(max_length=32, blank=True, default="", verbose_name="자동 카테고리")
    auto_grade_band = models.CharField(max_length=16, blank=True, default="", verbose_name="자동 학년군")
    auto_tags = models.JSONField(default=list, blank=True, verbose_name="자동 태그")
    auto_confidence = models.FloatField(default=0.0, verbose_name="자동 분류 신뢰도")
    search_text = models.TextField(blank=True, default="", verbose_name="검색 텍스트")
    is_auto_classified = models.BooleanField(default=False, verbose_name="자동 분류 완료")
    teacher_material_note = models.TextField(blank=True, default="", verbose_name="교사용 자료 활용 메모")

    class Meta:
        verbose_name = "미술 수업"
        verbose_name_plural = "미술 수업들"
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"수업 #{self.pk}"

    @property
    def display_title(self):
        return (self.title or "").strip() or f"수업 #{self.pk}"


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


class ArtClassAttachment(models.Model):
    """교사용 수업 자료 첨부 파일"""
    art_class = models.ForeignKey(
        ArtClass,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="수업",
    )
    file = models.FileField(upload_to=artclass_material_upload_to, verbose_name="첨부 파일")
    original_name = models.CharField(max_length=255, blank=True, default="", verbose_name="원본 파일명")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="정렬 순서")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "수업 자료 첨부"
        verbose_name_plural = "수업 자료 첨부"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.original_name or os.path.basename(self.file.name) or f"자료 #{self.pk}"
