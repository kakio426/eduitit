from django.db import models
from django.contrib.auth.models import User

class School(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, allow_unicode=True) # URL key like 'seoul-es'
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class SchoolConfig(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name='config')
    max_periods = models.IntegerField(default=6) # 1~N periods
    reservation_window_days = models.IntegerField(default=14) # How far in future to book

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
