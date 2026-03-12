from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    title = models.CharField(max_length=200)
    lead_text = models.TextField(blank=True, help_text="Short lead text for modal display")
    description = models.TextField()
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_guest_allowed = models.BooleanField(default=False, help_text="비회원 체험 가능 여부")
    
    # Display metadata fields
    COLOR_CHOICES = [
        ('purple', 'Purple'),
        ('green', 'Green'),
        ('red', 'Red'),
        ('orange', 'Orange'),
        ('blue', 'Blue'),
        ('dark', 'Dark'),
    ]
    
    SIZE_CHOICES = [
        ('small', 'Small (1x1)'),
        ('wide', 'Wide (2x1)'),
        ('tall', 'Tall (1x2)'),
        ('hero', 'Hero (2x2)'),
    ]
    
    SERVICE_CHOICES = [
        ('collect_sign', '수합·서명'),
        ('classroom', '수업·학급 운영'),
        ('work', '문서·작성'),
        ('game', '교실 활동'),
        ('counsel', '상담·리프레시'),
        ('edutech', '가이드·인사이트'),
        ('etc', '외부 서비스'),
    ]
    
    icon = models.CharField(max_length=50, default='🛠️', help_text="Emoji or FontAwesome class for card icon")
    color_theme = models.CharField(max_length=20, choices=COLOR_CHOICES, default='purple', help_text="Color theme")
    card_size = models.CharField(max_length=20, choices=SIZE_CHOICES, default='small', help_text="Card size")
    display_order = models.IntegerField(default=0, help_text="Order in which to display (lower numbers first)")
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_CHOICES,
        default='etc',
        help_text="서비스 카테고리(수합·서명은 launch_route_name 매핑으로도 자동 분류됨)",
    )
    external_url = models.URLField(blank=True, help_text="External URL for services hosted elsewhere")
    launch_route_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Internal Django URL name for direct launch (e.g. collect:landing).",
    )

    # V2 홈 목적별 섹션용 필드
    solve_text = models.CharField(max_length=100, blank=True, help_text="무엇을 해결? (예: '문서와 의견 수합, 번거로운 일은 이제 저에게 맡겨주세요!')")
    result_text = models.CharField(max_length=100, blank=True, help_text="결과물 (예: '엑셀 정리표')")
    time_text = models.CharField(max_length=50, blank=True, help_text="소요시간 (예: '3분')")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class ProductFeature(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='features')
    icon = models.CharField(max_length=50, help_text="Emoji or FontAwesome class")
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    def __str__(self):
        return f"{self.product.title} - {self.title}"

