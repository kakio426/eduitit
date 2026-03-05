from django.conf import settings
from django.db import models
from django.db.models import Q


class Sheetbook(models.Model):
    VISIBILITY_PRIVATE = "private"
    VISIBILITY_SCHOOL = "school"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, "비공개"),
        (VISIBILITY_SCHOOL, "학교 공유"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sheetbooks",
    )
    title = models.CharField(max_length=200)
    academic_year = models.PositiveSmallIntegerField(null=True, blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PRIVATE,
    )
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "updated_at"]),
            models.Index(fields=["owner", "is_archived", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.owner_id})"


class SheetTab(models.Model):
    TYPE_GRID = "grid"
    TYPE_CALENDAR = "calendar"
    TYPE_CHOICES = [
        (TYPE_GRID, "그리드"),
        (TYPE_CALENDAR, "달력"),
    ]

    sheetbook = models.ForeignKey(
        Sheetbook,
        on_delete=models.CASCADE,
        related_name="tabs",
    )
    name = models.CharField(max_length=100)
    tab_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_GRID)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["sheetbook", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.sheetbook_id}:{self.name}"


class SheetColumn(models.Model):
    TYPE_TEXT = "text"
    TYPE_NUMBER = "number"
    TYPE_DATE = "date"
    TYPE_SELECT = "select"
    TYPE_MULTI_SELECT = "multi_select"
    TYPE_CHECKBOX = "checkbox"
    TYPE_FILE = "file"
    TYPE_CHOICES = [
        (TYPE_TEXT, "텍스트"),
        (TYPE_NUMBER, "숫자"),
        (TYPE_DATE, "날짜"),
        (TYPE_SELECT, "단일선택"),
        (TYPE_MULTI_SELECT, "다중선택"),
        (TYPE_CHECKBOX, "체크박스"),
        (TYPE_FILE, "파일"),
    ]

    tab = models.ForeignKey(
        SheetTab,
        on_delete=models.CASCADE,
        related_name="columns",
    )
    key = models.SlugField(max_length=64)
    label = models.CharField(max_length=120)
    column_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TEXT)
    sort_order = models.PositiveIntegerField(default=0)
    width = models.PositiveSmallIntegerField(default=160)
    is_required = models.BooleanField(default=False)
    options = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        unique_together = [("tab", "key")]
        indexes = [
            models.Index(fields=["tab", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.tab_id}:{self.label}"


class SheetRow(models.Model):
    tab = models.ForeignKey(
        SheetTab,
        on_delete=models.CASCADE,
        related_name="rows",
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_sheet_rows",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_sheet_rows",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["tab", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.tab_id}#{self.id}"


class SheetCell(models.Model):
    row = models.ForeignKey(
        SheetRow,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    column = models.ForeignKey(
        SheetColumn,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    value_text = models.TextField(blank=True)
    value_number = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("row", "column")]
        indexes = [
            models.Index(fields=["column", "row"]),
        ]

    def __str__(self):
        return f"{self.row_id}:{self.column_id}"


class SavedView(models.Model):
    SORT_ASC = "asc"
    SORT_DESC = "desc"
    SORT_DIRECTION_CHOICES = [
        (SORT_ASC, "오름차순"),
        (SORT_DESC, "내림차순"),
    ]

    tab = models.ForeignKey(
        SheetTab,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    name = models.CharField(max_length=80)
    filter_text = models.CharField(max_length=120, blank=True)
    sort_column = models.ForeignKey(
        SheetColumn,
        on_delete=models.SET_NULL,
        related_name="saved_views",
        null=True,
        blank=True,
    )
    sort_direction = models.CharField(
        max_length=4,
        choices=SORT_DIRECTION_CHOICES,
        default=SORT_ASC,
    )
    is_favorite = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sheetbook_saved_views",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_favorite", "name", "id"]
        indexes = [
            models.Index(fields=["tab", "is_favorite", "id"]),
            models.Index(fields=["tab", "is_default"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tab"],
                condition=Q(is_default=True),
                name="sheetbook_savedview_one_default_per_tab",
            ),
        ]

    def __str__(self):
        return f"{self.tab_id}:{self.name}"


class ActionInvocation(models.Model):
    ACTION_CALENDAR = "calendar"
    ACTION_COLLECT = "collect"
    ACTION_CONSENT = "consent"
    ACTION_SIGNATURE = "signature"
    ACTION_HANDOFF = "handoff"
    ACTION_NOTICE = "notice"
    ACTION_CHOICES = [
        (ACTION_CALENDAR, "달력 등록"),
        (ACTION_COLLECT, "간편 수합"),
        (ACTION_CONSENT, "동의서"),
        (ACTION_SIGNATURE, "서명 요청"),
        (ACTION_HANDOFF, "배부 체크"),
        (ACTION_NOTICE, "안내문"),
    ]

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "성공"),
        (STATUS_FAILED, "실패"),
    ]

    sheetbook = models.ForeignKey(
        Sheetbook,
        on_delete=models.CASCADE,
        related_name="action_invocations",
    )
    tab = models.ForeignKey(
        SheetTab,
        on_delete=models.CASCADE,
        related_name="action_invocations",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sheetbook_action_invocations",
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS)

    selection_start_row = models.PositiveIntegerField(default=0)
    selection_start_col = models.PositiveIntegerField(default=0)
    selection_end_row = models.PositiveIntegerField(default=0)
    selection_end_col = models.PositiveIntegerField(default=0)
    selected_cell_count = models.PositiveIntegerField(default=0)

    summary = models.CharField(max_length=255, blank=True)
    result_label = models.CharField(max_length=200, blank=True)
    result_url = models.CharField(max_length=500, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["sheetbook", "created_at"]),
            models.Index(fields=["tab", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sheetbook_id}:{self.tab_id}:{self.action_type}:{self.status}"


class SheetbookMetricEvent(models.Model):
    event_name = models.CharField(max_length=80)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sheetbook_metric_events",
        null=True,
        blank=True,
    )
    sheetbook = models.ForeignKey(
        Sheetbook,
        on_delete=models.SET_NULL,
        related_name="metric_events",
        null=True,
        blank=True,
    )
    tab = models.ForeignKey(
        SheetTab,
        on_delete=models.SET_NULL,
        related_name="metric_events",
        null=True,
        blank=True,
    )
    action_type = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["event_name", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["sheetbook", "created_at"]),
            models.Index(fields=["tab", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_name}:{self.user_id}:{self.sheetbook_id}:{self.tab_id}"
