import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


DEFAULT_DAY_KEYS = ["월", "화", "수", "목", "금"]
DEFAULT_PERIOD_LABELS = ["1교시", "2교시", "3교시", "4교시", "5교시", "6교시"]


def _default_share_token():
    return secrets.token_urlsafe(24)


class TimetableSyncLog(models.Model):
    SYNC_MODE_CHOICES = [
        ("direct", "바로반영"),
        ("preview_manual", "미리보기 수동반영"),
    ]

    STATUS_CHOICES = [
        ("success", "성공"),
        ("partial", "부분반영"),
        ("skipped", "건너뜀"),
        ("failed", "실패"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_sync_logs",
        verbose_name="실행 사용자",
    )
    school_slug = models.CharField(max_length=120, verbose_name="학교 슬러그")
    school_name = models.CharField(max_length=120, blank=True, verbose_name="학교명")
    sync_mode = models.CharField(max_length=30, choices=SYNC_MODE_CHOICES, verbose_name="반영 방식")
    sync_options_text = models.CharField(max_length=120, blank=True, verbose_name="반영 대상 옵션")
    overwrite_existing = models.BooleanField(default=False, verbose_name="기존 고정시간표 덮어쓰기")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success", verbose_name="결과 상태")
    applied_count = models.PositiveIntegerField(default=0, verbose_name="새로 반영")
    updated_count = models.PositiveIntegerField(default=0, verbose_name="이름 갱신")
    skipped_count = models.PositiveIntegerField(default=0, verbose_name="건너뜀")
    conflict_count = models.PositiveIntegerField(default=0, verbose_name="기존값 충돌")
    room_created_count = models.PositiveIntegerField(default=0, verbose_name="신규 특별실")
    summary_text = models.TextField(blank=True, verbose_name="요약 메모")
    payload = models.JSONField(default=dict, blank=True, verbose_name="추가 기록")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="실행 시각")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "시간표 예약 반영 로그"
        verbose_name_plural = "시간표 예약 반영 로그"

    def __str__(self):
        return f"{self.school_name or self.school_slug} | {self.get_sync_mode_display()} | {self.get_status_display()}"


class TimetableWorkspace(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    school = models.ForeignKey(
        "reservations.School",
        on_delete=models.CASCADE,
        related_name="timetable_workspaces",
    )
    school_year = models.PositiveIntegerField()
    term = models.CharField(max_length=40)
    grade = models.PositiveIntegerField()
    term_start_date = models.DateField(null=True, blank=True)
    term_end_date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=200)
    days_json = models.JSONField(default=list, blank=True)
    period_labels_json = models.JSONField(default=list, blank=True)
    sheet_data = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_snapshot = models.ForeignKey(
        "TimetableSnapshot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_workspaces",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_timetable_workspaces",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_timetable_workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "school_year", "term", "grade", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "school_year", "term", "grade"],
                name="unique_timetable_workspace_scope",
            )
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.term_start_date and self.term_end_date and self.term_end_date < self.term_start_date:
            raise ValidationError({"term_end_date": "학기 종료일은 시작일보다 같거나 뒤여야 합니다."})

    @property
    def day_keys(self):
        return list(self.days_json or DEFAULT_DAY_KEYS)

    @property
    def period_labels(self):
        return list(self.period_labels_json or DEFAULT_PERIOD_LABELS)

    @property
    def grade_label(self):
        return f"{self.grade}학년"


class TimetableTeacher(models.Model):
    class TeacherType(models.TextChoices):
        HOMEROOM = "homeroom", "담임"
        SPECIALIST = "specialist", "전담"
        INSTRUCTOR = "instructor", "강사"

    school = models.ForeignKey(
        "reservations.School",
        on_delete=models.CASCADE,
        related_name="timetable_teachers",
    )
    name = models.CharField(max_length=80)
    teacher_type = models.CharField(max_length=20, choices=TeacherType.choices)
    target_weekly_hours = models.PositiveIntegerField(default=0)
    subjects_json = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "teacher_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_timetable_teacher_per_school",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def subjects(self):
        return list(self.subjects_json or [])


class TimetableClassroom(models.Model):
    school = models.ForeignKey(
        "reservations.School",
        on_delete=models.CASCADE,
        related_name="timetable_classrooms",
    )
    school_year = models.PositiveIntegerField()
    grade = models.PositiveIntegerField()
    class_no = models.PositiveIntegerField()
    homeroom_name = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "school_year", "grade", "class_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "school_year", "grade", "class_no"],
                name="unique_timetable_classroom_per_year",
            )
        ]

    def __str__(self):
        return self.label

    @property
    def label(self):
        return f"{self.grade}-{self.class_no}반"


