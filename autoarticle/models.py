from django.conf import settings
from django.db import models


class GeneratedArticle(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    # --- Input Fields ---
    school_name = models.CharField(max_length=100, verbose_name="참여 학교명", default="스쿨잇 초등학교")
    grade = models.CharField(max_length=50, verbose_name="참여 학년", blank=True)
    class_name = models.CharField(max_length=50, verbose_name="참여 반", blank=True)
    event_name = models.CharField(max_length=200, verbose_name="행사명", blank=True)
    location = models.CharField(max_length=100, verbose_name="장소", blank=True)
    event_date = models.DateField(verbose_name="일시", null=True, blank=True)
    tone = models.CharField(max_length=100, verbose_name="기사 톤", blank=True)
    keywords = models.TextField(verbose_name="주요 활동 내용", blank=True)

    # --- Legacy Compatibility ---
    topic = models.CharField(max_length=200, verbose_name="주제", blank=True)
    source_type = models.CharField(
        max_length=50,
        choices=[("topic", "주제 입력"), ("file", "파일 업로드")],
        default="topic",
    )

    # --- Generated Content ---
    title = models.CharField(max_length=300, verbose_name="생성된 제목", blank=True)
    content_summary = models.TextField(verbose_name="요약 내용", blank=True)
    full_text = models.TextField(verbose_name="전체 텍스트", blank=True)

    # --- Metadata & JSON Fields ---
    hashtags = models.JSONField(verbose_name="해시태그", default=list, blank=True)
    images = models.JSONField(verbose_name="이미지 경로 리스트", default=list, blank=True)

    # --- Generated Files ---
    ppt_file = models.FileField(upload_to="autoarticle/ppt/", null=True, blank=True)
    pdf_file = models.FileField(upload_to="autoarticle/pdf/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def content_summary_list(self):
        if not self.content_summary:
            return []
        return [line.strip() for line in self.content_summary.split("\n") if line.strip()]

    @property
    def audience_label(self):
        grade = (self.grade or "").strip()
        class_name = (self.class_name or "").strip()

        if grade and class_name and grade != "전교생":
            return f"{grade} {class_name}"
        if class_name and (not grade or grade == "전교생"):
            return class_name
        return grade or "전교생"

    def __str__(self):
        return f"[{self.event_date}] {self.event_name or self.topic}"
