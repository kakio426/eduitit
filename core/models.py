from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import os

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('school', '학교 (관리자 및 정교사)'),
        ('instructor', '강사 (기간제, 돌봄, 늘봄 등)'),
        ('company', '교육행사업체'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True, verbose_name="역할")
    nickname = models.CharField(max_length=50, blank=True, null=True, verbose_name="별명")
    gemini_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Gemini API Key")
    padlet_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Padlet API Key")

    def __str__(self):
        return self.user.username

class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField(max_length=500, verbose_name="내용")
    image = models.ImageField(upload_to='posts/%Y/%m/', null=True, blank=True, verbose_name="이미지")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author.username} - {self.created_at}"

    @property
    def like_count(self):
        return self.likes.count()

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Ensure profile exists whenever user is saved
    UserProfile.objects.get_or_create(user=instance)

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(max_length=300, verbose_name="댓글 내용")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post}"

class SiteConfig(models.Model):
    """싱글톤 사이트 설정 모델 - Admin에서 배너 등 글로벌 설정 관리"""
    banner_text = models.CharField(max_length=200, blank=True, default='', verbose_name="배너 텍스트")
    banner_active = models.BooleanField(default=False, verbose_name="배너 활성화")
    banner_color = models.CharField(max_length=7, default='#7c3aed', verbose_name="배너 색상 (HEX)")
    banner_link = models.URLField(blank=True, default='', verbose_name="배너 링크 URL")

    class Meta:
        verbose_name = "사이트 설정"
        verbose_name_plural = "사이트 설정"

    def __str__(self):
        return "사이트 설정"

    def save(self, *args, **kwargs):
        # 싱글톤 패턴: pk를 항상 1로 강제
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Feedback(models.Model):
    CATEGORY_CHOICES = [
        ('bug', '버그 신고'),
        ('suggestion', '제안/건의'),
        ('other', '기타'),
    ]
    name = models.CharField(max_length=50, verbose_name="이름")
    email = models.EmailField(blank=True, default='', verbose_name="이메일 (선택)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other', verbose_name="카테고리")
    message = models.TextField(max_length=1000, verbose_name="내용")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="작성일시")
    is_resolved = models.BooleanField(default=False, verbose_name="처리 완료")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "피드백"
        verbose_name_plural = "피드백"

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name} - {self.created_at:%Y-%m-%d}"


class VisitorLog(models.Model):
    ip_address = models.GenericIPAddressField(verbose_name="IP 주소")
    visit_date = models.DateField(auto_now_add=True, verbose_name="방문 날짜")

    class Meta:
        # Prevent multiple entries for same IP on same day
        unique_together = ('ip_address', 'visit_date')
        verbose_name = "방문자 기록"
        verbose_name_plural = "방문자 기록"

    def __str__(self):
        return f"{self.visit_date} - {self.ip_address}"
