from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils import timezone


def _unique_slug(*, model, source: str, current_pk=None, field_name: str = "slug", prefix: str = "item") -> str:
    base = slugify(source or "", allow_unicode=True).strip("-")[:80] or prefix
    candidate = base
    index = 2
    queryset = model.objects.all()
    if current_pk:
        queryset = queryset.exclude(pk=current_pk)
    while queryset.filter(**{field_name: candidate}).exists():
        suffix = f"-{index}"
        candidate = f"{base[: max(1, 80 - len(suffix))]}{suffix}"
        index += 1
    return candidate


class ProviderProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_program_provider",
    )
    slug = models.SlugField(max_length=100, unique=True, blank=True, allow_unicode=True)
    provider_name = models.CharField(max_length=120, verbose_name="업체명")
    summary = models.CharField(max_length=160, blank=True, verbose_name="한 줄 소개")
    description = models.TextField(blank=True, verbose_name="업체 소개")
    contact_email = models.EmailField(blank=True, verbose_name="대표 이메일")
    contact_phone = models.CharField(max_length=30, blank=True, verbose_name="대표 연락처")
    website = models.URLField(blank=True, verbose_name="홈페이지")
    service_area_summary = models.CharField(max_length=120, blank=True, verbose_name="주 활동 지역")
    verification_document = models.FileField(
        upload_to="schoolprograms/provider_docs/",
        max_length=500,
        blank=True,
        null=True,
        verbose_name="증빙 서류",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider_name", "id"]
        verbose_name = "학교 프로그램 업체"
        verbose_name_plural = "학교 프로그램 업체"

    def __str__(self) -> str:
        return self.provider_name or self.user.username

    def save(self, *args, **kwargs):
        if not self.slug:
            source = self.provider_name or self.user.username or "provider"
            self.slug = _unique_slug(model=ProviderProfile, source=source, current_pk=self.pk, prefix="provider")
        super().save(*args, **kwargs)

    @property
    def is_profile_ready(self) -> bool:
        return bool(self.provider_name and self.summary and self.verification_document)


class ProgramListing(models.Model):
    class Category(models.TextChoices):
        FIELDTRIP = "fieldtrip", "찾아오는 체험학습"
        TEACHER_TRAINING = "teacher_training", "교사연수"
        SCHOOL_EVENT = "school_event", "학교행사"
        SPORTS_DAY = "sports_day", "스포츠데이"
        ONE_DAY_CLASS = "one_day_class", "원데이 클래스"

    class DeliveryMode(models.TextChoices):
        VISITING = "visiting", "학교 방문형"
        EVENT_SUPPORT = "event_support", "행사 지원형"
        HYBRID = "hybrid", "혼합형"
        ONLINE = "online", "온라인/원격형"

    class ApprovalStatus(models.TextChoices):
        DRAFT = "draft", "임시 저장"
        PENDING = "pending", "심사 대기"
        APPROVED = "approved", "공개중"
        REJECTED = "rejected", "반려"

    PROVINCE_CHOICES = [
        ("nationwide", "전국"),
        ("seoul", "서울"),
        ("busan", "부산"),
        ("daegu", "대구"),
        ("incheon", "인천"),
        ("gwangju", "광주"),
        ("daejeon", "대전"),
        ("ulsan", "울산"),
        ("sejong", "세종"),
        ("gyeonggi", "경기"),
        ("gangwon", "강원"),
        ("chungbuk", "충북"),
        ("chungnam", "충남"),
        ("jeonbuk", "전북"),
        ("jeonnam", "전남"),
        ("gyeongbuk", "경북"),
        ("gyeongnam", "경남"),
        ("jeju", "제주"),
    ]

    GRADE_BAND_CHOICES = [
        ("kindergarten", "유치원"),
        ("elementary_low", "초등 저학년"),
        ("elementary_high", "초등 고학년"),
        ("middle", "중학교"),
        ("high", "고등학교"),
        ("teacher_only", "교직원 전용"),
        ("all_school", "전교 단위"),
    ]

    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.CASCADE,
        related_name="listings",
    )
    title = models.CharField(max_length=140, verbose_name="프로그램명")
    slug = models.SlugField(max_length=100, unique=True, blank=True, allow_unicode=True)
    summary = models.CharField(max_length=180, verbose_name="대표 소개")
    description = models.TextField(verbose_name="프로그램 소개")
    category = models.CharField(max_length=40, choices=Category.choices, verbose_name="카테고리")
    theme_tags = models.JSONField(default=list, blank=True, verbose_name="주제 태그")
    theme_tags_text = models.CharField(max_length=300, blank=True, verbose_name="주제 태그 입력값")
    grade_bands = models.JSONField(default=list, blank=True, verbose_name="대상 학년")
    grade_bands_text = models.CharField(max_length=200, blank=True, verbose_name="대상 학년 검색용")
    delivery_mode = models.CharField(max_length=30, choices=DeliveryMode.choices, verbose_name="진행 방식")
    province = models.CharField(max_length=20, choices=PROVINCE_CHOICES, verbose_name="대표 활동 지역")
    city = models.CharField(max_length=80, blank=True, verbose_name="대표 시군구")
    coverage_note = models.CharField(max_length=140, blank=True, verbose_name="추가 방문 가능 권역")
    duration_text = models.CharField(max_length=80, verbose_name="진행 시간")
    capacity_text = models.CharField(max_length=80, verbose_name="수용 인원")
    price_text = models.CharField(max_length=120, verbose_name="가격 표시")
    safety_info = models.TextField(blank=True, verbose_name="안전/보험 안내")
    materials_info = models.TextField(blank=True, verbose_name="준비물/요청 사항")
    faq = models.TextField(blank=True, verbose_name="자주 묻는 질문")
    admin_note = models.TextField(blank=True, verbose_name="운영 메모")
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
        verbose_name="공개 상태",
    )
    is_featured = models.BooleanField(default=False, verbose_name="추천 노출")
    view_count = models.PositiveIntegerField(default=0, verbose_name="누적 조회수")
    submitted_at = models.DateTimeField(blank=True, null=True, verbose_name="심사 요청 시각")
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="공개 시각")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-published_at", "-id"]
        indexes = [
            models.Index(fields=["approval_status", "category", "province"]),
            models.Index(fields=["provider", "approval_status"]),
            models.Index(fields=["slug"]),
        ]
        verbose_name = "학교 프로그램 등록글"
        verbose_name_plural = "학교 프로그램 등록글"

    def __str__(self) -> str:
        return self.title

    def mark_pending_review(self):
        self.approval_status = self.ApprovalStatus.PENDING
        if self.submitted_at is None:
            self.submitted_at = timezone.now()

    def mark_approved(self):
        self.approval_status = self.ApprovalStatus.APPROVED
        if self.published_at is None:
            self.published_at = timezone.now()

    def mark_rejected(self):
        self.approval_status = self.ApprovalStatus.REJECTED

    def mark_draft(self):
        self.approval_status = self.ApprovalStatus.DRAFT

    def save(self, *args, **kwargs):
        if self.approval_status == self.ApprovalStatus.PENDING and self.submitted_at is None:
            self.submitted_at = timezone.now()
        if self.approval_status == self.ApprovalStatus.APPROVED and self.published_at is None:
            self.published_at = timezone.now()
        if not self.slug:
            source = f"{self.provider.provider_name}-{self.title}"
            self.slug = _unique_slug(model=ProgramListing, source=source, current_pk=self.pk, prefix="listing")
        normalized_tags = [str(item).strip() for item in (self.theme_tags or []) if str(item).strip()]
        normalized_grades = [str(item).strip() for item in (self.grade_bands or []) if str(item).strip()]
        self.theme_tags = normalized_tags
        self.theme_tags_text = ", ".join(normalized_tags)
        self.grade_bands = normalized_grades
        self.grade_bands_text = ", ".join(normalized_grades)
        super().save(*args, **kwargs)

    @property
    def primary_image(self):
        return self.images.order_by("sort_order", "id").first()

    @property
    def public_regions_text(self) -> str:
        region_parts = [self.get_province_display()]
        if self.city:
            region_parts.append(self.city)
        region = " ".join(part for part in region_parts if part)
        if self.coverage_note:
            return f"{region} · {self.coverage_note}"
        return region


