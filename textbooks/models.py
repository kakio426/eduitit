import hashlib
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TextbookMaterial(models.Model):
    SOURCE_HTML = "html"
    SOURCE_MARKDOWN = "markdown"
    SOURCE_PDF = "pdf"
    SOURCE_CHOICES = [
        (SOURCE_HTML, "HTML"),
        (SOURCE_MARKDOWN, "Markdown"),
        (SOURCE_PDF, "PDF"),
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
        related_name="textbook_materials",
    )
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, verbose_name="과목")
    grade = models.CharField(max_length=50, blank=True, verbose_name="학년/학기")
    unit_title = models.CharField(max_length=200, verbose_name="단원명")
    title = models.CharField(max_length=200, verbose_name="자료 제목")
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_MARKDOWN,
        verbose_name="자료 형식",
    )
    content = models.TextField(blank=True, verbose_name="자료 내용/메모")
    pdf_file = models.FileField(upload_to="textbooks/pdf/%Y/%m/", blank=True, null=True)
    page_count = models.PositiveIntegerField(default=0)
    pdf_sha256 = models.CharField(max_length=64, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=False, verbose_name="공개 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.source_type == self.SOURCE_PDF and not self.pdf_file:
            raise ValidationError({"pdf_file": "PDF 자료에는 파일이 필요합니다."})
        if self.source_type != self.SOURCE_PDF and self.pdf_file:
            raise ValidationError({"pdf_file": "PDF 형식일 때만 파일을 업로드할 수 있습니다."})

    @property
    def is_html_document(self):
        return self.source_type == self.SOURCE_HTML

    @property
    def is_pdf(self):
        return self.source_type == self.SOURCE_PDF

    def mark_pdf_digest(self, uploaded_file):
        sha256 = hashlib.sha256()
        uploaded_file.seek(0)
        for chunk in uploaded_file.chunks():
            sha256.update(chunk)
        uploaded_file.seek(0)
        self.pdf_sha256 = sha256.hexdigest()


class TextbookLiveSession(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_LIVE = "live"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "준비 중"),
        (STATUS_LIVE, "진행 중"),
        (STATUS_ENDED, "종료"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(
        TextbookMaterial,
        on_delete=models.CASCADE,
        related_name="live_sessions",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="textbook_live_sessions",
    )
    classroom = models.ForeignKey(
        "happy_seed.HSClassroom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="textbook_live_sessions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    join_code = models.CharField(max_length=6, db_index=True)
    allow_student_annotation = models.BooleanField(default=False)
    follow_mode = models.BooleanField(default=True)
    current_page = models.PositiveIntegerField(default=1)
    zoom_scale = models.FloatField(default=1.0)
    viewport_json = models.JSONField(default=dict, blank=True)
    last_seq = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at", "-created_at"]

    def __str__(self):
        return f"{self.material.title} ({self.get_status_display()})"

    @property
    def is_live(self):
        return self.status == self.STATUS_LIVE


class TextbookLivePageState(models.Model):
    session = models.ForeignKey(
        TextbookLiveSession,
        on_delete=models.CASCADE,
        related_name="page_states",
    )
    page_index = models.PositiveIntegerField()
    fabric_json = models.JSONField(default=dict, blank=True)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("session", "page_index")
        ordering = ["page_index"]

    def __str__(self):
        return f"{self.session_id}:{self.page_index}"


class TextbookLiveEvent(models.Model):
    ACTOR_TEACHER = "teacher"
    ACTOR_STUDENT = "student"
    ACTOR_DISPLAY = "display"
    ACTOR_SYSTEM = "system"
    ACTOR_CHOICES = [
        (ACTOR_TEACHER, "교사"),
        (ACTOR_STUDENT, "학생"),
        (ACTOR_DISPLAY, "전광판"),
        (ACTOR_SYSTEM, "시스템"),
    ]

    session = models.ForeignKey(
        TextbookLiveSession,
        on_delete=models.CASCADE,
        related_name="events",
    )
    seq = models.PositiveIntegerField()
    event_type = models.CharField(max_length=50)
    page_index = models.PositiveIntegerField(null=True, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)
    actor_role = models.CharField(max_length=20, choices=ACTOR_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("session", "seq")
        ordering = ["seq"]

    def __str__(self):
        return f"{self.session_id}:{self.seq}:{self.event_type}"


class TextbookLiveParticipant(models.Model):
    ROLE_TEACHER = "teacher"
    ROLE_STUDENT = "student"
    ROLE_DISPLAY = "display"
    ROLE_CHOICES = [
        (ROLE_TEACHER, "교사"),
        (ROLE_STUDENT, "학생"),
        (ROLE_DISPLAY, "TV 화면"),
    ]

    session = models.ForeignKey(
        TextbookLiveSession,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="textbook_live_participations",
    )
    display_name = models.CharField(max_length=80, blank=True)
    device_id = models.CharField(max_length=64)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_connected = models.BooleanField(default=True)

    class Meta:
        unique_together = ("session", "device_id")
        ordering = ["role", "display_name", "joined_at"]

    def __str__(self):
        return self.display_name or f"{self.role}:{self.device_id}"
