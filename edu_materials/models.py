import uuid

from django.conf import settings
from django.db import models


class EduMaterial(models.Model):
    INPUT_PASTE = "paste"
    INPUT_FILE = "file"
    INPUT_MODE_CHOICES = [
        (INPUT_PASTE, "코드 붙여넣기"),
        (INPUT_FILE, "HTML 파일 업로드"),
    ]

    SUBJECT_CHOICES = [
        ("KOREAN", "국어"),
        ("MATH", "수학"),
        ("SOCIAL", "사회"),
        ("SCIENCE", "과학"),
        ("OTHER", "기타"),
    ]

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
    is_published = models.BooleanField(default=True, verbose_name="공개 여부")
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return self.title
