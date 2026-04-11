import uuid

from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# MVP1 Models (8)
# ---------------------------------------------------------------------------

class HSClassroom(models.Model):
    """교실(학급)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hs_classrooms',
    )
    name = models.CharField('학급 이름', max_length=100)
    school_name = models.CharField('학교명', max_length=100, blank=True)
    shared_roster_group = models.ForeignKey(
        "handoff.HandoffRosterGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hs_classrooms",
        verbose_name="공용 명부",
    )
    slug = models.SlugField('공개 정원 슬러그', unique=True, max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '교실'
        verbose_name_plural = '교실 목록'

    def __str__(self):
        return f"{self.name} ({self.teacher.username})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:8]
        super().save(*args, **kwargs)

    @property
    def has_available_rewards(self):
        return self.prizes.filter(is_active=True).exclude(remaining_quantity=0).exists()


class HSClassroomConfig(models.Model):
    """교실 설정 (Classroom과 분리)"""
    classroom = models.OneToOneField(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name='config',
    )
    seeds_per_bloom = models.IntegerField('블룸 전환 기준', default=10)
    base_win_rate = models.IntegerField('기본 당첨 확률(%)', default=5)
    group_draw_count = models.IntegerField('모둠 성공 시 랜덤 인원수', default=1)
    balance_mode_enabled = models.BooleanField('따뜻한 균형 모드', default=False)
    balance_epsilon = models.FloatField('보정 계수', default=0.05)
    balance_lookback_days = models.IntegerField('보정 기간(일)', default=30)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '교실 설정'
        verbose_name_plural = '교실 설정 목록'

    def __str__(self):
        return f"{self.classroom.name} 설정"


class HSStudent(models.Model):
    """학생"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name='students',
    )
    shared_roster_member = models.ForeignKey(
        "handoff.HandoffRosterMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="happy_seed_students",
    )
    name = models.CharField('이름', max_length=50)
    number = models.IntegerField('번호', default=0)
    seed_count = models.IntegerField('현재 씨앗', default=0)
    ticket_count = models.IntegerField('현재 보유 티켓 수', default=0)
    total_wins = models.IntegerField('총 당첨 횟수', default=0)
    pending_forced_win = models.BooleanField('다음 회 강제 당첨', default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['number', 'name']
        unique_together = [('classroom', 'number')]
        verbose_name = '학생'
        verbose_name_plural = '학생 목록'

    def __str__(self):
        return f"{self.number}번 {self.name}"


class HSGuardianConsent(models.Model):
    """보호자 동의 상태"""
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('approved', '동의완료'),
        ('rejected', '거부'),
        ('expired', '만료'),
        ('withdrawn', '철회'),
    ]

    student = models.OneToOneField(
        HSStudent,
        on_delete=models.CASCADE,
        related_name='consent',
    )
    status = models.CharField('동의 상태', max_length=10, choices=STATUS_CHOICES, default='pending')
    external_url = models.URLField('외부 전자서명 링크', blank=True)
    note = models.TextField('비고', blank=True)
    requested_at = models.DateTimeField('동의 요청 시각', null=True, blank=True)
    completed_at = models.DateTimeField('동의 완료 시각', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '보호자 동의'
        verbose_name_plural = '보호자 동의 목록'

    def __str__(self):
        return f"{self.student.name} - {self.get_status_display()}"


class HSPrize(models.Model):
    """당첨 보상"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name='prizes',
    )
    name = models.CharField('보상 이름', max_length=200)
    description = models.TextField('설명', blank=True)
    win_rate_percent = models.DecimalField(
        '보상 선택 확률(%)',
        max_digits=5,
        decimal_places=2,
        default=100,
        help_text='당첨 시 이 보상이 선택되는 상대 확률입니다. (예: 70, 20, 10)',
    )
    total_quantity = models.IntegerField('총 수량', null=True, blank=True, help_text='비워두면 무제한')
    remaining_quantity = models.IntegerField('남은 수량', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField('표시 순서', default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = '보상'
        verbose_name_plural = '보상 목록'

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        return self.total_quantity is None or (self.remaining_quantity is not None and self.remaining_quantity > 0)


class HSTicketLedger(models.Model):
    """꽃피움 티켓 원장"""
    SOURCE_CHOICES = [
        ('participation', '성실참여'),
        ('achievement', '우수성취'),
        ('seed_accumulation', '씨앗누적'),
        ('group_draw', '모둠추첨'),
        ('teacher_grant', '교사부여'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.CASCADE,
        related_name='ticket_ledger',
    )
    source = models.CharField('원천', max_length=20, choices=SOURCE_CHOICES)
    amount = models.IntegerField('변동량')
    detail = models.CharField('상세', max_length=200, blank=True)
    balance_after = models.IntegerField('변동 후 잔액')
    request_id = models.UUIDField('멱등성 키', default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('student', 'request_id')]
        verbose_name = '티켓 원장'
        verbose_name_plural = '티켓 원장 목록'

    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.student.name} {sign}{self.amount} ({self.get_source_display()})"


class HSSeedLedger(models.Model):
    """씨앗 원장"""
    REASON_CHOICES = [
        ('no_win', '미당첨 보상'),
        ('behavior', '행동 인정'),
        ('recovery', '회복'),
        ('bloom_convert', '블룸 전환'),
        ('teacher_grant', '교사부여'),
        ('teacher_correction', '교사 정정'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.CASCADE,
        related_name='seed_ledger',
    )
    amount = models.IntegerField('변동량')
    reason = models.CharField('사유', max_length=20, choices=REASON_CHOICES)
    detail = models.CharField('상세', max_length=200, blank=True)
    balance_after = models.IntegerField('변동 후 잔액')
    request_id = models.UUIDField('멱등성 키', default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('student', 'request_id')]
        verbose_name = '씨앗 원장'
        verbose_name_plural = '씨앗 원장 목록'

    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.student.name} {sign}{self.amount} ({self.get_reason_display()})"


class HSBloomDraw(models.Model):
    """추첨 결과 로그"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.CASCADE,
        related_name='bloom_draws',
    )
    is_win = models.BooleanField('당첨 여부')
    prize = models.ForeignKey(
        HSPrize,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='draw_results',
    )
    input_probability = models.DecimalField('투입 확률(%)', max_digits=5, decimal_places=2)
    balance_adjustment = models.DecimalField('균형모드 보정값', max_digits=5, decimal_places=4, default=0)
    effective_probability = models.DecimalField('최종 적용 확률(%)', max_digits=5, decimal_places=2)
    is_forced = models.BooleanField('교사 개입 여부', default=False)
    force_reason = models.CharField('개입 사유', max_length=200, blank=True)
    request_id = models.UUIDField('멱등성 키', default=uuid.uuid4, unique=True)
    celebration_token = models.UUIDField('축하 화면 토큰', default=uuid.uuid4, unique=True)
    celebration_closed = models.BooleanField('축하 화면 닫힘', default=False)
    drawn_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='hs_draws',
    )

    class Meta:
        ordering = ['-drawn_at']
        verbose_name = '추첨 결과'
        verbose_name_plural = '추첨 결과 목록'

    def __str__(self):
        result = '당첨' if self.is_win else '미당첨'
        return f"{self.student.name} - {result} ({self.drawn_at})"


