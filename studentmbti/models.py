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
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '학생 MBTI 검사 세션'
        verbose_name_plural = '학생 MBTI 검사 세션 목록'
    
    def __str__(self):
        return f"{self.session_name} ({self.teacher.username})"
    
    @property
    def result_count(self):
        return self.results.count()


class StudentMBTIResult(models.Model):
    """학생 MBTI 결과 (비회원 접근)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='results')
    student_name = models.CharField(max_length=50, help_text="학생 이름")
    mbti_type = models.CharField(max_length=4, help_text="예: ENFP")
    animal_name = models.CharField(max_length=50, help_text="예: 여우")
    answers_json = models.JSONField(help_text="학생이 선택한 답변들", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '학생 MBTI 결과'
        verbose_name_plural = '학생 MBTI 결과 목록'
    
    def __str__(self):
        return f"{self.student_name} - {self.animal_name}({self.mbti_type})"