class ServiceManual(models.Model):
    """Product specific manual/guide"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='manual')
    title = models.CharField(max_length=200, help_text="매뉴얼 제목 (예: '선생님과 함께하는 000 시작하기')")
    description = models.TextField(blank=True, help_text="매뉴얼 소개글")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.title} 매뉴얼"

class ManualSection(models.Model):
    """Section of a service manual"""
    LAYOUT_CHOICES = [
        ('text_only', '텍스트 전용'),
        ('image_left', '이미지 좌측 + 텍스트'),
        ('image_right', '텍스트 + 이미지 우측'),
        ('full_visual', '전체 너비 이미지/비디오'),
        ('card_carousel', '카드 캐러셀 (Quick Start)'),
    ]

    manual = models.ForeignKey(ServiceManual, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, help_text="Markdown 지원")
    image = models.ImageField(upload_to='manuals/', null=True, blank=True)
    video_url = models.URLField(blank=True, help_text="YouTube/Vimeo 임베드 URL")
    layout_type = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='text_only')
    badge_text = models.CharField(max_length=50, blank=True, help_text="섹션 배지 (예: Tip, 핵심, 주의)")
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"{self.manual.product.title} - {self.title}"

class UserOwnedProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.title}"

# --- DutyTicker Models ---

class DTSettings(models.Model):
    """User-specific settings for DutyTicker"""
    ROTATION_MODE_CHOICES = [
        ("auto_sequential", "자동 순차 (하루 1칸)"),
        ("auto_random", "자동 랜덤 (하루 1회)"),
        ("manual_sequential", "수동 순차"),
        ("manual_random", "수동 랜덤"),
    ]
    THEME_CHOICES = [
        ("deep_space", "딥 스페이스 (기본, 다크)"),
        ("sunny", "살구빛 햇살 (밝음)"),
        ("pastel", "민트 파스텔 (부드러움)"),
        ("vivid", "코랄 팝 (선명함)"),
    ]
    ROLE_VIEW_MODE_CHOICES = [
        ("compact", "밀도형 (기본)"),
        ("readable", "가독성형 (큰 글씨)"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dutyticker_settings')
    classroom = models.ForeignKey(
        'happy_seed.HSClassroom',
        on_delete=models.CASCADE,
        related_name='dutyticker_settings',
        null=True,
        blank=True,
    )
    auto_rotation = models.BooleanField(default=False, help_text="Automatically rotate roles daily/weekly")
    rotation_frequency = models.CharField(
        max_length=20, 
        choices=[('daily', 'Daily'), ('weekly', 'Weekly')], 
        default='daily'
    )
    last_rotation_date = models.DateField(null=True, blank=True)
    rotation_mode = models.CharField(
        max_length=20,
        choices=ROTATION_MODE_CHOICES,
        default="manual_sequential",
        help_text="역할 순환 모드",
    )
    last_broadcast_message = models.TextField(blank=True, help_text="Persisted broadcast message")
    mission_title = models.CharField(max_length=200, default="오늘도 행복한 우리 교실", help_text="Main display mission title")
    mission_desc = models.TextField(default="선생님 말씀에 집중해 주세요.", help_text="Main display mission description")
    spotlight_student = models.ForeignKey(
        "DTStudent",
        on_delete=models.SET_NULL,
        related_name="dutyticker_spotlight_settings",
        null=True,
        blank=True,
    )
    theme = models.CharField(
        max_length=20,
        choices=THEME_CHOICES,
        default="deep_space",
        help_text="디자인 테마",
    )
    role_view_mode = models.CharField(
        max_length=20,
        choices=ROLE_VIEW_MODE_CHOICES,
        default="compact",
        help_text="오늘의 역할 표시 모드",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'classroom'], name='dtsettings_user_classroom_unique'),
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(classroom__isnull=True),
                name='dtsettings_user_global_unique',
            ),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s Settings"


class DTTimeSlot(models.Model):
    """Slot definitions for one classroom day timeline (periods + breaks + lunch)."""

    SLOT_KIND_CHOICES = [
        ("period", "교시"),
        ("break", "쉬는시간"),
        ("lunch", "점심시간"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dutyticker_time_slots")
    classroom = models.ForeignKey(
        "happy_seed.HSClassroom",
        on_delete=models.CASCADE,
        related_name="dutyticker_time_slots",
        null=True,
        blank=True,
    )
    slot_code = models.CharField(max_length=20)
    slot_kind = models.CharField(max_length=20, choices=SLOT_KIND_CHOICES, default="period")
    slot_order = models.PositiveSmallIntegerField(default=1)
    slot_label = models.CharField(max_length=50, default="1교시")
    period_number = models.PositiveSmallIntegerField(null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["slot_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "classroom", "slot_code"],
                name="dttimeslot_user_classroom_code_unique",
            ),
            models.UniqueConstraint(
                fields=["user", "slot_code"],
                condition=models.Q(classroom__isnull=True),
                name="dttimeslot_user_global_code_unique",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} {self.slot_label}"


class DTStudent(models.Model):
    """Student roster for each teacher"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_students')
    classroom = models.ForeignKey(
        'happy_seed.HSClassroom',
        on_delete=models.CASCADE,
        related_name='dutyticker_students',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    number = models.IntegerField(default=0, help_text="Student number for ordering")
    is_active = models.BooleanField(default=True)
    is_mission_completed = models.BooleanField(default=False, help_text="Daily mission completion status")
    
    class Meta:
        ordering = ['number', 'name']
        
    def __str__(self):
        return self.name

class DTRole(models.Model):
    """Duty roles defined by the teacher"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_roles')
    classroom = models.ForeignKey(
        'happy_seed.HSClassroom',
        on_delete=models.CASCADE,
        related_name='dutyticker_roles',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    time_slot = models.CharField(max_length=50, default="쉬는시간", help_text="When to perform this role")
    icon = models.CharField(max_length=50, blank=True, default="📋")
    color = models.CharField(max_length=50, blank=True, default="bg-white")
    
    def __str__(self):
        return self.name

class DTRoleAssignment(models.Model):
    """Assignment of a role to a student for a specific period"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_assignments')
    classroom = models.ForeignKey(
        'happy_seed.HSClassroom',
        on_delete=models.CASCADE,
        related_name='dutyticker_assignments',
        null=True,
        blank=True,
    )
    role = models.ForeignKey(DTRole, on_delete=models.CASCADE)
    student = models.ForeignKey(DTStudent, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(auto_now_add=True) # Assignments are typically daily, but tracked
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'role', 'date') 
        # Ideally one assignment per role per day, but we might simply update the current assignment without date constraint if it's strictly state-based.
        # However, for history or rotation, date is good. For now, let's keep it simple: current state.
        # Actually, let's just model *Current* assignment. History can be another table if needed.
        # Let's drop 'date' uniqueness for now and just rely on logic to fetch the "latest" or "active".
        # Better yet: One assignment object per role that gets UPDATED, or new ones created?
        # Let's stick to: This table holds the CURRENT configuration.
    
    def __str__(self):
        return f"{self.role.name} - {self.student.name if self.student else 'Unassigned'}"

class DTSchedule(models.Model):
    """Weekly schedule"""
    DAYS_OF_WEEK = [
        (0, 'Sunday'),
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_schedules')
    classroom = models.ForeignKey(
        'happy_seed.HSClassroom',
        on_delete=models.CASCADE,
        related_name='dutyticker_schedules',
        null=True,
        blank=True,
    )
    day = models.IntegerField(choices=DAYS_OF_WEEK)
    period = models.IntegerField(help_text="1 for 1st period, etc.")
    subject = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    class Meta:
        ordering = ['day', 'period']
        
    def __str__(self):
        return f"{self.get_day_display()} {self.period} - {self.subject}"


class DTStudentGamesLaunchTicket(models.Model):
    """Short-lived launch ticket for the anonymous student games portal."""

    issued_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dutyticker_student_game_tickets",
    )
    classroom = models.ForeignKey(
        "happy_seed.HSClassroom",
        on_delete=models.CASCADE,
        related_name="dutyticker_student_game_tickets",
        null=True,
        blank=True,
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        scope = self.classroom.name if self.classroom_id else "global"
        return f"{self.issued_by.username} student games ticket ({scope})"