class TimetableSlotAssignment(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "수동"
        MEETING = "meeting", "회의"
        IMPORT = "import", "가져오기"

    workspace = models.ForeignKey(
        TimetableWorkspace,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    classroom = models.ForeignKey(
        TimetableClassroom,
        on_delete=models.CASCADE,
        related_name="timetable_assignments",
    )
    day_key = models.CharField(max_length=20)
    period_no = models.PositiveIntegerField()
    subject_name = models.CharField(max_length=120, blank=True)
    teacher = models.ForeignKey(
        TimetableTeacher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="timetable_assignments",
    )
    special_room = models.ForeignKey(
        "reservations.SpecialRoom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="timetable_assignments",
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    display_text = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace_id", "classroom__class_no", "day_key", "period_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "classroom", "day_key", "period_no"],
                name="unique_timetable_slot_assignment",
            )
        ]

    def __str__(self):
        return f"{self.workspace} | {self.classroom.label} | {self.day_key} {self.period_no}교시"

    @property
    def cell_key(self):
        return f"{self.classroom_id}:{self.day_key}:{self.period_no}"


class TimetableRoomPolicy(models.Model):
    workspace = models.ForeignKey(
        TimetableWorkspace,
        on_delete=models.CASCADE,
        related_name="room_policies",
    )
    special_room = models.ForeignKey(
        "reservations.SpecialRoom",
        on_delete=models.CASCADE,
        related_name="timetable_policies",
    )
    capacity_per_slot = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace_id", "special_room__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "special_room"],
                name="unique_timetable_room_policy",
            )
        ]

    def __str__(self):
        return f"{self.workspace} | {self.special_room.name} x{self.capacity_per_slot}"


class TimetableSnapshot(models.Model):
    workspace = models.ForeignKey(
        TimetableWorkspace,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    name = models.CharField(max_length=120)
    sheet_data = models.JSONField(default=list, blank=True)
    events_json = models.JSONField(default=list, blank=True)
    date_overrides_json = models.JSONField(default=list, blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="timetable_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.workspace} | {self.name}"


class TimetableSharedEvent(models.Model):
    class ScopeType(models.TextChoices):
        SCHOOL = "school", "학교 전체"
        GRADE = "grade", "학년 공통"

    school = models.ForeignKey(
        "reservations.School",
        on_delete=models.CASCADE,
        related_name="timetable_shared_events",
    )
    school_year = models.PositiveIntegerField()
    term = models.CharField(max_length=40)
    scope_type = models.CharField(max_length=20, choices=ScopeType.choices)
    grade = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=120)
    day_key = models.CharField(max_length=20)
    period_start = models.PositiveIntegerField()
    period_end = models.PositiveIntegerField()
    note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_timetable_shared_events",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_timetable_shared_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "school_year", "term", "day_key", "period_start", "scope_type", "grade", "id"]

    def __str__(self):
        return f"{self.scope_label} | {self.title}"

    def clean(self):
        super().clean()
        if self.scope_type == self.ScopeType.SCHOOL and self.grade is not None:
            raise ValidationError({"grade": "학교 전체 행사는 학년을 비워 두어야 합니다."})
        if self.scope_type == self.ScopeType.GRADE and self.grade is None:
            raise ValidationError({"grade": "학년 공통 행사는 학년을 지정해야 합니다."})
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "종료 교시는 시작 교시보다 같거나 커야 합니다."})

    @property
    def scope_label(self):
        if self.scope_type == self.ScopeType.GRADE and self.grade:
            return f"{self.grade}학년 공통"
        return "학교 전체"


class TimetableSchoolProfile(models.Model):
    class SchoolStage(models.TextChoices):
        ELEMENTARY = "elementary", "초등"
        MIDDLE = "middle", "중등"
        HIGH = "high", "고등"
        CUSTOM = "custom", "직접 입력"

    school = models.OneToOneField(
        "reservations.School",
        on_delete=models.CASCADE,
        related_name="timetable_profile",
    )
    school_stage = models.CharField(
        max_length=20,
        choices=SchoolStage.choices,
        default=SchoolStage.ELEMENTARY,
    )
    grade_start = models.PositiveIntegerField(default=1)
    grade_end = models.PositiveIntegerField(default=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "id"]

    def __str__(self):
        return f"{self.school.name} | {self.get_school_stage_display()}"

    def clean(self):
        super().clean()
        preset_ranges = {
            self.SchoolStage.ELEMENTARY: (1, 6),
            self.SchoolStage.MIDDLE: (1, 3),
            self.SchoolStage.HIGH: (1, 3),
        }
        if self.school_stage in preset_ranges:
            expected_start, expected_end = preset_ranges[self.school_stage]
            self.grade_start = expected_start
            self.grade_end = expected_end
        elif self.school_stage == self.SchoolStage.CUSTOM:
            if not self.grade_start or not self.grade_end:
                raise ValidationError("직접 입력 학교급은 시작/종료 학년을 모두 입력해야 합니다.")
            if self.grade_end < self.grade_start:
                raise ValidationError({"grade_end": "종료 학년은 시작 학년보다 같거나 커야 합니다."})

    @property
    def grade_range(self):
        return range(int(self.grade_start or 1), int(self.grade_end or 0) + 1)


