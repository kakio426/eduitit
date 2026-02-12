import uuid
from django.db import models
from django.contrib.auth.models import User

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

class SchoolConfig(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name='config')
    max_periods = models.IntegerField(default=6) # Safety/Legacy
    period_labels = models.TextField(default="1교시,2교시,3교시,4교시,5교시,6교시") # Custom labels
    reservation_window_days = models.IntegerField(default=14)
    # 주간 예약 오픈 제한 설정 (Weekly Opening Rule)
    weekly_opening_mode = models.BooleanField(default=False)
    weekly_opening_weekday = models.IntegerField(default=4, help_text="0=월, 1=화, ... 4=금, 6=일") # Default: Friday
    weekly_opening_hour = models.IntegerField(default=9, help_text="0-23시") # Default: 9 AM

    def get_period_list(self):
        """Returns labels as a list of strings: ['1교시', '2교시', ...]"""
        return [p.strip() for p in self.period_labels.split(',') if p.strip()]

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
    date = models.DateField()
    period = models.IntegerField() # 1~max_periods
    grade = models.IntegerField()
    class_no = models.IntegerField()
    name = models.CharField(max_length=20)
    memo = models.CharField(max_length=100, blank=True) # 한 줄 메모
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'date', 'period'], name='unique_reservation_per_slot')
        ]

    def __str__(self):
        return f"{self.date} {self.period}교시 - {self.room.name} ({self.grade}-{self.class_no} {self.name})"

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

class BlackoutDate(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.school.name} Blackout ({self.start_date} ~ {self.end_date}): {self.reason}"