# ---------------------------------------------------------------------------
# MVP2 Models (6) - 향후 구현
# ---------------------------------------------------------------------------

class HSBehaviorCategory(models.Model):
    """행동 카테고리"""
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name='behavior_categories',
    )
    code = models.CharField('코드', max_length=20)
    name = models.CharField('이름', max_length=50)
    icon = models.CharField('아이콘', max_length=10, default='🌱')
    seeds_reward = models.IntegerField('씨앗 보상', default=1)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField('표시 순서', default=0)

    class Meta:
        ordering = ['display_order']
        unique_together = [('classroom', 'code')]
        verbose_name = '행동 카테고리'
        verbose_name_plural = '행동 카테고리 목록'

    def __str__(self):
        return f"{self.icon} {self.name}"


class HSBehaviorLog(models.Model):
    """행동 기록"""
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.CASCADE,
        related_name='behavior_logs',
    )
    category = models.ForeignKey(
        HSBehaviorCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='logs',
    )
    note = models.TextField('메모', blank=True)
    seeds_awarded = models.IntegerField('부여 씨앗', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='hs_behavior_logs',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = '행동 기록'
        verbose_name_plural = '행동 기록 목록'

    def __str__(self):
        return f"{self.student.name} - {self.category}"


class HSActivity(models.Model):
    """활동 (시험/과제)"""
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name='activities',
    )
    title = models.CharField('제목', max_length=200)
    description = models.TextField('설명', blank=True)
    threshold_score = models.IntegerField('기준 점수', default=80)
    extra_bloom_count = models.IntegerField('추가 블룸 수', default=1)

    class Meta:
        verbose_name = '활동'
        verbose_name_plural = '활동 목록'

    def __str__(self):
        return self.title


