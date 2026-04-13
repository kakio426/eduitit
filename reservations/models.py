import re
import unicodedata
import uuid
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.contrib.auth.models import User


OWNER_TEXT_WHITESPACE_RE = re.compile(r"\s+")
EDIT_CODE_RE = re.compile(r"^\d{4}$")


def normalize_reservation_owner_text(value):
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = OWNER_TEXT_WHITESPACE_RE.sub("", normalized).strip().lower()
    return normalized[:80]


def build_reservation_owner_key(*, grade=0, class_no=0, target_label="", name=""):
    normalized_name = normalize_reservation_owner_text(name)
    normalized_target_label = normalize_reservation_owner_text(target_label)

    try:
        grade_value = int(grade or 0)
    except (TypeError, ValueError):
        grade_value = 0

    try:
        class_value = int(class_no or 0)
    except (TypeError, ValueError):
        class_value = 0

    if normalized_target_label:
        return f"target|{normalized_target_label}|{normalized_name}"[:160]
    if grade_value > 0 and class_value > 0:
        return f"class|{grade_value}|{class_value}|{normalized_name}"[:160]
    if grade_value > 0:
        return f"grade|{grade_value}|{normalized_name}"[:160]
    if normalized_name:
        return f"name|{normalized_name}"[:160]
    return ""


def normalize_reservation_edit_code(value):
    return str(value or "").strip()


def validate_reservation_edit_code(value):
    normalized = normalize_reservation_edit_code(value)
    if not EDIT_CODE_RE.fullmatch(normalized):
        raise ValueError("invalid-edit-code")
    return normalized


def hash_reservation_edit_code(value):
    return make_password(validate_reservation_edit_code(value))

class School(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, allow_unicode=True) # Public identifier (randomized)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.slug:
            # Generate a random 8-character slug
            self.slug = uuid.uuid4().hex[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ReservationCollaborator(models.Model):
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="collaborators",
    )
    collaborator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shared_reservation_schools",
    )
    can_edit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("school", "collaborator")]
        verbose_name = "예약 시스템 협업자"
        verbose_name_plural = "예약 시스템 협업자"

    def __str__(self):
        permission = "편집" if self.can_edit else "보기"
        return f"{self.school.name} -> {self.collaborator.username} ({permission})"

class SchoolConfig(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name='config')
    max_periods = models.IntegerField(default=6) # Safety/Legacy
    period_labels = models.TextField(default="1교시,2교시,3교시,4교시,5교시,6교시") # Custom labels
    period_times = models.TextField(blank=True, default="") # Optional times matched by index
    reservation_window_days = models.IntegerField(default=14)
    # 주간 예약 오픈 제한 설정 (Weekly Opening Rule)
    weekly_opening_mode = models.BooleanField(default=False)
    weekly_opening_weekday = models.IntegerField(default=4, help_text="0=월, 1=화, ... 4=금, 6=일") # Default: Friday
    weekly_opening_hour = models.IntegerField(default=9, help_text="0-23시") # Default: 9 AM

    def get_period_list(self):
        """Returns labels as a list of strings: ['1교시', '2교시', ...]"""
        return [p.strip() for p in self.period_labels.split(',') if p.strip()]

    def get_period_time_list(self, expected_count=None):
        """
        Returns optional time strings matched by index.
        Example: '09:00-09:40,09:50-10:30' -> ['09:00-09:40', '09:50-10:30', ...]
        """
        if expected_count is None:
            expected_count = len(self.get_period_list())
        raw = [p.strip() for p in (self.period_times or "").split(',')]
        if len(raw) < expected_count:
            raw.extend([''] * (expected_count - len(raw)))
        return raw[:expected_count]

    def get_period_slots(self):
        """
        Returns structured period rows preserving order.
        [{'id': 1, 'label': '1교시', 'time': '09:00-09:40', 'display_label': '1교시 (09:00-09:40)'}, ...]
        """
        labels = self.get_period_list()
        times = self.get_period_time_list(len(labels))
        slots = []
        for idx, label in enumerate(labels):
            time_text = times[idx]
            display = f"{label} ({time_text})" if time_text else label
            slots.append({
                'id': idx + 1,
                'label': label,
                'time': time_text,
                'display_label': display,
            })
        return slots

    def __str__(self):
        return f"{self.school.name} Config"

class SpecialRoom(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    name = models.CharField(max_length=50) # e.g., 과학실
    icon = models.CharField(max_length=10, default="📍")
    color = models.CharField(max_length=20, default="text-purple-500") # Tailwind class
    equipment_info = models.TextField(blank=True) # e.g., 현미경 15대

    def __str__(self):
        return f"{self.school.name} - {self.name}"

class Reservation(models.Model):
    room = models.ForeignKey(SpecialRoom, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_reservations')
    owner_key = models.CharField(max_length=160, blank=True, default="", db_index=True)
    edit_code_hash = models.CharField(max_length=256, blank=True, default="")
    date = models.DateField()
    period = models.IntegerField() # 1~max_periods
    grade = models.IntegerField()
    class_no = models.IntegerField()
    target_label = models.CharField(max_length=40, blank=True, default="")  # 예: 사서, 보건, 영양
    name = models.CharField(max_length=20)
    memo = models.CharField(max_length=100, blank=True) # 한 줄 메모
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'date', 'period'], name='unique_reservation_per_slot')
        ]

    def __str__(self):
        if self.target_label:
            who = f"{self.target_label} {self.name}".strip()
        elif self.grade > 0 and self.class_no > 0:
            who = f"{self.grade}-{self.class_no} {self.name}"
        elif self.grade > 0:
            who = f"{self.grade}학년 {self.name}"
        else:
            who = self.name
        return f"{self.date} {self.period}교시 - {self.room.name} ({who})"

    def has_edit_code(self):
        return bool(self.edit_code_hash)

    def set_edit_code(self, edit_code):
        self.edit_code_hash = hash_reservation_edit_code(edit_code)

    def check_edit_code(self, edit_code):
        try:
            normalized = validate_reservation_edit_code(edit_code)
        except ValueError:
            return False
        return bool(self.edit_code_hash and check_password(normalized, self.edit_code_hash))

class RecurringSchedule(models.Model):
    room = models.ForeignKey(SpecialRoom, on_delete=models.CASCADE)
    day_of_week = models.IntegerField() # 0(Mon)~6(Sun)
    period = models.IntegerField()
    name = models.CharField(max_length=50) # e.g., "6-1 고정수업"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'day_of_week', 'period'], name='unique_recurring_schedule')
        ]

    def __str__(self):
        days = ['월', '화', '수', '목', '금', '토', '일']
        return f"{self.room.name} {days[self.day_of_week]}요일 {self.period}교시 - {self.name}"

class GradeRecurringLock(models.Model):
    room = models.ForeignKey(SpecialRoom, on_delete=models.CASCADE)
    day_of_week = models.IntegerField()  # 0(Mon)~6(Sun)
    period = models.IntegerField()
    grade = models.IntegerField()  # 1~6
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'day_of_week', 'period'], name='unique_grade_lock_per_slot')
        ]

    def __str__(self):
        days = ['월', '화', '수', '목', '금', '토', '일']
        return f"{self.room.name} {days[self.day_of_week]}요일 {self.period}교시 - {self.grade}학년 고정"

class BlackoutDate(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.school.name} Blackout ({self.start_date} ~ {self.end_date}): {self.reason}"
