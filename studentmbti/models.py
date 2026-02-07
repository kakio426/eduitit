from django.db import models
from django.contrib.auth.models import User
import uuid


class TestSession(models.Model):
    """교사가 생성하는 검사 세션"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_mbti_sessions')
    session_name = models.CharField(max_length=100, help_text="예: 3학년 1반 MBTI 검사")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    access_code = models.CharField(max_length=10, unique=True, null=True, blank=True, help_text="학생 입장 코드 (예: AB12CD)")
    
    class Meta:
        app_label = 'studentmbti'
        ordering = ['-created_at']
        verbose_name = '학생 MBTI 검사 세션'
        verbose_name_plural = '학생 MBTI 검사 세션 목록'
    
    def __str__(self):
        return f"{self.session_name} ({self.teacher.username})"
    
    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = self.generate_unique_access_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_access_code():
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not TestSession.objects.filter(access_code=code).exists():
                return code

    @property
    def result_count(self):
        return self.results.count()


class StudentMBTIResult(models.Model):
    """학생 MBTI 결과 (비회원 접근)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='results')
    student_name = models.CharField(max_length=50, help_text="학생 이름")
    mbti_type = models.CharField(max_length=4, help_text="예: ENFP", null=True, blank=True)
    animal_name = models.CharField(max_length=50, help_text="예: 여우", null=True, blank=True)
    answers_json = models.JSONField(help_text="학생이 선택한 답변들", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'studentmbti'
        ordering = ['-created_at']
        verbose_name = '학생 MBTI 결과'
        verbose_name_plural = '학생 MBTI 결과 목록'
    
    def __str__(self):
        return f"{self.student_name} - {self.animal_name}({self.mbti_type})"
