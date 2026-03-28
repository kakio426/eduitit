import random
import string
import uuid

from django.conf import settings
from django.db import models


class NextEduMaterial(models.Model):
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

    class EntryMode(models.TextChoices):
        LEARN = "learn", "처음 배우기"
        STARTER = "starter", "예시로 시작"
        IMPORT = "import", "기존 버전에서 가져오기"
        PASTE = "paste", "HTML 붙여넣기"
        FILE = "file", "HTML 파일 올리기"

    class DifficultyLevel(models.TextChoices):
        BEGINNER = "beginner", "입문"
        INTERMEDIATE = "intermediate", "확장"
        ADVANCED = "advanced", "응용"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="edu_materials_next",
    )
    title = models.CharField(max_length=200, verbose_name="자료 제목")
    html_content = models.TextField(verbose_name="HTML 코드")
    access_code = models.CharField(max_length=6, unique=True, null=True, blank=True)
    is_published = models.BooleanField(default=True, verbose_name="학생 공유 여부")
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, default="OTHER", blank=True)
    grade = models.CharField(max_length=50, blank=True, default="")
    unit_title = models.CharField(max_length=200, blank=True, default="")
    material_type = models.CharField(
        max_length=20,
        choices=MaterialType.choices,
        default=MaterialType.OTHER,
    )
    summary = models.CharField(max_length=120, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    search_text = models.TextField(blank=True, default="")
    entry_mode = models.CharField(max_length=20, choices=EntryMode.choices, default=EntryMode.LEARN)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    teacher_guide = models.TextField(blank=True, default="")
    student_questions = models.JSONField(default=list, blank=True)
    remix_tips = models.JSONField(default=list, blank=True)
    estimated_minutes = models.PositiveIntegerField(default=15)
    difficulty_level = models.CharField(
        max_length=20,
        choices=DifficultyLevel.choices,
        default=DifficultyLevel.BEGINNER,
    )
    reflection_note = models.TextField(blank=True, default="")
    legacy_source_material_id = models.UUIDField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "legacy_source_material_id"],
                condition=models.Q(legacy_source_material_id__isnull=False),
                name="edu_materials_next_unique_import_per_teacher_legacy",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = self.generate_unique_access_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_access_code():
        for _ in range(100):
            code = "".join(random.choices(string.digits, k=6))
            if not NextEduMaterial.objects.filter(access_code=code).exists():
                return code
        raise RuntimeError("학생 공유 코드를 생성하지 못했습니다.")

    def __str__(self):
        return self.title

