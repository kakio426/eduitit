import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q

from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.topics import DEFAULT_TOPIC, TOPIC_CHOICES

User = get_user_model()

GRADE_CHOICES = [
    (0, "학년무관"),
    (1, "1학년"),
    (2, "2학년"),
    (3, "3학년"),
    (4, "4학년"),
    (5, "5학년"),
    (6, "6학년"),
]


class SQQuizBank(models.Model):
    """관리자/공유용 퀴즈 은행 세트."""

    SOURCE_CHOICES = [
        ("ai", "AI생성"),
        ("csv", "CSV임포트"),
        ("manual", "직접입력"),
    ]
    QUALITY_CHOICES = [
        ("draft", "초안"),
        ("review", "검토대기"),
        ("approved", "승인"),
        ("rejected", "반려"),
    ]
    PRESET_CHOICES = TOPIC_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    preset_type = models.CharField(
        max_length=20,
        choices=PRESET_CHOICES,
        default=DEFAULT_TOPIC,
        verbose_name="주제",
    )
    grade = models.IntegerField(default=3, choices=GRADE_CHOICES, verbose_name="학년")
    title = models.CharField(max_length=200, verbose_name="제목")
    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default="manual",
        verbose_name="출처",
    )
    is_official = models.BooleanField(default=False, verbose_name="공식 세트")
    is_public = models.BooleanField(default=False, verbose_name="공개 세트")
    share_opt_in = models.BooleanField(default=False, verbose_name="공유 신청")
    source_hash = models.CharField(max_length=64, blank=True, default="", verbose_name="원문 해시")
    quality_status = models.CharField(
        max_length=10,
        choices=QUALITY_CHOICES,
        default="approved",
        verbose_name="품질 상태",
    )
    is_active = models.BooleanField(default=True, verbose_name="활성")
    use_count = models.IntegerField(default=0, verbose_name="사용 횟수")
    available_from = models.DateField(null=True, blank=True, verbose_name="노출 시작일")
    available_to = models.DateField(null=True, blank=True, verbose_name="노출 종료일")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sq_quiz_banks_created",
        verbose_name="생성자",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sq_quiz_banks_reviewed",
        verbose_name="검토자",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="검토 시각")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "퀴즈 은행 세트"
        verbose_name_plural = "퀴즈 은행 세트"
        ordering = ["preset_type", "grade", "-created_at"]
        indexes = [
            models.Index(fields=["preset_type", "grade", "is_active"]),
            models.Index(fields=["is_official", "is_active"]),
            models.Index(fields=["is_public", "is_active"]),
            models.Index(fields=["quality_status", "is_active"]),
            models.Index(fields=["source_hash", "created_at"]),
        ]

    def __str__(self):
        grade_label = "학년무관" if self.grade == 0 else f"{self.grade}학년"
        return f"[{self.get_preset_type_display()}·{grade_label}] {self.title}"


