from datetime import timedelta
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.db import models
from django.db.models import Q
from django.utils import timezone


def get_raw_storage():
    """Cloudinary가 설정된 경우에만 Cloudinary 로컬/원격 저장소 반환, 
    그렇지 않으면 장고 기본 저장소(FileSystemStorage) 반환"""
    if getattr(settings, 'USE_CLOUDINARY', False):
        try:
            from cloudinary_storage.storage import RawMediaCloudinaryStorage
            return RawMediaCloudinaryStorage()
        except (ImportError, Exception):
            return default_storage
    return default_storage


class CollectionRequest(models.Model):
    """수합 요청"""
    STATUS_CHOICES = [
        ('active', '진행중'),
        ('closed', '마감'),
        ('archived', '보관'),
    ]
    CHOICE_MODE_CHOICES = [
        ('single', '단일 선택'),
        ('multi', '복수 선택'),
    ]
    BTI_INTEGRATION_SOURCE_CHOICES = [
        ("none", "사용 안 함"),
        ("ssambti", "쌤BTI"),
        ("studentmbti", "우리반BTI"),
        ("both", "쌤BTI + 우리반BTI"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection_requests')
    shared_roster_group = models.ForeignKey(
        "handoff.HandoffRosterGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collect_requests",
        help_text="배부 체크 명단과 연동할 대상 (선택)",
    )
    access_code = models.CharField(max_length=6, unique=True, null=True, blank=True, help_text="6자리 입장코드")
    title = models.CharField(max_length=200, help_text="수합 제목")
    description = models.TextField(blank=True, help_text="안내사항")
    allow_file = models.BooleanField(default=True, help_text="파일 업로드 허용")
    allow_link = models.BooleanField(default=True, help_text="링크 제출 허용")
    allow_text = models.BooleanField(default=True, help_text="텍스트 제출 허용")
    allow_choice = models.BooleanField(default=False, help_text="선택형 제출 허용")
    choice_mode = models.CharField(
        max_length=10,
        choices=CHOICE_MODE_CHOICES,
        default='single',
        help_text="선택형 제출 모드",
    )
    bti_integration_source = models.CharField(
        max_length=20,
        choices=BTI_INTEGRATION_SOURCE_CHOICES,
        default="none",
        help_text="BTI 결과 연동 대상",
    )
    choice_options = models.JSONField(default=list, blank=True, help_text="선택형 보기 목록")
    choice_min_selections = models.PositiveIntegerField(default=1, help_text="복수 선택 최소 개수")
    choice_max_selections = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="복수 선택 최대 개수 (비우면 제한 없음)",
    )
    choice_allow_other = models.BooleanField(default=False, help_text="기타 직접 입력 허용")
    deadline = models.DateTimeField(null=True, blank=True, help_text="마감일시")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    closed_at = models.DateTimeField(null=True, blank=True, help_text="마감 처리 시각")
    retention_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="자동 정리 유예 시각",
    )
    max_file_size_mb = models.IntegerField(default=30, help_text="파일당 최대 크기(MB)")
    max_submissions = models.IntegerField(default=50, help_text="최대 제출 건수")
    expected_submitters = models.TextField(blank=True, help_text="예상 제출자 목록 (줄바꿈 구분)")
    template_file = models.FileField(
        upload_to='collect/templates/', 
        null=True, blank=True, 
        storage=get_raw_storage,
        help_text="양식 파일 (hwp, xlsx 등)"
    )
    template_file_name = models.CharField(max_length=255, blank=True, help_text="양식 파일 원본 이름")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '수합 요청'
        verbose_name_plural = '수합 요청 목록'

    def __str__(self):
        return f"{self.title} ({self.creator.username})"

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = CollectionRequest.generate_unique_access_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_access_code():
        import random
        import string
        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not CollectionRequest.objects.filter(access_code=code).exists():
                return code

    @property
    def submission_count(self):
        return self.submissions.count()

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def expected_submitters_list(self):
        """배부 체크 공유 명단 + 수동 입력 명단을 합쳐 제출자 목록으로 반환"""
        merged = []
        seen = set()

        for name in self._shared_roster_names():
            if name in seen:
                continue
            seen.add(name)
            merged.append(name)

        for name in self._manual_submitter_names():
            if name in seen:
                continue
            seen.add(name)
            merged.append(name)

        return merged

    def _manual_submitter_names(self):
        if not self.expected_submitters:
            return []
        return [name.strip() for name in self.expected_submitters.strip().splitlines() if name.strip()]

    def _shared_roster_names(self):
        group = self.shared_roster_group
        if not group or group.owner_id != self.creator_id:
            return []

        names = []
        seen = set()
        rows = group.members.filter(is_active=True).order_by("sort_order", "id").values_list("display_name", flat=True)
        for raw_name in rows:
            name = str(raw_name or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        return names

    @property
    def allowed_submission_types(self):
        submission_types = []
        if self.allow_file:
            submission_types.append('file')
        if self.allow_link:
            submission_types.append('link')
        if self.allow_text:
            submission_types.append('text')
        if self.allow_choice:
            submission_types.append('choice')
        return submission_types

    @property
    def normalized_choice_options(self):
        if not isinstance(self.choice_options, list):
            return []
        options = []
        seen = set()
        for raw_option in self.choice_options:
            option = str(raw_option).strip()
            if not option or option in seen:
                continue
            options.append(option)
            seen.add(option)
        return options

    @property
    def is_deadline_passed(self):
        if not self.deadline:
            return False
        return timezone.now() > self.deadline

    def extend_deadline(self, days):
        """마감 기한을 지정된 일수만큼 연장한다."""
        now = timezone.now()
        base = self.deadline if self.deadline and self.deadline > now else now
        self.deadline = base + timedelta(days=days)
        self.save(update_fields=["deadline", "updated_at"])

    def extend_retention(self, days):
        """자동 정리 유예 기한을 지정된 일수만큼 연장한다."""
        now = timezone.now()
        base = self.retention_until if self.retention_until and self.retention_until > now else now
        self.retention_until = base + timedelta(days=days)
        self.save(update_fields=["retention_until", "updated_at"])


class Submission(models.Model):
    """제출물"""
    TYPE_CHOICES = [
        ('file', '파일'),
        ('link', '링크'),
        ('text', '텍스트'),
        ('choice', '선택형'),
    ]
    INTEGRATION_SOURCE_CHOICES = [
        ("", "직접 제출"),
        ("ssambti", "쌤BTI"),
        ("studentmbti", "우리반BTI"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collection_request = models.ForeignKey(CollectionRequest, on_delete=models.CASCADE, related_name='submissions')
    contributor_name = models.CharField(max_length=100, help_text="제출자 이름")
    contributor_affiliation = models.CharField(max_length=100, blank=True, help_text="소속")
    submission_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    # 파일 제출 (이미지 외 일반 파일 허용을 위해 Raw 스토리지 사용)
    file = models.FileField(upload_to='collect/submissions/', null=True, blank=True, storage=get_raw_storage)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(default=0, help_text="파일 크기(bytes)")

    # 관리용 보안 ID (로그인 없이 수정/삭제 접근용)
    management_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # 링크 제출
    link_url = models.URLField(max_length=500, blank=True)
    link_description = models.CharField(max_length=200, blank=True)
    # 텍스트 제출
    text_content = models.TextField(blank=True)
    # 선택형 제출
    choice_answers = models.JSONField(default=list, blank=True)
    choice_other_text = models.TextField(blank=True)
    integration_source = models.CharField(
        max_length=20,
        choices=INTEGRATION_SOURCE_CHOICES,
        default="",
        blank=True,
        help_text="외부/연동 경로 식별자",
    )
    integration_ref = models.CharField(
        max_length=120,
        default="",
        blank=True,
        help_text="연동 중복 방지를 위한 외부 참조 키",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_downloaded = models.BooleanField(default=False, help_text="다운로드 여부")

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = '제출물'
        verbose_name_plural = '제출물 목록'
        constraints = [
            models.UniqueConstraint(
                fields=["collection_request", "integration_source", "integration_ref"],
                condition=~Q(integration_source="") & ~Q(integration_ref=""),
                name="collect_submission_unique_integration_ref",
            ),
        ]

    def __str__(self):
        return f"{self.contributor_name} - {self.get_submission_type_display()}"

    @property
    def choice_summary(self):
        if self.submission_type != 'choice':
            return ''
        answers = self.choice_answers if isinstance(self.choice_answers, list) else []
        tokens = [str(answer).strip() for answer in answers if str(answer).strip()]
        if self.choice_other_text.strip():
            tokens.append(f"기타: {self.choice_other_text.strip()}")
        return ", ".join(tokens)