class HSActivityScore(models.Model):
    """활동 점수"""
    activity = models.ForeignKey(
        HSActivity,
        on_delete=models.CASCADE,
        related_name='scores',
    )
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.CASCADE,
        related_name='activity_scores',
    )
    score = models.IntegerField('점수', default=0)
    bloom_granted = models.BooleanField('블룸 부여됨', default=False)

    class Meta:
        unique_together = [('activity', 'student')]
        verbose_name = '활동 점수'
        verbose_name_plural = '활동 점수 목록'

    def __str__(self):
        return f"{self.student.name} - {self.activity.title}: {self.score}"


class HSStudentGroup(models.Model):
    """모둠"""
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name='groups',
    )
    name = models.CharField('모둠 이름', max_length=100)
    members = models.ManyToManyField(HSStudent, related_name='student_groups', blank=True)

    class Meta:
        verbose_name = '모둠'
        verbose_name_plural = '모둠 목록'

    def __str__(self):
        return self.name


class HSInterventionLog(models.Model):
    """교사 개입 로그 (학생 비공개)"""
    ACTION_CHOICES = [
        ('forced_win_immediate', '즉시 강제 당첨'),
        ('forced_win_next', '다음 회 강제 당첨'),
        ('seed_grant', '씨앗 부여'),
        ('seed_deduct', '씨앗 차감'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name='intervention_logs',
    )
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.CASCADE,
        related_name='intervention_logs',
    )
    action = models.CharField('개입 유형', max_length=25, choices=ACTION_CHOICES)
    detail = models.TextField('사유', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='hs_interventions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '교사 개입 로그'
        verbose_name_plural = '교사 개입 로그 목록'

    def __str__(self):
        return f"{self.student.name} - {self.get_action_display()}"


class HSClassEventLog(models.Model):
    """표준 이벤트 로그 (분석/감사 용)"""
    TYPE_CHOICES = [
        ("TOKEN_GRANTED_DILIGENT", "성실참여 꽃피움권 지급"),
        ("TOKEN_GRANTED_SCORE_BONUS", "우수성취 추가 꽃피움권 지급"),
        ("SEED_GRANTED_MANUAL", "교사 수동 씨앗 지급"),
        ("SEED_CORRECTED_MANUAL", "교사 수동 씨앗 정정"),
        ("DRAW_EXECUTED", "꽃피움 실행"),
        ("DRAW_WIN", "꽃피움 당첨"),
        ("DRAW_LOSE", "꽃피움 미당첨"),
        ("SEED_AUTO_FROM_LOSS", "미당첨 씨앗 자동적립"),
        ("TOKEN_AUTO_FROM_SEEDS_THRESHOLD", "씨앗 누적 자동 전환"),
        ("TEACHER_OVERRIDE_SET", "교사 개입 예약"),
        ("TEACHER_OVERRIDE_USED", "교사 개입 사용"),
        ("GROUP_MISSION_REWARD", "모둠 미션 랜덤 지급"),
        ("WARM_BALANCE_MODE_TOGGLED", "균형모드 토글"),
        ("CONSENT_REQUEST_SENT", "동의 요청 발송"),
        ("CONSENT_SIGNED", "동의 완료"),
    ]

    class_ref = models.ForeignKey(
        HSClassroom,
        on_delete=models.CASCADE,
        related_name="event_logs",
        verbose_name="반",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField("유형", max_length=40, choices=TYPE_CHOICES)
    student = models.ForeignKey(
        HSStudent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_logs",
    )
    group = models.ForeignKey(
        HSStudentGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_logs",
    )
    meta = models.JSONField("부가정보", default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "반 이벤트 로그"
        verbose_name_plural = "반 이벤트 로그 목록"

    def __str__(self):
        return f"{self.class_ref.name} - {self.type} - {self.timestamp}"
