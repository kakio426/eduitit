from django.db import models
from django.contrib.auth.models import User
import uuid
from django.conf import settings
from django.core.files.storage import default_storage


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection_requests')
    access_code = models.CharField(max_length=6, unique=True, null=True, blank=True, help_text="6자리 입장코드")
    title = models.CharField(max_length=200, help_text="수합 제목")
    description = models.TextField(blank=True, help_text="안내사항")
    allow_file = models.BooleanField(default=True, help_text="파일 업로드 허용")
    allow_link = models.BooleanField(default=True, help_text="링크 제출 허용")
    allow_text = models.BooleanField(default=True, help_text="텍스트 제출 허용")
    deadline = models.DateTimeField(null=True, blank=True, help_text="마감일시")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
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
        """줄바꿈으로 구분된 제출자 목록을 리스트로 반환"""
        if not self.expected_submitters:
            return []
        return [name.strip() for name in self.expected_submitters.strip().splitlines() if name.strip()]

    @property
    def is_deadline_passed(self):
        if not self.deadline:
            return False
        from django.utils import timezone
        return timezone.now() > self.deadline


class Submission(models.Model):
    """제출물"""
    TYPE_CHOICES = [
        ('file', '파일'),
        ('link', '링크'),
        ('text', '텍스트'),
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
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_downloaded = models.BooleanField(default=False, help_text="다운로드 여부")

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = '제출물'
        verbose_name_plural = '제출물 목록'

    def __str__(self):
        return f"{self.contributor_name} - {self.get_submission_type_display()}"
