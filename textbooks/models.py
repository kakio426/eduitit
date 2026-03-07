from django.db import models
from django.contrib.auth.models import User
import uuid

class TextbookMaterial(models.Model):
    """
    교과서 단원별 자료실의 배포 세션 모델.
    교사가 특정 과목, 단원의 자료를 등록/생성하여 학생들에게 배포합니다.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='textbook_materials')
    
    SUBJECT_CHOICES = [
        ('KOREAN', '국어'),
        ('MATH', '수학'),
        ('SOCIAL', '사회'),
        ('SCIENCE', '과학'),
    ]
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, verbose_name="과목")
    grade = models.CharField(max_length=50, blank=True, null=True, verbose_name="학년/학기")
    unit_title = models.CharField(max_length=200, verbose_name="단원명")
    
    title = models.CharField(max_length=200, verbose_name="자료 제목", default="수업 자료")
    content = models.TextField(verbose_name="자료 내용", help_text="Markdown 형식의 본문", blank=True)
    
    is_published = models.BooleanField(default=False, verbose_name="학생 배포 여부")
    is_shared = models.BooleanField(default=True, verbose_name="다른 교사와 공유 여부")
    view_count = models.IntegerField(default=0, verbose_name="조회수")
    likes = models.ManyToManyField(User, related_name='liked_textbook_materials', blank=True, verbose_name="추천한 사용자")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '교과서 자료'
        verbose_name_plural = '교과서 자료들'

    def __str__(self):
        return f"[{self.get_subject_display()}] {self.unit_title} - {self.teacher.username}"
        
    @property
    def is_html_document(self):
        """본문이 파싱 불필요한 날것의 HTML 코드(<!DOCTYPE html 등)인지 확인"""
        if not self.content:
            return False
        c = self.content.strip().lower()
        return c.startswith('<!doctype html') or c.startswith('<html')


class AiUsage(models.Model):
    """일일 AI 기능 사용 횟수를 추적하는 모델 (교사당 1일 1레코드)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='textbooks_ai_usages')
    date = models.DateField(auto_now_add=True, verbose_name="기준일")
    
    categorize_count = models.IntegerField(default=0, verbose_name="자동 분류 사용 횟수")
    prompt_count = models.IntegerField(default=0, verbose_name="프롬프트 도우미 사용 횟수")
    
    class Meta:
        unique_together = ('user', 'date')
        verbose_name = 'AI 사용 기록'
        verbose_name_plural = 'AI 사용 기록들'

    @classmethod
    def get_todays_usage(cls, user):
        from django.utils import timezone
        today = timezone.localtime().date()
        usage, _ = cls.objects.get_or_create(user=user, date=today)
        return usage
