import random
import string
import uuid

from django.conf import settings
from django.db import models


class EduMaterial(models.Model):
    INPUT_PASTE = "paste"
    INPUT_FILE = "file"
    INPUT_MODE_CHOICES = [
        (INPUT_PASTE, "자료 붙여넣기"),
        (INPUT_FILE, "파일 올리기"),
    ]

    SUBJECT_CHOICES = [
        ("KOREAN", "국어"),
        ("MATH", "수학"),
        ("SOCIAL", "사회"),
        ("SCIENCE", "과학"),
        ("OTHER", "기타"),
    ]

    class MaterialType(models.TextChoices):
        INTRO = "intro", "도입"
        EXPLORATION = "exploration", "탐구"
        PRACTICE = "practice", "연습"
        QUIZ = "quiz", "퀴즈"
        GAME = "game", "게임"
        REFERENCE = "reference", "참고자료"
        PRESENTATION = "presentation", "발표"
        TOOL = "tool", "도구"
        OTHER = "other", "기타"

    class MetadataStatus(models.TextChoices):
        PENDING = "pending", "분류 대기"
        DONE = "done", "분류 완료"
        FAILED = "failed", "분류 실패"

    class MetadataSource(models.TextChoices):
        AUTO = "auto", "자동 분류"
        MANUAL = "manual", "직접 수정"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="edu_materials",
    )
    subject = models.CharField(
        max_length=20,
        choices=SUBJECT_CHOICES,
        default="OTHER",
        blank=True,
        verbose_name="과목",
    )
    grade = models.CharField(max_length=50, blank=True, default="", verbose_name="학년/학기")
    unit_title = models.CharField(max_length=200, blank=True, default="", verbose_name="단원명")
    title = models.CharField(max_length=200, verbose_name="자료 제목")
    html_content = models.TextField(verbose_name="HTML 코드")
    input_mode = models.CharField(
        max_length=10,
        choices=INPUT_MODE_CHOICES,
        default=INPUT_PASTE,
        verbose_name="입력 방식",
    )
    original_filename = models.CharField(max_length=255, blank=True)
    material_type = models.CharField(
        max_length=20,
        choices=MaterialType.choices,
        default=MaterialType.OTHER,
        verbose_name="자료 유형",
    )
    tags = models.JSONField(default=list, blank=True, verbose_name="태그")
    summary = models.CharField(max_length=120, blank=True, default="", verbose_name="한줄 요약")
    search_text = models.TextField(blank=True, default="", verbose_name="검색 텍스트")
    access_code = models.CharField(max_length=6, unique=True, null=True, blank=True, help_text="학생 공유 코드")
    metadata_status = models.CharField(
        max_length=20,
        choices=MetadataStatus.choices,
        default=MetadataStatus.PENDING,
        verbose_name="분류 상태",
    )
    metadata_source = models.CharField(
        max_length=20,
        choices=MetadataSource.choices,
        default=MetadataSource.AUTO,
        verbose_name="분류 출처",
    )
    metadata_confidence = models.FloatField(default=0.0, verbose_name="자동 분류 신뢰도")
    is_published = models.BooleanField(default=True, verbose_name="공개 여부")
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = self.generate_unique_access_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_access_code():
        for _ in range(100):
            code = "".join(random.choices(string.digits, k=6))
            if not EduMaterial.objects.filter(access_code=code).exists():
                return code
        raise RuntimeError("학생 공유 코드를 생성하지 못했습니다.")

    def __str__(self):
        return self.title
