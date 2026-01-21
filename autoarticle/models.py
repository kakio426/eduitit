from django.db import models
from django.conf import settings

class GeneratedArticle(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    topic = models.CharField(max_length=200, verbose_name="주제")
    source_type = models.CharField(max_length=50, choices=[('topic', '주제 입력'), ('file', '파일 업로드')], default='topic')
    
    # 생성된 콘텐츠 내용
    content_summary = models.TextField(verbose_name="요약 내용", blank=True)
    full_text = models.TextField(verbose_name="전체 텍스트", blank=True)
    
    # 생성된 파일 경로 (Cloudinary 또는 로컬)
    ppt_file = models.FileField(upload_to='autoarticle/ppt/', null=True, blank=True)
    pdf_file = models.FileField(upload_to='autoarticle/pdf/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} ({self.created_at.strftime('%Y-%m-%d')})"