class TimetableClassInputStatus(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "아직 안 함"
        EDITING = "editing", "입력 중"
        SUBMITTED = "submitted", "입력 완료"
        REVIEWED = "reviewed", "관리자 검토 완료"

    workspace = models.ForeignKey(
        TimetableWorkspace,
        on_delete=models.CASCADE,
        related_name="class_input_statuses",
    )
    classroom = models.ForeignKey(
        TimetableClassroom,
        on_delete=models.CASCADE,
        related_name="input_statuses",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    editor_name = models.CharField(max_length=80, blank=True)
    last_saved_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace_id", "classroom__class_no", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "classroom"],
                name="unique_timetable_class_input_status",
            )
        ]

    def __str__(self):
        return f"{self.workspace} | {self.classroom.label} | {self.get_status_display()}"


class TimetableClassEditLink(models.Model):
    workspace = models.ForeignKey(
        TimetableWorkspace,
        on_delete=models.CASCADE,
        related_name="class_edit_links",
    )
    classroom = models.ForeignKey(
        TimetableClassroom,
        on_delete=models.CASCADE,
        related_name="edit_links",
    )
    token = models.CharField(max_length=80, unique=True, default=_default_share_token)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_timetable_edit_links",
    )
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace_id", "classroom__class_no", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "classroom"],
                name="unique_timetable_class_edit_link",
            )
        ]

    def __str__(self):
        return f"{self.workspace} | {self.classroom.label} 입력 링크"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())


class TimetableDateOverride(models.Model):
    class Source(models.TextChoices):
        TEACHER_LINK = "teacher_link", "반별 입력"
        MEETING = "meeting", "회의"
        MANUAL = "manual", "관리자 수동"

    workspace = models.ForeignKey(
        TimetableWorkspace,
        on_delete=models.CASCADE,
        related_name="date_overrides",
    )
    classroom = models.ForeignKey(
        TimetableClassroom,
        on_delete=models.CASCADE,
        related_name="timetable_date_overrides",
    )
    date = models.DateField()
    period_no = models.PositiveIntegerField()
    subject_name = models.CharField(max_length=120, blank=True)
    teacher = models.ForeignKey(
        TimetableTeacher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="timetable_date_overrides",
    )
    special_room = models.ForeignKey(
        "reservations.SpecialRoom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="timetable_date_overrides",
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.TEACHER_LINK)
    display_text = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace_id", "date", "classroom__class_no", "period_no", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "classroom", "date", "period_no"],
                name="unique_timetable_date_override",
            )
        ]

    def __str__(self):
        return f"{self.workspace} | {self.classroom.label} | {self.date} {self.period_no}교시"


class TimetableSharePortal(models.Model):
    snapshot = models.OneToOneField(
        TimetableSnapshot,
        on_delete=models.CASCADE,
        related_name="share_portal",
    )
    token = models.CharField(max_length=80, unique=True, default=_default_share_token)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.snapshot} | 공유 포털"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())


class TimetableShareLink(models.Model):
    class AudienceType(models.TextChoices):
        CLASSROOM = "class", "반"
        TEACHER = "teacher", "교사"

    snapshot = models.ForeignKey(
        TimetableSnapshot,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    audience_type = models.CharField(max_length=20, choices=AudienceType.choices)
    classroom = models.ForeignKey(
        TimetableClassroom,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="timetable_share_links",
    )
    teacher = models.ForeignKey(
        TimetableTeacher,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="timetable_share_links",
    )
    token = models.CharField(max_length=80, unique=True, default=_default_share_token)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["audience_type", "id"]

    def __str__(self):
        return f"{self.snapshot} | {self.audience_type}"

    def clean(self):
        super().clean()
        if self.audience_type == self.AudienceType.CLASSROOM:
            if not self.classroom_id or self.teacher_id:
                raise ValidationError("반 링크는 classroom만 지정해야 합니다.")
        if self.audience_type == self.AudienceType.TEACHER:
            if not self.teacher_id or self.classroom_id:
                raise ValidationError("교사 링크는 teacher만 지정해야 합니다.")

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())


class TimetablePublishedRecurring(models.Model):
    workspace = models.ForeignKey(
        TimetableWorkspace,
        on_delete=models.CASCADE,
        related_name="published_recurrings",
    )
    snapshot = models.ForeignKey(
        TimetableSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_recurrings",
    )
    special_room = models.ForeignKey(
        "reservations.SpecialRoom",
        on_delete=models.CASCADE,
        related_name="timetable_published_recurrings",
    )
    recurring_schedule = models.ForeignKey(
        "reservations.RecurringSchedule",
        on_delete=models.CASCADE,
        related_name="timetable_publications",
    )
    day_key = models.CharField(max_length=20)
    period_no = models.PositiveIntegerField()
    name_snapshot = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace_id", "day_key", "period_no", "special_room__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "special_room", "day_key", "period_no"],
                name="unique_timetable_published_recurring_slot",
            )
        ]

    def __str__(self):
        return f"{self.workspace} | {self.special_room.name} {self.day_key} {self.period_no}교시"