class ListingImage(models.Model):
    listing = models.ForeignKey(
        ProgramListing,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        upload_to="schoolprograms/listings/",
        max_length=500,
        verbose_name="이미지",
    )
    caption = models.CharField(max_length=140, blank=True, verbose_name="이미지 설명")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="정렬 순서")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "학교 프로그램 이미지"
        verbose_name_plural = "학교 프로그램 이미지"

    def __str__(self) -> str:
        return f"{self.listing.title} 이미지 {self.id}"


class ListingViewLog(models.Model):
    listing = models.ForeignKey(
        ProgramListing,
        on_delete=models.CASCADE,
        related_name="view_logs",
    )
    viewer_key = models.CharField(max_length=120, blank=True, default="")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-viewed_at", "-id"]
        indexes = [
            models.Index(fields=["listing", "viewed_at"]),
        ]
        verbose_name = "학교 프로그램 조회 기록"
        verbose_name_plural = "학교 프로그램 조회 기록"


class InquiryThread(models.Model):
    class Status(models.TextChoices):
        AWAITING_VENDOR = "awaiting_vendor", "업체 답변 대기"
        IN_PROGRESS = "in_progress", "진행 중"
        PROPOSAL_SENT = "proposal_sent", "제안 도착"
        CLOSED = "closed", "종료"

    class SenderRole(models.TextChoices):
        TEACHER = "teacher", "교사"
        VENDOR = "vendor", "업체"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(
        ProgramListing,
        on_delete=models.CASCADE,
        related_name="inquiries",
    )
    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.CASCADE,
        related_name="inquiries",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_program_inquiries",
    )
    category = models.CharField(max_length=40, choices=ProgramListing.Category.choices)
    school_region = models.CharField(max_length=80, verbose_name="학교 지역")
    preferred_schedule = models.CharField(max_length=120, verbose_name="희망 시기")
    target_audience = models.CharField(max_length=120, verbose_name="대상")
    expected_participants = models.PositiveIntegerField(verbose_name="예상 인원")
    budget_text = models.CharField(max_length=120, blank=True, verbose_name="예산")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_VENDOR)
    is_agreement_reached = models.BooleanField(default=False, verbose_name="합의 완료 여부")
    last_message_at = models.DateTimeField(blank=True, null=True, db_index=True)
    last_message_preview = models.CharField(max_length=200, blank=True)
    last_message_sender_role = models.CharField(
        max_length=20,
        choices=SenderRole.choices,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-updated_at", "-id"]
        indexes = [
            models.Index(fields=["teacher", "status"]),
            models.Index(fields=["provider", "status"]),
        ]
        verbose_name = "학교 프로그램 문의 스레드"
        verbose_name_plural = "학교 프로그램 문의 스레드"

    def __str__(self) -> str:
        return f"{self.listing.title} 문의 {self.id}"

    @property
    def workflow_status_label(self) -> str:
        if self.status == self.Status.CLOSED and self.is_agreement_reached:
            return "합의 완료"
        return self.get_status_display()

    @property
    def teacher_bucket(self) -> str:
        if self.status == self.Status.CLOSED:
            return "closed"
        if self.status == self.Status.PROPOSAL_SENT and getattr(self, "proposal", None) is not None:
            return "proposal"
        if self.last_message_sender_role == self.SenderRole.VENDOR:
            return "new"
        return "progress"

    @property
    def vendor_bucket(self) -> str:
        if self.status == self.Status.CLOSED:
            return "closed"
        if self.status == self.Status.PROPOSAL_SENT:
            return "proposal"
        if self.status == self.Status.AWAITING_VENDOR:
            return "new"
        return "progress"


def _build_message_preview(text: str, *, limit: int = 200) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


class InquiryMessage(models.Model):
    thread = models.ForeignKey(
        InquiryThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_program_messages",
    )
    sender_role = models.CharField(max_length=20, choices=InquiryThread.SenderRole.choices)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "학교 프로그램 문의 메시지"
        verbose_name_plural = "학교 프로그램 문의 메시지"

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.sender_role}:{self.sender_id}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if not is_new:
            return
        InquiryThread.objects.filter(id=self.thread_id).update(
            last_message_at=self.created_at,
            last_message_preview=_build_message_preview(self.body),
            last_message_sender_role=self.sender_role,
        )


class InquiryProposal(models.Model):
    thread = models.OneToOneField(
        InquiryThread,
        on_delete=models.CASCADE,
        related_name="proposal",
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="school_program_proposals",
    )
    price_text = models.CharField(max_length=200, verbose_name="비용 범위")
    included_items = models.TextField(verbose_name="포함 항목")
    schedule_note = models.TextField(verbose_name="일정 메모")
    preparation_note = models.TextField(blank=True, verbose_name="준비 요청")
    followup_request = models.TextField(blank=True, verbose_name="후속 요청")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "학교 프로그램 제안 카드"
        verbose_name_plural = "학교 프로그램 제안 카드"

    def __str__(self) -> str:
        return f"제안 {self.thread_id}"


class SavedListing(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_school_program_listings",
    )
    listing = models.ForeignKey(
        ProgramListing,
        on_delete=models.CASCADE,
        related_name="saved_by_users",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "listing"], name="schoolprograms_unique_saved_listing"),
        ]
        verbose_name = "학교 프로그램 저장"
        verbose_name_plural = "학교 프로그램 저장"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.listing_id}"
