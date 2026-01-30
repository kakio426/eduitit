from django.db import models
from django.contrib.auth.models import User


class SsambtiResult(models.Model):
    """사용자가 저장한 쌤BTI(Teachable Zoo MBTI) 결과"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ssambti_results')
    mbti_type = models.CharField(max_length=4, help_text="e.g. ENFP")
    animal_name = models.CharField(max_length=50, help_text="e.g. 해달")
    result_text = models.TextField(help_text="AI가 생성한 분석 결과 내용")
    answers_json = models.JSONField(help_text="사용자가 선택한 답변들", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '쌤BTI 결과'
        verbose_name_plural = '쌤BTI 결과 목록'

    def __str__(self):
        return f"{self.user.username} - {self.animal_name}({self.mbti_type})"