class SQQuizBankItem(models.Model):
    """퀴즈 은행 세트의 개별 문항."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank = models.ForeignKey(
        SQQuizBank,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="은행 세트",
    )
    order_no = models.IntegerField(verbose_name="순서")
    question_text = models.TextField(verbose_name="문제")
    choices = models.JSONField(verbose_name="선택지")
    correct_index = models.IntegerField(verbose_name="정답 인덱스")
    explanation = models.TextField(blank=True, verbose_name="해설")
    difficulty = models.CharField(max_length=10, default="medium", verbose_name="난이도")

    class Meta:
        verbose_name = "은행 문항"
        verbose_name_plural = "은행 문항"
        unique_together = [("bank", "order_no")]
        constraints = [
            models.CheckConstraint(
                condition=Q(correct_index__gte=0) & Q(correct_index__lte=3),
                name="sq_bank_item_correct_index_range",
            )
        ]

    def __str__(self):
        return f"Q{self.order_no}: {self.question_text[:30]}"


class SQQuizSet(models.Model):
    STATUS_CHOICES = [
        ("draft", "초안"),
        ("published", "배포중"),
        ("closed", "종료"),
        ("archived", "보관"),
        ("failed", "생성실패"),
    ]
    SOURCE_CHOICES = [
        ("ai", "AI"),
        ("fallback", "기본문제"),
        ("bank", "은행"),
        ("csv", "CSV"),
    ]
    PRESET_CHOICES = TOPIC_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name="sq_quiz_sets",
        verbose_name="교실",
    )
    target_date = models.DateField(verbose_name="대상 날짜")
    preset_type = models.CharField(
        max_length=20,
        choices=PRESET_CHOICES,
        default=DEFAULT_TOPIC,
        verbose_name="주제",
    )
    grade = models.IntegerField(default=3, choices=GRADE_CHOICES, verbose_name="학년")
    title = models.CharField(max_length=100, verbose_name="제목")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name="상태",
    )
    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default="ai",
        verbose_name="출처",
    )
    time_limit_seconds = models.IntegerField(default=600, verbose_name="제한시간(초)")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sq_quiz_sets_created",
        verbose_name="생성자",
    )
    published_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sq_quiz_sets_published",
        verbose_name="배포자",
    )
    bank_source = models.ForeignKey(
        SQQuizBank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_sets",
        verbose_name="은행 출처",
    )
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="배포 시각")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "퀴즈 세트"
        verbose_name_plural = "퀴즈 세트"
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "target_date", "preset_type"],
                condition=Q(status="published"),
                name="unique_published_quiz_per_class_date_preset",
            )
        ]
        indexes = [
            models.Index(fields=["classroom", "target_date", "status"]),
            models.Index(fields=["status", "published_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class SQBatchJob(models.Model):
    """월간 배치 생성 작업 추적."""

    STATUS_CHOICES = [
        ("pending", "대기"),
        ("submitted", "제출됨"),
        ("validating", "검증중"),
        ("in_progress", "진행중"),
        ("finalizing", "마무리중"),
        ("completed", "완료"),
        ("failed", "실패"),
        ("cancelled", "취소"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=30, default="openai", verbose_name="제공자")
    target_month = models.DateField(verbose_name="대상 월(1일 기준)")
    batch_id = models.CharField(max_length=120, blank=True, default="", verbose_name="외부 배치 ID")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="상태",
    )
    input_file_id = models.CharField(max_length=120, blank=True, default="", verbose_name="입력 파일 ID")
    output_file_id = models.CharField(max_length=120, blank=True, default="", verbose_name="출력 파일 ID")
    error_file_id = models.CharField(max_length=120, blank=True, default="", verbose_name="오류 파일 ID")
    requested_count = models.IntegerField(default=0, verbose_name="요청 수")
    success_count = models.IntegerField(default=0, verbose_name="성공 수")
    failed_count = models.IntegerField(default=0, verbose_name="실패 수")
    meta_json = models.JSONField(default=dict, blank=True, verbose_name="메타 정보")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sq_batch_jobs_created",
        verbose_name="생성자",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "퀴즈 배치 작업"
        verbose_name_plural = "퀴즈 배치 작업"
        indexes = [
            models.Index(fields=["status", "target_month"]),
            models.Index(fields=["provider", "target_month"]),
        ]

    def __str__(self):
        return f"{self.provider}:{self.target_month} ({self.status})"


class SQRagDailyUsage(models.Model):
    """교사/교실 단위 RAG 일일 사용량."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usage_date = models.DateField(verbose_name="사용 날짜")
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name="sq_rag_usages",
        verbose_name="교실",
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sq_rag_usages",
        verbose_name="교사",
    )
    count = models.IntegerField(default=0, verbose_name="사용 횟수")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "RAG 일일 사용량"
        verbose_name_plural = "RAG 일일 사용량"
        unique_together = [("usage_date", "classroom", "teacher")]
        indexes = [
            models.Index(fields=["usage_date", "teacher"]),
            models.Index(fields=["usage_date", "classroom"]),
        ]

    def __str__(self):
        return f"{self.usage_date} {self.classroom_id}:{self.teacher_id} ({self.count})"


class SQQuizItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz_set = models.ForeignKey(
        SQQuizSet,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="퀴즈 세트",
    )
    order_no = models.IntegerField(verbose_name="순서")
    question_text = models.TextField(verbose_name="문제")
    choices = models.JSONField(verbose_name="선택지")  # list[str], 길이=4
    correct_index = models.IntegerField(verbose_name="정답 인덱스")  # 0~3
    explanation = models.TextField(blank=True, verbose_name="해설")
    difficulty = models.CharField(max_length=10, default="medium", verbose_name="난이도")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "퀴즈 문항"
        verbose_name_plural = "퀴즈 문항"
        unique_together = [("quiz_set", "order_no")]
        constraints = [
            models.CheckConstraint(
                condition=Q(correct_index__gte=0) & Q(correct_index__lte=3),
                name="sq_item_correct_index_range",
            )
        ]

    def __str__(self):
        return f"Q{self.order_no}: {self.question_text[:30]}"

    def clean(self):
        from seed_quiz.services.validator import normalize_and_check

        if isinstance(self.choices, list):
            choices = [normalize_and_check(c) for c in self.choices]
            if len(choices) != 4:
                from django.core.exceptions import ValidationError
                raise ValidationError("선택지는 정확히 4개여야 합니다.")
            if len(set(choices)) != 4:
                from django.core.exceptions import ValidationError
                raise ValidationError("선택지에 중복이 있습니다.")


class SQAttempt(models.Model):
    STATUS_CHOICES = [
        ("in_progress", "진행중"),
        ("submitted", "제출완료"),
        ("rewarded", "보상완료"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz_set = models.ForeignKey(
        SQQuizSet,
        on_delete=models.CASCADE,
        related_name="attempts",
        verbose_name="퀴즈 세트",
    )
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.CASCADE,
        related_name="sq_attempts",
        verbose_name="학생",
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="in_progress",
        verbose_name="상태",
    )
    request_id = models.UUIDField(unique=True, default=uuid.uuid4, verbose_name="요청 ID")
    score = models.IntegerField(default=0, verbose_name="점수")
    max_score = models.IntegerField(default=3, verbose_name="만점")
    reward_seed_amount = models.IntegerField(default=0, verbose_name="보상 씨앗 수")
    consent_snapshot = models.CharField(
        max_length=15, blank=True, verbose_name="동의 상태 스냅샷"
    )
    reward_applied_at = models.DateTimeField(
        null=True, blank=True, verbose_name="보상 지급 시각"
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="시작 시각")
    submitted_at = models.DateTimeField(
        null=True, blank=True, verbose_name="제출 시각"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "시도"
        verbose_name_plural = "시도"
        unique_together = [("student", "quiz_set")]

    def __str__(self):
        return f"{self.student} - {self.quiz_set} ({self.get_status_display()})"


class SQAttemptAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        SQAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="시도",
    )
    item = models.ForeignKey(
        SQQuizItem,
        on_delete=models.CASCADE,
        verbose_name="문항",
    )
    selected_index = models.IntegerField(verbose_name="선택한 답")
    is_correct = models.BooleanField(verbose_name="정답 여부")
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name="답변 시각")

    class Meta:
        verbose_name = "답변"
        verbose_name_plural = "답변"
        unique_together = [("attempt", "item")]
        constraints = [
            models.CheckConstraint(
                condition=Q(selected_index__gte=0) & Q(selected_index__lte=3),
                name="sq_answer_selected_index_range",
            )
        ]

    def __str__(self):
        return f"{self.attempt} - {self.item} ({'O' if self.is_correct else 'X'})"


class SQGenerationLog(models.Model):
    LEVEL_CHOICES = [
        ("info", "정보"),
        ("warn", "경고"),
        ("error", "오류"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz_set = models.ForeignKey(
        SQQuizSet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
        verbose_name="퀴즈 세트",
    )
    level = models.CharField(
        max_length=5,
        choices=LEVEL_CHOICES,
        default="info",
        verbose_name="레벨",
    )
    code = models.CharField(max_length=50, verbose_name="코드")
    message = models.TextField(verbose_name="메시지")
    payload = models.JSONField(default=dict, blank=True, verbose_name="페이로드")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "생성 로그"
        verbose_name_plural = "생성 로그"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.level.upper()}] {self.code}: {self.message[:50]}"
